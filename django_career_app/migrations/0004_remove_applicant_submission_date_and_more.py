# Generated by Django 5.2.1 on 2025-05-26 01:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_career_app', '0003_tag_remove_applicant_ai_score_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='applicant',
            name='submission_date',
        ),
        migrations.RemoveField(
            model_name='applicant',
            name='years_experience',
        ),
        migrations.AddField(
            model_name='applicant',
            name='latest_work_organization',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
