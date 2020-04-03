import sys
sys.path.append("..")

from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions
from django.http import HttpResponse, JsonResponse
from agw.models import Player
import datetime

from communications import profile
from communications.rpc import resolve
from communications.notifications import send_notification
from communications.presence import is_online
from communications import chat
from communications import team

from common.logger import *

times = []

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def get_my_profile(request):
	log_info(f"requesting own profile {request.user.pk}")
	info = resolve(profile.request_profile(request.user.pk))
	return JsonResponse(info, status=200)

@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def get_user_profile(request, pk):
	#log_info(f"requesting user profile {pk}")
	#start_time = time.time_ns()
	info = resolve(profile.request_profile(pk))
	#times.append(time.time_ns() - start_time)
	return JsonResponse(info, status=200)

@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def make_error(request):
	return HttpResponse(status=500)

@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def get_perf(request):
	return HttpResponse(sum(times)/len(times), status=200)

@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def get_config(request):
	if request.method == "GET":
		return Response({'chat': 'ws://25.64.141.174:8768', 'notification': 'ws://25.64.141.174:8767'})

def now():
	return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp() * 1000)

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def fetch_friends(request):
	friends = resolve(profile.get_friends(request.user))
	friend_objects = []
	print("GOT FRIENDS")
	friends = resolve([profile.request_profile(friend) for friend in friends])
	print(friends)
	for friend in friends:
		friend_objects.append({"id": friend["id"], "username": friend["username"], "last_seen": int((now()-friend["last_seen"])/1000), "is_online": resolve(is_online(friend["id"]))})
	print("RETURNING")
	return JsonResponse(friend_objects, safe=False)

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def add_friend(request, pk):
	if request.user.pk == pk:
		return HttpResponse(status=404)
	try:
		invitee = Player.objects.get(pk=pk)
	except Player.DoesNotExist:
		return HttpResponse(status=404)
	friends, friend_invites = resolve(profile.get_friends(request.user), profile.get_friend_invites(pk))
	print(friends)
	print(friend_invites)
	if pk in friends:
		send_notification(request.user, "already in friends", username=invitee.username)
		return HttpResponse(status=404)
	if request.user.pk in friend_invites:
		send_notification(request.user, "already in friend invites", username=invitee.username)
		return HttpResponse(status=404)
	send_notification(invitee, "friend invite", username=request.user.username, id=request.user.pk)
	send_notification(request.user, "friend invite sent", username=invitee.username)
	profile.invite_friend(pk, request.user)
	return HttpResponse()

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def remove_friend(request, pk):
	friends = resolve(profile.get_friends(request.user))
	if pk not in friends:
		return HttpResponse(status=403)
	send_notification(pk, "removed from friends", username=request.user.username)
	resolve(profile.remove_friend(pk, request.user))
	user_team = resolve(team.get_team_for_player(request.user))
	if pk in user_team["members"]:
		remove_from_team(pk)
	return HttpResponse()

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def accept_friend(request, pk):
	send_notification(pk, "friend invite accepted", username=request.user.username)
	resolve(profile.accept_friend_invite(request.user, pk))
	return HttpResponse()

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def reject_friend(request, pk):
	send_notification(pk, "friend invite declined", username=request.user.username)
	resolve(profile.reject_friend_invite(request.user, pk))
	return HttpResponse()

@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def check_user_exists(request, name):
	prof = resolve(profile.request_profile_by_name(name))
	if not prof:
		return HttpResponse({"exists": False}, status=200)
	return JsonResponse({"exists": True, "id": prof["id"]}, status=200)

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def retrieve_notifications(request):
	friend_reqs = resolve(profile.get_friend_invites(request.user))
	for friend in friend_reqs:
		username = Player.objects.get(pk=friend).username
		send_notification(request.user, "friend invite", username=username, id=friend)
	return HttpResponse()

@api_view(['POST'])
@permission_classes((permissions.IsAuthenticated,))
def send_chat_message(request):
	chat.send_chat_message(request.user.username, request.data["message"])
	return HttpResponse()

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def get_team(request):
	user_team = resolve(team.get_team_for_player(request.user))
	if not user_team:
		return JsonResponse([], safe=False)
	else:
		teammates = resolve([profile.request_profile(tm) for tm in user_team["members"]])
		leader = None
		for tm in teammates:
			if tm["id"] == user_team["leader"]:
				leader = tm
				break
		return JsonResponse({"leader": leader, "members": teammates})

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def invite_to_team(request, pk):
	user_team = team.get_or_create_team(request.user)
	if user_team["leader"] != request.user.pk:
		send_notification(request.user, "not the leader")
		return HttpResponse(status=403)
	if pk in user_team["invitees"]:
		send_notification(request.user, "already invited to team")
		return HttpResponse(status=412)
	if pk in user_team["members"]:
		send_notification(request.user, "already in team")
		return HttpResponse(status=412)
	team.invite_player_to_team(pk, user_team["pk"])
	send_notification(pk, "invited to team", id=user_team["pk"], inviter_name=request.user.username)
	send_notification(request.user, "invite sent", text="You have invited a player to your team")
	return HttpResponse()

def remove_from_team(pk, kicked=False):
	if not isinstance(pk, int):
		pk = pk.pk
	username = Player.objects.get(pk=pk).username
	user_team = resolve(team.get_team_for_player(pk))
	if not user_team:
		return
	team.remove_player_from_team(pk)
	if kicked:
		for member in user_team["members"]:
			if member != pk:
				send_notification(member, "teammate kicked", teammate_name=username)
		send_notification(pk, "kicked from team")
	else:
		for member in user_team["members"]:
			if member != pk:
				send_notification(member, "teammate left", teammate_name=username)
		send_notification(pk, "left team")

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def join_team(request, pk):
	user_team = resolve(team.get_team(pk))
	if not user_team:
		return HttpResponse(status=404)

	if request.user.pk in user_team["invitees"]:
		remove_from_team(request.user)
		for member in user_team["members"]:
			send_notification(member, "new teammate", teammate_name=request.user.username)
		send_notification(request.user, "team joined")
		team.add_player_to_team(request.user, user_team["pk"])
		return HttpResponse(status=200)

	return HttpResponse(status=400)

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def decline_invitation(request, pk):
	if request.method == "GET":
		user_team = resolve(team.get_team(pk))
		if not user_team:
			return HttpResponse(status=404)

		if request.user.pk in user_team["invitees"]:
			send_notification(user_team["leader"], "invitation declined", username=request.user.username)
			team.remove_player_from_invitations(request.user, user_team["pk"])
			return HttpResponse(status=200)

		return HttpResponse(status=400)

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def leave_team(request):
	if request.method == "GET":
		user_team = resolve(team.get_team_for_player(request.user))
		if not user_team:
			return HttpResponse(status=412)

		remove_from_team(request.user)
		return HttpResponse(status=200)

@api_view(['GET'])
@permission_classes((permissions.IsAuthenticated,))
def kick_from_team(request, pk):
	if request.method == "GET":
		user_team = resolve(team.get_team_for_player(pk))
		if not user_team:
			return HttpResponse(status=412)

		remove_from_team(pk, True)
		return HttpResponse(status=200)
