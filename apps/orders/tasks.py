from __future__ import absolute_import, unicode_literals

import os
import django
import logging
from decimal import Decimal
import random
import json

from django.db import transaction
from django.conf import settings
from channels.layers import get_channel_layer
from celery import shared_task

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()


@shared_task
def buy_now_with_izipay_task(auth_header, user, request_data):
    pass