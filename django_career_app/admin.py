from django.contrib import admin
from .models import CompanyProfile, JobPosting, JobRequirement, Applicant, Application, Tag # Added Application and Tag

# Inline class for JobRequirement
class JobRequirementInline(admin.TabularInline):
    model = JobRequirement
    extra = 1  # Allows adding one extra requirement by default

# ModelAdmin class for JobPosting
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ('title', 'location', 'department', 'is_active', 'date_posted', 'deadline')
    list_filter = ('is_active', 'department', 'location')
    search_fields = ('title', 'description')
    inlines = [JobRequirementInline]

# ModelAdmin class for Applicant
class ApplicantAdmin(admin.ModelAdmin):
    list_display = ('user_full_name', 'user_email', 'current_title', 'user', 'latest_degree', 'latest_work_organization')

    def user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}" if obj.user else "N/A"
    user_full_name.short_description = 'Full Name'
    user_full_name.admin_order_field = 'user__last_name' # Allows sorting by last name

    def user_email(self, obj):
        return obj.user.email if obj.user else "N/A"
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email' # Allows sorting by email
    list_filter = ('latest_degree', 'user__email', 'latest_work_organization', 'current_title') # Removed submission_date; Added latest_work_organization, current_title
    search_fields = ('user__first_name', 'user__last_name', 'user__email', 'current_title', 'user__username', 'latest_degree', 'school', 'major', 'latest_work_organization')
    readonly_fields = ('resume_pdf', 'current_title', 'latest_degree', 'school', 'major', 'graduate_year', 'latest_work_organization','resume_markdown') # Removed submission_date, years_experience; Added latest_work_organization
    ordering = ['user__last_name', 'user__first_name']
    
    fieldsets = (
        (None, {'fields': ('user', 'phone_number', 'linkedin_profile','resume_markdown')}),
        ('Resume Details', {'fields': ('resume_pdf',)}), # Renamed, removed submission_date
        ('Parsed Profile Data', {
            'fields': ('current_title', 'latest_work_organization', 'latest_degree', 'school', 'major', 'graduate_year'), # Removed years_experience, Added latest_work_organization
            'classes': ('collapse',),
        }),
        ('Tags', {'fields': ('tags',)}),
    )
    filter_horizontal = ('tags',) # For better ManyToMany handling of tags

# ModelAdmin class for Application
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'job_posting', 'ai_score', 'application_date')
    list_filter = ('job_posting', 'application_date', 'ai_score')
    search_fields = ('user__username', 'user__email', 'job_posting__title')
    readonly_fields = ('application_date', 'user', 'job_posting')
    ordering = ['-application_date', '-ai_score']

    fieldsets = (
        (None, {'fields': ('user', 'job_posting')}),
        ('Application Details', {'fields': ('ai_score', 'application_date')}),
    )

# ModelAdmin class for Tag
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

# Register models with the admin site
admin.site.register(CompanyProfile)
admin.site.register(JobPosting, JobPostingAdmin)
admin.site.register(Applicant, ApplicantAdmin)
admin.site.register(Application, ApplicationAdmin) # Register Application model
admin.site.register(Tag, TagAdmin) # Register Tag model
# JobRequirement is handled by the inline in JobPostingAdmin
