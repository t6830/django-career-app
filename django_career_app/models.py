from django.db import models
from django.contrib.auth.models import User
# from django.db.models import JSONField # Removed as no longer used after removing parsed_resume_raw
from django.conf import settings
from django.core.files.storage import storages

def select_storage():
    if "django_career_app" in settings.STORAGES:
        return storages["django_career_app"]
    return storages["default"]

class CompanyProfile(models.Model):
    """
    Stores the company's general description or profile information.
    This is typically a singleton model or used to display 'About Us' type content.
    """
    description = models.TextField(help_text="A general description of the company. Use Markdown for formatting.")

    def __str__(self):
        return f"Company Profile (ID: {self.id})"

class JobPosting(models.Model):
    """
    Stores details about a specific job opening offered by the company.
    Includes information like title, description, location, and status.
    """
    title = models.CharField(max_length=255, help_text="The title of the job posting (e.g., Software Engineer).")
    description = models.TextField(help_text="Detailed description of the job, responsibilities, and qualifications. Use Markdown for formatting.")
    location = models.CharField(max_length=255, help_text="Location of the job (e.g., City, State, Remote).")
    department = models.CharField(max_length=255, blank=True, null=True, help_text="Department offering the job (e.g., Engineering, Marketing).")
    is_active = models.BooleanField(default=True, help_text="Indicates if the job posting is currently active and accepting applications.")
    date_posted = models.DateTimeField(auto_now_add=True, help_text="Date when the job posting was created.")
    deadline = models.DateTimeField(blank=True, null=True, help_text="Optional deadline for applications.")

    def __str__(self):
        return self.title

class JobRequirement(models.Model):
    """
    Stores specific requirements and their weights for a job posting.
    These are used by the AI to score applicant resumes against the job.
    """
    job_posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='requirements', help_text="The job posting these requirements belong to.")
    name = models.CharField(max_length=255, help_text="Name of the requirement (e.g., Python, Communication Skills).")
    weight = models.FloatField(help_text="Weight of this requirement for scoring (e.g., 0.0 to 1.0).")

    def __str__(self):
        return f"{self.name} for {self.job_posting.title}"

class Applicant(models.Model):
    """
    Stores information about an individual job seeker (candidate profile).
    Includes their contact details, resume, parsed profile data, and a link to their User account.
    This model represents the candidate's overall profile, not a specific application.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, help_text="Links to the Django User model for authentication and profile management.")
    phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Contact phone number of the applicant.")
    linkedin_profile = models.URLField(blank=True, null=True, help_text="URL to the applicant's LinkedIn profile.")
    resume_pdf = models.FileField(upload_to='resumes/', storage=select_storage, null=True, blank=True, help_text="Stores the applicant's resume file (PDF format preferred).")
    resume_markdown = models.TextField(blank=True, null=True, help_text="The applicant's resume content in Markdown format.")
    
    # Fields populated from resume parsing or user input during review
    current_title = models.CharField(max_length=255, blank=True, null=True, help_text="Applicant's current or most recent job title.")
    latest_work_organization = models.CharField(max_length=255, blank=True, null=True, help_text="Applicant's current or most recent company/organization.")
    latest_degree = models.CharField(max_length=255, blank=True, null=True, help_text="Applicant's latest educational degree.")
    school = models.CharField(max_length=255, blank=True, null=True, help_text="School or university for the latest degree.")
    major = models.CharField(max_length=255, blank=True, null=True, help_text="Major or field of study for the latest degree.")
    graduate_year = models.IntegerField(blank=True, null=True, help_text="Year of graduation for the latest degree.")
    
    tags = models.ManyToManyField('Tag', blank=True, help_text="Tags associated with the applicant, like skills or keywords.")

    # Removed fields (kept as comments for historical context if needed by developer, but should be removed eventually):
    # job_posting = models.ForeignKey(JobPosting, on_delete=models.PROTECT)
    # submission_date = models.DateTimeField(auto_now_add=True)
    # years_experience = models.FloatField(null=True, blank=True)
    # parsed_resume_raw = models.JSONField(null=True, blank=True)
    # ai_score = models.FloatField(null=True, blank=True)

    def __str__(self):
        if self.user:
            return f"{self.user.first_name} {self.user.last_name} - {self.user.email}"
        return f"Applicant Profile (ID: {self.id})"

class Tag(models.Model):
    """
    Stores unique, AI-generated or user-provided tags to categorize applicants
    or highlight skills, achievements, etc. Tag names are normalized to lowercase.
    """
    name = models.CharField(max_length=100, unique=True, help_text="The name of the tag (e.g., 'python', 'project management'). Normalized to lowercase.")

    def save(self, *args, **kwargs):
        """
        Overrides the default save method to normalize the tag name
        to lowercase before saving. This ensures uniqueness and consistency
        regardless of the case used during input.
        """
        self.name = self.name.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Application(models.Model):
    """
    Represents a specific application made by a User for a JobPosting.
    It links a user (via their Applicant profile's User link) and a job,
    and stores the AI-calculated score for that particular application context.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, help_text="The user who submitted this application.")
    job_posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, help_text="The job posting this application is for.")
    ai_score = models.FloatField(null=True, blank=True, help_text="AI-calculated score for this specific application, based on resume fit to job description and requirements.")
    application_date = models.DateTimeField(auto_now_add=True, help_text="Timestamp of when the application was submitted.")

    def __str__(self):
        return f"Application for {self.user.username if self.user else 'Unknown User'} to {self.job_posting.title if self.job_posting else 'Unknown Job'}"
