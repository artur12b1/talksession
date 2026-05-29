from django.contrib import admin
from .models import Room, Message, UserProfile, UserReport


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_direct', 'created_at')
    search_fields = ('name',)
    list_filter = ('is_direct', 'created_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'user', 'author', 'created_at', 'edited_at')
    search_fields = ('content', 'author', 'user__username')
    list_filter = ('created_at',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_blocked')
    search_fields = ('user__username', 'user__email')
    list_filter = ('is_blocked',)


@admin.register(UserReport)
class UserReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'reporter', 'reported_user', 'status', 'created_at')
    search_fields = ('reporter__username', 'reported_user__username', 'reason')
    list_filter = ('status', 'created_at')
    readonly_fields = ('reporter', 'reported_user', 'message', 'reason', 'created_at')