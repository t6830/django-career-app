# django-career-app

A Django-based platform designed to streamline the job application process for both applicants and recruiters, leveraging AI for resume analysis and scoring.

## Features

*   **Browse Job Postings:** Users can view a list of available job openings, including details like title and location.
*   **Detailed Job View:** Each job posting has a dedicated page showing a full description, requirements, and department (if applicable).
*   **Resume Upload (PDF):** Applicants can easily submit their resume in PDF format.
*   **Automated Resume Parsing:** Utilizes Large Language Models (LLMs) to automatically extract key information from uploaded resumes, including:
    *   Contact details (full name, email, phone, LinkedIn).
    *   Latest education (degree, school, major, graduation year).
    *   Recent work experience (job title, company).
    *   Top achievements and differentiating skills as "tags".
*   **AI-Powered Resume Scoring:** Resumes are automatically scored against the specific job description and its weighted requirements using LLMs, providing an initial assessment of fit.
*   **Two-Step Application Process:**
    1.  **Initial Submission:** Applicant uploads their resume.
    2.  **Review & Finalize:** Applicant reviews the LLM-parsed data and AI score, can edit details, and confirms their application.
*   **User Account Management:**
    *   Automatic user account creation for new applicants using their email.
    *   Links application to existing user accounts if the email is already registered.
    *   Secure password handling for user accounts.
*   **Data Management:** Stores and manages company profiles, job postings, applicant data, and application records.
*   **Secure Application Handling:** Ensures user data and application details are handled securely throughout the process.

## Installation

Install the `django-career-app` package:

```bash
pip install django-career-app
```

## Settings

Add `django_career_app` to your `INSTALLED_APPS` in your project's `settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps
    'django_career_app',
]
```

Configure the following settings in your `settings.py`. You can load these credentials using `python-decouple` or `python-dotenv`.

```python
# Required for LLM features
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY" # Or load from environment variable
LLM_MODEL_NAME = "gemini-pro" # Or your preferred LLM model

# Optional: Configure resume storage backend
# By default, resumes are stored locally.
# To use AWS S3 for resume storage (requires django-storages):
STORAGES = {
    "django_career_app": {
        "BACKEND": "storages.backends.s3.S3Storage",
        # Options are typically derived from environment variables
        # like AWS_STORAGE_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.
        # 'OPTIONS': {
        #     'bucket_name': os.environ.get('AWS_STORAGE_BUCKET_NAME'),
        #     # etc.
        # }
    }
}

# AWS S3 settings (if using S3Storage)
AWS_STORAGE_BUCKET_NAME = "your-s3-bucket-name"
AWS_S3_REGION_NAME = "your-s3-region"
AWS_S3_FILE_OVERWRITE = False # Set to True if you want to overwrite files with the same name

# AWS credentials (if using S3Storage, load from .env or environment variables)
# AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
# AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
```

## Usage

1.  **Include App URLs:**
    In your project's main `urls.py` file, include the `django_career_app`'s URL patterns:

    ```python
    from django.urls import path, include

    urlpatterns = [
        # ... other project urls
        path('career-portal/', include('django_career_app.urls')),
    ]
    ```
    Replace `'career-portal/'` with your desired URL prefix.

2.  **Run Database Migrations:**
    Apply the app's database migrations:

    ```bash
    python manage.py migrate
    ```

3.  **Collect Static Files (If applicable):**
    If the `django_career_app` uses static files (CSS, JavaScript, images) that need to be served by your project, run:

    ```bash
    python manage.py collectstatic
    ```
    This will gather all static files into the directory specified by `STATIC_ROOT` in your `settings.py`.

