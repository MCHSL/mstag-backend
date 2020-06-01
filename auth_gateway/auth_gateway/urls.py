from django.contrib import admin
from django.urls import path, include
from agw import views
from django.urls import register_converter
from . import converters

register_converter(converters.LazyPlayerConverter, 'lazyplayer')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('rest_framework.urls')),
    path('api/v1/oauth/google/', views.login_google),
    #
    path('api/v1/users/profile/', views.get_my_profile),
    #
    path('api/v1/guest_login/', views.create_guest),
    path('api/v1/users/', include('rest_registration.api.urls')),
    path('api/v1/user/<int:user>/', views.get_user_profile),
    path('api/v1/users/check_exists/<str:name>/', views.check_user_exists),
    path('api/v1/users/set_username/', views.set_username),
    path('api/v1/users/online/', views.get_players_online),
    #
    path('api/v1/get_perf/', views.get_perf),
    path('api/v1/error/', views.make_error),
    #
    path('api/v1/team/', views.get_team),
    path('api/v1/team/invite/<lazyplayer:invitee>/', views.invite_to_team),
    path('api/v1/team/join/<int:team_id>/', views.join_team),
    path('api/v1/team/decline/<int:team_id>/', views.decline_invitation),
    path('api/v1/team/leave/', views.leave_team),
    path('api/v1/team/kick/<lazyplayer:victim>', views.kick_from_team),
    #
    path('api/v1/server_config/', views.get_config),
    #
    path('api/v1/notification/retrieve/', views.retrieve_notifications),
    #
    path('api/v1/users/profile/friends/', views.fetch_friends),
    path('api/v1/users/profile/friends/add/<lazyplayer:invitee>/',
         views.invite_friend),
    path('api/v1/users/profile/friends/remove/<lazyplayer:removee>/',
         views.remove_friend),
    path('api/v1/users/profile/friends/accept/<lazyplayer:acceptee>/',
         views.accept_friend),
    path('api/v1/users/profile/friends/decline/<lazyplayer:rejectee>/',
         views.reject_friend),
    #
    path('api/v1/chat/send/global/', views.send_global_chat_message),
    path('api/v1/chat/send/party/', views.send_team_chat_message),
    #
    path('api/v1/game/request/', views.request_game),
]
