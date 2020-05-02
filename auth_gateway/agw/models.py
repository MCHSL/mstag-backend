import sys
sys.path.append("..")

from django.db import models
from django.contrib.auth.models import AbstractUser
from rest_registration.signals import user_registered
from communications.profile import create_profile
from django.dispatch import receiver


class Player(AbstractUser):
	first_name = None
	last_name = None


@receiver(user_registered)
def create_user_profile(sender, user, request, **kwargs):
	create_profile(user.pk, user.username)
