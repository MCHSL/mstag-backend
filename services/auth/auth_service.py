import sys
sys.path.append("..")
sys.path.append("../..")
sys.path.append("../../auth_gateway")

import django
import os

from common.logger import *
from communications.request_handler import ServiceRequestHandler

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "auth_gateway.settings")
django.setup()

from agw.models import Player
from rest_framework.authtoken.models import Token

def on_request(msg):
	if msg["type"] == "get_id_from_token":
		log_debug(f"Looking up player with token {msg['token']}")
		return Token.objects.get(key=msg["token"]).user.pk

rrh = ServiceRequestHandler("auth", "auth_queue", on_request)
rrh.run()
