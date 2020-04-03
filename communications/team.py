import sys
sys.path.append("..")

import pika
import uuid
import json
from communications.rpc import RPCClient, resolve
from common.utils import convert_to_pk

__rpc = RPCClient("team_queue")

@convert_to_pk
def get_team_for_player(who):
	return __rpc.request({"type": "get_player_team", "id": who})

@convert_to_pk
def get_team(team):
	return __rpc.request({"type": "get_team", "team": team})

@convert_to_pk
def get_or_create_team(who):
	team = resolve(__rpc.request({"type": "get_player_team", "id": who}))
	if not team:
		team = resolve(__rpc.request({"type": "add_player_to_team", "id": who}))
	return team

@convert_to_pk
def invite_player_to_team(who, team):
	__rpc.request_forget({"type": "invite_player_to_team", "id": who, "team": team})

@convert_to_pk
def add_player_to_team(who, team):
	__rpc.request_forget({"type": "add_player_to_team", "id": who, "team": team})

@convert_to_pk
def remove_player_from_team(who):
	__rpc.request_forget({"type": "remove_player_from_team", "id": who})

@convert_to_pk
def remove_player_from_invitations(who, team):
	__rpc.request_forget({"type": "remove_player_from_invitations", "id": who, "team": team})
