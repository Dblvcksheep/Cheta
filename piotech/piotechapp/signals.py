import re
import logging
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.dispatch import receiver
from allauth.socialaccount.signals import pre_social_login
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from django.contrib.auth import login
from .Blockchain import create_wallet_for_new_user


@receiver(pre_social_login)
def save_google_user_data(sender, request, sociallogin, **kwargs):
    logger = logging.getLogger(__name__)
    user = sociallogin.user
    if sociallogin.account.provider == 'google':
        extra_data = getattr(sociallogin.account, 'extra_data', {})
        email = extra_data.get('email')
        given_name = extra_data.get('given_name', '')
        family_name = extra_data.get('family_name', '')

        # To Validate the login email
        if not email:
            logger.error('Google login missing email.')
            return
        try:
            validate_email(email)
        except ValidationError:
            logger.error(f'Invalid email format: {email}')
            return

        existing_user = User.objects.filter(email=email).first()
        if existing_user is None:
            user.email = email
            user.first_name = given_name or user.first_name
            user.last_name = family_name or user.last_name

            # Make username unique and valid
            base_username = re.sub(r'\W+', '', given_name) or 'user'
            username = base_username[:150]  # Django username max length
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                username = username[:150]
                counter += 1
            user.username = username

            try:
                user.save()
                create_wallet_for_new_user(user)
            except Exception as e:
                logger.error(f'Error saving user: {e}')
                return
        else:
            try:
                if not SocialAccount.objects.filter(user=existing_user, provider='google').exists():
                    sociallogin.connect(request, existing_user)
            except Exception as e:
                logger.error(f'Error connecting social account: {e}')
                return
            try:
                login(request, existing_user, backend="allauth.account.auth_backends.AuthenticationBackend")
            except Exception as e:
                logger.error(f'Error logging in user: {e}')
                return

