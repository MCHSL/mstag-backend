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
from communications.rpc import resolve

clients = {}

async def on_request(msg):
	print("REQUEST RECEIVED")
	if msg["type"] == "send_notification":
		print(msg["target"])
		print(clients)
		if msg["target"] in clients:
			try:
				await clients[msg["target"]].send(json.dumps(msg["notification"]))
			except websockets.exceptions.ConnectionClosedError as e:
				print(e)
				pass


async def handle_websockets(websocket, path):
	print("fufu")
	sys.stdout.flush()
	token = json.loads(await websocket.recv())
	pid = resolve(get_id_from_token(token))
	clients[pid] = websocket
	log_debug(f"Notification client connected: {pid}")
	try:
		async for m in websocket:
			pass
	except websockets.exceptions.ConnectionClosedError:
		pass
	try:
		del clients[pid]
	except KeyError:
		pass
	log_debug(f"Notification client disconnected: {pid}")

reqh = AsyncServiceRequestHandler("notifications", None, on_request, broadcasts=["notifications"])

loop = asyncio.get_event_loop()
loop.run_until_complete(reqh.run())
loop.run_until_complete(websockets.serve(handle_websockets, "0.0.0.0", 8767)),
print("run forever")
loop.run_forever()
print("a")
