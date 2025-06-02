from django.urls import path, reverse_lazy # Added reverse_lazy
from django.contrib.auth import views as auth_views # Added for auth views
from .views import (
    CareerHomeView, JobDetailView, ReviewApplicationView, ApplicationThankYouView,
    AdminJobListView, AdminCandidateListView, download_resume # Added Admin views
)

app_name = 'django_career_app'

urlpatterns = [
    path('', CareerHomeView.as_view(), name='career_home'),
    path('job/<int:pk>/', JobDetailView.as_view(), name='job_detail'),
    path('application/review/', ReviewApplicationView.as_view(), name='review_application'),
    path('application/thank-you/', ApplicationThankYouView.as_view(), name='application_thank_you'),

    # Admin views
    path('admin/jobs/', AdminJobListView.as_view(), name='admin_job_list'),
    path('admin/jobs/<int:job_posting_id>/candidates/', AdminCandidateListView.as_view(), name='admin_candidate_list'),
    path('admin/applicant/<int:applicant_id>/resume/download/', download_resume, name='download_resume'),

    # Authentication URLs
    path('login/', 
         auth_views.LoginView.as_view(template_name='registration/login.html'), 
         name='login'),
    path('logout/', 
         auth_views.LogoutView.as_view(next_page=reverse_lazy('django_career_app:career_home')), 
         name='logout'),

    # Password Reset URLs
    path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html', # HTML part of email
             subject_template_name='registration/password_reset_subject.txt',
             success_url=reverse_lazy('django_career_app:password_reset_done')
         ), 
         name='password_reset_request'), # Matches link in review_application_details.html & login.html
    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url=reverse_lazy('django_career_app:password_reset_complete')
         ), 
         name='password_reset_confirm'), # Matches link in password_reset_email.html
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
]
