import sys
sys.path.append("..")
sys.path.append("../..")
import pika
import json
from common.logger import *
from communications.request_handler import AsyncServiceRequestHandler
import asyncio
import websockets

clients = set()

async def on_request(msg):
	if msg["type"] == "send_chat_message":
		for client in clients:
			await client.send(json.dumps({"name": msg["name"], "text": msg["text"]}))


async def handle_websockets(websocket, path):
	log_debug(f"Chat client connected")
	clients.add(websocket)
	try:
		async for m in websocket:
			pass
	except websockets.exceptions.ConnectionClosedError as e:
		print(e)
		pass
	clients.discard(websocket)

reqh = AsyncServiceRequestHandler("chat_messages", None, on_request, broadcasts=["chat"])

loop = asyncio.get_event_loop()
loop.run_until_complete(websockets.serve(handle_websockets, "0.0.0.0", 8768)),
loop.run_until_complete(reqh.run())
loop.run_forever()
