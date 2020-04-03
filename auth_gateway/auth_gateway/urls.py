from django.contrib import admin
from django.urls import path, include
from agw import views

urlpatterns = [
	path('admin/', admin.site.urls),
	path('auth/', include('rest_framework.urls')),

	path('api/v1/users/profile/', views.get_my_profile),

	path('api/v1/users/', include('rest_registration.api.urls')),
	path('api/v1/user/<int:pk>/', views.get_user_profile),
	path('api/v1/users/check_exists/<str:name>/', views.check_user_exists),

	path('api/v1/get_perf/', views.get_perf),
	path('api/v1/error/', views.make_error),

	path('api/v1/team/', views.get_team),
	path('api/v1/team/invite/<int:pk>/', views.invite_to_team),
	path('api/v1/team/join/<int:pk>/', views.join_team),
	path('api/v1/team/decline/<int:pk>/', views.decline_invitation),
	path('api/v1/team/leave/', views.leave_team),
	path('api/v1/team/kick/<int:pk>', views.kick_from_team),

	path('api/v1/server_config/', views.get_config),

	path('api/v1/notification/retrieve/', views.retrieve_notifications),

	path('api/v1/users/profile/friends/', views.fetch_friends),
	path('api/v1/users/profile/friends/add/<int:pk>/', views.add_friend),
	path('api/v1/users/profile/friends/remove/<int:pk>/', views.remove_friend),
	path('api/v1/users/profile/friends/accept/<int:pk>/', views.accept_friend),
	path('api/v1/users/profile/friends/decline/<int:pk>/', views.reject_friend),

	path('api/v1/chat/send/', views.send_chat_message),

]
