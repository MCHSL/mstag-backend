import sys
sys.path.append("..")

import pika
import uuid
import json
from communications.broadcast import broadcast

def send_chat_message(username, text):
	return broadcast("chat", {"type": "send_chat_message", "name": username, "text": text})
