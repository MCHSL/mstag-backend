import sys
sys.path.append("..")

import pika
import uuid
import json

from communications.broadcast import broadcast

def send_notification(who, ntype, **fields):
	if not isinstance(who, int):
		who = who.pk
	notif = {"type": ntype}
	notif.update(fields)
	print("BROADCASTING NOTIFICATION: " + str(notif) + " TO " + str(who))
	broadcast("notifications", {"type": "send_notification", "target": who, "notification": notif})
