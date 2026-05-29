from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('users/', views.users_view, name='users'),
    path('room/<int:id>/', views.room_view, name='room'),
    path('room/<int:room_id>/voice/', views.voice_channel_view, name='voice_channel'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('message/<int:message_id>/delete/', views.delete_message_view, name='delete_message'),
    path('message/<int:message_id>/reaction/', views.toggle_reaction_view, name='toggle_reaction'),
    path('message/<int:message_id>/report/', views.report_user_view, name='report_user'),
    path('reports/', views.reports_view, name='reports'),
    path('reports/<int:report_id>/status/', views.update_report_status_view, name='update_report_status'),
    path('user/<int:user_id>/toggle-block/', views.toggle_block_view, name='toggle_block'),
    path('dm/start/<int:user_id>/', views.start_dm_view, name='start_dm'),
    path('message/<int:message_id>/edit/', views.edit_message_view, name='edit_message'),
    path('channels/create/', views.create_channel_view, name='create_channel'),
    path('channels/<int:room_id>/delete/', views.delete_channel_view, name='delete_channel'),
    path('channels/<int:room_id>/join/', views.join_channel_view, name='join_channel'),
    path('channels/<int:room_id>/leave/', views.leave_channel_view, name='leave_channel'),
    path('channels/search/', views.search_channels_view, name='search_channels'),
]