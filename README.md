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

To get this application up and running, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd django-career-app
    ```
2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Configure Environment Variables:**
    *   This project uses a `.env` file to manage environment-specific settings.
    *   Copy the example file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and update the following variables with your specific settings:
        *   `GEMINI_API_KEY`: Your API key for the Gemini LLM (or other LLM provider if configured).
        *   `SECRET_KEY`: Your Django secret key. Generate a new one for production.
        *   `DEBUG`: Set to `True` for development, `False` for production.
        *   `DATABASE_URL`: (Optional) If you are using a database other than the default SQLite, configure its URL here (e.g., `postgres://user:password@host:port/dbname`).
    *   **Note:** The `.env` file is included in `.gitignore` and should not be committed to your repository.

4.  **Install dependencies:**
    This project uses a `requirements.txt` file to manage its dependencies.
    ```bash
    pip install -r requirements.txt
    ```
    *Note: If `requirements.txt` does not exist, you may need to create it based on the project's imports or Django version.*

4.  **Apply database migrations:**
    ```bash
    python manage.py migrate
    ```
5.  **Create a superuser (optional, for admin access):**
    ```bash
    python manage.py createsuperuser
    ```

## Usage

Once the installation is complete, you can run the Django development server:

```bash
python manage.py runserver
```

The application will typically be accessible at `http://127.0.0.1:8000/` in your web browser.

## Integrating as a Django App

This section details how to integrate the `careers` app into your existing Django project.

1.  **Copy App Directory:**
    -   Copy the `careers` directory (located at `career_portal/careers` in this repository) into your existing Django project. A common location is the root of your project, alongside other apps.

2.  **Add to INSTALLED_APPS:**
    -   In your existing project's `settings.py` file, add `'careers.apps.CareersConfig'` to the `INSTALLED_APPS` list.
        ```python
        INSTALLED_APPS = [
            # ... other apps
            'careers.apps.CareersConfig',
            # ... or 'careers', if you prefer the shorter version
        ]
        ```

3.  **Include App URLs:**
    -   In your existing project's main `urls.py` file (usually located in the project's configuration directory), include the `careers` app's URL patterns.
        ```python
        from django.urls import path, include

        urlpatterns = [
            # ... other project urls
            path('your_desired_path/', include('careers.urls')),
            # Example: path('career-portal/', include('careers.urls')),
        ]
        ```
    -   Make sure to replace `'your_desired_path/'` with the actual URL prefix you want to use for this app (e.g., `careers/`, `jobs/`, etc.).

4.  **Install Dependencies:**
    -   This app's dependencies are listed in `requirements.txt`. Compare this file with your existing project's dependencies.
    -   Install any missing packages, being mindful of potential version conflicts. You might need to adjust versions to ensure compatibility with your project.
        ```bash
        pip install -r requirements.txt # Run this if you've copied requirements.txt to your project
        # Or, install specific packages:
        # pip install Django==4.2.21 # Example, ensure compatibility
        # pip install litellm json-repair # Key dependencies for LLM features
        ```
    -   Key dependencies for this app include Django, `litellm` for LLM interaction, and `json-repair` for handling LLM responses. Review `requirements.txt` carefully.

5.  **Run Database Migrations:**
    -   After adding the app and ensuring dependencies are met, run database migrations:
        ```bash
        python manage.py makemigrations careers
        python manage.py migrate
        ```
    -   The `makemigrations careers` command might not be necessary initially if you are using the migrations already present in the copied `careers/migrations` folder and no model changes have been made. However, it's good practice if you intend to modify the app's models. `migrate` will apply the app's migrations to your database.

6.  **Collect Static Files (If applicable):**
    -   If the `careers` app uses static files (CSS, JavaScript, images) that need to be served by your project, run:
        ```bash
        python manage.py collectstatic
        ```
    - This will gather all static files into the directory specified by `STATIC_ROOT` in your `settings.py`.

*(Note: The "Features (Example)" section from the old README has been removed as it's now replaced by the comprehensive "Features" section above.)*