import sys
sys.path.append("..")
sys.path.append("../..")
import pika
import json
from common.logger import *
from communications.request_handler import AsyncServiceRequestHandler
import asyncio
import websockets
from communications.auth import get_id_from_token
from communications.notifications import send_notification
from communications.profile import get_friends
from communications.broadcast import broadcast
from communications.rpc import resolve

clients = set()

async def on_request(msg):
	if msg["type"] == "is_online":
		return msg["id"] in clients


async def handle_websockets(websocket, path):
	token = json.loads(await websocket.recv())
	pid = resolve(get_id_from_token(token))
	clients.add(pid)
	log_debug(f"Presence client connected: {pid}")
	for friend in resolve(get_friends(pid)):
		send_notification(friend, "friend online", id=pid)
	broadcast("presence", {"type": "id_online", "id": pid})
	try:
		async for m in websocket:
			pass
	except websockets.exceptions.ConnectionClosedError:
		pass
	clients.discard(pid)
	for friend in resolve(get_friends(pid)):
		send_notification(friend, "friend offline", id=pid)
	broadcast("presence", {"type": "id_offline", "id": pid})
	log_debug(f"Presence client disconnected: {pid}")

reqh = AsyncServiceRequestHandler("presence", "presence_queue", on_request)

loop = asyncio.get_event_loop()
loop.run_until_complete(websockets.serve(handle_websockets, "0.0.0.0", 8769)),
loop.run_until_complete(reqh.run())
loop.run_forever()
