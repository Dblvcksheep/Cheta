from celery import shared_task
from django.core.management import call_command

@shared_task
def approve_courses_task():
    call_command('approve_courses')