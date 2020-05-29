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
from math import floor, cos, sin, pi, hypot
import string

random.seed(time.time())


def clamp(x: float, minimum: float, maximum: float) -> float:
	return max(minimum, min(x, maximum))


class JSRand:
	def __init__(self, seed):
		self.seed = seed

	def __call__(self):
		self.seed = floor(self.seed * 16807 % 2147483647)
		return self.seed / 2147483646


rand = JSRand(random.random())

GameState = NewType("GameState", int)

GAME_STATE_WAITING: GameState = GameState(0)
GAME_STATE_SETTING_UP: GameState = GameState(1)
GAME_STATE_PLAYING: GameState = GameState(2)
GAME_STATE_ENDED: GameState = GameState(3)

TURN_STATE_WAITING: int = 0
TURN_STATE_SIMULATING: int = 1

REQUIRED_PLAYERS = 2


class Client:
	def __init__(self):
		self.websocket: websockets.WebSocketClientProtocol = None
		self.profile: LazyPlayer
		self.id: int = -1
		self.lobby: Lobby
		self.tank: Tank
		self.team: int = 0

	async def assign(
	    self, websocket: websockets.WebSocketClientProtocol) -> "Client":

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
		self.max_hp: int = 200
		self.hp: int = self.max_hp

	@property
	def alive(self):
		return self.hp > 0


class Projectile:
	explosion_radius: int = 30
	mass: float = 1
	damage: int = 100

	def __init__(self, x: float, y: float, owner: Client):
		self.x: float = x
		self.y: float = y
		self.owner: Client = owner

		self.x_vel: float = 0
		self.y_vel: float = 0
		self.id = ''.join(
		    random.choices(string.ascii_uppercase + string.digits, k=5))

		self.sim: PhysicsSimulation

	async def update(self, dt: float):
		self.x = round(self.x + self.x_vel * dt, 2)
		self.y = round(self.y + self.y_vel * dt, 2)

		self.y_vel = round(self.y_vel + (self.sim.gravity * dt * self.mass), 2)
		self.x_vel = round(self.x_vel + (self.sim.wind * dt), 2)


class MIRV(Projectile):
	async def update(self, dt: float):
		await super().update(dt)

		if self.y_vel > 2:
			await self.sim.remove_projectile(self)
			for i in range(-2, 3):
				frag = MIRVFragment(self.x, self.y, self.owner)
				frag.x_vel = self.x_vel + (i * 3)
				frag.y_vel = self.y_vel
				await self.sim.add_projectile(frag)


class MIRVFragment(Projectile):
	explosion_radius = 10
	damage = 30


ClientEq = Union[int, Client]


class Terrain:
	def __init__(self, seed: int):
		self.seed: int = seed

		self.width: int = 1600
		self.base_height: int = 500

		self.amplitude: int = 300
		self.correction_force: float = 5

		self.random: Callable = JSRand(self.seed)
		self.heightmap: List[float] = []

	async def generate(self):
		await self.generate_base()
		for i in range(5):
			await self.smooth_base()
		#await self.rotate_horizontal()

	async def generate_base(self):
		y = self.base_height
		for x in range(self.width):
			self.heightmap.append(y)
			delta: float = self.random() * 17 - 8 - (self.correction_force * (
			    (y - self.base_height) / self.amplitude))
			y += delta * 3

	async def smooth_base(self):
		for x in range(3, self.width - 3):
			avg: float = (self.heightmap[x - 2] + self.heightmap[x - 1] +
			              self.heightmap[x] + self.heightmap[x + 1] +
			              self.heightmap[x + 2]) // 5
			self.heightmap[x - 2] = avg
			self.heightmap[x - 1] = avg
			self.heightmap[x] = avg
			self.heightmap[x + 1] = avg
			self.heightmap[x + 2] = avg

	async def rotate_horizontal(self):
		dev = self.heightmap[-1]
		for x in range(self.width):
			self.heightmap[x] -= dev * (x / self.width)

	def get_at(self, x):
		return self.heightmap[floor(x)]

	def set_at(self, x, y):
		self.heightmap[floor(x)] = floor(y)


class Impact:
	def __init__(self, x, y, start_point, modifications,
	             projectile: Projectile):
		self.start_point = start_point
		self.modifications = modifications
		self.projectile = projectile
		self.x = x
		self.y = y


class PhysicsSimulation:
	def __init__(self, terrain, seed):
		self.terrain: Terrain = terrain
		self.random: Callable = JSRand(seed)
		self.wind: float = 0
		self.gravity: float = 500

		self.projectiles: List[Projectile] = []

	async def add_projectile(self, projectile: Projectile):
		self.projectiles.append(projectile)
		projectile.sim = self

	async def remove_projectile(self, projectile: Projectile):
		self.projectiles.remove(projectile)

	async def simulate_impact(self, projectile: Projectile):
		impact_x: int = int(projectile.x)
		impact_y: int = int(projectile.y)
		angle = -0.01
		last_x: int = floor(impact_x + projectile.explosion_radius)
		first_x: int = floor(impact_x - projectile.explosion_radius)
		modifications = []
		while angle < pi:
			angle += 0.01
			reached_x = floor(impact_x +
			                  cos(angle) * projectile.explosion_radius)
			if reached_x == last_x or reached_x >= self.terrain.width:
				continue
			last_x = reached_x
			t_height = self.terrain.get_at(reached_x)
			upper_y = impact_y - sin(angle) * projectile.explosion_radius
			lower_y = impact_y + sin(angle) * projectile.explosion_radius
			highest_point = max(t_height, upper_y)
			delta = max(0, lower_y - highest_point)
			self.terrain.set_at(reached_x, t_height + delta)
			modifications.append((t_height + delta, upper_y, lower_y))
		return (first_x, modifications)

	async def simulate(self):
		impacts = []
		while self.projectiles:
			start_time = int(time.time() * 1000)
			await asyncio.sleep(0.008)
			for projectile in self.projectiles[:]:
				await projectile.update(
				    (int(time.time() * 1000) - start_time) / 1000)
				if projectile.x < 0 or projectile.x > self.terrain.width:
					await self.remove_projectile(projectile)
					impacts.append(
					    Impact(projectile.x, projectile.y, 0, [], projectile))
					continue
				if projectile.y < self.terrain.get_at(projectile.x):
					continue
				start_point, modifications = await self.simulate_impact(
				    projectile)
				await self.remove_projectile(projectile)
				impacts.append(
				    Impact(projectile.x, projectile.y, start_point,
				           modifications, projectile))
		return impacts

	async def rewind(self) -> float:
		self.wind = (self.random() * 100) - 50
		return self.wind


class Lobby:
	def __init__(self, lid: int, manager: "LobbyManager"):
		self.id: int = lid
		self.manager: LobbyManager = manager
		self.clients: Dict[int, Client] = {}
		self.alive_clients: Dict[int, Client] = {}
		self.dead_clients: Dict[int, Client] = {}
		self.reservations: List[int] = []
		self.required_players: int = REQUIRED_PLAYERS

		self.teams: Dict[int, List[Client]] = {}
		self.teams[0] = []
		self.next_team_id: int = 1

		self.game_state: GameState = GAME_STATE_WAITING
		self.turn_timer_task: asyncio.Task
		self.turn_length: int = 3

		self.projectile_launches: Dict[int, Dict] = {}
		self.turn_state = TURN_STATE_WAITING

		self.seed = int(random.random() * 1000)
		self.sim: PhysicsSimulation = PhysicsSimulation(
		    Terrain(self.seed), self.seed)

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

	async def schedule_turn_finish(self):
		self.turn_timer_task = asyncio.ensure_future(self.wait_and_finish())

	async def wait_and_finish(self):
		try:
			await asyncio.sleep(self.turn_length)
			await self.finish_turn()
		except asyncio.CancelledError:
			pass

	async def cancel_scheduled_finish(self):
		try:
			if not self.turn_timer_task.done():
				self.turn_timer_task.cancel()
				await self.turn_timer_task
		except asyncio.CancelledError:
			pass

	async def check_victory(self):
		team_counts: Dict[int, int] = {}
		for client in self.alive_clients.values():
			team_counts[client.team] = team_counts.get(client.team, 0) + 1

		if len(team_counts) > 1:
			return  # Two teams are alive, game not over yet

		independents = team_counts.get(0, 0)
		if independents > 1:
			return  # If there is more than one independent, game is not over yet
		elif independents == 1:
			await self.announce_victory(
			    [v for v in self.teams[0] if v.tank.alive])
			return

		winners = next(iter(team_counts.keys()))

		await self.announce_victory(self.teams[winners])

	async def announce_victory(self, winners: List[Client]):
		self.game_state = GAME_STATE_ENDED
		await self.broadcast({
		    "type":
		    "victory",
		    "victors": [winner.profile.username for winner in winners]
		})

	async def simulate(self, projectiles: List[Projectile]):
		self.turn_state = TURN_STATE_SIMULATING
		for p in projectiles:
			await self.sim.add_projectile(p)

		impacts = await self.sim.simulate()
		for impact in impacts:
			for cli in list(self.alive_clients.values()):
				tank = cli.tank
				dist = hypot(tank.x - impact.x, tank.y - impact.y)
				if dist <= impact.projectile.explosion_radius:
					damage = floor(
					    (1 - (dist / impact.projectile.explosion_radius)) *
					    impact.projectile.damage)

					tank.hp -= damage
					await self.broadcast({
					    "type": "damage",
					    "player": cli.profile.username,
					    "amount": damage
					})
					if not tank.alive:
						del self.alive_clients[cli.id]
						self.dead_clients[cli.id] = cli
						await self.broadcast({
						    "type": "death",
						    "player": cli.profile.username,
						})
						await self.check_victory()
				tank.y = self.sim.terrain.get_at(tank.x)

			await self.broadcast({
			    "type": "impact",
			    "start_point": impact.start_point,
			    "modifications": impact.modifications,
			    "projectile_id": impact.projectile.id
			})

		self.turn_state = TURN_STATE_WAITING

	async def finish_turn(self):
		await self.cancel_scheduled_finish()

		projectiles = []

		await self.broadcast({"type": "turn_ended"})
		for _client_id, launch in self.projectile_launches.items():
			cli: Client = launch["client"]
			proj = MIRV(cli.tank.x + 3, cli.tank.y - 16, cli)
			proj.x_vel = round(cos(launch["angle"]) * launch["force"], 2)
			proj.y_vel = round(sin(launch["angle"]) * launch["force"], 2)
			projectiles.append(proj)
			await self.broadcast({
			    "type": "fire",
			    "player": launch["player"],
			    "force": launch["force"],
			    "angle": launch["angle"],
			    "projectile_id": proj.id
			})

		await self.simulate(projectiles)

		self.projectile_launches.clear()
		if self.game_state == GAME_STATE_PLAYING:
			await self.broadcast({"type": "next_turn"})
			await self.broadcast({
			    "type": "wind",
			    "strength": await self.sim.rewind()
			})
			await self.schedule_turn_finish()

	async def check_fast_track_finish(self):
		if len(self.projectile_launches) >= len(self.alive_clients):
			await self.finish_turn()

	async def check_readiness(self) -> None:
		if len(self.clients) >= self.required_players:
			await self.prepare_game()

	async def start_game(self) -> None:
		print("LET'S GO!!!")
		self.game_state = GAME_STATE_PLAYING
		await self.broadcast({"type": "event_game_start"})
		await self.schedule_turn_finish()

	async def prepare_game(self) -> None:
		print("Setting up game...")
		await self.sim.terrain.generate()
		self.game_state = GAME_STATE_SETTING_UP
		await self.manager.close_lobby(self)
		margin = 300
		margin_left = 0 + margin
		margin_right = self.sim.terrain.width - margin
		play_area = self.sim.terrain.width - 2 * margin
		clis = list(self.clients.values())
		for i, (client) in enumerate(clis):
			my_x = margin_left + (i + 1) * floor(play_area /
			                                     (len(self.clients) + 1))
			my_y = self.sim.terrain.get_at(my_x)
			client.tank = Tank(client, my_x, my_y)
			for i in range(my_x - 10, my_x + 10):
				self.sim.terrain.set_at(i, my_y)
			await client.send({
			    "type": "your tank",
			    "x": my_x,
			    "y": my_y,
			    "username": client.profile.username,
			    "team": client.team
			})
			await self.broadcast(
			    {
			        "type": "enemy tank",
			        "x": my_x,
			        "y": my_y,
			        "username": client.profile.username,
			        "team": client.team
			    },
			    except_for=client)

			await client.send({
			    "type": "terrain",
			    "terrain": self.sim.terrain.heightmap
			})

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
		self.alive_clients[client.id] = client
		client.lobby = self
		self.teams[team].append(client)
		client.team = team
		await self.broadcast({
		    "type": "event_player_count",
		    "have": len(self.clients),
		    "need": self.required_players
		})
		asyncio.ensure_future(self.check_readiness())
		await client.loop()

	async def on_message(self, client: Client, msg: Dict) -> None:
		if self.game_state == GAME_STATE_WAITING:
			return
		elif self.game_state == GAME_STATE_PLAYING:
			if self.turn_state == TURN_STATE_WAITING:
				if msg["type"] == "fire":
					if not client.tank.alive:
						return
					launch_data = {
					    "force": clamp(msg["force"], 0, 600),
					    "angle": msg["angle"],
					    "player": client.profile.username,
					    "client": client
					}
					self.projectile_launches[client.id] = launch_data
					asyncio.ensure_future(self.check_fast_track_finish())


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
