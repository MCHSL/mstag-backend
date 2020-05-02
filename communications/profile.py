import sys
sys.path.append("..")

import pika
import uuid
import json

from communications.rpc import RPCClient, RPCRequest
from common.utils import convert_to_pk

__rpc = RPCClient("profile_queue")


@convert_to_pk
def request_profile(user: int) -> RPCRequest:
	return __rpc.request({"type": "get_profile", "id": user})


def request_profile_by_name(username: str) -> RPCRequest:
	return __rpc.request({"type": "get_profile_by_name", "name": username})


def create_profile(user, username: str) -> RPCRequest:
	if not isinstance(user, int):
		user = user.pk
	return __rpc.request({
	    "type": "create_profile",
	    "id": user,
	    "username": username
	})


@convert_to_pk
def get_friends(user: int) -> RPCRequest:
	return __rpc.request({"type": "get_friends", "id": user})


@convert_to_pk
def get_friend_invites(user: int) -> RPCRequest:
	return __rpc.request({"type": "get_friend_invites", "id": user})


@convert_to_pk
def invite_friend(invitee: int, inviter: int) -> None:
	__rpc.request_forget({
	    "type": "invite_friend",
	    "invitee": invitee,
	    "inviter": inviter
	})


@convert_to_pk
def accept_friend_invite(invitee: int, inviter: int) -> RPCRequest:
	return __rpc.request({
	    "type": "accept_friend_invite",
	    "invitee": invitee,
	    "inviter": inviter
	})


@convert_to_pk
def reject_friend_invite(invitee: int, inviter: int) -> RPCRequest:
	return __rpc.request({
	    "type": "reject_friend_invite",
	    "invitee": invitee,
	    "inviter": inviter
	})


@convert_to_pk
def remove_friend(removee: int, remover: int) -> RPCRequest:
	return __rpc.request({
	    "type": "remove_friend",
	    "removee": removee,
	    "remover": remover
	})


def set_username(user, username: str) -> RPCRequest:
	if not isinstance(user, int):
		user = user.pk
	return __rpc.request({
	    "type": "set_username",
	    "user": user,
	    "username": username
	})
