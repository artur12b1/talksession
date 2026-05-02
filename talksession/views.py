import os
from PIL import Image
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.db.models import Count
from .models import Room, Message, UserProfile
from .forms import UserProfileForm


def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def is_user_blocked(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return False
    profile = get_or_create_profile(user)
    return profile.is_blocked


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None

    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            profile = get_or_create_profile(user)

            if profile.is_blocked and not user.is_superuser:
                error = 'To konto zostało zablokowane przez moderatora lub administratora.'
            else:
                login(request, user)
                return redirect('dashboard')
        else:
            error = 'Nieprawidłowy login lub hasło.'

    return render(request, 'talksession/login.html', {
        'error': error
    })


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None

    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not username or not email or not password1 or not password2:
            error = 'Wypełnij wszystkie pola.'
        elif User.objects.filter(username=username).exists():
            error = 'Taki login już istnieje.'
        elif User.objects.filter(email=email).exists():
            error = 'Taki adres e-mail już istnieje.'
        elif password1 != password2:
            error = 'Hasła nie są takie same.'
        else:
            try:
                temp_user = User(username=username, email=email)
                validate_password(password1, user=temp_user)
            except ValidationError as e:
                error = " ".join(e.messages)
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1
                )
                UserProfile.objects.get_or_create(user=user)

                default_group, _ = Group.objects.get_or_create(name='Użytkownik')
                user.groups.add(default_group)

                login(request, user)
                return redirect('dashboard')

    return render(request, 'talksession/register.html', {
        'error': error
    })


def logout_view(request):
    logout(request)
    return redirect('login')

def attach_role_badge(user):
    if not user:
        return

    user.role_badge = None
    user.role_badge_class = ''

    if user.is_superuser:
        user.role_badge = 'ADMIN'
        user.role_badge_class = 'admin'
    elif user.groups.filter(name='Moderator').exists():
        user.role_badge = 'MOD'
        user.role_badge_class = 'moderator'

@login_required(login_url='login')
def dashboard_view(request):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    get_or_create_profile(request.user)

    channel_items = build_channel_items()

    for item in channel_items:
        item['is_member'] = item['room'].participants.filter(id=request.user.id).exists()

    channel_items.sort(
        key=lambda item: (
            not item['is_member'],
            -(item['last_message'].created_at.timestamp() if item['last_message'] else item['room'].created_at.timestamp())
        )
    )
    
    for item in channel_items:
        item['is_member'] = item['room'].participants.filter(id=request.user.id).exists()

    dm_items = build_dm_items_for_user(request.user)
    
    for item in dm_items:
        attach_role_badge(item['other_user'])

    existing_dm_user_ids = [item['other_user'].id for item in dm_items]
 
    users = (
        User.objects
        .exclude(id=request.user.id)
        .exclude(username__iexact=request.user.username)
        .exclude(id__in=existing_dm_user_ids)
        .order_by('username')
    )

    for user in users:
        get_or_create_profile(user)
        attach_role_badge(user)

    return render(request, 'talksession/dashboard.html', {
        'channel_items': channel_items,
        'dm_items': dm_items,
        'users': users,
    })

@login_required(login_url='login')
def room_view(request, id):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    room = get_object_or_404(Room, id=id)

    is_channel_member = False
    if not room.is_direct:
        is_channel_member = room.participants.filter(id=request.user.id).exists()

    if room.is_direct and request.user not in room.participants.all():
        return HttpResponseForbidden("Nie masz dostępu do tej rozmowy.")

    get_or_create_profile(request.user)

    channel_items = build_channel_items()

    for item in channel_items:
        item['is_member'] = item['room'].participants.filter(id=request.user.id).exists()

    channel_items.sort(
        key=lambda item: (
            not item['is_member'],
            -(item['last_message'].created_at.timestamp() if item['last_message'] else item['room'].created_at.timestamp())
        )
    )


    for item in channel_items:
        item['is_member'] = item['room'].participants.filter(id=request.user.id).exists()

    dm_items = build_dm_items_for_user(request.user)

    for item in dm_items:
        attach_role_badge(item['other_user'])
    
    upload_error = None

    if request.method == 'POST':
        if not room.is_direct and not is_channel_member:
            upload_error = "Aby wysyłać wiadomości, dołącz do kanału."
        else:
            content = request.POST.get('content', '').strip()
            image = request.FILES.get('image')
            audio = request.FILES.get('audio')
            upload_error = None
     
            if image:
                upload_error = validate_uploaded_image(image)
            if not upload_error and audio:
                upload_error = validate_uploaded_audio(audio)
     
            if not upload_error and (content or image or audio):
                Message.objects.create(
                    room=room,
                    user=request.user,
                    author=request.user.username,
                    content=content,
                    image=image,
                    audio=audio
                )
                return redirect('room', id=room.id)
     
            if not upload_error and not content and not image and not audio:
                upload_error = "Wiadomość musi zawierać tekst, obrazek lub plik audio."


    chat_messages = room.messages.all().order_by('created_at')

    for message in chat_messages:
        if message.user:
            attach_role_badge(message.user)

    if room.is_direct:
        other_user = room.participants.exclude(id=request.user.id).first()
        if other_user:
            get_or_create_profile(other_user)
        room_title = other_user.username if other_user else "DM"
    else:
        room_title = f"# {room.name}"

    is_channel_member = False
    if not room.is_direct:
        is_channel_member = room.participants.filter(id=request.user.id).exists()

    return render(request, 'talksession/room.html', {
        'room': room,
        'channel_items': channel_items,
        'dm_items': dm_items,
        'chat_messages': chat_messages,
        'room_title': room_title,
        'upload_error': upload_error,
        'is_channel_member': is_channel_member,
    })

@login_required(login_url='login')
def profile_view(request):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    profile = get_or_create_profile(request.user)

    return render(request, 'talksession/profile.html', {
        'profile': profile
    })

@login_required(login_url='login')
def edit_profile_view(request):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    profile = get_or_create_profile(request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)

    return render(request, 'talksession/edit_profile.html', {
        'form': form,
        'profile': profile
    })


@login_required(login_url='login')
def delete_message_view(request, message_id):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    message = get_object_or_404(Message, id=message_id)
    room_id = message.room.id

    if request.method != 'POST':
        return HttpResponseForbidden("Nieprawidłowa metoda żądania.")

    is_owner = message.user == request.user
    can_moderate = request.user.is_superuser or request.user.has_perm('talksession.moderate_messages')

    if not is_owner and not can_moderate:
        return HttpResponseForbidden("Nie masz uprawnień do usunięcia tej wiadomości.")

    message.delete()
    return redirect('room', id=room_id)

@login_required(login_url='login')
@permission_required('talksession.block_users', raise_exception=True)
def toggle_block_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id)

    if request.method != 'POST':
        return HttpResponseForbidden("Nieprawidłowa metoda żądania.")

    if target_user == request.user:
        return HttpResponseForbidden("Nie możesz zablokować własnego konta.")

    if target_user.is_superuser:
        return HttpResponseForbidden("Nie możesz zablokować administratora.")

    profile = get_or_create_profile(target_user)
    profile.is_blocked = not profile.is_blocked
    profile.save()

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)

    return redirect('dashboard')

def get_or_create_direct_room(user1, user2):
    candidate_rooms = (
        Room.objects
        .filter(is_direct=True, participants=user1)
        .prefetch_related('participants')
    )

    for room in candidate_rooms:
        participant_ids = set(room.participants.values_list('id', flat=True))
        if participant_ids == {user1.id, user2.id}:
            return room

    room = Room.objects.create(
        name='',
        is_direct=True
    )
    room.participants.add(user1, user2)
    return room

@login_required(login_url='login')
def start_dm_view(request, user_id):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    target_user = get_object_or_404(User, id=user_id)

    # blokada pisania do samego siebie
    if target_user.id == request.user.id:
        return redirect('dashboard')

    room = get_or_create_direct_room(request.user, target_user)
    return redirect('room', id=room.id)

def build_dm_items_for_user(user):
    dm_rooms = (
        Room.objects
        .filter(is_direct=True, participants=user)
        .prefetch_related('participants', 'messages')
    )

    dm_items = []
    seen_other_users = set()

    for dm_room in dm_rooms:
        other_user = dm_room.participants.exclude(id=user.id).first()

        if not other_user:
            continue

        if other_user.id in seen_other_users:
            continue

        seen_other_users.add(other_user.id)
        get_or_create_profile(other_user)

        last_message = dm_room.messages.order_by('-created_at').first()

        dm_items.append({
            'room': dm_room,
            'other_user': other_user,
            'last_message': last_message,
        })

    dm_items.sort(
        key=lambda item: item['last_message'].created_at if item['last_message'] else item['room'].created_at,
        reverse=True
    )

    return dm_items

def build_channel_items():
    channel_rooms = Room.objects.filter(is_direct=False).prefetch_related('messages')

    channel_items = []

    for channel_room in channel_rooms:
        last_message = channel_room.messages.order_by('-created_at').first()

        channel_items.append({
            'room': channel_room,
            'last_message': last_message,
        })

    channel_items.sort(
        key=lambda item: item['last_message'].created_at if item['last_message'] else item['room'].created_at,
        reverse=True
    )

    return channel_items

@login_required(login_url='login')
def edit_message_view(request, message_id):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    message = get_object_or_404(Message, id=message_id)
    room_id = message.room.id

    is_owner = message.user == request.user
    can_moderate = request.user.is_superuser or request.user.has_perm('talksession.moderate_messages')

    if not is_owner and not can_moderate:
        return HttpResponseForbidden("Nie masz uprawnień do edycji tej wiadomości.")

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()

        if content and content != message.content:
            message.content = content
            message.edited_at = timezone.now()
            message.save()

        return redirect('room', id=room_id)

    return render(request, 'talksession/edit_message.html', {
        'message': message,
        'room_id': room_id,
    })

def validate_uploaded_image(uploaded_file):
    if not uploaded_file:
        return None

    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    max_size_mb = 5
    max_size_bytes = max_size_mb * 1024 * 1024
    max_width = 4096
    max_height = 4096

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in allowed_extensions:
        return "Dozwolone formaty obrazów: JPG, JPEG, PNG, GIF, WEBP."

    if uploaded_file.size > max_size_bytes:
        return f"Plik jest za duży. Maksymalny rozmiar to {max_size_mb} MB."

    content_type = getattr(uploaded_file, 'content_type', '')
    if content_type and not content_type.startswith('image/'):
        return "Przesłany plik nie jest obrazem."

    try:
        img = Image.open(uploaded_file)
        img.verify()
    except Exception:
        return "Nie udało się odczytać obrazu. Plik może być uszkodzony lub niepoprawny."

    uploaded_file.seek(0)

    try:
        img = Image.open(uploaded_file)
        width, height = img.size
    except Exception:
        return "Nie udało się odczytać wymiarów obrazu."

    uploaded_file.seek(0)

    if width > max_width or height > max_height:
        return f"Obraz ma zbyt duże wymiary. Maksimum to {max_width}x{max_height}px."

    return None

def validate_uploaded_audio(uploaded_file):
    if not uploaded_file:
        return None

    allowed_extensions = {'.mp3', '.wav', '.ogg', '.m4a', '.webm'}
    max_size_mb = 10
    max_size_bytes = max_size_mb * 1024 * 1024

    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in allowed_extensions:
        return "Dozwolone formaty audio: MP3, WAV, OGG, M4A, WEBM."

    if uploaded_file.size > max_size_bytes:
        return f"Plik audio jest za duży. Maksymalny rozmiar to {max_size_mb} MB."

    content_type = getattr(uploaded_file, 'content_type', '')
    if content_type and not content_type.startswith('audio/'):
        return "Przesłany plik nie wygląda na plik audio."

    return None

@login_required(login_url='login')
def join_channel_view(request, room_id):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    room = get_object_or_404(Room, id=room_id, is_direct=False)

    if request.method != 'POST':
        return HttpResponseForbidden("Nieprawidłowa metoda żądania.")

    room.participants.add(request.user)
    messages.success(request, f'Dołączono do kanału „{room.name}”.')
    return redirect('room', id=room.id)

@login_required(login_url='login')
def leave_channel_view(request, room_id):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    room = get_object_or_404(Room, id=room_id, is_direct=False)

    if request.method != 'POST':
        return HttpResponseForbidden("Nieprawidłowa metoda żądania.")

    if room.participants.filter(id=request.user.id).exists():
        room.participants.remove(request.user)
        messages.success(request, f'Opuszczono kanał „{room.name}”.')
    else:
        messages.info(request, 'Nie należysz do tego kanału.')

    return redirect('dashboard')

@login_required(login_url='login')
@permission_required('talksession.manage_channels', raise_exception=True)
def create_channel_view(request):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    if request.method != 'POST':
        return redirect('dashboard')

    channel_name = request.POST.get('channel_name', '').strip()
    next_url = request.POST.get('next', 'dashboard')

    if not channel_name:
        messages.error(request, 'Podaj nazwę kanału.')
        return redirect(next_url)

    if Room.objects.filter(is_direct=False, name__iexact=channel_name).exists():
        messages.error(request, 'Kanał o takiej nazwie już istnieje.')
        return redirect(next_url)

    room = Room.objects.create(
        name=channel_name,
        is_direct=False
    )
    room.participants.add(request.user)

    messages.success(request, f'Utworzono kanał „{room.name}”.')
    return redirect('room', id=room.id)

@login_required(login_url='login')
@permission_required('talksession.manage_channels', raise_exception=True)
def delete_channel_view(request, room_id):
    if is_user_blocked(request.user):
        logout(request)
        return redirect('login')

    room = get_object_or_404(Room, id=room_id, is_direct=False)

    if request.method != 'POST':
        return HttpResponseForbidden("Nieprawidłowa metoda żądania.")

    room_name = room.name
    room.delete()

    messages.success(request, f'Usunięto kanał „{room_name}”.')
    return redirect('dashboard')

def custom_404_view(request, exception):
    return render(request, 'talksession/404.html', status=404)