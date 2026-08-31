from django.apps import AppConfig
from django.contrib.auth import get_user_model
import os


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
