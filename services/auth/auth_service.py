import os
import sys
from typing import *

sys.path.append("..")
sys.path.append("../..")
sys.path.append("../../auth_gateway")

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auth_gateway.settings")
django.setup()

from rest_framework.authtoken.models import Token

from common.logger import *
from communications.request_handler import ServiceRequestHandler


def on_request(msg: dict) -> Any:
	if msg["type"] == "get_id_from_token":
		log_debug(f"Looking up player with token {msg['token']}")
		try:
			return Token.objects.get(key=msg["token"]).user.pk
		except Token.DoesNotExist:
			return None


rrh = ServiceRequestHandler("auth", "auth_queue", on_request)
rrh.run()
