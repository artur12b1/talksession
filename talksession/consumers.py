import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .models import Room, UserProfile


class PresenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add("presence", self.channel_name)
        await self.accept()

        await self.set_online_status(True)

        await self.channel_layer.group_send(
            "presence",
            {
                "type": "presence_update",
                "user_id": self.user.id,
                "is_online": True,
                "username": self.user.username,
            }
        )

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.set_online_status(False)

            await self.channel_layer.group_send(
                "presence",
                {
                    "type": "presence_update",
                    "user_id": self.user.id,
                    "is_online": False,
                    "username": self.user.username,
                }
            )

        await self.channel_layer.group_discard("presence", self.channel_name)

    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            "user_id": event["user_id"],
            "is_online": event["is_online"],
            "username": event["username"],
        }))

    @database_sync_to_async
    def set_online_status(self, value):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.is_online = value
        profile.save(update_fields=["is_online"])


class VoiceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"voice_{self.room_id}"

        if not self.user.is_authenticated:
            await self.close()
            return

        has_access = await self.user_has_access()

        if not has_access:
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "voice_signal",
                "data": {
                    "type": "user_joined",
                    "from_user_id": self.user.id,
                    "from_username": self.user.username,
                }
            }
        )

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "voice_signal",
                    "data": {
                        "type": "user_left",
                        "from_user_id": self.user.id,
                        "from_username": self.user.username,
                    }
                }
            )

        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        data["from_user_id"] = self.user.id
        data["from_username"] = self.user.username

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "voice_signal",
                "data": data,
            }
        )

    async def voice_signal(self, event):
        data = event["data"]

        if data.get("from_user_id") == self.user.id:
            return

        await self.send(text_data=json.dumps(data))

    @database_sync_to_async
    def user_has_access(self):
        try:
            room = Room.objects.get(id=self.room_id)
        except Room.DoesNotExist:
            return False

        return room.participants.filter(id=self.user.id).exists()
    
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = f"user_{self.user.id}_notifications"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def new_message_notification(self, event):
        await self.send(text_data=json.dumps({
            "type": "new_message",
            "room_id": event["room_id"],
            "room_name": event["room_name"],
            "sender": event["sender"],
            "preview": event["preview"],
        }))

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"chat_{self.room_id}"

        if not self.user.is_authenticated:
            await self.close()
            return

        has_access = await self.user_has_access()

        if not has_access:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            "message_id": event["message_id"],
            "user_id": event["user_id"],
            "username": event["username"],
            "content": event["content"],
            "image_url": event["image_url"],
            "audio_url": event["audio_url"],
            "created_at": event["created_at"],
        }))

    @database_sync_to_async
    def user_has_access(self):
        try:
            room = Room.objects.get(id=self.room_id)
        except Room.DoesNotExist:
            return False

        return room.participants.filter(id=self.user.id).exists()
