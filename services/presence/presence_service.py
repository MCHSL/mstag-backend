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
from typing import *

clients: Set[int] = set()


async def on_request(msg):
	if msg["type"] == "is_online":
		return msg["id"] in clients

	elif msg["type"] == "player_count":
		return len(clients)


async def handle_websockets(websocket, path):
	try:
		token = json.loads(await websocket.recv())
	except:
		return
	pid: Optional[int] = resolve(get_id_from_token(token))
	if pid is None:
		await websocket.send(
		    json.dumps({
		        "error": True,
		        "error_type": "No such token"
		    }))
		return
	if pid in clients:
		await websocket.send(
		    json.dumps({
		        "error": True,
		        "error_type": "Already connected"
		    }))
		return
	print(pid)
	print("adding pid")
	clients.add(pid)
	await websocket.send(json.dumps({"error": False}))
	log_debug(f"Presence client connected: {pid}")
	friends = resolve(get_friends(pid))
	print(friends)
	for friend in friends:
		print("LALALLAL")
		send_notification(friend, "friend online", id=pid)
	broadcast("presence", {"type": "id_online", "id": pid})
	try:
		async for m in websocket:
			pass
	except websockets.exceptions.ConnectionClosedError:
		pass
	clients.discard(pid)
	for friend in resolve(get_friends(pid)):
		print("ASDFSEDFSDF")
		send_notification(friend, "friend offline", id=pid)
	broadcast("presence", {"type": "id_offline", "id": pid})
	log_debug(f"Presence client disconnected: {pid}")


reqh = AsyncServiceRequestHandler("presence",
                                  "presence_queue",
                                  on_request,
                                  broadcasts=["presence_requests"])

loop = asyncio.get_event_loop()
loop.run_until_complete(reqh.run())
loop.run_until_complete(websockets.serve(handle_websockets, "0.0.0.0", 8769)),
loop.run_forever()
