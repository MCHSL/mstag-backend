import datetime
import sys

from django.core.cache import caches
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from agw.models import Player  # type: ignore
from common.lazy import LazyPlayer, LazyTeam
from common.logger import *
from communications import chat, game, profile, team
from communications.notifications import send_notification
from communications.presence import is_online
from communications.rpc import resolve

sys.path.append("..")

times = []


def lazy_user(fn):
	def wrapper(request, *args, **kwargs):
		request.user = LazyPlayer(request.user.pk,
		                          precached_username=request.user.username)
		return fn(request, *args, **kwargs)

	return wrapper


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
def get_my_profile(request):
	log_info(f"requesting own profile {request.user.pk}")
	info = resolve(profile.request_profile(request.user.pk))
	return JsonResponse(info, status=200)


@api_view(['GET'])
@permission_classes((permissions.AllowAny, ))
def get_user_profile(request, user):
	info = resolve(profile.request_profile(user))
	return JsonResponse(info, status=200)


@api_view(['GET'])
@permission_classes((permissions.AllowAny, ))
def make_error(request):
	return HttpResponse(status=500)


@api_view(['GET'])
@permission_classes((permissions.AllowAny, ))
def get_perf(request):
	return HttpResponse(sum(times) / len(times), status=200)


@api_view(['GET'])
@permission_classes((permissions.AllowAny, ))
def get_config(request):
	return JsonResponse({
	    'chat': 'ws://25.64.141.174:8768',
	    'notification': 'ws://25.64.141.174:8767'
	})


def now():
	return int(
	    datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def fetch_friends(request):
	friend_objects = []
	for friend in request.user.friends:
		friend_objects.append({
		    "id": friend.pk,
		    "username": friend.username,
		    "last_seen": friend.last_seen_delta,
		    "is_online": friend.online
		})
	return JsonResponse(friend_objects, safe=False)


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def invite_friend(request, invitee):
	if request.user == invitee:
		return HttpResponse(status=403)
	if invitee in request.user.friends:
		request.user.notify("already in friends", username=invitee.username)
		return HttpResponse(status=412)
	print(request.user)
	print(invitee.friend_invites)
	if request.user in invitee.friend_invites:
		request.user.notify("already in friend invites",
		                    username=invitee.username)
		return HttpResponse(status=412)
	invitee.notify("friend invite",
	               username=request.user.username,
	               id=request.user.pk)
	request.user.notify("friend invite sent", username=invitee.username)
	profile.invite_friend(invitee, request.user)
	return HttpResponse()


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def remove_friend(request, removee):
	if removee not in request.user.friends:
		return HttpResponse(status=403)
	removee.notify("removed from friends", username=request.user.username)
	resolve(profile.remove_friend(removee, request.user))
	if request.user.team and removee in request.user.team.members:
		remove_from_team(removee)
	return HttpResponse()


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
def accept_friend(request, acceptee):
	resolve(profile.accept_friend_invite(request.user, acceptee))
	acceptee.notify("friend invite accepted", username=request.user.username)
	return HttpResponse()


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
def reject_friend(request, rejectee):
	resolve(profile.reject_friend_invite(request.user, rejectee))
	rejectee.notify("friend invite declined", username=request.user.username)
	return HttpResponse()


@api_view(['GET'])
@permission_classes((permissions.AllowAny, ))
def check_user_exists(request, name):
	prof = resolve(profile.request_profile_by_name(name))
	if not prof:
		return HttpResponse({"exists": False}, status=200)
	return JsonResponse({"exists": True, "id": prof["id"]}, status=200)


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
def retrieve_notifications(request):
	friend_reqs = resolve(profile.get_friend_invites(request.user))
	for friend in friend_reqs:
		username = Player.objects.get(pk=friend).username
		send_notification(request.user,
		                  "friend invite",
		                  username=username,
		                  id=friend)
	return HttpResponse()


def check_cooldown(ctype, who):
	try:
		if caches[ctype + "_cooldown"].get(who) <= time.time():
			caches[ctype + "_cooldown"].set(who, time.time() + 1)
			return True
		return False
	except TypeError:
		caches[ctype + "_cooldown"].set(who, time.time() + 1)
		return True


@api_view(['POST'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def send_global_chat_message(request):
	if check_cooldown("chat", request.user.username):
		request.user.chat_global(request.data["message"])
		return HttpResponse()
	return HttpResponse(status=429)


@api_view(['POST'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def send_team_chat_message(request):
	if check_cooldown("chat", request.user.username):
		request.user.chat_team(request.data["message"])
		return HttpResponse()
	return HttpResponse(status=429)


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def get_team(request):
	if not request.user.team:
		return JsonResponse([], safe=False)
	else:
		teammates = resolve([
		    profile.request_profile(tm)
		    for tm in request.user.team.member_pks()
		] + [profile.request_profile(request.user.team.leader)
		     ])  # Parallel profile lookup
		leader = teammates.pop()
		return JsonResponse({"leader": leader, "members": teammates})


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def invite_to_team(request, invitee):
	user_team = request.user.create_team()
	if user_team.leader != request.user:
		request.user.notify("not the leader")
		return HttpResponse(status=403)
	if invitee in user_team.invitees:
		request.user.notify("already invited to team")
		return HttpResponse(status=412)
	if invitee in user_team.members:
		request.user.notify("already in team")
		return HttpResponse(status=412)
	resolve(team.invite_player_to_team(invitee, user_team))
	invitee.notify("invited to team",
	               id=user_team.pk,
	               inviter_name=request.user.username)
	request.user.notify("invite sent",
	                    text="You have invited a player to your team")
	return HttpResponse()


def remove_from_team(pk, kicked=False):
	if not isinstance(pk, int):
		pk = pk.pk
	username = Player.objects.get(pk=pk).username
	user_team = resolve(team.get_team_for_player(pk))
	if not user_team:
		return
	resolve(team.remove_player_from_team(pk))
	if kicked:
		for member in user_team["members"]:
			if member != pk:
				send_notification(member,
				                  "teammate kicked",
				                  teammate_name=username)
				chat.send_direct_chat_message(
				    member, "*", "party", username + " has left your party.")
		send_notification(pk, "kicked from team")
	else:
		for member in user_team["members"]:
			if member != pk:
				send_notification(member,
				                  "teammate left",
				                  teammate_name=username)
				chat.send_direct_chat_message(
				    member, "*", "party", username + " has left your party.")
		send_notification(pk, "left team")


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def join_team(request, team_id):
	user_team = LazyTeam(team_id)
	if not user_team:
		return HttpResponse(status=404)

	print(user_team.invitees)
	if request.user in user_team.invitees:
		remove_from_team(request.user)
		resolve(team.add_player_to_team(request.user, user_team))
		for member in user_team.members:
			member.notify("new teammate", teammate_name=request.user.username)
			chat.send_direct_chat_message(
			    member, "*", "party",
			    request.user.username + " has joined your party.")
		request.user.notify("team joined")
		return HttpResponse(status=200)

	return HttpResponse(status=400)


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def decline_invitation(request, team_id):
	if request.method == "GET":
		user_team = LazyTeam(team_id)
		if not user_team:
			return HttpResponse(status=404)

		if request.user in user_team.invitees:
			user_team.leader.notify("invitation declined",
			                        username=request.user.username)
			resolve(
			    team.remove_player_from_invitations(request.user, user_team))
			return HttpResponse(status=200)

		return HttpResponse(status=400)


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def leave_team(request):
	if request.method == "GET":
		user_team = resolve(team.get_team_for_player(request.user))
		if not user_team:
			return HttpResponse(status=412)

		remove_from_team(request.user)
		return HttpResponse(status=200)


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def kick_from_team(request, victim):
	if request.method == "GET":
		user_team = victim.team
		if not user_team:
			return HttpResponse(status=412)

		remove_from_team(victim, True)
		return HttpResponse(status=200)


@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated, ))
@lazy_user
def request_game(request):
	if request.user.team:
		if request.user.team.leader != request.user:
			return HttpResponse(status=403)
		resolve(game.reserve_lobby(request.user.team.members))
		for member in request.user.team.members:
			member.notify("starting game", address="ws://25.64.141.174:8765/1")
	return HttpResponse("ws://25.64.141.174:8765/1")
