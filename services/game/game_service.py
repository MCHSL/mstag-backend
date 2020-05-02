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
from common.lazy import LazyPlayer


class Player:
	def __init__(self, websocket):
		self.websocket = websocket
		self.id = -1
		self.username = ""
		self.token = ""

	def __str__(self):
		return f"Player {self.username} ({self.websocket.host})"

	async def populate_info(self):
		self.token = json.loads(await self.websocket.recv())
		p = LazyPlayer(resolve(get_id_from_token(self.token)))
		self.id = p.pk
		self.username = p.username

	async def recv(self):
		return json.loads(await self.websocket.recv())

	async def send(self, message):
		if isinstance(message, dict):
			message = json.dumps(message)
		await self.websocket.send(message)


class Tank:
	def __init__(self, player, x, y):
		self.player = player
		self.x = x
		self.y = y


class PlayerHandler:
	def __init__(self):
		self.players = []

	async def register(self, player):
		print("Registering player")
		self.players.append(player)
		await self.on_join(player)

	async def unregister(self, player):
		print("Unregistering player")
		self.players.remove(player)
		await self.on_leave(player)

	async def on_join(self, player):
		pass

	async def on_leave(self, player):
		pass

	async def broadcast(self, message, except_for=None):
		if isinstance(message, dict):
			message = json.dumps(message)
		for player in self.players[:]:
			if player != except_for:
				try:
					await player.send(message)
				except:
					await self.unregister(player)

	async def on_message(self, player, message):
		print(f"GENERIC HANDLER: {player}: {message}")

	async def ping(self) -> None:
		while self.players:
			for player in self.players[:]:
				try:
					await player.send({"type": "ping"})
				except:
					await self.unregister(player)
			await asyncio.sleep(1)


class Game(PlayerHandler):
	def __init__(self):
		super().__init__()
		self.tanks = []
		self.launches = {}

	async def handle_player(self, player):
		while True:
			try:
				message = await player.recv()
				if message["type"] == "fire":
					message["player"] = player.username
					self.launches[player.username] = {
					    "player": player.username,
					    "angle": message["angle"],
					    "force": message["force"]
					}
				print(f"GAME: {player}: {message}")
			except:
				break
		await self.unregister(player)

	async def end_turn(self):
		for launch in self.launches.values():
			launch["type"] = "fire"
			await self.broadcast(launch)
		self.launches = {}

	async def create_tank(self, player, x, y):
		tank = Tank(player, x, y)
		self.tanks.append(tank)
		return tank

	async def setup(self) -> None:
		for i, player in enumerate(self.players):
			asyncio.get_event_loop().create_task(self.handle_player(player))
			tank = await self.create_tank(player, 50 + i * 200, 200)
			await player.send({
			    "type": "your tank",
			    "x": tank.x,
			    "y": tank.y,
			    "username": tank.player.username
			})
			await self.broadcast(
			    {
			        "type": "enemy tank",
			        "x": tank.x,
			        "y": tank.y,
			        "username": tank.player.username
			    }, player)
		asyncio.create_task(self.run())

	async def run(self) -> None:
		while True:
			for i in range(5):
				if len(self.launches) == len(self.players):
					break
				await self.broadcast({"type": "countdown", "countdown": 5 - i})
				await asyncio.sleep(1)
			await self.broadcast({"type": "countdown", "countdown": 0})
			await self.end_turn()


class Lobby(PlayerHandler):
	def __init__(self):
		super().__init__()
		self.required_players = 1
		self.reservations = []

	async def on_join(self, player):
		if player.id in self.reservations:
			self.reservations.remove(player.id)
		print("Have " + str(len(self.players)) + " players.")
		for player in self.players[:]:
			info = {
			    "type": "event_player_count",
			    "need": self.required_players,
			    "have": len(self.players),
			}
			try:
				await player.send(info)
			except:
				self.unregister(player)
		if len(self.players) == self.required_players:
			await self.start_game()

	async def on_leave(self, player):
		print("Player left!")
		print("Have " + str(len(self.players)) + " players.")
		for player in self.players[:]:
			info = {
			    "type": "event_player_count",
			    "need": self.required_players,
			    "have": len(self.players),
			}
			try:
				await player.send(info)
			except:
				await self.unregister(player)

	@property
	def space_left(self):
		return self.required_players - len(self.players) - len(
		    self.reservations)

	async def start_game(self):
		print("Starting game.")
		game = Game()
		for player in self.players[:]:
			try:
				await player.send({"type": "event_game_start"})
			except:
				await self.unregister(player)
				continue
			print("Transferring player")
			await game.register(player)
			await self.unregister(player)
		print(f"After transfer, have {len(self.players)} players")
		asyncio.get_event_loop().create_task(game.setup())


loop = asyncio.get_event_loop()

default_lobby = Lobby()
loop.create_task(default_lobby.ping())

reservations = {}  # Key = player id, Value = Lobby instance
reserved_lobbies = []


async def find_lobby(reserve_count):
	found = None
	for lobby in reserved_lobbies:
		if lobby.space_left >= reserve_count:
			found = lobby
			break
	if found:
		reserved_lobbies.remove(found)
	return found


async def hello(websocket, path):
	print("connection")
	player = Player(websocket)
	await player.populate_info()
	try:
		lobby = reservations[player.id]
		await lobby.register(player)
		del reservations[player.id]
		print("Added to reservated")
	except KeyError:
		lobby = await find_lobby(1)
		if not lobby:
			print("adding to default lobby")
			lobby = default_lobby
		print("register")
		await lobby.register(player)
	await asyncio.sleep(3600)


async def on_request(msg):
	if msg["type"] == "reserve_lobby":
		player_count = len(msg["ids"])
		lobby = await find_lobby(player_count)
		if not lobby:
			lobby = Lobby()
			reserved_lobbies.append(lobby)
			loop.create_task(lobby.ping())
		lobby.reservations += msg["ids"]
		for pid in msg["ids"]:
			reservations[pid] = lobby
		return 1


reqh = AsyncServiceRequestHandler("game", "game_queue", on_request)
loop.run_until_complete(reqh.run())
loop.run_until_complete(websockets.serve(hello, "0.0.0.0", 8765)),
loop.run_forever()
