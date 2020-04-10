import sys
sys.path.append("..")

import pika
import uuid
import json
from communications.broadcast import broadcast
from common.utils import convert_to_pk
from common.lazy import LazyPlayer, LazyPlayerEquivalent


def send_global_chat_message(from_who: LazyPlayer, text: str) -> None:
	return broadcast(
	    "chat", {
	        "type": "send_global_chat_message",
	        "name": from_who.username,
	        "text": text,
	        "from": from_who.pk
	    })


def send_team_chat_message(who: LazyPlayer, text: str) -> None:
	broadcast(
	    "chat", {
	        "type": "send_team_chat_message",
	        "id": who.pk,
	        "name": who.username,
	        "from": who.pk,
	        "text": text
	    })
	if not who.team:
		return
	for member in who.team.members:
		if member == who: continue
		broadcast(
		    "chat", {
		        "type": "send_team_chat_message",
		        "id": member.pk,
		        "name": who.username,
		        "from": who.pk,
		        "text": text
		    })


def send_direct_chat_message(who: LazyPlayerEquivalent, sender: str,
                             source: str, text: str) -> None:
	if not isinstance(who, int):
		who = who.pk
	broadcast(
	    "chat", {
	        "type": "send_direct_chat_message",
	        "id": who,
	        "sender": sender,
	        "text": text,
	        "source": source
	    })
