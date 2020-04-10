import sys
sys.path.append("..")

import pika
import uuid
import json

from typing import *
from communications.broadcast import broadcast
from common.lazy import LazyPlayer, LazyPlayerEquivalent


def send_notification(who: LazyPlayerEquivalent, ntype, **fields):
	if not isinstance(who, int):
		who = who.pk
	notif = {"type": ntype}
	notif.update(fields)
	print("Sending notifications")
	broadcast("notifications", {
	    "type": "send_notification",
	    "target": who,
	    "notification": notif
	})
