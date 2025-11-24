from django.core.mail import EmailMessage
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


class Util:
    @staticmethod
    def send_email(data):
    # Create a plain-text version by stripping HTML tags

        email = EmailMultiAlternatives(
            subject=data["subject"],
            body="",  # Plain text content
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[data["to_email"]],
        )
        
        email.send(fail_silently=False)  # Set to False to raise exceptions on errors,