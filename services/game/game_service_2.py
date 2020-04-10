from __future__ import annotations
from typing import *

import sys
sys.path.append("..")
sys.path.append("../..")

import websockets
import json

from common.logger import *
from communications.request_handler import AsyncServiceRequestHandler
import asyncio
import websockets
from communications.auth import get_id_from_token
from communications.rpc import resolve
from common.lazy import LazyPlayer
import random
from math import floor

random.seed(time.time())


def clamp(x: float, minimum: float, maximum: float) -> float:
	return max(minimum, min(x, maximum))


class JSRand:
	def __init__(self, seed):
		self.seed = seed

	def __call__(self):
		self.seed = floor(self.seed * 16807 % 2147483647)
		return self.seed / 2147483646


rand = JSRand(2137)

GameState = NewType("GameState", int)

GAME_STATE_WAITING: GameState = GameState(0)
GAME_STATE_SETTING_UP: GameState = GameState(1)
GAME_STATE_PLAYING: GameState = GameState(2)
GAME_STATE_ENDED: GameState = GameState(3)


class Client:
	def __init__(self):
		self.websocket: websockets.WebSocketClientProtocol = None
		self.profile: LazyPlayer
		self.id: int = -1
		self.lobby: Lobby
		self.tank: Tank
		self.team: int = 0

	async def assign(self,
	                 websocket: websockets.WebSocketClientProtocol) -> Client:

		self.websocket = websocket
		token: str = json.loads(await self.websocket.recv())
		self.id = resolve(get_id_from_token(token))
		self.profile = LazyPlayer(self.id)
		return self

	async def send(self, msg: Mapping):
		await self.websocket.send(json.dumps(msg))

	async def loop(self):
		async for msg in self.websocket:
			msg = json.loads(msg)
			await self.lobby.on_message(self, msg)

		print("connection closed")

	def __eq__(self, other):
		if isinstance(other, int):
			return self.id == other
		elif isinstance(other, Client):
			return self.id == other.id
		else:
			return False


class Tank:
	def __init__(self, client: Client, x: float, y: float):
		self.client: Client = client
		self.x: float = x
		self.y: float = y


ClientEq = Union[int, Client]


class Terrain:
	def __init__(self, seed):
		pass


class Lobby:
	def __init__(self, lid: int, manager: LobbyManager):
		self.id: int = lid
		self.manager: LobbyManager = manager
		self.clients: Dict[int, Client] = {}
		self.reservations: List[int] = []
		self.required_players: int = 2

		self.teams: Dict[int, List[Client]] = {}
		self.teams[0] = []
		self.next_team_id: int = 1

		self.game_state: GameState = GAME_STATE_WAITING
		self.round_timer_task: asyncio.Task
		self.round_length: int = 10

		self.projectile_launches: Dict[int, Dict] = {}

	def create_team(self) -> int:
		self.next_team_id += 1
		self.teams[self.next_team_id - 1] = []
		return self.next_team_id - 1

	async def send_to(self, client: ClientEq, msg: Mapping):
		if isinstance(client, int):
			client = self.clients[client]
		await client.send(msg)

	async def broadcast(self,
	                    msg: Mapping,
	                    except_for: Optional[ClientEq] = None):

		for cli in self.clients.values():
			if cli != except_for:
				await cli.send(msg)

	async def schedule_round_finish(self):
		self.round_timer_task = asyncio.create_task(self.wait_and_finish())

	async def wait_and_finish(self):
		try:
			await asyncio.sleep(self.round_length)
			await self.finish_round()
		except asyncio.CancelledError:
			pass

	async def cancel_scheduled_finish(self):
		try:
			if not self.round_timer_task.done():
				self.round_timer_task.cancel()
				await self.round_timer_task
		except asyncio.CancelledError:
			pass

	async def finish_round(self):
		await self.cancel_scheduled_finish()

		for _client_id, launch in self.projectile_launches.items():
			await self.broadcast({
			    "type": "fire",
			    "player": launch["player"],
			    "force": launch["force"],
			    "angle": launch["angle"]
			})

		await self.broadcast({"type": "round_ended"})

		self.projectile_launches.clear()
		await self.broadcast({"type": "next_round"})
		await self.schedule_round_finish()

	async def check_fast_track_finish(self):
		if len(self.projectile_launches) >= len(self.clients):
			await self.finish_round()

	async def check_readiness(self) -> None:
		if len(self.clients) >= self.required_players:
			await self.prepare_game()

	async def start_game(self) -> None:
		print("LET'S GO!!!")
		self.game_state = GAME_STATE_PLAYING
		await self.broadcast({"type": "event_game_start"})
		await self.schedule_round_finish()

	async def prepare_game(self) -> None:
		print("Setting up game...")
		self.game_state = GAME_STATE_SETTING_UP
		await self.manager.close_lobby(self)
		for i, (_id, client) in enumerate(self.clients.items()):
			client.tank = Tank(client, 250 + i * 50, 250)
			await client.send({
			    "type": "your tank",
			    "x": 250 + i * 50,
			    "y": 250,
			    "username": client.profile.username,
			    "team": client.team
			})
			await self.broadcast(
			    {
			        "type": "enemy tank",
			        "x": 250 + i * 50,
			        "y": 250,
			        "username": client.profile.username,
			        "team": client.team
			    },
			    except_for=client)

			await client.send({"type": "generate_terrain", "seed": 2137})
		await self.start_game()

	async def register_client(self, client: Client, team: int = 0) -> None:

		print(
		    f"Registering player {client.profile.username} at lobby {self.id}")
		if self.game_state != GAME_STATE_WAITING:
			return

		try:
			self.reservations.remove(client.id)
		except:
			pass
		self.clients[client.id] = client
		client.lobby = self
		if team:
			self.teams[team].append(client)
			client.team = team
		asyncio.create_task(self.check_readiness())
		await client.loop()

	async def on_message(self, client: Client, msg: Dict) -> None:
		if self.game_state == GAME_STATE_WAITING:
			return
		elif self.game_state == GAME_STATE_PLAYING:
			if msg["type"] == "fire":
				launch_data = {
				    "force": clamp(msg["force"], 0, 600),
				    "angle": msg["angle"],
				    "player": client.profile.username
				}
				self.projectile_launches[client.id] = launch_data
				await self.check_fast_track_finish()


class PlayerReservation:
	def __init__(self, lobby: Lobby, team: int):
		self.lobby: Lobby = lobby
		self.team: int = team


class LobbyManager:
	def __init__(self):
		self.lobbies: Dict[int, Lobby] = {}
		self.player_reservations: Dict[int, PlayerReservation] = {}
		self.next_lobby_id: int = 1

	async def create_lobby(self):
		print("Creating new lobby")
		lobby = Lobby(self.next_lobby_id, self)
		self.next_lobby_id += 1
		self.lobbies[lobby.id] = lobby
		return lobby

	async def close_lobby(self, lobby: Lobby) -> None:
		del self.lobbies[lobby.id]

	async def find_reservable_lobby(self, count) -> Lobby:
		for lid, lobby in self.lobbies.items():
			space_left: int = lobby.required_players - len(
			    lobby.clients) - len(lobby.reservations)

			if space_left >= count:
				return lobby

		return await self.create_lobby()

	async def reserve_lobby(self, players: List[int]) -> int:
		print(f"Reserving a lobby for team: {players}")
		lobby: Lobby = await self.find_reservable_lobby(len(players))
		team = lobby.create_team()
		for player in players:
			lobby.reservations.append(player)
			self.player_reservations[player] = PlayerReservation(lobby, team)

		return lobby.id

	async def assign_player(self, player: Client) -> None:
		print(f"Finding lobby for player {player.profile.username}")
		reservation: Optional[
		    PlayerReservation] = self.player_reservations.get(player.id, None)
		lobby: Lobby
		team: int = 0
		if not reservation:
			print(f"No reserved lobby for player {player.profile.username}")
			lobby = await self.find_reservable_lobby(1)
		else:
			print("Removing reserved lobby")
			lobby = self.player_reservations[player.id].lobby
			team = self.player_reservations[player.id].team
			del self.player_reservations[player.id]
		await lobby.register_client(player, team)


lobby_manager = LobbyManager()


async def hello(websocket, path):
	print("New player connected")
	player: Client = await Client().assign(websocket)
	await lobby_manager.assign_player(player)


async def on_request(msg):
	if msg["type"] == "reserve_lobby":
		await lobby_manager.reserve_lobby(msg["ids"])
		return 1


loop = asyncio.get_event_loop()
reqh = AsyncServiceRequestHandler("game", "game_queue", on_request)
loop.run_until_complete(reqh.run())
loop.run_until_complete(websockets.serve(hello, "0.0.0.0", 8765)),
loop.run_forever()
