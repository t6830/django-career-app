from django import forms
from .models import Applicant

class ApplicantForm(forms.ModelForm):
    """
    Form for initial job application submission.

    Based on the Applicant model, it captures the applicant's full name,
    email, optional phone/LinkedIn, and the resume PDF file.
    """
    resume_pdf = forms.FileField(
        label="Upload Resume (PDF)", 
        help_text="Please upload your resume in PDF format. Max size: 2MB." # Updated help_text
    )

    class Meta:
        model = Applicant
        fields = ['resume_pdf'] # Only resume_pdf as per current form

    def clean_resume_pdf(self):
        resume_file = self.cleaned_data.get('resume_pdf')

        if resume_file:
            # File Type Validation
            is_pdf_content_type = resume_file.content_type == 'application/pdf'
            # Check name as fallback, especially if content_type is generic (e.g., application/octet-stream)
            is_pdf_name = resume_file.name.lower().endswith('.pdf')

            if not is_pdf_content_type and not is_pdf_name: # Stricter: if content_type is wrong, reject. If content_type is missing/generic, rely on name.
                 raise forms.ValidationError("File is not a PDF. Please upload a PDF document.")
            elif not is_pdf_content_type and is_pdf_name:
                 # Optionally log a warning if content_type was not 'application/pdf' but name was okay
                 pass # Allowing it based on name for now as per example's lenient condition

            # File Size Validation (2MB limit)
            if resume_file.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Resume file size cannot exceed 2MB.")
        
        return resume_file

class ReviewApplicantForm(forms.Form):
    """
    Form used on the application review page.

    Allows users to review and edit data that was initially provided in the
    ApplicantForm and/or parsed from their resume by an LLM. It also handles
    password setting for new user registration. The form's behavior, particularly
    for password fields, is dynamic based on the `is_new_user` flag passed
    during instantiation.
    """
    first_name = forms.CharField(max_length=150, required=True, label="First Name")
    last_name = forms.CharField(max_length=150, required=True, label="Last Name")
    email = forms.EmailField(required=True, label="Email Address")
    phone_number = forms.CharField(max_length=20, required=False, label="Phone Number")
    linkedin_profile = forms.URLField(required=False, label="LinkedIn Profile URL")
    
    current_title = forms.CharField(max_length=255, required=False, label="Current/Recent Job Title")
    latest_work_organization = forms.CharField(max_length=255, required=False, label="Company/Organization")
    
    latest_degree = forms.CharField(max_length=255, required=False, label="Degree")
    school = forms.CharField(max_length=255, required=False, label="School/University")
    major = forms.CharField(max_length=255, required=False, label="Major/Field of Study")
    graduate_year = forms.IntegerField(required=False, label="Graduation Year")
    
    tags_edit = forms.CharField(
        label="Tags (comma-separated)", 
        required=False, 
        help_text="Review and edit your skills or tags, separated by commas."
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput, 
        required=False, 
        label="Password"
    )
    password_confirmation = forms.CharField(
        widget=forms.PasswordInput, 
        required=False, 
        label="Confirm Password"
    )

    def __init__(self, *args, **kwargs):
        """
        Initializes the ReviewApplicantForm.

        Accepts an `is_new_user` keyword argument (defaulting to False).
        If `is_new_user` is True, the 'password' and 'password_confirmation'
        fields are marked as required for new user registration.
        """
        self.is_new_user = kwargs.pop('is_new_user', False) 
        super().__init__(*args, **kwargs)
        
        if self.is_new_user:
            self.fields['password'].required = True
            self.fields['password_confirmation'].required = True

    def clean_email(self):
        """
        Normalizes the email address by converting it to lowercase and
        stripping leading/trailing whitespace.
        """
        email = self.cleaned_data.get('email')
        if email:
            return email.lower().strip()
        return email

    def clean(self):
        """
        Performs cross-field validation, primarily for password confirmation
        when a new user is being registered.

        If `is_new_user` is True (passed during form instantiation):
            - Ensures that if a password is provided, the password confirmation
              field is also provided.
            - Ensures that the password and password confirmation fields match.
        Field-level 'required' validation for password fields (if `is_new_user`
        is True) is handled by the logic in `__init__`.

        This method does not handle checking an existing user's current password;
        that logic is managed in the view's POST method.
        """
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirmation = cleaned_data.get("password_confirmation")

        if self.is_new_user:
            # 'password' and 'password_confirmation' are set to required=True in __init__ if is_new_user.
            # This clean method focuses on ensuring they match if both are present (or confirmation is present if password is).
            if password and not password_confirmation: 
                 self.add_error('password_confirmation', "Please confirm your password.")
            elif password and password_confirmation and password != password_confirmation: 
                self.add_error('password_confirmation', "Passwords do not match.")
        # For existing users (self.is_new_user is False), password_confirmation is not relevant
        # in this form as it's not displayed. The view handles checking the 'password' field
        # against the user's actual current password.
             
        return cleaned_data
