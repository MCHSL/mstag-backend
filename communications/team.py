import sys
sys.path.append("..")

import pika
import uuid
import json
from communications.rpc import RPCClient, RPCRequest, resolve
from common.utils import convert_to_pk

__rpc = RPCClient("team_queue")


@convert_to_pk
def get_team_for_player(who: int) -> RPCRequest:
	return __rpc.request({"type": "get_player_team", "id": who})


@convert_to_pk
def get_team(team: int) -> RPCRequest:
	return __rpc.request({"type": "get_team", "team": team})


@convert_to_pk
def get_or_create_team(who: int) -> RPCRequest:
	team = resolve(__rpc.request({"type": "get_player_team", "id": who}))
	if not team:
		team = resolve(__rpc.request({
		    "type": "add_player_to_team",
		    "id": who
		}))
	return team


@convert_to_pk
def invite_player_to_team(who: int, team: int) -> RPCRequest:
	return __rpc.request({
	    "type": "invite_player_to_team",
	    "id": who,
	    "team": team
	})


@convert_to_pk
def add_player_to_team(who: int, team: int) -> RPCRequest:
	return __rpc.request({
	    "type": "add_player_to_team",
	    "id": who,
	    "team": team
	})


@convert_to_pk
def remove_player_from_team(who: int) -> RPCRequest:
	return __rpc.request({"type": "remove_player_from_team", "id": who})


@convert_to_pk
def remove_player_from_invitations(who: int, team: int) -> RPCRequest:
	return __rpc.request({
	    "type": "remove_player_from_invitations",
	    "id": who,
	    "team": team
	})


@convert_to_pk
def get_invitations_for_player(player: int) -> RPCRequest:
	return __rpc.request({"type": "get_invitations_for_player", "id": player})
