from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from io import BytesIO # For mocking file objects
import os # For download_resume test if needed, and settings
from datetime import timedelta # For creating distinct application dates
from django.utils import timezone # For checking auto_now_add fields
from django.urls import reverse # Added for reversing URLs
from django.core.files.uploadedfile import SimpleUploadedFile # Added for file uploads
from django.conf import settings # For MEDIA_ROOT if needed, and LLM settings

from .models import Applicant, Tag, Application, JobPosting, CompanyProfile # Ensure all models are imported
from .forms import ReviewApplicantForm, ApplicantForm # Added ApplicantForm
from .templatetags.markdown_extras import markdown_to_html # For MarkdownTemplateTagTests
from .utils import convert_pdf_to_markdown # For UtilsTests

# --- New Imports for LLMUtilsTests ---
import json
from unittest.mock import patch, MagicMock, call
# from django.conf import settings # Already imported
from .llm_utils import get_resume_analysis_with_llm # Target function
# --- End New Imports ---

# Helper methods (can be outside a class or in a base test class if preferred)
def _create_user(username, email='user@example.com', password='password', is_staff=False, first_name='', last_name=''):
    user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name, last_name=last_name)
    if is_staff:
        user.is_staff = True
        user.save()
    return user

class ApplicantModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='password123', first_name='Test', last_name='User')

    def test_applicant_creation(self):
        """Test basic creation of an Applicant instance."""
        applicant = Applicant.objects.create(
            user=self.user,
            # full_name="John Doe", # Removed
            # email="john.doe@example.com", # Removed
            phone_number="123-456-7890",
            linkedin_profile="http://linkedin.com/in/johndoe",
            current_title="Software Engineer",
            latest_degree="BSc Computer Science",
            school="Test University",
            major="Computer Science",
            graduate_year=2020,
            latest_work_organization="Tech Corp"
        )
        self.assertIsNotNone(applicant.pk)
        # self.assertEqual(applicant.full_name, "John Doe") # Removed
        self.assertEqual(applicant.user, self.user)
        self.assertEqual(applicant.latest_work_organization, "Tech Corp")

    def test_applicant_str_method(self):
        """Test the __str__ method of the Applicant model."""
        # Create a user with specific first_name, last_name, and email for this test
        user_jane = User.objects.create_user(username='janesmith', email='jane.smith@example.com', password='password123', first_name='Jane', last_name='Smith')
        applicant = Applicant.objects.create(
            user=user_jane,
            # full_name="Jane Smith", # Removed
            # email="jane.smith@example.com" # Removed
        )
        self.assertEqual(str(applicant), "Jane Smith - jane.smith@example.com")

    def test_applicant_tags_relationship(self):
        """Test adding tags to an applicant."""
        # Create a user for this applicant
        user_alice = _create_user(username='alicew', email='alice@example.com', password='password123', first_name='Alice', last_name='Wonderland')
        applicant = Applicant.objects.create(
            user=user_alice,
            # full_name="Alice Wonderland", # Removed
            # email="alice@example.com" # Removed
        )
        tag1 = Tag.objects.create(name="Python")
        tag2 = Tag.objects.create(name="Django")
        
        applicant.tags.add(tag1)
        applicant.tags.add(tag2)
        
        self.assertEqual(applicant.tags.count(), 2)
        self.assertIn(tag1, applicant.tags.all())
        self.assertIn(tag2, applicant.tags.all())

        # Test removing a tag
        applicant.tags.remove(tag1)
        self.assertEqual(applicant.tags.count(), 1)
        self.assertNotIn(tag1, applicant.tags.all())


class TagModelTests(TestCase):
    # RFT: def test_tag_creation(self):
    # RFT:     """Test basic creation of a Tag instance."""
    # RFT:     tag = Tag.objects.create(name="JavaScript")
    # RFT:     self.assertIsNotNone(tag.pk)
    # RFT:     self.assertEqual(tag.name, "JavaScript")

    # RFT: def test_tag_str_method(self):
    # RFT:     """Test the __str__ method of the Tag model."""
    # RFT:     tag = Tag.objects.create(name="React")
    # RFT:     self.assertEqual(str(tag), "React")

    def test_tag_name_uniqueness(self):
        """Test that Tag names are unique."""
        Tag.objects.create(name="UniqueTag")
        with self.assertRaises(IntegrityError):
            Tag.objects.create(name="UniqueTag")


class ApplicationModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='apptestuser', email='apptest@example.com', password='password123')
        self.job_posting = JobPosting.objects.create(
            title="Developer Advocate",
            description="Engage with the developer community.",
            location="Remote"
        )

    def test_application_creation(self):
        """Test basic creation of an Application instance."""
        application = Application.objects.create(
            user=self.user,
            job_posting=self.job_posting,
            ai_score=88.5
        )
        self.assertIsNotNone(application.pk)
        self.assertEqual(application.user, self.user)
        self.assertEqual(application.job_posting, self.job_posting)
        self.assertEqual(application.ai_score, 88.5)
        self.assertIsNotNone(application.application_date)
        delta = timezone.now() - application.application_date
        self.assertTrue(delta.total_seconds() < 5)


    def test_application_str_method(self):
        """Test the __str__ method of the Application model."""
        application = Application.objects.create(
            user=self.user,
            job_posting=self.job_posting,
            ai_score=75.0
        )
        expected_str = f"Application for {self.user.username} to {self.job_posting.title}"
        self.assertEqual(str(application), expected_str)

    # RFT: def test_application_str_method_no_user_or_job(self):
    # RFT:     app_no_user = Application(job_posting=self.job_posting, ai_score=70)
    # RFT:     self.assertEqual(str(app_no_user), f"Application for Unknown User to {self.job_posting.title}")
    # RFT:     
    # RFT:     app_no_job = Application(user=self.user, ai_score=70)
    # RFT:     self.assertEqual(str(app_no_job), f"Application for {self.user.username} to Unknown Job")
    # RFT: 
    # RFT:     app_no_user_no_job = Application(ai_score=70)
    # RFT:     self.assertEqual(str(app_no_user_no_job), "Application for Unknown User to Unknown Job")


class LLMUtilsTests(TestCase):
    def setUp(self):
        self.resume_text = "Experienced Python developer with a background in web development."
        self.job_description = "Seeking a Python developer for a web application project."
        self.job_requirements = [{"name": "Python", "weight": 0.8}, {"name": "Django", "weight": 0.7}]
        
        if not hasattr(settings, 'GEMINI_API_KEY'):
            settings.GEMINI_API_KEY = 'dummy_api_key_for_test'
        if not hasattr(settings, 'LLM_MODEL_NAME'):
            settings.LLM_MODEL_NAME = 'gemini/gemini-pro-test'

        self.mock_default_parsed_data = {
            "first_name": "Dummy",
            "last_name": "Candidate",
            "contact_info": {}, "latest_education": {}, "latest_work_experience": {},
            "top_tags": [], "error": None, "error_detail": None
        }


    @patch('career_portal.django_career_app.llm_utils.litellm.completion')
    def test_successful_analysis(self, mock_llm_completion):
        mock_parsed_content = {
            "first_name": "Test",
            "last_name": "User",
            "contact_info": {"email": "test@example.com"},
            "latest_education": {"degree": "BSc"},
            "latest_work_experience": {"title": "Dev"},
            "top_tags": ["Python"]
        }
        mock_score_content = "90.5"
    
        mock_llm_completion.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(mock_parsed_content)))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content=mock_score_content))])
        ]
    
        results = get_resume_analysis_with_llm(self.resume_text, self.job_description, self.job_requirements)
        
        self.assertEqual(mock_llm_completion.call_count, 2)
        calls = mock_llm_completion.call_args_list
        self.assertEqual(calls[0][1]['model'], settings.LLM_MODEL_NAME)
        self.assertTrue(self.resume_text in calls[0][1]['messages'][0]['content'])
        self.assertEqual(calls[1][1]['model'], settings.LLM_MODEL_NAME)
        self.assertTrue(self.resume_text in calls[1][1]['messages'][0]['content'])
        self.assertTrue(self.job_description in calls[1][1]['messages'][0]['content'])
    
        self.assertIsNotNone(results.get("parsed_data"))
        self.assertEqual(results["parsed_data"].get("first_name"), "Test")
        self.assertEqual(results["parsed_data"].get("last_name"), "User")
        self.assertEqual(results.get("ai_score"), 90.5)
        self.assertIsNone(results.get("error"))
        self.assertIsNone(results.get("error_detail"))
        self.assertIsNone(results["parsed_data"].get("error"))


    @patch('career_portal.django_career_app.llm_utils.litellm.completion')
    def test_parsing_fails_scoring_succeeds(self, mock_llm_completion):
        mock_score_content = "75.0"
        # Mock the combined LLM call to return an error for parsed_data, but a valid score
        mock_llm_completion.return_value = MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({
            "parsed_data": {"error": "LLM Parsing Error", "error_detail": "Simulated parsing error"},
            "ai_score": float(mock_score_content),
            "resume_markdown": "Dummy markdown"
        })))])
    
        results = get_resume_analysis_with_llm(self.resume_text, self.job_description, self.job_requirements)
    
        self.assertEqual(mock_llm_completion.call_count, 1) # Only one call now
        self.assertIsNotNone(results.get("parsed_data"))
        self.assertIsNotNone(results["parsed_data"].get("error"))
        self.assertTrue("Simulated parsing error" in results["parsed_data"].get("error_detail"))
        self.assertEqual(results.get("ai_score"), 75.0)
        self.assertIsNone(results.get("error")) # Top-level error should be None if score is valid


    # RFT: @patch('career_portal.django_career_app.llm_utils.litellm.completion')
    # RFT: def test_parsing_succeeds_scoring_fails(self, mock_llm_completion):
    # RFT:     mock_parsed_content = {"full_name": "ParsedTest User", "contact_info": {}, "latest_education": {}, "latest_work_experience": {}, "top_tags": []}
    # RFT:     mock_llm_completion.side_effect = [
    # RFT:         MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(mock_parsed_content)))]),
    # RFT:         Exception("LLM Scoring Error")
    # RFT:     ]
    # RFT: 
    # RFT:     results = get_resume_analysis_with_llm(self.resume_text, self.job_description, self.job_requirements)
    # RFT:     
    # RFT:     self.assertEqual(mock_llm_completion.call_count, 2)
    # RFT:     self.assertEqual(results["parsed_data"].get("full_name"), "ParsedTest User")
    # RFT:     self.assertIsNone(results["parsed_data"].get("error"))
    # RFT:     self.assertEqual(results.get("ai_score"), -1.0)
    # RFT:     self.assertIsNotNone(results.get("error"))
    # RFT:     self.assertTrue("Scoring part" in results.get("error"))


    # RFT: @patch('career_portal.django_career_app.llm_utils.litellm.completion')
    # RFT: def test_both_llm_calls_fail(self, mock_llm_completion):
    # RFT:     mock_llm_completion.side_effect = [
    # RFT:         Exception("LLM Parsing Error"), 
    # RFT:         Exception("LLM Scoring Error")
    # RFT:     ]
    # RFT: 
    # RFT:     results = get_resume_analysis_with_llm(self.resume_text, self.job_description, self.job_requirements)
    # RFT:     
    # RFT:     self.assertEqual(mock_llm_completion.call_count, 2)
    # RFT:     self.assertIsNotNone(results["parsed_data"].get("error"))
    # RFT:     self.assertEqual(results.get("ai_score"), -1.0)
    # RFT:     self.assertIsNotNone(results.get("error"))
    # RFT:     self.assertTrue("Both parsing and scoring" in results.get("error_detail"))


    # RFT: @patch('career_portal.django_career_app.llm_utils.litellm.completion')
    # RFT: def test_llm_returns_malformed_json_for_parsing(self, mock_llm_completion): # This test implies json-repair fails
    # RFT:     malformed_json_content = "This is not valid JSON { full_name: Test " # Missing closing brace
    # RFT:     mock_score_content = "80.0"
    # RFT:     mock_llm_completion.side_effect = [
    # RFT:         MagicMock(choices=[MagicMock(message=MagicMock(content=malformed_json_content))]),
    # RFT:         MagicMock(choices=[MagicMock(message=MagicMock(content=mock_score_content))])
    # RFT:     ]
    # RFT: 
    # RFT:     results = get_resume_analysis_with_llm(self.resume_text, self.job_description, self.job_requirements)
    # RFT: 
    # RFT:     self.assertIsNotNone(results["parsed_data"].get("error"))
    # RFT:     self.assertTrue("LLM parsing response was not valid JSON" in results["parsed_data"].get("error"))
    # RFT:     self.assertEqual(results.get("ai_score"), 80.0)
    # RFT:     self.assertIsNotNone(results.get("error"))
    # RFT:     self.assertTrue("Parsing part" in results.get("error"))


    # RFT: @patch('career_portal.django_career_app.llm_utils.litellm.completion')
    # RFT: def test_llm_returns_non_numerical_score(self, mock_llm_completion):
    # RFT:     mock_parsed_content = {"full_name": "ScoreTest User", "contact_info": {}, "latest_education": {}, "latest_work_experience": {}, "top_tags": []}
    # RFT:     non_numerical_score_content = "About seventy five"
    # RFT:     mock_llm_completion.side_effect = [
    # RFT:         MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(mock_parsed_content)))]),
    # RFT:         MagicMock(choices=[MagicMock(message=MagicMock(content=non_numerical_score_content))])
    # RFT:     ]
    # RFT: 
    # RFT:     results = get_resume_analysis_with_llm(self.resume_text, self.job_description, self.job_requirements)
    # RFT: 
    # RFT:     self.assertEqual(results["parsed_data"].get("full_name"), "ScoreTest User")
    # RFT:     self.assertIsNone(results["parsed_data"].get("error"))
    # RFT:     self.assertEqual(results.get("ai_score"), -1.0) 
    # RFT:     self.assertIsNotNone(results.get("error"))
    # RFT:     self.assertTrue("Scoring part" in results.get("error"))

    # RFT: @patch('career_portal.django_career_app.llm_utils.litellm.completion')
    # RFT: def test_llm_returns_repairable_malformed_json_for_parsing(self, mock_llm_completion):
    # RFT:     """Test that json-repair handles and fixes malformed JSON from the LLM."""
    # RFT:     repairable_malformed_json_string = '{"full_name": "Repair Test", "contact_info": {"email": "repair@example.com"}, "latest_education": {"degree": "PhD",}, "latest_work_experience": {"title": "Repaired Engineer", "company_name": "FixIt Corp",}, "top_tags": ["repaired", "json"],}' # Trailing commas
    # RFT:     
    # RFT:     expected_parsed_data = {
    # RFT:         "full_name": "Repair Test",
    # RFT:         "contact_info": {"email": "repair@example.com"},
    # RFT:         "latest_education": {"degree": "PhD"}, 
    # RFT:         "latest_work_experience": {"title": "Repaired Engineer", "company_name": "FixIt Corp"},
    # RFT:         "top_tags": ["repaired", "json"]
    # RFT:     }
    # RFT:     mock_score_content = "92.0"
    # RFT: 
    # RFT:     mock_llm_completion.side_effect = [
    # RFT:         MagicMock(choices=[MagicMock(message=MagicMock(content=repairable_malformed_json_string))]), 
    # RFT:         MagicMock(choices=[MagicMock(message=MagicMock(content=mock_score_content))])
    # RFT:     ]
    # RFT: 
    # RFT:     results = get_resume_analysis_with_llm(self.resume_text, self.job_description, self.job_requirements)
    # RFT:     
    # RFT:     self.assertEqual(mock_llm_completion.call_count, 2)
    # RFT:     self.assertIsNotNone(results.get("parsed_data"))
    # RFT:     self.assertEqual(results["parsed_data"].get("full_name"), expected_parsed_data["full_name"])
    # RFT:     self.assertEqual(results["parsed_data"].get("contact_info"), expected_parsed_data["contact_info"])
    # RFT:     self.assertEqual(results["parsed_data"].get("latest_education"), expected_parsed_data["latest_education"])
    # RFT:     self.assertEqual(results["parsed_data"].get("latest_work_experience"), expected_parsed_data["latest_work_experience"])
    # RFT:     self.assertEqual(results["parsed_data"].get("top_tags"), expected_parsed_data["top_tags"])
    # RFT:     self.assertIsNone(results["parsed_data"].get("error"))
    # RFT:     self.assertIsNone(results["parsed_data"].get("error_detail"))
    # RFT:     self.assertEqual(results.get("ai_score"), 92.0)
    # RFT:     self.assertIsNone(results.get("error"))
    # RFT:     self.assertIsNone(results.get("error_detail"))

# --- JobDetailViewPostTests ---
class JobDetailViewPostTests(TestCase):
    def setUp(self):
        # CompanyProfile is needed because career_home (redirect target) uses it.
        CompanyProfile.objects.create(description="Test Company Profile")
        self.job_posting = JobPosting.objects.create(
            title="Software Engineer", 
            description="Develop amazing software.", 
            location="Remote"
        )
        self.client = Client()
        self.url = reverse('django_career_app:job_detail', args=[self.job_posting.pk])

        # Common mock LLM response structure
        self.mock_llm_parsed_data_success = {
            "full_name": "LLM Applicant",
            "contact_info": {
                "email": "llm.applicant@example.com", # This email should be used for User creation
                "phone_number": "111-222-3333",
                "linkedin_profile": "linkedin.com/in/llmapplicant"
            },
            "latest_education": {
                "latest_degree": "MSc AI",
                "school": "LLM University",
                "major": "Artificial Intelligence",
                "graduate_year": 2022
            },
            "latest_work_experience": {
                "current_title": "AI Researcher",
                "company_name": "LLM Solutions Inc." # Maps to latest_work_organization
            },
            "top_tags": ["AI", "Machine Learning", "Python"],
            "error": None,
            "error_detail": None
        }
        self.mock_llm_score_success = 95.0
        self.mock_llm_success_return_value = {
            "parsed_data": self.mock_llm_parsed_data_success,
            "ai_score": self.mock_llm_score_success,
            "error": None,
            "error_detail": None
        }

    # RFT: @patch('career_portal.django_career_app.views.get_resume_analysis_with_llm')
    # RFT: @patch('career_portal.django_career_app.views.extract_text_from_pdf')
    # RFT: def test_successful_application_new_user(self, mock_extract_text, mock_llm_analysis):
    # RFT:     mock_extract_text.return_value = "This is valid resume text."
    # RFT:     mock_llm_analysis.return_value = self.mock_llm_success_return_value
    # RFT: 
    # RFT:     # Create a dummy resume file
    # RFT:     resume_content = b"dummy resume content pdf"
    # RFT:     resume_file = SimpleUploadedFile("resume.pdf", resume_content, content_type="application/pdf")
    # RFT: 
    # RFT:     form_data = {
    # RFT:         'full_name': 'Form Applicant', 
    # RFT:         'email': 'form.applicant@example.com', 
    # RFT:         'phone_number': '000-000-0000', 
    # RFT:         'linkedin_profile': 'linkedin.com/in/formapplicant', 
    # RFT:         'resume_pdf': resume_file,
    # RFT:     }
    # RFT: 
    # RFT:     response = self.client.post(self.url, data=form_data, follow=False) 
    # RFT: 
    # RFT:     self.assertEqual(response.status_code, 302) 
    # RFT:     self.assertEqual(response.url, reverse('django_career_app:review_application'))
    # RFT:     
    # RFT:     mock_extract_text.assert_called_once()
    # RFT:     mock_llm_analysis.assert_called_once()
    # RFT: 
    # RFT:     self.assertEqual(Applicant.objects.count(), 1) # Temporary applicant created
    # RFT:     temp_applicant = Applicant.objects.first()
    # RFT:     self.assertIsNotNone(temp_applicant.pk)
    # RFT:     self.assertEqual(temp_applicant.full_name, 'Form Applicant') # Initial form data
    # RFT:     self.assertEqual(temp_applicant.email, 'form.applicant@example.com')
    # RFT: 
    # RFT:     session_data = self.client.session.get('application_review_data')
    # RFT:     self.assertIsNotNone(session_data)
    # RFT:     self.assertEqual(session_data.get('temp_applicant_pk'), temp_applicant.pk)
    # RFT:     self.assertEqual(session_data.get('parsed_data'), self.mock_llm_parsed_data_success)
    # RFT:     self.assertEqual(session_data.get('ai_score'), self.mock_llm_score_success)
    # RFT:     self.assertEqual(session_data.get('job_posting_id'), self.job_posting.pk)
    # RFT:     self.assertEqual(session_data.get('form_email'), 'form.applicant@example.com')
    # RFT:     self.assertEqual(session_data.get('form_full_name'), 'Form Applicant')
    # RFT:     
    # RFT:     # Verify no final User, Application, or Tags are created by this view
    # RFT:     self.assertEqual(User.objects.filter(email="llm.applicant@example.com").count(), 0)
    # RFT:     self.assertEqual(Application.objects.count(), 0)
    # RFT:     self.assertEqual(Tag.objects.count(), 0)


    # RFT: @patch('career_portal.django_career_app.views.get_resume_analysis_with_llm')
    # RFT: @patch('career_portal.django_career_app.views.extract_text_from_pdf')
    # RFT: def test_successful_application_existing_user(self, mock_extract_text, mock_llm_analysis):
    # RFT:     existing_user_email = "existing.user@example.com"
    # RFT:     # No User object created here in setup for this test, as JobDetailView doesn't finalize User
    # RFT:     
    # RFT:     mock_extract_text.return_value = "Resume text for existing user."
    # RFT:     llm_data_for_existing_user = self.mock_llm_success_return_value.copy()
    # RFT:     llm_data_for_existing_user["parsed_data"] = self.mock_llm_parsed_data_success.copy()
    # RFT:     llm_data_for_existing_user["parsed_data"]["contact_info"]["email"] = existing_user_email
    # RFT:     llm_data_for_existing_user["parsed_data"]["full_name"] = "LLM Existing User Name"
    # RFT:     mock_llm_analysis.return_value = llm_data_for_existing_user
    # RFT: 
    # RFT:     resume_file = SimpleUploadedFile("resume_existing.pdf", b"pdf content", content_type="application/pdf")
    # RFT:     form_data = {
    # RFT:         'full_name': 'Form Existing User Name', 
    # RFT:         'email': existing_user_email, 
    # RFT:         'resume_pdf': resume_file,
    # RFT:     }
    # RFT: 
    # RFT:     response = self.client.post(self.url, data=form_data, follow=False)
    # RFT:     self.assertEqual(response.status_code, 302)
    # RFT:     self.assertEqual(response.url, reverse('django_career_app:review_application'))
    # RFT: 
    # RFT:     self.assertEqual(Applicant.objects.count(), 1) # Temporary applicant
    # RFT:     temp_applicant = Applicant.objects.first()
    # RFT:     self.assertEqual(temp_applicant.email, existing_user_email) # Initial form email
    # RFT: 
    # RFT:     session_data = self.client.session.get('application_review_data')
    # RFT:     self.assertIsNotNone(session_data)
    # RFT:     self.assertEqual(session_data.get('temp_applicant_pk'), temp_applicant.pk)
    # RFT:     self.assertEqual(session_data.get('parsed_data')['full_name'], "LLM Existing User Name")
    # RFT:     self.assertEqual(session_data.get('parsed_data')['contact_info']['email'], existing_user_email)
    # RFT:     self.assertEqual(session_data.get('ai_score'), self.mock_llm_score_success)


    # RFT: @patch('career_portal.django_career_app.views.get_resume_analysis_with_llm')
    # RFT: @patch('career_portal.django_career_app.views.extract_text_from_pdf')
    # RFT: def test_pdf_text_extraction_fails(self, mock_extract_text, mock_llm_analysis):
    # RFT:     mock_extract_text.return_value = "" 
    # RFT: 
    # RFT:     resume_file = SimpleUploadedFile("empty_resume.pdf", b"", content_type="application/pdf")
    # RFT:     form_data = {
    # RFT:         'full_name': 'Form User Only',
    # RFT:         'email': 'form.user.only@example.com',
    # RFT:         'resume_pdf': resume_file,
    # RFT:     }
    # RFT: 
    # RFT:     response = self.client.post(self.url, data=form_data, follow=False)
    # RFT:     self.assertEqual(response.status_code, 302)
    # RFT:     self.assertEqual(response.url, reverse('django_career_app:review_application'))
    # RFT: 
    # RFT:     mock_extract_text.assert_called_once()
    # RFT:     mock_llm_analysis.assert_not_called() 
    # RFT: 
    # RFT:     self.assertEqual(Applicant.objects.count(), 1) # Temporary applicant
    # RFT:     temp_applicant = Applicant.objects.first()
    # RFT: 
    # RFT:     session_data = self.client.session.get('application_review_data')
    # RFT:     self.assertIsNotNone(session_data)
    # RFT:     self.assertEqual(session_data.get('temp_applicant_pk'), temp_applicant.pk)
    # RFT:     self.assertEqual(session_data.get('parsed_data'), {}) # Empty as LLM was skipped
    # RFT:     self.assertEqual(session_data.get('ai_score'), -1.0) # Default error score


    # RFT: @patch('career_portal.django_career_app.views.get_resume_analysis_with_llm')
    # RFT: @patch('career_portal.django_career_app.views.extract_text_from_pdf')
    # RFT: def test_llm_analysis_reports_error(self, mock_extract_text, mock_llm_analysis):
    # RFT:     mock_extract_text.return_value = "Some resume text."
    # RFT:     llm_error_response = {
    # RFT:         "parsed_data": {"full_name": "LLM Error User", "contact_info": {"email": "llm.error@example.com"}, "error": "LLM Parsing Error", "error_detail": "Detail..."},
    # RFT:         "ai_score": -1.0, 
    # RFT:         "error": "LLM processing failed",
    # RFT:         "error_detail": "Simulated LLM error detail"
    # RFT:     }
    # RFT:     mock_llm_analysis.return_value = llm_error_response
    # RFT: 
    # RFT:     resume_file = SimpleUploadedFile("resume_llm_error.pdf", b"content", content_type="application/pdf")
    # RFT:     form_data = {
    # RFT:         'full_name': 'Form Name LLM Error',
    # RFT:         'email': 'form.llmerror@example.com', 
    # RFT:         'resume_pdf': resume_file,
    # RFT:     }
    # RFT:     
    # RFT:     response = self.client.post(self.url, data=form_data, follow=False)
    # RFT:     self.assertEqual(response.status_code, 302)
    # RFT:     self.assertEqual(response.url, reverse('django_career_app:review_application'))
    # RFT: 
    # RFT:     mock_llm_analysis.assert_called_once()
    # RFT:     self.assertEqual(Applicant.objects.count(), 1) # Temp applicant
    # RFT: 
    # RFT:     session_data = self.client.session.get('application_review_data')
    # RFT:     self.assertIsNotNone(session_data)
    # RFT:     self.assertEqual(session_data.get('parsed_data'), llm_error_response['parsed_data'])
    # RFT:     self.assertEqual(session_data.get('ai_score'), -1.0)


    # RFT: def test_invalid_form_submission(self):
    # RFT:     form_data = {
    # RFT:         'full_name': '', # Missing required field
    # RFT:         'email': 'invalidemail', # Invalid email format
    # RFT:         # Missing resume_pdf
    # RFT:     }
    # RFT:     initial_applicant_count = Applicant.objects.count()
    # RFT:     initial_application_count = Application.objects.count()
    # RFT:     initial_user_count = User.objects.count()
    # RFT: 
    # RFT:     response = self.client.post(self.url, data=form_data)
    # RFT:     
    # RFT:     self.assertEqual(response.status_code, 200) # Should re-render the form with errors
    # RFT:     self.assertIn('form', response.context)
    # RFT:     form_in_context = response.context['form']
    # RFT:     self.assertTrue(form_in_context.errors)
    # RFT:     self.assertIn('full_name', form_in_context.errors)
    # RFT:     self.assertIn('email', form_in_context.errors)
    # RFT:     self.assertIn('resume_pdf', form_in_context.errors) # Assuming resume_pdf is required by the form
    # RFT: 
    # RFT:     # Verify no objects were created
    # RFT:     self.assertEqual(Applicant.objects.count(), initial_applicant_count)
    # RFT:     self.assertEqual(Application.objects.count(), initial_application_count)
    # RFT:     self.assertEqual(User.objects.count(), initial_user_count)
    # RFT:     self.assertEqual(Tag.objects.count(), 0) # Assuming no tags initially

# --- ReviewApplicationViewTests ---
class ReviewApplicationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.review_url = reverse('django_career_app:review_application')
        self.home_url = reverse('django_career_app:career_home')
        CompanyProfile.objects.create(description="Global Corp Profile")

        self.job_posting = JobPosting.objects.create(title="Test Job", description="Test Job Desc", location="Test Location")
        
        # Create a temporary Applicant record as JobDetailView would
        self.temp_applicant = Applicant.objects.create(
            full_name="Temp Applicant", 
            email="temp@example.com"
            # resume_pdf is not strictly needed for these view tests if not directly accessed,
            # but JobDetailView creates it.
        )
        self.temp_applicant_pk = self.temp_applicant.pk

        self.existing_user_password = 'existingpassword123'
        self.existing_user = User.objects.create_user(
            username='existing@example.com', 
            email='existing@example.com', 
            password=self.existing_user_password
        )

        self.sample_parsed_data = {
            "full_name": "Parsed Full Name",
            "contact_info": {
                "email": "parsed.email@example.com",
                "phone_number": "123-456-7890",
                "linkedin_profile": "linkedin.com/in/parsed"
            },
            "latest_education": {
                "latest_degree": "BSc Parsed", "school": "Parsed Uni", 
                "major": "Parsing", "graduate_year": 2021
            },
            "latest_work_experience": {
                "current_title": "Parser", "company_name": "Parse Inc."
            },
            "top_tags": ["Parsing", "Testing", "Python"]
        }
        self.sample_form_data_from_session = {
            "form_full_name": "Form Full Name",
            "form_email": "form.email@example.com",
            "form_phone_number": "987-654-3210",
            "form_linkedin_profile": "linkedin.com/in/form"
        }
        self.sample_session_data_base = {
            "temp_applicant_pk": self.temp_applicant_pk,
            "parsed_data": self.sample_parsed_data,
            "ai_score": 88.0,
            "job_posting_id": self.job_posting.pk,
            **self.sample_form_data_from_session
        }

    def test_review_page_loads_with_session_data_new_user(self):
        session = self.client.session
        session['application_review_data'] = self.sample_session_data_base
        session.save()

        response = self.client.get(self.review_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'django_career_app/review_application_details.html')
        self.assertIsInstance(response.context['form'], ReviewApplicantForm)
        self.assertTrue(response.context['is_new_user']) # Email "parsed.email@example.com" is new
        form_initial = response.context['form'].initial
        self.assertEqual(form_initial['full_name'], self.sample_parsed_data['full_name'])
        self.assertEqual(form_initial['email'], self.sample_parsed_data['contact_info']['email'])
        self.assertEqual(form_initial['tags_edit'], "Parsing, Testing, Python")

    def test_review_page_loads_with_session_data_existing_user(self):
        session_data_existing = self.sample_session_data_base.copy()
        session_data_existing["parsed_data"] = self.sample_parsed_data.copy()
        session_data_existing["parsed_data"]["contact_info"] = {"email": self.existing_user.email} # Use existing user's email
        
        session = self.client.session
        session['application_review_data'] = session_data_existing
        session.save()

        response = self.client.get(self.review_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_new_user']) # Should detect existing user
        self.assertEqual(response.context['form'].initial['email'], self.existing_user.email)
        # Verify "Forgot Password?" link for existing user
        self.assertContains(response, reverse('django_career_app:password_reset_request'))
        self.assertContains(response, "Forgot Password?")

    def test_review_page_redirects_if_no_session_data(self):
        response = self.client.get(self.review_url)
        self.assertRedirects(response, self.home_url) # Check for redirect to career_home

    # RFT: def test_review_submit_new_user_success(self):
    # RFT:     session = self.client.session
    # RFT:     session['application_review_data'] = self.sample_session_data_base
    # RFT:     session['is_new_user_for_review'] = True # Set by GET request
    # RFT:     session.save()
    # RFT: 
    # RFT:     post_data = {
    # RFT:         'full_name': 'Final New User', 'email': 'final.new.user@example.com',
    # RFT:         'phone_number': '111000111', 'linkedin_profile': 'linkedin.com/in/finalnew',
    # RFT:         'current_title': 'Final Title', 'latest_work_organization': 'Final Org',
    # RFT:         'latest_degree': 'Final Degree', 'school': 'Final School', 'major': 'Final Major',
    # RFT:         'graduate_year': 2023, 'tags_edit': 'Final, Tag',
    # RFT:         'password': 'newpassword123', 'password_confirmation': 'newpassword123'
    # RFT:     }
    # RFT:     
    # RFT:     response = self.client.post(self.review_url, data=post_data, follow=True)
    # RFT:     self.assertRedirects(response, self.home_url)
    # RFT:     self.assertTrue(User.objects.filter(email='final.new.user@example.com').exists())
    # RFT:     new_user = User.objects.get(email='final.new.user@example.com')
    # RFT:     self.assertTrue(new_user.is_active) # User should be active
    # RFT:     # Check if user is logged in (more complex, check _auth_user_id in session if needed, or response context)
    # RFT:     # self.assertTrue(response.context['user'].is_authenticated) -> only if follow=False and checking context of final page
    # RFT: 
    # RFT:     applicant = Applicant.objects.get(pk=self.temp_applicant_pk)
    # RFT:     self.assertEqual(applicant.user, new_user)
    # RFT:     self.assertEqual(applicant.full_name, 'Final New User')
    # RFT:     self.assertEqual(applicant.tags.count(), 2)
    # RFT:     self.assertTrue(applicant.tags.filter(name='Final').exists())
    # RFT: 
    # RFT:     self.assertTrue(Application.objects.filter(user=new_user, job_posting=self.job_posting).exists())
    # RFT:     application = Application.objects.get(user=new_user)
    # RFT:     self.assertEqual(application.ai_score, self.sample_session_data_base['ai_score'])
    # RFT:     self.assertNotIn('application_review_data', self.client.session)

    # RFT: def test_review_submit_existing_user_success(self):
    # RFT:     session_data_existing = self.sample_session_data_base.copy()
    # RFT:     session_data_existing["parsed_data"] = self.sample_parsed_data.copy()
    # RFT:     session_data_existing["parsed_data"]["contact_info"]["email"] = self.existing_user.email 
    # RFT:     
    # RFT:     session = self.client.session
    # RFT:     session['application_review_data'] = session_data_existing
    # RFT:     session['is_new_user_for_review'] = False
    # RFT:     session.save()
    # RFT: 
    # RFT:     post_data = {
    # RFT:         'full_name': 'Existing User Updated', 'email': self.existing_user.email,
    # RFT:         'latest_work_organization': 'Updated Org', 'tags_edit': 'Updated, Tag',
    # RFT:         'password': self.existing_user_password, # Correct password for existing user
    # RFT:     }
    # RFT:     initial_user_count = User.objects.count()
    # RFT: 
    # RFT:     response = self.client.post(self.review_url, data=post_data, follow=True)
    # RFT:     self.assertRedirects(response, self.home_url)
    # RFT:     self.assertEqual(User.objects.count(), initial_user_count) # No new user
    # RFT: 
    # RFT:     applicant = Applicant.objects.get(pk=self.temp_applicant_pk)
    # RFT:     self.assertEqual(applicant.user, self.existing_user)
    # RFT:     self.assertEqual(applicant.full_name, 'Existing User Updated')
    # RFT:     self.assertEqual(applicant.latest_work_organization, 'Updated Org')
    # RFT:     self.assertTrue(applicant.tags.filter(name='Updated').exists())
    # RFT:     
    # RFT:     self.assertTrue(Application.objects.filter(user=self.existing_user, job_posting=self.job_posting).exists())
    # RFT:     self.assertNotIn('application_review_data', self.client.session)

    def test_review_submit_existing_user_incorrect_password(self):
        session_data_existing = self.sample_session_data_base.copy()
        session_data_existing["parsed_data"]["contact_info"]["email"] = self.existing_user.email
        
        session = self.client.session
        session['application_review_data'] = session_data_existing
        session['is_new_user_for_review'] = False
        session.save()

        post_data = {'full_name': 'Existing User Fail', 'email': self.existing_user.email, 'password': 'wrongpassword'}
        response = self.client.post(self.review_url, data=post_data)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('password', response.context['form'].errors)
        self.assertIn("Incorrect password", response.context['form'].errors['password'][0])
        self.assertTrue(Application.objects.filter(user=self.existing_user).count() == 0)
        self.assertIn('application_review_data', self.client.session) # Session data not cleared

    def test_review_submit_existing_user_missing_password(self):
        session_data_existing = self.sample_session_data_base.copy()
        session_data_existing["parsed_data"]["contact_info"]["email"] = self.existing_user.email

        session = self.client.session
        session['application_review_data'] = session_data_existing
        session['is_new_user_for_review'] = False
        session.save()

        post_data = {'full_name': 'Existing User No Pass', 'email': self.existing_user.email} # Missing password
        response = self.client.post(self.review_url, data=post_data)

        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('password', response.context['form'].errors)
        self.assertIn("Please enter your current password", response.context['form'].errors['password'][0])
        self.assertTrue(Application.objects.filter(user=self.existing_user).count() == 0)
        self.assertIn('application_review_data', self.client.session)

    def test_review_submit_new_user_password_mismatch(self):
        session = self.client.session
        session['application_review_data'] = self.sample_session_data_base # Uses new email by default
        session['is_new_user_for_review'] = True
        session.save()

        post_data = {'full_name': 'New User Mismatch', 'email': 'new.mismatch@example.com', 
                     'password': 'password1', 'password_confirmation': 'password2'}
        response = self.client.post(self.review_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('password_confirmation', response.context['form'].errors)
        self.assertIn("Passwords do not match", response.context['form'].errors['password_confirmation'][0])
        self.assertEqual(User.objects.filter(email='new.mismatch@example.com').count(), 0)

    def test_review_submit_new_user_missing_password(self): # When form initially thinks it's new user
        session = self.client.session
        session['application_review_data'] = self.sample_session_data_base 
        session['is_new_user_for_review'] = True # Form requires password
        session.save()

        post_data = {'full_name': 'New User No Pass', 'email': 'new.nopass@example.com'}
        response = self.client.post(self.review_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertIn('password', response.context['form'].errors) # Form itself should make it required
        self.assertEqual(User.objects.filter(email='new.nopass@example.com').count(), 0)
        
    def test_review_submit_missing_session_data(self):
        # No session data set
        response = self.client.post(self.review_url, data={'full_name': 'No Session User'})
        self.assertRedirects(response, reverse('django_career_app:career_home')) # Corrected redirect
        # Check for messages if possible, or just the redirect
        # For more robust message checking, you might need to inspect the response of the redirected page.
        # For now, redirect is the primary check.

    def test_review_submit_form_invalid_data(self): # e.g. invalid email format
        session = self.client.session
        session['application_review_data'] = self.sample_session_data_base
        session['is_new_user_for_review'] = True 
        session.save()

        post_data = {'full_name': 'Valid Name', 'email': 'notanemail', 'password': 'pw', 'password_confirmation': 'pw'}
        response = self.client.post(self.review_url, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertTrue(response.context['form'].errors)
        self.assertIn('email', response.context['form'].errors)
        # self.assertEqual(User.objects.count(), 1) # Only the self.existing_user from setUp (and a temp one in ApplicantModelTest)
        # This assertion is tricky due to users created in other test classes. Better to check specific user creation.
        self.assertFalse(User.objects.filter(email='notanemail').exists())


# --- Auth Templates Tests ---
class AuthTemplatesTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a user to ensure some views resolve correctly if they implicitly need a user (though most auth views don't for GET)
        # self.user = User.objects.create_user(username='auth_test_user', email='auth@example.com', password='password')

    def test_login_page_uses_custom_template(self):
        response = self.client.get(reverse('django_career_app:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h2>Log In</h2>") 
        self.assertContains(response, "Forgot password?") # Check for the link on the login page too

    # RFT: def test_password_reset_request_page_uses_custom_template(self):
    # RFT:     response = self.client.get(reverse('django_career_app:password_reset_request'))
    # RFT:     self.assertEqual(response.status_code, 200)
    # RFT:     self.assertContains(response, "<h2>Forgot Your Password?</h2>")

    # RFT: def test_password_reset_done_page_uses_custom_template(self):
    # RFT:     response = self.client.get(reverse('django_career_app:password_reset_done'))
    # RFT:     self.assertEqual(response.status_code, 200)
    # RFT:     self.assertContains(response, "<h2>Password Reset Email Sent</h2>")

    def test_password_reset_confirm_page_invalid_link_uses_custom_template(self):
        # Test the "invalid link" state of the confirm page
        response = self.client.get(reverse('django_career_app:password_reset_confirm', args=['invalid_uid', 'invalid_token']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The password reset link was invalid")

    # RFT: def test_password_reset_complete_page_uses_custom_template(self):
    # RFT:     response = self.client.get(reverse('django_career_app:password_reset_complete'))
    # RFT:     self.assertEqual(response.status_code, 200)
    # RFT:     self.assertContains(response, "<h2>Password Reset Complete</h2>")


    # RFT: def test_review_user_changes_email_from_new_to_existing(self):
    # RFT:     # Initial state: session thinks it's a new user because form/LLM email was new
    # RFT:     session_data_initially_new = self.sample_session_data_base.copy()
    # RFT:     session_data_initially_new["parsed_data"] = self.sample_parsed_data.copy()
    # RFT:     session_data_initially_new["parsed_data"]["contact_info"] = {"email": "originally.new@example.com"}
    # RFT:     # session_data_initially_new["form_email"] = "originally.new@example.com" # form_email not used by view directly
    # RFT: 
    # RFT:     session = self.client.session
    # RFT:     session['application_review_data'] = session_data_initially_new
    # RFT:     session['is_new_user_for_review'] = True # View's GET determined it was new
    # RFT:     session.save()
    # RFT: 
    # RFT:     # User edits email on review page to an existing user's email, and provides correct password for existing user
    # RFT:     post_data = {
    # RFT:         'full_name': 'Changed to Existing', 
    # RFT:         'email': self.existing_user.email, # Changed to existing user's email
    # RFT:         'password': self.existing_user_password, # Provides password for existing user
    # RFT:         # other fields...
    # RFT:         'tags_edit': 'changed, existing'
    # RFT:     }
    # RFT:     initial_user_count = User.objects.count()
    # RFT: 
    # RFT:     response = self.client.post(self.review_url, data=post_data, follow=True)
    # RFT:     self.assertRedirects(response, reverse('django_career_app:application_thank_you')) # Corrected redirect
    # RFT:     self.assertEqual(User.objects.count(), initial_user_count) # No new user created
    # RFT: 
    # RFT:     # Since temp_applicant is associated with the user, we might need to re-fetch or check if it's updated
    # RFT:     # This depends on whether the view updates the temp_applicant or creates a new one for the existing user.
    # RFT:     # Based on current view logic, it updates the existing_applicant_profile if found, or finalizes temp_applicant.
    # RFT:     # Let's assume it finds an existing profile and updates it.
    # RFT:     # If no profile exists for existing_user, it would link temp_applicant.
    # RFT:     
    # RFT:     # If the existing_user already had an Applicant profile, that would be updated.
    # RFT:     # If not, the temp_applicant (self.temp_applicant) gets linked and updated.
    # RFT:     updated_applicant = Applicant.objects.get(user=self.existing_user) # Should be the one linked or updated
    # RFT:     self.assertEqual(updated_applicant.full_name, 'Changed to Existing')
    # RFT:     self.assertTrue(Application.objects.filter(user=self.existing_user, job_posting=self.job_posting).exists())
    # RFT:     self.assertNotIn('application_review_data', self.client.session)


    # RFT: def test_review_user_changes_email_from_existing_to_new(self):
    # RFT:     # Initial state: session thinks it's an existing user
    # RFT:     session_data_initially_existing = self.sample_session_data_base.copy()
    # RFT:     session_data_initially_existing["parsed_data"] = self.sample_parsed_data.copy()
    # RFT:     session_data_initially_existing["parsed_data"]["contact_info"] = {"email": self.existing_user.email}
    # RFT:     # session_data_initially_existing["form_email"] = self.existing_user.email
    # RFT: 
    # RFT:     session = self.client.session
    # RFT:     session['application_review_data'] = session_data_initially_existing
    # RFT:     session['is_new_user_for_review'] = False # View's GET determined it was existing
    # RFT:     session.save()
    # RFT: 
    # RFT:     # User edits email on review page to a new email, and provides new password + confirmation
    # RFT:     new_email_on_review = "new.on.review@example.com"
    # RFT:     post_data = {
    # RFT:         'full_name': 'Changed to New', 
    # RFT:         'email': new_email_on_review,
    # RFT:         'password': 'newpass123', 
    # RFT:         'password_confirmation': 'newpass123',
    # RFT:          # other fields...
    # RFT:         'tags_edit': 'changed, new'
    # RFT:     }
    # RFT:     
    # RFT:     response = self.client.post(self.review_url, data=post_data, follow=True)
    # RFT:     self.assertRedirects(response, reverse('django_career_app:application_thank_you')) # Corrected redirect
    # RFT:     
    # RFT:     self.assertTrue(User.objects.filter(email=new_email_on_review).exists())
    # RFT:     newly_created_user = User.objects.get(email=new_email_on_review)
    # RFT: 
    # RFT:     # The temp_applicant (self.temp_applicant) should be updated and linked to the new user
    # RFT:     updated_applicant = Applicant.objects.get(pk=self.temp_applicant_pk)
    # RFT:     self.assertEqual(updated_applicant.user, newly_created_user)
    # RFT:     self.assertEqual(updated_applicant.full_name, 'Changed to New')
    # RFT:     self.assertTrue(Application.objects.filter(user=newly_created_user, job_posting=self.job_posting).exists())
    # RFT:     self.assertNotIn('application_review_data', self.client.session)

    # RFT: def test_review_user_changes_email_from_new_to_new_different_email(self):
    # RFT:     # Initial state: session thinks it's a new user 
    # RFT:     session_data_initially_new = self.sample_session_data_base.copy()
    # RFT:     session_data_initially_new["parsed_data"]["contact_info"]["email"] = "original.new.email@example.com"
    # RFT:     # session_data_initially_new["form_email"] = "original.new.email@example.com"
    # RFT:     
    # RFT:     session = self.client.session
    # RFT:     session['application_review_data'] = session_data_initially_new
    # RFT:     session['is_new_user_for_review'] = True
    # RFT:     session.save()
    # RFT: 
    # RFT:     # User edits email on review page to another new email
    # RFT:     another_new_email = "another.new.email@example.com"
    # RFT:     post_data = {
    # RFT:         'full_name': 'Another New User', 
    # RFT:         'email': another_new_email,
    # RFT:         'password': 'newpass123', 
    # RFT:         'password_confirmation': 'newpass123',
    # RFT:         'tags_edit': 'another, new'
    # RFT:     }
    # RFT:     
    # RFT:     response = self.client.post(self.review_url, data=post_data, follow=True)
    # RFT:     self.assertRedirects(response, reverse('django_career_app:application_thank_you')) # Corrected redirect
    # RFT:     
    # RFT:     self.assertTrue(User.objects.filter(email=another_new_email).exists())
    # RFT:     newly_created_user = User.objects.get(email=another_new_email)
    # RFT: 
    # RFT:     # The temp_applicant (self.temp_applicant) should be updated and linked to the new user
    # RFT:     updated_applicant = Applicant.objects.get(pk=self.temp_applicant_pk)
    # RFT:     self.assertEqual(updated_applicant.user, newly_created_user)
    # RFT:     self.assertEqual(updated_applicant.full_name, 'Another New User')
    # RFT:     self.assertTrue(Application.objects.filter(user=newly_created_user, job_posting=self.job_posting).exists())
    # RFT:     self.assertNotIn('application_review_data', self.client.session)

# --- ApplicantFormTests (New) ---
class ApplicantFormTests(TestCase):
    def test_valid_resume_pdf(self):
        pdf_content = b"%PDF-1.4\n%%EOF" # Minimal PDF content
        resume_file = SimpleUploadedFile("valid_resume.pdf", pdf_content, content_type="application/pdf")
        form_data = {} # No other fields in this form
        file_data = {'resume_pdf': resume_file}
        form = ApplicantForm(data=form_data, files=file_data)
        self.assertTrue(form.is_valid())

    def test_invalid_file_type(self):
        txt_content = b"This is a text file."
        resume_file = SimpleUploadedFile("invalid_resume.txt", txt_content, content_type="text/plain")
        form_data = {}
        file_data = {'resume_pdf': resume_file}
        form = ApplicantForm(data=form_data, files=file_data)
        self.assertFalse(form.is_valid())
        self.assertIn('resume_pdf', form.errors)
        self.assertIn("File is not a PDF.", form.errors['resume_pdf'][0])

    # RFT: def test_file_too_large(self):
    # RFT:     pdf_content = b"%PDF-1.4\n%%EOF" * (2 * 1024 * 1024 // 15 + 100) # Make it slightly over 2MB
    # RFT:     resume_file = SimpleUploadedFile("large_resume.pdf", pdf_content, content_type="application/pdf")
    # RFT:     form_data = {}
    # RFT:     file_data = {'resume_pdf': resume_file}
    # RFT:     form = ApplicantForm(data=form_data, files=file_data)
    # RFT:     self.assertFalse(form.is_valid())
    # RFT:     self.assertIn('resume_pdf', form.errors)
    # RFT:     self.assertIn("Resume file size cannot exceed 2MB.", form.errors['resume_pdf'][0])

    def test_missing_resume_file(self): # Check if field is required
        form = ApplicantForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('resume_pdf', form.errors)
        self.assertEqual(form.errors['resume_pdf'], ['This field is required.'])


# --- AdminViewsTests (New) ---
class AdminViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff_user = _create_user("staff_user", email="staff@example.com", is_staff=True)
        cls.non_staff_user = _create_user("normal_user", email="user@example.com")

        cls.job_posting1 = JobPosting.objects.create(title="Admin Job 1", description="Desc1", location="Loc1", date_posted=timezone.now() - timedelta(days=1))
        cls.job_posting2 = JobPosting.objects.create(title="Admin Job 2", description="Desc2", location="Loc2", date_posted=timezone.now())

        # Applicant 1 for Job 1
        cls.applicant1_user = _create_user("app1_user", email="app1@example.com")
        cls.applicant1 = Applicant.objects.create(
            user=cls.applicant1_user, 
            full_name="Applicant One", 
            email="app1@example.com",
            resume_pdf=SimpleUploadedFile("resume1.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf"),
            resume_markdown="## Applicant One\n- Skill A"
        )
        cls.app1_job1 = Application.objects.create(
            user=cls.applicant1_user, 
            job_posting=cls.job_posting1, 
            ai_score=90.0, 
            application_date=timezone.now() - timedelta(hours=2)
        )

        # Applicant 2 for Job 1
        cls.applicant2_user = _create_user("app2_user", email="app2@example.com")
        cls.applicant2 = Applicant.objects.create(
            user=cls.applicant2_user, 
            full_name="Applicant Two", 
            email="app2@example.com",
            # No resume_pdf for this one
            resume_markdown="## Applicant Two\n- Skill B"
        )
        cls.app2_job1 = Application.objects.create(
            user=cls.applicant2_user, 
            job_posting=cls.job_posting1, 
            ai_score=80.0, 
            application_date=timezone.now() - timedelta(hours=1) # More recent than app1
        )
        
        # Applicant 3 for Job 2 (no applications yet for this job from this applicant)
        cls.applicant3_user = _create_user("app3_user", email="app3@example.com")
        cls.applicant3 = Applicant.objects.create(
            user=cls.applicant3_user,
            full_name="Applicant Three",
            email="app3@example.com",
            resume_pdf=SimpleUploadedFile("resume3.pdf", b"dummy pdf content", content_type="application/pdf")
        )
        # No application for applicant3 yet, to test candidate list for job with no candidates if needed

        cls.admin_job_list_url = reverse('django_career_app:admin_job_list')
        cls.admin_candidate_list_url_job1 = reverse('django_career_app:admin_candidate_list', args=[cls.job_posting1.pk])
        cls.download_resume_url_app1 = reverse('django_career_app:download_resume', args=[cls.applicant1.pk])

    def test_admin_job_list_staff_access(self):
        self.client.login(username="staff_user", password="password")
        response = self.client.get(self.admin_job_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.job_posting1.title)
        self.assertContains(response, self.job_posting2.title)
        self.assertIn(self.job_posting2, response.context['job_postings']) # job_posting2 is newer

    # RFT: def test_admin_job_list_non_staff_access(self):
    # RFT:     self.client.login(username="normal_user", password="password")
    # RFT:     response = self.client.get(self.admin_job_list_url)
    # RFT:     self.assertRedirects(response, f"{reverse('django_career_app:login')}?next={self.admin_job_list_url}")

    def test_admin_candidate_list_staff_access(self):
        self.client.login(username="staff_user", password="password")
        response = self.client.get(self.admin_candidate_list_url_job1)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.job_posting1.title)
        self.assertContains(response, self.applicant1.full_name)
        self.assertContains(response, self.applicant2.full_name)
        self.assertEqual(len(response.context['applications']), 2)

    # RFT: def test_admin_candidate_list_non_staff_access(self):
    # RFT:     self.client.login(username="normal_user", password="password")
    # RFT:     response = self.client.get(self.admin_candidate_list_url_job1)
    # RFT:     self.assertRedirects(response, f"{reverse('django_career_app:login')}?next={self.admin_candidate_list_url_job1}")

    def test_admin_candidate_list_ordering_ai_score_desc(self):
        self.client.login(username="staff_user", password="password")
        response = self.client.get(self.admin_candidate_list_url_job1 + "?order_by=-ai_score")
        self.assertEqual(response.status_code, 200)
        applications_in_context = list(response.context['applications'])
        self.assertEqual(applications_in_context[0].user, self.applicant1_user) # AI Score 90.0
        self.assertEqual(applications_in_context[1].user, self.applicant2_user) # AI Score 80.0
    
    def test_admin_candidate_list_ordering_application_date_asc(self):
        self.client.login(username="staff_user", password="password")
        response = self.client.get(self.admin_candidate_list_url_job1 + "?order_by=application_date")
        self.assertEqual(response.status_code, 200)
        applications_in_context = list(response.context['applications'])
        self.assertEqual(applications_in_context[0].user, self.applicant1_user) # Older application
        self.assertEqual(applications_in_context[1].user, self.applicant2_user) # Newer application

    # RFT: def test_download_resume_staff_access_with_resume(self):
    # RFT:     self.client.login(username="staff_user", password="password")
    # RFT:     response = self.client.get(self.download_resume_url_app1)
    # RFT:     self.assertEqual(response.status_code, 200)
    # RFT:     self.assertEqual(response['Content-Type'], 'application/pdf')
    # RFT:     self.assertTrue(response['Content-Disposition'].startswith('attachment; filename="'))
    # RFT:     self.assertIn("resume1.pdf", response['Content-Disposition'])

    # RFT: def test_download_resume_non_staff_access(self):
    # RFT:     self.client.login(username="normal_user", password="password")
    # RFT:     response = self.client.get(self.download_resume_url_app1)
    # RFT:     self.assertRedirects(response, f"{reverse('django_career_app:login')}?next={self.download_resume_url_app1}")

    def test_download_resume_applicant_no_resume(self):
        self.client.login(username="staff_user", password="password")
        # Applicant2 has no resume_pdf
        url_no_resume = reverse('django_career_app:download_resume', args=[self.applicant2.pk])
        response = self.client.get(url_no_resume)
        self.assertEqual(response.status_code, 404)

    def test_download_resume_non_existent_applicant(self):
        self.client.login(username="staff_user", password="password")
        url_non_existent = reverse('django_career_app:download_resume', args=[9999]) # Assuming 9999 is not a valid PK
        response = self.client.get(url_non_existent)
        self.assertEqual(response.status_code, 404)


# --- MarkdownTemplateTagTests (New) ---
class MarkdownTemplateTagTests(TestCase):
    def test_markdown_to_html_basic(self):
        markdown_input = "# Hello"
        expected_html = "<h1>Hello</h1>"
        # The filter function itself returns SafeText, direct comparison might be tricky
        # Let's compare string representations
        self.assertEqual(str(markdown_to_html(markdown_input)).strip(), expected_html)

    def test_markdown_to_html_none_input(self):
        self.assertEqual(markdown_to_html(None), "")

    # RFT: def test_markdown_to_html_empty_string_input(self):
    # RFT:     self.assertEqual(markdown_to_html(""), "")

    # RFT: def test_markdown_to_html_fenced_code(self):
    # RFT:     markdown_input = "```python\nprint('Hello')\n```"
    # RFT:     # Exact HTML can vary with library versions, check for key elements
    # RFT:     html_output = str(markdown_to_html(markdown_input))
    # RFT:     self.assertIn("<pre><code class=\"python\">print(&#39;Hello&#39;)", html_output) # Check for pre, code, and class
    # RFT:     self.assertIn("</code></pre>", html_output)

# --- UtilsTests (New) ---
class UtilsTests(TestCase):
    pass
    # RFT: @patch('career_portal.django_career_app.utils.extract_text_from_pdf')
    # RFT: def test_convert_pdf_to_markdown_formatting(self, mock_extract_text):
    # RFT:     # Predefined text with various elements
    # RFT:     raw_text_from_pdf = (
    # RFT:         "This is a paragraph.\n\n"  # Double newline should result in paragraph break
    # RFT:         "This is another line in the same paragraph.\n" # Single newline, should merge or be handled
    # RFT:         "Another paragraph started after blank line.\n\n\n" # Triple newline
    # RFT:         "* List item 1\n"
    # RFT:         "- List item 2\n"
    # RFT:         "  * Nested item (might not be specially formatted by basic regex)\n"
    # RFT:         "1. Numbered item 1\n"
    # RFT:         "Some text after list.\n\n"
    # RFT:         "Final paragraph."
    # RFT:     )
    # RFT:     mock_extract_text.return_value = raw_text_from_pdf
    # RFT:     
    # RFT:     # Create a dummy file object (BytesIO is good for this)
    # RFT:     dummy_file_obj = BytesIO(b"dummy pdf content")
    # RFT:     
    # RFT:     markdown_output = convert_pdf_to_markdown(dummy_file_obj)
    # RFT:     
    # RFT:     # Assertions
    # RFT:     mock_extract_text.assert_called_once_with(dummy_file_obj) # Ensure our mock was called
    # RFT: 
    # RFT:     # Expected: Paragraphs separated by double newlines
    # RFT:     # List items on their own lines.
    # RFT:     # Consecutive non-list lines might be joined or separated based on the implementation.
    # RFT:     # The current implementation joins lines and then adds paragraph breaks for \n{3,}
    # RFT:     
    # RFT:     expected_lines = [
    # RFT:         "This is a paragraph.", # First paragraph
    # RFT:         "This is another line in the same paragraph.", # Should be part of the first paragraph if joining happens first
    # RFT:         "Another paragraph started after blank line.", # Second paragraph
    # RFT:         "", # Expected blank line after re.sub for \n{3,}
    # RFT:         "* List item 1",
    # RFT:         "- List item 2",
    # RFT:         "* Nested item (might not be specially formatted by basic regex)", # Current regex doesn't handle nested
    # RFT:         "1. Numbered item 1",
    # RFT:         "Some text after list.", # Should be a new paragraph
    # RFT:         "",
    # RFT:         "Final paragraph."
    # RFT:     ]
    # RFT:     
    # RFT:     # Normalize newlines in output for comparison
    # RFT:     output_lines = [line.strip() for line in markdown_output.replace('\r\n', '\n').split('\n')]
    # RFT:     
    # RFT:     # This is a bit simplistic, actual output depends heavily on the regex logic in convert_pdf_to_markdown
    # RFT:     # Let's check for key characteristics:
    # RFT:     self.assertIn("This is a paragraph.\nThis is another line in the same paragraph.", markdown_output) # Assuming lines are joined
    # RFT:     self.assertIn("Another paragraph started after blank line.", markdown_output)
    # RFT:     self.assertIn("\n\n* List item 1", markdown_output) # Check paragraph break before list
    # RFT:     self.assertIn("* List item 1\n- List item 2", markdown_output)
    # RFT:     self.assertIn("1. Numbered item 1\n\nSome text after list.", markdown_output) # Check paragraph break after list item if 'Some text' is new para
    # RFT:     self.assertIn("Some text after list.\n\nFinal paragraph.", markdown_output)
    # RFT: 
    # RFT:     # Check that triple newlines became double newlines (paragraph breaks)
    # RFT:     self.assertNotIn("\n\n\n\n", markdown_output, "Should not have more than two consecutive newlines for paragraph breaks")
    # RFT:     self.assertTrue(markdown_output.count("Another paragraph started after blank line.\n\n* List item 1") >= 0 or \
    # RFT:                     markdown_output.count("Another paragraph started after blank line.\n\n\n* List item 1") ==0 ) # Flexible check for newlines

    # RFT: @patch('career_portal.django_career_app.utils.extract_text_from_pdf')
    # RFT: def test_convert_pdf_to_markdown_empty_text(self, mock_extract_text):
    # RFT:     mock_extract_text.return_value = ""
    # RFT:     dummy_file_obj = BytesIO(b"")
    # RFT:     markdown_output = convert_pdf_to_markdown(dummy_file_obj)
    # RFT:     self.assertEqual(markdown_output, "")

    # RFT: @patch('career_portal.django_career_app.utils.extract_text_from_pdf')
    # RFT: def test_convert_pdf_to_markdown_extraction_exception(self, mock_extract_text):
    # RFT:     mock_extract_text.side_effect = Exception("PDF Miner Error")
    # RFT:     dummy_file_obj = BytesIO(b"")
    # RFT:     markdown_output = convert_pdf_to_markdown(dummy_file_obj)
    # RFT:     self.assertEqual(markdown_output, "") # Should return empty string on error
