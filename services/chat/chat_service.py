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
	if msg["type"] == "send_global_chat_message":
		print("sending global")
		for client in clients.values():
			await client.send(
			    json.dumps({
			        "name": msg["name"],
			        "text": msg["text"],
			        "id": msg["from"],
			        "source": "global"
			    }))
	elif msg["type"] == "send_team_chat_message":
		print("sending team")
		try:
			client = clients[msg["id"]]
			await client.send(
			    json.dumps({
			        "name": msg["name"],
			        "text": msg["text"],
			        "id": msg["from"],
			        "source": "party"
			    }))
		except KeyError:
			pass
	elif msg["type"] == "send_direct_chat_message":
		print("sending direct")
		try:
			await clients[msg["id"]].send(
			    json.dumps({
			        "name": msg["sender"],
			        "text": msg["text"],
			        "source": msg["source"],
			        "id": -1
			    }))
		except KeyError:
			pass


async def handle_websockets(websocket, path):
	print("Chat client connected")
	log_debug(f"Chat client connected")
	token = json.loads(await websocket.recv())
	pid = resolve(get_id_from_token(token))
	if pid is None:
		print("fucc")
		return
	clients[pid] = websocket
	try:
		async for m in websocket:
			pass
	except websockets.exceptions.ConnectionClosedError as e:
		print(e)
		pass
	try:
		del clients[pid]
	except KeyError:
		pass


reqh = AsyncServiceRequestHandler("chat_messages",
                                  None,
                                  on_request,
                                  broadcasts=["chat"])

loop = asyncio.get_event_loop()
loop.run_until_complete(reqh.run())
loop.run_until_complete(websockets.serve(handle_websockets, "0.0.0.0", 8768)),
loop.run_forever()
