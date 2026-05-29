from django.db import models
from django.conf import settings



class Room(models.Model):
    name = models.CharField(max_length=100, blank=True)
    is_direct = models.BooleanField(default=False)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='rooms',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("manage_channels", "Can manage channels"),
        ]

    def __str__(self):
        if self.is_direct:
            return f"DM #{self.id}"
        return self.name



class Message(models.Model):
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='messages',
        null=True,
        blank=True
    )
    author = models.CharField(max_length=100, blank=True)
    content = models.TextField(blank=True)
    image = models.ImageField(upload_to='message_images/', blank=True, null=True)
    audio = models.FileField(upload_to='message_audio/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['created_at']
        permissions = [
            ("moderate_messages", "Can moderate messages"),
            ("block_users", "Can block users"),
        ]

    def __str__(self):
        username = self.user.username if self.user else self.author or "Unknown"
        return f"{username}: {self.content[:30]}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    bio = models.TextField(blank=True)
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True
    )
    is_blocked = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)

    def __str__(self):
        return f"Profil: {self.user.username}"

class UserReport(models.Model):
    STATUS_CHOICES = [
        ('new', 'Nowe'),
        ('reviewed', 'Sprawdzone'),
        ('rejected', 'Odrzucone'),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_reports'
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_reports'
    )
    message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports'
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Zgłoszenie: {self.reporter.username} -> {self.reported_user.username}"

class MessageReaction(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_reactions'
    )
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} {self.emoji}"

