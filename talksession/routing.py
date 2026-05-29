from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/presence/$', consumers.PresenceConsumer.as_asgi()),
    re_path(r'ws/voice/(?P<room_id>\d+)/$', consumers.VoiceConsumer.as_asgi()),
]