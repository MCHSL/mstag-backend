import sys
sys.path.append("..")
sys.path.append("../..")
import pika
import json
from common.logger import *
from communications.request_handler import ServiceRequestHandler
from communications.notifications import send_notification
from communications.profile import request_profile
from communications.rpc import resolve
from communications import chat


class SetEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, set):
			return list(obj)
		elif isinstance(obj, Player):
			return obj.pk
		return json.JSONEncoder.default(self, obj)


teams = {}
players = {}
next_id = 1


class Team:
	def __init__(self, leader):
		if isinstance(leader, int):
			leader = players[leader]
		global next_id
		self.pk = next_id
		next_id += 1
		self.leader = leader
		self.invitees = set()
		self.members = set()
		if (self.leader):
			self.add_member(leader)

	def add_member(self, member):
		if isinstance(member, int):
			member = players[member]
		member.invites.discard(self)
		self.invitees.discard(member)
		if member.team:
			member.team.remove_member(member)
		self.members.add(member)
		member.team = self

	def remove_member(self, member):
		if isinstance(member, int):
			member = players[member]
		self.members.discard(member)
		member.team = None
		if self.leader == member and self.members:
			self.leader = next(iter(self.members))
		if not self.members:
			del teams[self.pk]

	def invite(self, player):
		if isinstance(player, int):
			player = players[player]
		self.invitees.add(player)
		player.invites.add(self)

	def remove_invite(self, player):
		if isinstance(player, int):
			player = players[player]
		self.invitees.discard(player)
		player.invites.discard(self)


def create_team(leader):
	team = Team(leader)
	teams[team.pk] = team
	return team


class Player:
	def __init__(self, id):
		self.pk = id
		self.team = None
		self.invites = set()

	def __str__(self):
		return str(self.pk)

	def __repr__(self):
		return str(self.pk)


def on_request(message):
	playerid = message.get("id", None)
	if playerid is not None:
		player = players.get(playerid, None)
		if not player:
			player = players[playerid] = Player(playerid)
	else:
		player = None
	team = message.get("team", None)
	if team is not None:
		team = teams.get(team, None)
	if message["type"] == "add_player_to_team":
		return add_player_to_team(player, team)
	elif message["type"] == "remove_player_from_team":
		remove_player_from_team(player)
	elif message["type"] == "get_player_team":
		return get_player_team(player)
	elif message["type"] == "get_team":
		return get_team(team)
	elif message["type"] == "invite_player_to_team":
		invite_player_to_team(player, team)
	elif message["type"] == "remove_player_from_invitations":
		remove_player_from_invitations(player, team)
	elif message["type"] == "id_offline":
		remove_player_from_everything(player)
	elif message["type"] == "id_online":
		pass
	elif message["type"] == "get_team_invitations_for_player":
		return get_team_invites(player)
	else:
		log_error("Unknown message type: " + message["type"])


def get_team_invites(player):
	return player.invites


def remove_player_from_everything(player):
	log_debug("Removing player from everything")
	prof = resolve(request_profile(player.pk))
	if player.team:
		for member in player.team.members:
			if member != player:
				send_notification(member,
				                  "teammate left",
				                  teammate_name=prof["username"])
				chat.send_direct_chat_message(
				    member, "*", "party",
				    prof["username"] + " has left your party.")
		player.team.remove_member(player)
	xd = list(player.invites)
	for team in xd:
		send_notification(team.leader,
		                  "invitation declined",
		                  username=prof["username"])
		team.remove_invite(player)


def add_player_to_team(player, team):
	log_debug(f"Adding player {player} to team {team}")
	if team is None:
		team = create_team(player)
	else:
		team.add_member(player)
	return team.__dict__


def remove_player_from_team(player):
	log_debug(f"Removing player {player} from their team")
	if player.team is not None:
		player.team.remove_member(player)


def remove_player_from_invitations(player, team):
	log_debug(f"Removing player {player} from team {team} invitations")
	team.remove_invite(player)


def get_player_team(player):
	log_debug(f"Getting team for player {player}")
	print(f"Getting team for player {player}")
	try:
		team = player.team
		print(team)
		if not team:
			return None
		return team.__dict__
	except KeyError:
		return None


def get_team(team):
	log_debug(f"Getting team {team}")
	if not team:
		return None
	try:
		return team.__dict__
	except KeyError:
		return None


def invite_player_to_team(player, team):
	log_debug("Inviting player to team")
	try:
		team.invite(player)
	except KeyError:
		pass


rrh = ServiceRequestHandler("teams",
                            "team_queue",
                            on_request,
                            custom_json_encoder=SetEncoder,
                            broadcasts=["presence"])
rrh.run()
