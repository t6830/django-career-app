import datetime
import logging
import os

from django.contrib import messages
from django.contrib.auth import login  # Added for user login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User  # Added User
from django.db import IntegrityError
from django.http import (FileResponse, Http404, HttpResponse,
                         HttpResponseForbidden)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import ListView, TemplateView, View

from .forms import (ApplicantForm,  # Added ReviewApplicantForm
                    ReviewApplicantForm)
from .llm_utils import get_resume_analysis_with_llm  # Changed import
from .models import (Applicant, Application, CompanyProfile, JobPosting,
                     JobRequirement, Tag)
from .utils import \
    extract_text_from_pdf  # Restored and added convert_pdf_to_markdown

logger = logging.getLogger(__name__)


class ReviewApplicationView(View):
    """
    Handles the two-stage application review and submission process.

    The GET method displays data extracted from the resume (via LLM) and initial
    form input, allowing the user to review and edit it. It also handles
    pre-filling password fields conditionally if a new user is detected.

    The POST method processes the reviewed data, validates user input (including
    password for new user creation or existing user confirmation), creates or
    updates User and Applicant records, creates related Tag and Application
    records, logs in new users, cleans up session data, and redirects to the
    careers home page upon successful submission.
    """
    template_name = 'django_career_app/review_application_details.html'

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests for the application review page.

        Retrieves application data (parsed resume, form inputs, AI score)
        from the session, prepares it for display in the ReviewApplicantForm,
        determines if the user is likely new (for password field display logic),
        and renders the review template. Redirects to career home if essential
        session data is missing.
        """
        session_data = request.session.get('application_review_data')

        if not session_data:
            messages.error(request, "No application data found to review. Please submit an application first.")
            return redirect(reverse('django_career_app:career_home'))

        parsed_data = session_data.get('parsed_data', {})
        contact_info = parsed_data.get('contact_info', {})
        latest_education = parsed_data.get('latest_education', {})
        latest_work_experience = parsed_data.get('latest_work_experience', {})
        
        # Determine initial values, prioritizing parsed data, then form data from session
        initial_data = {
            'first_name': parsed_data.get('first_name'),
            'last_name': parsed_data.get('last_name'),
            'email': contact_info.get('email'),
            'phone_number': contact_info.get('phone_number'),
            'linkedin_profile': contact_info.get('linkedin_profile'),
            
            'latest_degree': latest_education.get('latest_degree'),
            'school': latest_education.get('school'),
            'major': latest_education.get('major'),
            'graduate_year': latest_education.get('graduate_year'),
            
            'current_title': latest_work_experience.get('current_title'),
            'latest_work_organization': latest_work_experience.get('company_name'), # company_name from LLM maps to latest_work_organization
            
            # Tags will be handled separately for display/editing
        }
        
        # Handle tags: join list into a comma-separated string for display in a text input
        parsed_tags_list = parsed_data.get('top_tags', [])
        initial_data['tags_edit'] = ", ".join(parsed_tags_list) if isinstance(parsed_tags_list, list) else ""

        # Determine if user is new based on the email that will be used (final_email from initial_data)
        # This email could be from parsed data or form data.
        email_to_check = initial_data.get('email')
        is_new_user = True # Default to new user
        if email_to_check:
            is_new_user = not User.objects.filter(email=email_to_check).exists()
        else:
            # If there's no email at all, consider it a new user flow, though validation should catch this.
            logger.warning("Review page: No email found in session or parsed data for user check.")


        
        form = ReviewApplicantForm(initial=initial_data, is_new_user=is_new_user) 
        
        # Store is_new_user in session for POST method to access
        request.session['is_new_user_for_review'] = is_new_user
        # No need to store initial_data separately if form is always re-instantiated in POST
        # if 'application_review_initial_data' in request.session:
        #     del request.session['application_review_data']

        context = {
            'form': form,  # Use Django form
            'is_new_user': is_new_user,
            'job_posting_id': session_data.get('job_posting_id'),
        }

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests for submitting the reviewed application.

        Validates the submitted data using ReviewApplicantForm. If valid, it
        proceeds to:
        1. Create a new User (and log them in) or retrieve an existing User
           based on the submitted email. Handles password validation for both
           new (creation) and existing (confirmation) users.
        2. Update the temporary Applicant record (created in the initial submission)
           with the finalized data from the form and link it to the User.
        3. Create or retrieve Tag objects based on the 'tags_edit' field and
           associate them with the Applicant.
        4. Create the final Application record, linking the User, JobPosting,
           and storing the AI score.
        5. Clears relevant session data.
        6. Redirects to the careers home page with a success message.
        If the form is invalid, it re-renders the review page with errors.
        """
        session_data = request.session.get('application_review_data')
        if not session_data:
            messages.error(request, "Your session expired or data was not found. Please submit again.")
            return redirect(reverse('django_career_app:career_home'))

        temp_applicant_pk = session_data.get('temp_applicant_pk')
        job_posting_id = session_data.get('job_posting_id')
        ai_score = session_data.get('ai_score')
        
        # Retrieve is_new_user status set by GET; default to True if somehow missing
        is_new_user_initial_check = request.session.get('is_new_user_for_review', True)

        form = ReviewApplicantForm(request.POST, is_new_user=is_new_user_initial_check)

        if form.is_valid():
            cleaned_data = form.cleaned_data
            final_email = cleaned_data['email']
            password = cleaned_data.get('password') # Password from form (might be empty if not new user and not changing)
            user = None

            is_actually_new_user = not User.objects.filter(email=final_email).exists()
            
            if is_actually_new_user:
                # The form's __init__ and clean methods (based on is_new_user_initial_check)
                # should have already validated password and password_confirmation if is_new_user_initial_check was True.
                # If is_new_user_initial_check was False, but user changed email to a new one,
                # then password might be empty here. The form's 'required' for password fields
                # depends on the initial state, not the final state after email edit.
                if not password: # Explicitly check if password is provided for a truly new user
                    form.add_error('password', 'Password is required for new account registration.')
                    # Use is_new_user_initial_check for re-rendering template as form was initialized with it
                    context = {'form': form, 'is_new_user': is_new_user_initial_check, 'job_posting_id': job_posting_id, 'ai_score': ai_score}
                    return render(request, self.template_name, context)
                
                try:
                    # Create user with first_name and last_name from cleaned_data
                    user = User.objects.create_user(
                        username=final_email, # Using email as username for simplicity
                        email=final_email,
                        password=password,
                        first_name=cleaned_data.get('first_name', ''),
                        last_name=cleaned_data.get('last_name', '')
                    )
                    login(request, user) 
                    logger.info(f"New user created and logged in: {final_email} ({user.first_name} {user.last_name})")
                except IntegrityError: 
                    form.add_error('email', 'This email address is already associated with an account. Please log in or use a different email.')
                    context = {'form': form, 'is_new_user': True, 'job_posting_id': job_posting_id, 'ai_score': ai_score} # Pass True for is_new_user as it's an attempt to create new
                    return render(request, self.template_name, context)
                except Exception as e:
                    logger.error(f"Error creating new user {final_email}: {e}", exc_info=True)
                    form.add_error(None, "An unexpected error occurred while creating your account.")
                    context = {'form': form, 'is_new_user': True, 'job_posting_id': job_posting_id, 'ai_score': ai_score}
                    return render(request, self.template_name, context)
            else: # Existing user based on final_email
                try:
                    user = User.objects.get(email=final_email)
                    if not password: # Password must be provided for existing user
                        form.add_error('password', "Please enter your current password to confirm changes.")
                        context = {'form': form, 'is_new_user': False, 'job_posting_id': job_posting_id, 'ai_score': ai_score}
                        return render(request, self.template_name, context)
                    if not user.check_password(password):
                        form.add_error('password', "Incorrect password. Please try again.")
                        context = {'form': form, 'is_new_user': False, 'job_posting_id': job_posting_id, 'ai_score': ai_score}
                        return render(request, self.template_name, context)
                    logger.info(f"Processing application for existing user (password verified): {final_email}")
                except User.DoesNotExist:
                     logger.error(f"User.DoesNotExist for supposedly existing user (should not happen if is_actually_new_user is False): {final_email}", exc_info=True)
                     form.add_error('email', "User not found. Please try again or contact support.")
                     context = {'form': form, 'is_new_user': False, 'job_posting_id': job_posting_id, 'ai_score': ai_score} # is_new_user is False as we attempted to find existing
                     return render(request, self.template_name, context)


            # Applicant Profile Handling (New Logic)
            applicant_to_process = None
            try:
                existing_applicant_profile = Applicant.objects.filter(user=user).first()
                temp_applicant_with_new_resume = Applicant.objects.get(pk=temp_applicant_pk)

                if existing_applicant_profile:
                    logger.info(f"Updating existing Applicant profile {existing_applicant_profile.pk} for user {user.email}")
                    applicant_to_process = existing_applicant_profile
                    
                    # Update fields from form
                    # Update user's first_name and last_name
                    user.first_name = cleaned_data.get('first_name', '')
                    user.last_name = cleaned_data.get('last_name', '')
                    user.save(update_fields=['first_name', 'last_name'])
                    
                    # No full_name or email on Applicant model anymore
                    # applicant_to_process.full_name = cleaned_data['full_name']
                    # applicant_to_process.email = final_email 
                    applicant_to_process.phone_number = cleaned_data.get('phone_number')
                    applicant_to_process.linkedin_profile = cleaned_data.get('linkedin_profile')
                    applicant_to_process.current_title = cleaned_data.get('current_title')
                    applicant_to_process.latest_work_organization = cleaned_data.get('latest_work_organization')
                    applicant_to_process.latest_degree = cleaned_data.get('latest_degree')
                    applicant_to_process.school = cleaned_data.get('school')
                    applicant_to_process.major = cleaned_data.get('major')
                    applicant_to_process.graduate_year = cleaned_data.get('graduate_year')
                    
                    # Transfer resume if a new one was uploaded with the temporary applicant
                    if temp_applicant_with_new_resume.resume_pdf:
                        applicant_to_process.resume_pdf = temp_applicant_with_new_resume.resume_pdf
                    if temp_applicant_with_new_resume.resume_markdown: # Added for resume_markdown
                        applicant_to_process.resume_markdown = temp_applicant_with_new_resume.resume_markdown
                    
                    fields_to_update = [
                        'phone_number', 'linkedin_profile', 
                        'current_title', 'latest_work_organization', 'latest_degree', 
                        'school', 'major', 'graduate_year'
                    ]
                    if temp_applicant_with_new_resume.resume_pdf:
                        fields_to_update.append('resume_pdf')
                    if temp_applicant_with_new_resume.resume_markdown:
                        fields_to_update.append('resume_markdown')
                    applicant_to_process.save(update_fields=fields_to_update)
                    
                    # Delete the temporary applicant record as it's now merged/superfluous
                    if temp_applicant_with_new_resume.pk != applicant_to_process.pk: # Ensure not deleting the same object
                        temp_applicant_with_new_resume.delete()
                        logger.info(f"Temporary applicant {temp_applicant_with_new_resume.pk} deleted after merging into existing profile {applicant_to_process.pk}.")

                else: # No existing profile, finalize the temporary one
                    logger.info(f"Linking new Applicant record {temp_applicant_pk} to user {user.email}")
                    applicant_to_process = temp_applicant_with_new_resume
                    
                    # Update fields from form
                    # No full_name or email on Applicant model anymore
                    # applicant_to_process.full_name = cleaned_data['full_name']
                    # applicant_to_process.email = final_email 
                    applicant_to_process.phone_number = cleaned_data.get('phone_number')
                    applicant_to_process.linkedin_profile = cleaned_data.get('linkedin_profile')
                    applicant_to_process.current_title = cleaned_data.get('current_title')
                    applicant_to_process.latest_work_organization = cleaned_data.get('latest_work_organization')
                    applicant_to_process.latest_degree = cleaned_data.get('latest_degree')
                    applicant_to_process.school = cleaned_data.get('school')
                    applicant_to_process.major = cleaned_data.get('major')
                    applicant_to_process.graduate_year = cleaned_data.get('graduate_year')
                    
                    applicant_to_process.user = user # Link to the user
                    # resume_markdown is already set on temp_applicant_with_new_resume, which is applicant_to_process here
                    applicant_to_process.save() # Full save, includes resume_markdown if set
                
                # Tag Handling (operates on applicant_to_process)
                tags_str = cleaned_data.get('tags_edit', '')
                applicant_to_process.tags.clear() # Clear existing tags before adding new ones
                if tags_str:
                    tag_names = [name.strip() for name in tags_str.split(',') if name.strip()]
                    for tag_name in tag_names:
                        normalized_tag_name = tag_name.lower()
                        tag_obj, created = Tag.objects.get_or_create(name=normalized_tag_name)
                        applicant_to_process.tags.add(tag_obj)
                        if created: 
                            logger.info(f"Tag '{normalized_tag_name}' created/added to applicant {applicant_to_process.pk}")
                        else:
                            logger.info(f"Tag '{normalized_tag_name}' added to applicant {applicant_to_process.pk}")
                
                # Application Record Creation (uses user, not applicant_to_process directly)
                job_posting = JobPosting.objects.get(pk=job_posting_id)
                Application.objects.create(user=user, job_posting=job_posting, ai_score=ai_score)
                logger.info(f"Application record created for user {user.email} and job {job_posting.title}")

                # Cleanup session data
                if 'application_review_data' in request.session:
                    del request.session['application_review_data']
                if 'is_new_user_for_review' in request.session:
                    del request.session['is_new_user_for_review']

                messages.success(request, "Your application has been successfully submitted!")
                return redirect(reverse('django_career_app:application_thank_you'))

            except Applicant.DoesNotExist:
                logger.error(f"Critical error: Temporary Applicant with pk {temp_applicant_pk} not found during POST. This should not happen if session is consistent.", exc_info=True)
                messages.error(request, "A critical error occurred with your application data. Please try submitting again.")
                return redirect(reverse('django_career_app:career_home'))
            except JobPosting.DoesNotExist:
                logger.error(f"JobPosting with pk {job_posting_id} not found during POST.", exc_info=True)
                messages.error(request, "The job posting you applied for was not found. Please try again or contact support.")
                return redirect(reverse('django_career_app:career_home'))
            except Exception as e: # Catch any other unexpected errors during this block
                logger.error(f"Unexpected error during final application processing for user {final_email}: {e}", exc_info=True)
                form.add_error(None, "An unexpected error occurred while finalizing your application. Please try again.")
                context = {'form': form, 'is_new_user': is_new_user_initial_check, 'job_posting_id': job_posting_id, 'ai_score': ai_score}
                return render(request, self.template_name, context)
        else: # Form is not valid (this else corresponds to 'if form.is_valid()')
            logger.warning(f"ReviewApplicantForm invalid. Errors: {form.errors.as_json()}")
            # Re-render form with errors. is_new_user status should be based on initial check.
            context = {
                'form': form, 
                'is_new_user': is_new_user_initial_check, 
                'job_posting_id': job_posting_id, 
                'ai_score': ai_score
            }
            return render(request, self.template_name, context)

class CareerHomeView(View):
    """
    Displays the main django_career_app landing page.

    Shows general company information (if available) from the CompanyProfile
    model and a list of currently active job postings.
    """
    template_name = 'django_career_app/career_home.html'

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests for the careers home page.

        Fetches the first CompanyProfile instance and all active JobPosting
        instances to display on the page.
        """
        company_profile = CompanyProfile.objects.first() # Fetch the first CompanyProfile
        job_postings = JobPosting.objects.filter(is_active=True) # Fetch active job postings
        
        context = {
            'company_profile': company_profile,
            'job_postings': job_postings,
        }
        return render(request, self.template_name, context)

class JobDetailView(View):
    """
    Displays the details of a single job posting and handles the initial
    application submission process.

    The GET method shows job details and an application form.
    The POST method handles the first stage of application: validates form input,
    saves the resume file to a temporary Applicant record, processes the resume
    using an LLM, stores all relevant data (form input, LLM results, temporary
    applicant PK) in the session, and then redirects to the application review page.
    """
    template_name = 'django_career_app/job_detail.html'

    def get(self, request, pk, *args, **kwargs):
        """
        Handles GET requests for the job detail page.

        Fetches the specified JobPosting by its primary key (pk) and
        displays its details along with an empty ApplicantForm for users
        to start an application.
        """
        job_posting = get_object_or_404(JobPosting, pk=pk)
        form = ApplicantForm()
        context = {
            'job_posting': job_posting,
            'form': form,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk, *args, **kwargs):
        """
        Handles POST requests for initial application submission.

        Validates the submitted ApplicantForm (containing applicant details
        and resume). If valid:
        1. Creates a temporary Applicant record to store the uploaded resume
           and initial form data.
        2. Extracts text from the resume PDF.
        3. If text is extracted, calls an LLM utility to parse the resume
           and calculate an AI score against the job description.
        4. Stores all relevant data (temporary applicant's PK, parsed data from
           LLM, AI score, job posting ID, and original form data) in the
           user's session.
        5. Redirects the user to the 'review_application' page for them to
           verify and finalize their application.
        If the form is invalid, it re-renders the job detail page with errors.
        """
        job_posting = get_object_or_404(JobPosting, pk=pk)
        form = ApplicantForm(request.POST, request.FILES)

        if form.is_valid():
            applicant = form.save(commit=False)
            # applicant.job_posting = job_posting # Removed: job_posting is no longer a field on Applicant model
            # Save applicant first to handle file upload with django-storages
            # The resume_pdf field itself is handled by the form.save()
            # Removed: applicant.email is no longer a field on Applicant model
            # applicant.email = f"dummy_{datetime.datetime.now().timestamp()}@example.com" 
            # Initial save for file upload (only for resume_pdf and resume_markdown)
            try:
                applicant.save() 
            except Exception as e:
                logger.error(f"Error saving applicant: {e}", exc_info=True)
                messages.error(request, "An error occurred while saving your application. Please try again.")
                return render(request, self.template_name, {'job_posting': job_posting, 'form': form})

            extracted_text = ""
            logger.info(f"Attempting to extract text from resume for Applicant: {applicant.id}")
            if applicant.resume_pdf and applicant.resume_pdf.name:
                try:
                    # For GCS, resume_pdf.file might raise an error if not opened first.
                    # It's safer to use resume_pdf.open() as a context manager.
                    # The seek(0) should be on the file object obtained from open().
                    with applicant.resume_pdf.open('rb') as f:
                        if hasattr(f, 'seek') and callable(f.seek): # Check if the opened file object has seek
                           f.seek(0)
                        extracted_text = extract_text_from_pdf(f)

                    if extracted_text:
                        logger.info(f"Successfully extracted text for Applicant ID: {applicant.id}")
                    else:
                        logger.warning(
                            f"Text extraction yielded empty result for Applicant ID: {applicant.id}. PDF might be image-based or empty.")
                except Exception as e:
                    logger.error(
                        f"Error extracting text for Applicant ID {applicant.id}: {e}",
                        exc_info=True)
            else:
                logger.warning(f"No resume PDF found for Applicant ID: {applicant.id} for text extraction.")

            # Initialize ai_score_value for cases where LLM is not called
            ai_score_value = -1.0 
            parsed_data = {} # Initialize parsed_data to an empty dict

            if extracted_text:
                logger.info(f"Processing extracted text with LLM for Applicant ID: {applicant.id}")
                job_requirements = list(JobRequirement.objects.filter(job_posting=job_posting).values('name', 'weight'))
                llm_results = get_resume_analysis_with_llm(extracted_text, job_posting.description, job_requirements)

                parsed_data = llm_results.get("parsed_data", {})  # Ensure parsed_data is always a dict
                ai_score_value = llm_results.get("ai_score", -1.0)
                resume_markdown = llm_results.get("resume_markdown", "")

                if llm_results.get("error"):
                    logger.error(
                        f"LLM processing error for Applicant {applicant.id}: {llm_results.get('error_detail', 'No specific detail')}")

                # Log parsing specific errors if any
                if parsed_data.get("error"):
                    logger.error(
                        f"LLM parsing specific error for Applicant {applicant.id}: {parsed_data.get('error_detail', 'No specific detail')}")
                    # Potentially use dummy_combined_response structure for parsed_data if it's critical
                    # For now, we'll rely on .get() for safe access.

                # Update applicant with resume_markdown
                applicant.resume_markdown = resume_markdown
                applicant.save(update_fields=['resume_markdown'])

                # --- LLM Data Processed (or skipped) ---
                # The Applicant model fields (full_name, email, etc.) are NOT updated here directly anymore.
                # User objects are NOT created here.
                # Tag objects are NOT created here.
                # Application objects are NOT created here.
                logger.info(
                    f"LLM processing complete for temp applicant {applicant.id}. Parsed data and AI score obtained.")

            else:  # if not extracted_text
                logger.warning(
                    f"Skipping LLM processing for temp applicant {applicant.id} due to no extracted text.")
                # parsed_data will be {} and ai_score_value will be -1.0 as initialized

            # Prepare data for session
            session_data = {
                "temp_applicant_pk": applicant.pk,  # PK of the temporary Applicant record with the resume
                "parsed_data": parsed_data,
                "ai_score": ai_score_value,
                "job_posting_id": job_posting.pk,
                # resume_file_name can be accessed via applicant.resume_pdf.name if needed on review page
                "resume_markdown": resume_markdown,
            }
            request.session['application_review_data'] = session_data

            # Redirect to the new review page
            # The 'review_application' URL name is a placeholder and will be defined later.
            logger.info(f"Redirecting temp applicant {applicant.pk} to review page. Session data stored.")
            return redirect(reverse('django_career_app:review_application'))  # Placeholder URL name
        else:
            logger.warning(f"Applicant form was invalid for job posting {pk}. Errors: {form.errors.as_json()}")
            context = {
                'job_posting': job_posting,
                'form': form,
            }
            return render(request, self.template_name, context)


class ApplicationThankYouView(TemplateView):
    template_name = 'django_career_app/application_thank_you.html'


class AdminJobListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = JobPosting
    template_name = 'django_career_app/admin_job_list.html' # Will be created in next step
    context_object_name = 'job_postings'
    paginate_by = 20 # Optional: add pagination

    def test_func(self):
        return self.request.user.is_staff # Or self.request.user.is_superuser

    def get_queryset(self):
        return JobPosting.objects.order_by('-date_posted')

class AdminCandidateListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Application
    template_name = 'django_career_app/admin_candidate_list.html' # Will be created in next step
    context_object_name = 'applications'
    paginate_by = 15 # Optional: add pagination

    def test_func(self):
        return self.request.user.is_staff # Or self.request.user.is_superuser

    def dispatch(self, request, *args, **kwargs):
        # Store job_posting for use in other methods
        self.job_posting = get_object_or_404(JobPosting, pk=self.kwargs['job_posting_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Application.objects.filter(job_posting=self.job_posting).select_related('user', 'user__applicant')
        
        # Get ordering from GET parameter
        order_by = self.request.GET.get('order_by', '-application_date') # Default order
        
        allowed_orders = ['ai_score', '-ai_score', 'application_date', '-application_date']
        if order_by in allowed_orders:
            queryset = queryset.order_by(order_by)
        else:
            # Fallback to default if invalid order_by is provided
            queryset = queryset.order_by('-application_date') 
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['job_posting'] = self.job_posting
        context['current_order_by'] = self.request.GET.get('order_by', '-application_date')
        # For displaying applicant details, the Application model links to User,
        # and User links to Applicant profile. We need to ensure Applicant data is accessible.
        # Pre-fetching related data can be beneficial for performance.
        # The queryset in get_queryset could be updated:
        # queryset = Application.objects.filter(job_posting=self.job_posting) \
        #                           .select_related('user', 'user__applicant')
        # This assumes 'user__applicant' is a valid relationship (OneToOneField from User to Applicant is named 'applicant')
        # Let's check models.py: Applicant has OneToOneField to User. So user.applicant should work.
        # JobPosting has 'title'. Applicant has 'full_name', 'linkedin_profile', etc.
        # Application has 'ai_score', 'application_date'.
        # Tag is on Applicant.
        # The template will need to access applicant details via application.user.applicant
        return context

@login_required
@user_passes_test(lambda u: u.is_staff) # or u.is_superuser
def download_resume(request, applicant_id):
    """
    Allows admin users to download an applicant's resume PDF.
    """
    applicant = get_object_or_404(Applicant, pk=applicant_id)
    if not applicant.resume_pdf:
        raise Http404("Resume file not found for this applicant.")

    try:
        # Assuming resume_pdf.path gives the absolute path to the file.
        # This works for FileSystemStorage. For cloud storages, applicant.resume_pdf.url might be needed,
        # or applicant.resume_pdf.open() and then FileResponse.
        # For now, let's assume FileSystemStorage for simplicity.
        
        # Option 1: Using FileResponse (preferred for large files, handles streaming)
        # The file needs to be opened in binary mode.
        # file_path = applicant.resume_pdf.path
        # response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        # response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        # return response

        # Option 2: Using HttpResponse (reads whole file into memory)
        # Suitable for smaller files or if FileResponse has issues with storage backend.
        try:
            file_path = applicant.resume_pdf.path
            with open(file_path, 'rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
            return response
        except NotImplementedError:
            # More generic, works with S3 etc. if file can be read via open()
            # This part is tricky with remote storages.
            # applicant.resume_pdf.open() should provide a file-like object.
            with applicant.resume_pdf.open('rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
            # Try to get a sensible filename
            file_name = os.path.basename(applicant.resume_pdf.name) # Use .name for a more reliable filename
            response['Content-Disposition'] = f'attachment; filename="{file_name}"'
            return response
        except:
            logger.error(f"Cannot determine how to access resume_pdf for applicant {applicant_id}. No 'path' or 'url' attribute.")
            raise Http404("Error accessing resume file. Storage configuration issue.")

    except FileNotFoundError:
        logger.error(f"Resume file not found at path for applicant {applicant_id}.", exc_info=True)
        raise Http404("Resume file not found on server.")
    except Exception as e:
        logger.error(f"Error serving resume for applicant {applicant_id}: {e}", exc_info=True)
        # Return a generic error to the user or raise Http404
        return HttpResponse("Error serving file.", status=500)
