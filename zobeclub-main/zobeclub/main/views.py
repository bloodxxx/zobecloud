from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import Http404, JsonResponse, FileResponse, HttpResponseNotFound
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Max
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from datetime import timedelta
import os
import json

from .models import (
    Track, Genre, Activity, UserProfile, Follow, CommentLike,
    PremiumSubscription, TrackLike, Notification,
    Playlist, PlaylistTrack, TrackComment,
    Chat, Message, ChatMembership, SearchQuery,
    Album, TrackPlay, Block,
)

# список публичных плейлистов
def playlist_list(request):
    playlists = Playlist.objects.filter(
        visibility='public'
    ).select_related('user__profile').annotate(
        tracks_count=Count('tracks')
    ).order_by('-updated_at')

    context = {
        'title': 'Плейлисты',
        'playlists': playlists,
    }
    return render(request, 'main/playlist_list.html', context)

# главная страница
def home(request):
    now = timezone.now()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # публичные вышедшие треки
    public_qs = Track.objects.filter(
        visibility='public'
    ).filter(
        Q(release_at__isnull=True) | Q(release_at__lte=now)
    ).select_related('user__profile')

    # последние загрузки: альбомы показываем как один элемент
    _raw = public_qs.select_related('album').order_by('-uploaded_at')[:30]
    _seen_albums = set()
    recent_items = []
    for _t in _raw:
        if _t.album_id:
            if _t.album_id not in _seen_albums:
                _seen_albums.add(_t.album_id)
                recent_items.append({'is_album': True, 'album': _t.album, 'track': _t})
        else:
            recent_items.append({'is_album': False, 'track': _t})
        if len(recent_items) >= 8:
            break

    # топ за день / неделю / месяц по TrackPlay
    top_day = public_qs.annotate(
        period_plays=Count('plays', filter=Q(plays__created_at__gte=day_ago))
    ).order_by('-period_plays', '-plays_count')[:10]

    top_week = public_qs.annotate(
        period_plays=Count('plays', filter=Q(plays__created_at__gte=week_ago))
    ).order_by('-period_plays', '-plays_count')[:10]

    top_month = public_qs.annotate(
        period_plays=Count('plays', filter=Q(plays__created_at__gte=month_ago))
    ).order_by('-period_plays', '-plays_count')[:10]

    # featured = топ за неделю
    featured_track = top_week.first()

    artists = User.objects.filter(
        track__isnull=False
    ).distinct().annotate(
        tracks_count=Count('track'),
        total_plays=Sum('track__plays_count')
    ).order_by('-tracks_count')[:6]

    for artist in artists:
        try:
            if artist.profile.avatar and hasattr(artist.profile.avatar, 'url'):
                artist.avatar_url = artist.profile.avatar.url
            else:
                artist.avatar_url = '/static/images/default-avatar.png'
        except:
            artist.avatar_url = '/static/images/default-avatar.png'

    total_tracks = Track.objects.count()
    total_artists = User.objects.filter(track__isnull=False).distinct().count()
    total_plays = Track.objects.aggregate(total=Sum('plays_count'))['total'] or 0

    context = {
        'recent_items': recent_items,
        'top_tabs': [('Day', top_day), ('Week', top_week), ('Month', top_month)],
        'artists': artists,
        'total_tracks': total_tracks,
        'total_artists': total_artists,
        'total_plays': total_plays,
        'featured_track': featured_track,
    }

    return render(request, 'main/home.html', context)

# детальная страница трека
def track_detail(request, pk):
    track = get_object_or_404(Track.objects.select_related('album'), pk=pk)

    comments = track.comments.all().select_related('user__profile')

    user_liked = False
    user_liked_comments = []

    if request.user.is_authenticated:
        user_liked = TrackLike.objects.filter(
            user=request.user,
            track=track
        ).exists()

        try:
            user_liked_comments = list(
                CommentLike.objects.filter(
                    user=request.user,
                    comment__in=comments,
                    is_like=True
                ).values_list('comment_id', flat=True)
            )
        except:
            user_liked_comments = []

    likes_count = TrackLike.objects.filter(track=track).count()

    context = {
        'track': track,
        'comments': comments,
        'user_liked': user_liked,
        'user_liked_comments': user_liked_comments,
        'likes_count': likes_count,
    }

    return render(request, 'main/track_detail.html', context)

# поиск треков и пользователей
def search_view(request):
    query = request.GET.get('q', '').strip()
    filter_type = request.GET.get('type', 'all')
    results = {'tracks': [], 'users': []}

    if query:
        SearchQuery.record(query)

        tracks = Track.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query),
            visibility='public'
        ).select_related('user__profile').order_by('-plays_count')[:30]

        users = User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).exclude(username='admin').select_related('profile')[:12]

        results['tracks'] = tracks
        results['users'] = users

    popular_queries = SearchQuery.objects.order_by('-count')[:12]

    context = {
        'query': query,
        'filter_type': filter_type,
        'results': results,
        'tracks_count': len(results['tracks']),
        'users_count': len(results['users']),
        'popular_queries': popular_queries,
    }
    return render(request, 'main/search.html', context)

# авторизация пользователя
def user_login(request):
    if request.user.is_authenticated:
        return redirect('profile')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Добро пожаловать, {user.username}!")

            next_url = request.GET.get('next', 'profile')
            return redirect(next_url)
        else:
            messages.error(request, "Неправильное имя пользователя или пароль.")
    else:
        form = AuthenticationForm()
    return render(request, 'main/login.html', {'form': form})

# выход из системы
def user_logout(request):
    if request.user.is_authenticated:
        username = request.user.username
        logout(request)
        messages.info(request, f"До свидания, {username}! Вы вышли из аккаунта.")
    return redirect('home')

# регистрация пользователя
def register(request):
    if request.user.is_authenticated:
        return redirect('profile')

    if request.method == 'POST':
        # Проверяем обязательное согласие с лицензионным договором
        if not request.POST.get('license_accepted'):
            messages.error(request, 'Необходимо принять лицензионное соглашение для регистрации.')
            form = UserCreationForm(request.POST)
            return render(request, 'main/register.html', {'form': form})

        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            email = request.POST.get('email', '').strip()
            if email:
                user.email = email
            user.save()
            # Сохраняем дату и время принятия лицензионного соглашения
            from django.utils import timezone as tz
            profile = user.profile
            profile.terms_accepted_at = tz.now()
            profile.save(update_fields=['terms_accepted_at'])
            login(request, user)
            messages.success(request, f"Добро пожаловать в ZobeCloud, {user.username}! Регистрация прошла успешно!")
            return redirect('profile')
        else:
            # показываем конкретные ошибки каждого поля
            for field, errors in form.errors.items():
                field_label = {'username': 'Имя пользователя', 'password1': 'Пароль', 'password2': 'Подтверждение пароля'}.get(field, field)
                for error in errors:
                    messages.error(request, f"{field_label}: {error}")
    else:
        form = UserCreationForm()
    return render(request, 'main/register.html', {'form': form})

# загрузка трека
@login_required(login_url='/login/')
def upload_track(request):
    if request.method == 'POST':
        try:
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            cover = request.FILES.get('cover')
            audio_file = request.FILES.get('audio_file')

            if not title or not audio_file:
                messages.error(request, 'Название трека и аудиофайл обязательны!')
                return redirect('profile')

            if not audio_file.name.lower().endswith('.mp3'):
                messages.error(request, 'Поддерживается только формат MP3!')
                return redirect('profile')

            if audio_file.size > 15 * 1024 * 1024:
                messages.error(request, 'Размер аудиофайла не должен превышать 15MB!')
                return redirect('profile')

            if cover and cover.size > 5 * 1024 * 1024:
                messages.error(request, 'Размер обложки не должен превышать 5MB!')
                return redirect('profile')

            if not request.user.profile.is_premium:
                week_ago = timezone.now() - timedelta(days=7)
                weekly_uploads = Track.objects.filter(
                    user=request.user,
                    uploaded_at__gte=week_ago
                ).count()
                if weekly_uploads >= 5:
                    messages.error(request, 'Бесплатный аккаунт позволяет загружать не более 5 треков в неделю. Оформите Premium для безлимитной загрузки!')
                    return redirect('profile')

            visibility = request.POST.get('visibility', 'public')
            genre_id = request.POST.get('genre')
            release_at_str = request.POST.get('release_at', '').strip()
            album_id = request.POST.get('album_id', '').strip()

            release_at = None
            if release_at_str:
                try:
                    from django.utils.dateparse import parse_datetime
                    release_at = parse_datetime(release_at_str)
                    if release_at and timezone.is_naive(release_at):
                        release_at = timezone.make_aware(release_at)
                except Exception:
                    release_at = None

            genre = None
            if genre_id:
                try:
                    genre = Genre.objects.get(id=genre_id)
                except Genre.DoesNotExist:
                    pass

            album = None
            if album_id:
                try:
                    album = Album.objects.get(id=album_id, user=request.user)
                except Album.DoesNotExist:
                    pass

            track = Track.objects.create(
                title=title,
                description=description,
                audio_file=audio_file,
                cover=cover,
                user=request.user,
                visibility=visibility,
                genre=genre,
                album=album,
                release_at=release_at,
            )

            if release_at and release_at > timezone.now():
                Activity.objects.create(
                    user=request.user,
                    activity_type='album_release',
                    track=track,
                )
                messages.success(request, f'Трек "{title}" запланирован на {release_at.strftime("%d.%m.%Y %H:%M")}!')
            else:
                Activity.objects.create(
                    user=request.user,
                    activity_type='track_upload',
                    track=track,
                )
                messages.success(request, f'Трек "{title}" успешно загружен!')
            return redirect('profile')

        except Exception as e:
            messages.error(request, f'Ошибка при загрузке трека: {str(e)}')
            return redirect('profile')

    return redirect('profile')

# создание альбома
@login_required(login_url='/login/')
def upload_album(request):
    if request.method != 'POST':
        return redirect('profile')
    try:
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'Название альбома обязательно!')
            return redirect('profile')

        description = request.POST.get('description', '')
        cover = request.FILES.get('cover')
        visibility = request.POST.get('visibility', 'public')
        release_at_str = request.POST.get('release_at', '').strip()

        if cover and cover.size > 5 * 1024 * 1024:
            messages.error(request, 'Размер обложки не должен превышать 5MB!')
            return redirect('profile')

        release_at = None
        if release_at_str:
            try:
                from django.utils.dateparse import parse_datetime
                release_at = parse_datetime(release_at_str)
                if release_at and timezone.is_naive(release_at):
                    release_at = timezone.make_aware(release_at)
            except Exception:
                release_at = None

        album = Album.objects.create(
            title=title,
            description=description,
            cover=cover,
            user=request.user,
            visibility=visibility,
            release_at=release_at,
        )

        # загружаем треки из шага 2 (используем обложку альбома для каждого)
        audio_files = request.FILES.getlist('audio_files')
        track_names = request.POST.getlist('track_names')
        for i, af in enumerate(audio_files):
            if not af.name.lower().endswith('.mp3'):
                continue
            if i < len(track_names) and track_names[i].strip():
                track_title = track_names[i].strip()
            else:
                track_title = os.path.splitext(af.name)[0]
            Track.objects.create(
                title=track_title,
                audio_file=af,
                cover=album.cover,
                user=request.user,
                visibility=visibility,
                album=album,
                release_at=release_at,
            )

        if release_at and release_at > timezone.now():
            Activity.objects.create(
                user=request.user,
                activity_type='album_release',
                album=album,
            )
            messages.success(request, f'Альбом "{title}" запланирован на {release_at.strftime("%d.%m.%Y %H:%M")}!')
        else:
            Activity.objects.create(
                user=request.user,
                activity_type='album_upload',
                album=album,
            )
            messages.success(request, f'Альбом "{title}" создан!')

        return redirect('album_detail', pk=album.pk)

    except Exception as e:
        messages.error(request, f'Ошибка: {str(e)}')
        return redirect('profile')


# страница альбома
def album_detail(request, pk):
    album = get_object_or_404(Album, pk=pk)

    # приватный альбом видит только владелец
    if album.visibility == 'private' and album.user != request.user:
        raise Http404

    # отложенный релиз — скрыт для всех кроме владельца
    if not album.is_released and album.user != request.user:
        raise Http404

    tracks = album.tracks.filter(
        Q(release_at__isnull=True) | Q(release_at__lte=timezone.now())
    ).select_related('user__profile').order_by('sort_order', 'uploaded_at')

    if album.user == request.user:
        tracks = album.tracks.select_related('user__profile').order_by('sort_order', 'uploaded_at')

    is_owner = album.user == request.user
    user_tracks = []
    if is_owner:
        user_tracks = Track.objects.filter(user=request.user).order_by('-uploaded_at')

    return render(request, 'main/album_detail.html', {
        'album': album,
        'tracks': tracks,
        'is_owner': is_owner,
        'user_tracks': user_tracks,
    })


# удаление альбома
@login_required(login_url='/login/')
def delete_album(request, pk):
    album = get_object_or_404(Album, pk=pk, user=request.user)
    if request.method == 'POST':
        title = album.title
        album.delete()
        messages.success(request, f'Альбом "{title}" удалён.')
    return redirect('profile')


# редактирование альбома
@login_required(login_url='/login/')
def edit_album(request, pk):
    album = get_object_or_404(Album, pk=pk, user=request.user)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if title:
            album.title = title
            album.description = request.POST.get('description', '').strip()
            album.visibility = request.POST.get('visibility', 'public')
            if request.FILES.get('cover'):
                album.cover = request.FILES['cover']
            release_at_str = request.POST.get('release_at', '').strip()
            if release_at_str:
                from django.utils.dateparse import parse_datetime
                dt = parse_datetime(release_at_str)
                if dt and timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                album.release_at = dt
            else:
                album.release_at = None
            album.save()
            messages.success(request, 'Альбом обновлён.')
    return redirect('album_detail', pk=pk)


# добавить трек в альбом
@login_required(login_url='/login/')
def add_track_to_album(request, album_pk, track_id):
    if request.method == 'POST':
        album = get_object_or_404(Album, pk=album_pk, user=request.user)
        track = get_object_or_404(Track, pk=track_id, user=request.user)
        track.album = album
        track.save(update_fields=['album'])
    return redirect('album_detail', pk=album_pk)


# убрать трек из альбома
@login_required(login_url='/login/')
def remove_track_from_album(request, album_pk, track_id):
    if request.method == 'POST':
        album = get_object_or_404(Album, pk=album_pk, user=request.user)
        track = get_object_or_404(Track, pk=track_id, album=album, user=request.user)
        track.album = None
        track.save(update_fields=['album'])
    return redirect('album_detail', pk=album_pk)


# сохранить порядок треков в альбоме
@login_required(login_url='/login/')
def reorder_album_tracks(request, album_pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    album = get_object_or_404(Album, pk=album_pk, user=request.user)
    try:
        data = json.loads(request.body)
        ids = data.get('order', [])
        for i, track_id in enumerate(ids):
            Track.objects.filter(id=int(track_id), album=album).update(sort_order=i)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# редактирование трека
@login_required(login_url='/login/')
def edit_track(request, pk):
    track = get_object_or_404(Track, pk=pk)

    if track.user != request.user:
        messages.error(request, "У вас нет прав для редактирования этого трека.")
        return redirect('public_profile', username=track.user.username)

    if request.method == 'POST':
        try:
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            cover = request.FILES.get('cover')

            if not title:
                messages.error(request, 'Название трека обязательно!')
                return redirect('profile')

            if cover and cover.size > 5 * 1024 * 1024:
                messages.error(request, 'Размер обложки не должен превышать 5MB!')
                return redirect('profile')

            old_title = track.title

            track.title = title
            track.description = description

            if cover:
                if track.cover:
                    if os.path.isfile(track.cover.path):
                        os.remove(track.cover.path)

                track.cover = cover

            track.save()

            if old_title != title:
                messages.success(request, f'Трек "{old_title}" переименован в "{title}" и обновлен!')
            else:
                messages.success(request, f'Трек "{title}" успешно обновлен!')

            return redirect('profile')

        except Exception as e:
            messages.error(request, f'Ошибка при обновлении трека: {str(e)}')
            return redirect('profile')

    return redirect('profile')

# скачивание лицензионного соглашения
def download_license(request):
    from django.conf import settings
    pdf_path = os.path.join(settings.MEDIA_ROOT, 'docs', 'ЛИЦЕНЗИОННЫЙ ДОГОВОР ZobeCloud.pdf')
    if not os.path.exists(pdf_path):
        return HttpResponseNotFound('Файл не найден')
    response = FileResponse(
        open(pdf_path, 'rb'),
        content_type='application/pdf',
        as_attachment=True,
        filename='Лицензионный договор ZobeCloud.pdf'
    )
    return response

# ajax проверка доступности имени пользователя
def check_username_availability(request):
    username = request.GET.get('username', '').strip()

    if not username:
        return JsonResponse({'available': False, 'message': 'Имя пользователя не может быть пустым'})

    if len(username) < 3:
        return JsonResponse({'available': False, 'message': 'Имя пользователя должно содержать минимум 3 символа'})

    if User.objects.filter(username=username).exists():
        return JsonResponse({'available': False, 'message': 'Это имя пользователя уже занято'})

    return JsonResponse({'available': True, 'message': 'Имя пользователя доступно'})

# api статистики платформы
def get_platform_stats_api(request):
    try:
        total_tracks = Track.objects.count()
        total_artists = User.objects.filter(track__isnull=False).distinct().count()
        total_plays = Track.objects.aggregate(
            total=Sum('plays_count')
        )['total'] or 0

        online_users = UserProfile.objects.filter(
            last_seen__gte=timezone.now() - timedelta(minutes=10)
        ).count()

        return JsonResponse({
            'success': True,
            'total_tracks': total_tracks,
            'total_artists': total_artists,
            'total_plays': total_plays,
            'online_users': online_users,
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

# загрузка аватара
@login_required(login_url='/login/')
def upload_avatar(request):
    if request.method == 'POST':
        try:
            avatar_file = request.FILES.get('avatar')

            if not avatar_file:
                return JsonResponse({
                    'success': False,
                    'error': 'Файл не выбран'
                })

            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if avatar_file.content_type not in allowed_types:
                return JsonResponse({
                    'success': False,
                    'error': 'Неподдерживаемый тип файла. Используйте JPG, PNG, GIF или WebP'
                })

            if avatar_file.size > 5 * 1024 * 1024:
                return JsonResponse({
                    'success': False,
                    'error': 'Размер файла не должен превышать 5MB'
                })

            profile, created = UserProfile.objects.get_or_create(user=request.user)

            if profile.avatar:
                try:
                    if os.path.exists(profile.avatar.path):
                        os.remove(profile.avatar.path)
                except:
                    pass

            profile.avatar = avatar_file
            profile.save()

            return JsonResponse({
                'success': True,
                'avatar_url': profile.avatar_url,
                'message': 'Аватар успешно обновлен!'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Ошибка при загрузке аватара: {str(e)}'
            })

    return JsonResponse({
        'success': False,
        'error': 'Метод не поддерживается'
    })

# загрузка баннера профиля
@login_required(login_url='/login/')
def upload_banner(request):
    if request.method == 'POST':
        try:
            if not request.user.profile.is_premium:
                return JsonResponse({
                    'success': False,
                    'error': 'Баннер профиля доступен только для премиум пользователей'
                })

            banner_file = request.FILES.get('banner')

            if not banner_file:
                return JsonResponse({
                    'success': False,
                    'error': 'Файл не выбран'
                })

            allowed_types = ['image/jpeg', 'image/png', 'image/webp']
            if banner_file.content_type not in allowed_types:
                return JsonResponse({
                    'success': False,
                    'error': 'Неподдерживаемый тип файла. Используйте JPG, PNG, или WebP'
                })

            if banner_file.size > 10 * 1024 * 1024:
                return JsonResponse({
                    'success': False,
                    'error': 'Размер файла не должен превышать 10MB'
                })

            profile, created = UserProfile.objects.get_or_create(user=request.user)

            if profile.banner:
                try:
                    if os.path.exists(profile.banner.path):
                        os.remove(profile.banner.path)
                except:
                    pass

            profile.banner = banner_file
            profile.save()

            return JsonResponse({
                'success': True,
                'banner_url': profile.banner_url,
                'message': 'Баннер успешно обновлен!'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Ошибка при загрузке баннера: {str(e)}'
            })

    return JsonResponse({
        'success': False,
        'error': 'Метод не поддерживается'
    })

# содержимое вкладки профиля
@login_required(login_url='/login/')
def profile_tab_content(request, tab_name):
    try:
        user = request.user

        if tab_name == 'activity':
            activities = Activity.objects.filter(user=user).select_related('track', 'target_user')[:20]
            html = render_to_string('main/profile_tabs/activity.html', {
                'activities': activities
            })
            return JsonResponse({'success': True, 'html': html})

        return JsonResponse({'success': False, 'error': 'Неизвестная вкладка'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Ошибка: {str(e)}'})

# публичный профиль пользователя
def public_profile(request, username):
    try:
        profile_user = get_object_or_404(User, username=username)
        is_own_profile = request.user.is_authenticated and request.user == profile_user

        if profile_user.profile.is_private and not is_own_profile:
            if not request.user.is_authenticated:
                return redirect('login')

            is_following = Follow.objects.filter(
                follower=request.user,
                following=profile_user
            ).exists()

            if not is_following:
                return render(request, 'main/private_profile.html', {
                    'profile_user': profile_user
                })

        if is_own_profile:
            tracks = Track.objects.filter(user=profile_user).order_by('-uploaded_at')
        else:
            tracks = Track.objects.filter(
                user=profile_user,
                visibility='public'
            ).order_by('-uploaded_at')

        if is_own_profile:
            playlists = Playlist.objects.filter(user=profile_user).annotate(tracks_count=Count('tracks')).order_by('-updated_at')
        else:
            playlists = Playlist.objects.filter(
                user=profile_user,
                visibility='public'
            ).annotate(tracks_count=Count('tracks')).order_by('-updated_at')

        tracks_count = tracks.count()
        playlists_count = playlists.count()
        total_plays = sum(track.plays_count for track in tracks)

        liked_track_ids = TrackLike.objects.filter(
            user=profile_user, is_like=True
        ).values_list('track_id', flat=True)
        liked_tracks = Track.objects.filter(id__in=liked_track_ids).select_related('user').order_by('-uploaded_at')

        is_following = False
        if request.user.is_authenticated and not is_own_profile:
            is_following = Follow.objects.filter(
                follower=request.user,
                following=profile_user
            ).exists()

        is_blocked = False
        if request.user.is_authenticated and not is_own_profile:
            is_blocked = Block.objects.filter(blocker=request.user, blocked=profile_user).exists()

        context = {
            'profile_user': profile_user,
            'is_own_profile': is_own_profile,
            'tracks': tracks,
            'playlists': playlists,
            'liked_tracks': liked_tracks,
            'tracks_count': tracks_count,
            'playlists_count': playlists_count,
            'liked_count': liked_tracks.count(),
            'total_plays': total_plays,
            'is_following': is_following,
            'is_blocked': is_blocked,
        }

        return render(request, 'main/profile.html', context)

    except Exception as e:
        messages.error(request, f'Ошибка при загрузке профиля: {str(e)}')
        return redirect('home')

# страница планов премиум подписки
def premium_ord(request):
    plans = [
        {
            'id': 'monthly',
            'name': 'Месяц',
            'price': 299,
            'original_price': None,
            'duration': 30,
            'duration_text': '1 месяц',
            'features': [
                'Безлимитная загрузка треков',
                'Аналитика треков (прослушивания, лайки)',
                'Значок Premium в профиле',
                'Персональный баннер профиля',
                'Приоритетная поддержка',
            ],
            'popular': False,
            'savings': None,
        },
        {
            'id': 'quarterly',
            'name': 'Квартал',
            'price': 749,
            'original_price': 897,
            'duration': 90,
            'duration_text': '3 месяца',
            'features': [
                'Безлимитная загрузка треков',
                'Аналитика треков (прослушивания, лайки)',
                'Значок Premium в профиле',
                'Персональный баннер профиля',
                'Приоритетная поддержка',
                'Скидка 16% от месячной цены',
            ],
            'popular': True,
            'savings': 148,
        },
        {
            'id': 'yearly',
            'name': 'Год',
            'price': 2499,
            'original_price': 3588,
            'duration': 365,
            'duration_text': '12 месяцев',
            'features': [
                'Безлимитная загрузка треков',
                'Аналитика треков (прослушивания, лайки)',
                'Значок Premium в профиле',
                'Персональный баннер профиля',
                'Приоритетная поддержка',
                'Максимальная скидка 30%',
            ],
            'popular': False,
            'savings': 1089,
        }
    ]

    user_premium_status = None
    if request.user.is_authenticated:
        user_premium_status = get_user_premium_status(request.user)

    context = {
        'plans': plans,
        'user_premium_status': user_premium_status,
        'is_premium': user_premium_status and user_premium_status['is_active'] if user_premium_status else False
    }

    return render(request, 'main/premium_ord.html', context)


# оформление премиум подписки
@login_required(login_url='/login/')
def premium_checkout(request, plan_id):
    plans_data = {
        'monthly': {
            'name': 'Месячная подписка',
            'price': 299,
            'duration': 30,
            'duration_text': '1 месяц'
        },
        'quarterly': {
            'name': 'Квартальная подписка',
            'price': 749,
            'duration': 90,
            'duration_text': '3 месяца'
        },
        'yearly': {
            'name': 'Годовая подписка',
            'price': 2499,
            'duration': 365,
            'duration_text': '12 месяцев'
        }
    }

    if plan_id not in plans_data:
        messages.error(request, 'Выбранный план подписки не найден.')
        return redirect('premium_ord')

    selected_plan = plans_data[plan_id]
    selected_plan['id'] = plan_id

    user_premium_status = get_user_premium_status(request.user)
    if user_premium_status and user_premium_status['is_active']:
        messages.info(request, 'У вас уже есть активная премиум подписка!')
        return redirect('premium_status')

    context = {
        'plan': selected_plan,
        'user': request.user,
        'total_price': selected_plan['price']
    }

    return render(request, 'main/premium_checkout.html', context)


# обработка платежа за премиум
@login_required(login_url='/login/')
def process_premium_payment(request):
    if request.method != 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Неверный метод запроса'})
        return redirect('premium_plans')

    try:
        plan_id = request.POST.get('plan_id')
        payment_method = request.POST.get('payment_method')
        telegram_username = request.POST.get('telegram_username', '').strip()
        user_message = request.POST.get('user_message', '').strip()

        if not plan_id or not payment_method:
            error_msg = 'Не все данные для оплаты заполнены.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('premium_checkout', plan_id=plan_id or 'monthly')

        if not telegram_username or telegram_username == '@':
            error_msg = 'Укажите ваш Telegram username.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('premium_checkout', plan_id=plan_id)

        plans_data = {
            'monthly': {'duration': 30, 'price': 299, 'name': 'Месячная подписка'},
            'quarterly': {'duration': 90, 'price': 749, 'name': 'Квартальная подписка'},
            'yearly': {'duration': 365, 'price': 2499, 'name': 'Годовая подписка'}
        }

        if plan_id not in plans_data:
            error_msg = 'Неверный план подписки.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('premium_plans')

        plan = plans_data[plan_id]

        if is_user_premium(request.user):
            error_msg = 'У вас уже есть активная премиум подписка!'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('premium_status')

        existing_subscription = PremiumSubscription.objects.filter(
            user=request.user,
            status__in=['pending_payment', 'payment_sent']
        ).first()

        if existing_subscription:
            error_msg = 'У вас уже есть заявка на оплату в обработке.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg})
            messages.error(request, error_msg)
            return redirect('premium_status')

        expires_at = timezone.now() + timedelta(days=plan['duration'])

        subscription = PremiumSubscription.objects.create(
            user=request.user,
            plan_type=plan_id,
            price=plan['price'],
            expires_at=expires_at,
            telegram_username=telegram_username,
            telegram_message=user_message,
            status='payment_sent',
            telegram_payment_sent_at=timezone.now()
        )

        success_msg = f'Заявка на {plan["name"]} отправлена! Свяжитесь с администратором в Telegram.'

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': success_msg,
                'redirect_url': reverse('premium_success')
            })

        messages.success(request, success_msg)
        return redirect('premium_success')

    except Exception as e:
        error_msg = f'Ошибка при обработке платежа: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg})
        messages.error(request, error_msg)
        return redirect('premium_plans')

# профиль пользователя
@login_required(login_url='/login/')
def profile(request):
    tracks = Track.objects.filter(user=request.user).order_by('-uploaded_at')
    playlists = Playlist.objects.filter(user=request.user).annotate(
        tracks_count=Count('tracks')
    ).order_by('-updated_at')

    liked_track_ids = TrackLike.objects.filter(
        user=request.user, is_like=True
    ).values_list('track_id', flat=True)
    liked_tracks = Track.objects.filter(id__in=liked_track_ids).select_related('user').order_by('-uploaded_at')

    activities = Activity.objects.filter(
        user=request.user
    ).select_related('track', 'target_user', 'album').order_by('-created_at')[:30]

    albums = Album.objects.filter(user=request.user).order_by('-created_at')

    now = timezone.now()
    scheduled_tracks = tracks.filter(release_at__gt=now)
    scheduled_albums = albums.filter(release_at__gt=now)

    premium_status = get_user_premium_status(request.user)

    genres = Genre.objects.all()

    context = {
        'profile_user': request.user,
        'tracks': tracks,
        'playlists': playlists,
        'liked_tracks': liked_tracks,
        'activities': activities,
        'albums': albums,
        'scheduled_tracks': scheduled_tracks,
        'scheduled_albums': scheduled_albums,
        'is_own_profile': True,
        'tracks_count': tracks.count(),
        'playlists_count': playlists.count(),
        'liked_count': liked_tracks.count(),
        'total_plays': sum(track.plays_count for track in tracks),
        'premium_status': premium_status,
        'is_premium': premium_status and premium_status.get('is_active', False) if premium_status else False,
        'genres': genres,
    }
    return render(request, 'main/profile.html', context)


# api проверки премиум статуса
def premium_status_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({'is_premium': False, 'error': 'Not authenticated'})

    try:
        current_subscription = request.user.premium_subscriptions.filter(
            is_active=True,
            admin_confirmed=True,
            expires_at__gt=timezone.now()
        ).first()

        if current_subscription:
            premium_data = {
                'is_premium': True,
                'is_active': True,
                'plan_type': current_subscription.plan_type,
                'plan_display': current_subscription.get_plan_type_display(),
                'expires_at': current_subscription.expires_at.isoformat(),
                'days_left': current_subscription.days_left,
                'activated_at': current_subscription.activated_at.isoformat() if current_subscription.activated_at else None,
            }
        else:
            premium_data = {
                'is_premium': False,
                'is_active': False,
                'plan_type': None,
                'plan_display': None,
                'expires_at': None,
                'days_left': 0,
                'activated_at': None,
            }

        return JsonResponse({
            'success': True,
            'premium_status': premium_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка получения премиум статуса: {str(e)}'
        })

# страница успешной отправки заявки
@login_required(login_url='/login/')
def premium_success(request):
    latest_subscription = PremiumSubscription.objects.filter(
        user=request.user
    ).order_by('-created_at').first()

    context = {
        'subscription': latest_subscription
    }

    return render(request, 'main/premium_success.html', context)


# управление премиум подпиской
@login_required(login_url='/login/')
def premium_status(request):
    user = request.user

    current_subscription = user.premium_subscriptions.filter(
        is_active=True,
        admin_confirmed=True,
        expires_at__gt=timezone.now()
    ).first()

    subscription_history = user.premium_subscriptions.all().order_by('-created_at')

    progress_percentage = 0
    if current_subscription and current_subscription.activated_at:
        total_duration = current_subscription.expires_at - current_subscription.activated_at
        elapsed_duration = timezone.now() - current_subscription.activated_at

        if total_duration.total_seconds() > 0:
            progress_percentage = min(100, max(0, (elapsed_duration.total_seconds() / total_duration.total_seconds()) * 100))

    context = {
        'current_subscription': current_subscription,
        'subscription_history': subscription_history,
        'progress_percentage': round(progress_percentage, 1),
        'user': user,
    }

    return render(request, 'main/premium_status.html', context)


# отмена премиум подписки
@login_required(login_url='/login/')
def cancel_premium(request):
    if request.method == 'POST':
        try:
            current_subscription = request.user.premium_subscriptions.filter(
                is_active=True,
                admin_confirmed=True,
                expires_at__gt=timezone.now()
            ).first()

            if not current_subscription:
                messages.error(request, 'У вас нет активной премиум подписки для отмены.')
                return redirect('premium_status')

            current_subscription.cancel()

            try:
                Notification.objects.create(
                    recipient=request.user,
                    message=f"Ваша премиум подписка ({current_subscription.get_plan_type_display()}) была отменена. Доступ к премиум функциям сохранится до {current_subscription.expires_at.strftime('%d.%m.%Y')}."
                )
            except:
                pass

            messages.success(request, f'Премиум подписка успешно отменена. Доступ к премиум функциям сохранится до {current_subscription.expires_at.strftime("%d.%m.%Y")}.')

        except Exception as e:
            messages.error(request, f'Ошибка при отмене подписки: {str(e)}')

    return redirect('premium_status')


# декоратор для проверки премиум статуса
def premium_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Войдите в систему для доступа к премиум функциям.')
            return redirect('login')

        if not is_user_premium(request.user):
            messages.error(request, 'Эта функция доступна только для премиум пользователей.')
            return redirect('premium_ord')

        return view_func(request, *args, **kwargs)

    return wrapper


# аналитика треков (только премиум)
@login_required(login_url='/login/')
@premium_required
def premium_analytics(request):
    tracks = Track.objects.filter(user=request.user).annotate(
        likes_cnt=Count('likes', distinct=True),
        comments_cnt=Count('comments', distinct=True),
    ).order_by('-plays_count')

    total_tracks = tracks.count()
    total_plays = sum(t.plays_count for t in tracks)
    total_likes = sum(t.likes_cnt for t in tracks)
    total_comments = sum(t.comments_cnt for t in tracks)

    top_tracks = list(tracks[:5])

    context = {
        'tracks': tracks,
        'top_tracks': top_tracks,
        'total_tracks': total_tracks,
        'total_plays': total_plays,
        'total_likes': total_likes,
        'total_comments': total_comments,
        'premium_status': get_user_premium_status(request.user),
    }

    return render(request, 'main/premium_analytics.html', context)

# последние треки
def get_latest_tracks(request):
    tracks = Track.objects.filter(visibility='public').order_by('-uploaded_at')[:20]

    context = {
        'tracks': tracks,
        'page_title': 'Последние треки',
        'page_description': 'Самые свежие треки на платформе'
    }
    return render(request, 'main/tracks_list.html', context)


# популярные треки
def get_popular_tracks(request):
    tracks = Track.objects.filter(visibility='public').order_by('-plays_count')[:20]

    context = {
        'tracks': tracks,
        'page_title': 'Популярные треки',
        'page_description': 'Самые популярные треки на платформе'
    }
    return render(request, 'main/tracks_list.html', context)


# список пользователей
def user_list(request):
    users = User.objects.filter(
        track__isnull=False
    ).distinct().annotate(
        tracks_count=Count('track'),
        total_plays=Sum('track__plays_count')
    ).order_by('-tracks_count')[:50]

    context = {
        'users': users,
        'page_title': 'Артисты',
        'page_description': 'Все артисты на платформе'
    }
    return render(request, 'main/user_list.html', context)


# api треков пользователя
def get_user_tracks_api(request, username):
    try:
        user = get_object_or_404(User, username=username)
        tracks = Track.objects.filter(
            user=user,
            visibility='public'
        ).order_by('-uploaded_at')[:10]

        tracks_data = []
        for track in tracks:
            tracks_data.append({
                'id': track.id,
                'title': track.title,
                'description': track.description,
                'cover_url': track.cover_url,
                'audio_url': track.audio_url,
                'plays_count': track.plays_count,
                'uploaded_at': track.uploaded_at.isoformat(),
                'duration': track.duration,
            })

        return JsonResponse({
            'success': True,
            'tracks': tracks_data,
            'user': {
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# счётчик прослушиваний
def increment_play_count(request, track_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Только POST запросы'})

    try:
        track = get_object_or_404(Track, id=track_id)

        if request.user != track.user:
            track.plays_count += 1
            track.save(update_fields=['plays_count'])
            TrackPlay.objects.create(track=track)

        return JsonResponse({
            'success': True,
            'plays_count': track.plays_count
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# api живого поиска
def live_search_api(request):
    query = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')

    if len(query) < 2:
        return JsonResponse({'success': False, 'tracks': [], 'artists': [], 'suggestions': []})

    try:
        tracks_data = []
        artists_data = []
        suggestions = []

        if filter_type in ['all', 'tracks']:
            tracks_q = Q(visibility='public') & (
                Q(title__icontains=query) | Q(description__icontains=query)
            )
            if request.user.is_authenticated:
                tracks_q = tracks_q | (Q(user=request.user) & Q(title__icontains=query))
            tracks = Track.objects.filter(tracks_q).select_related('user__profile').order_by('-plays_count').distinct()[:12]

            for t in tracks:
                tracks_data.append({
                    'id': t.id,
                    'title': t.title,
                    'artist': t.user.username,
                    'cover_url': t.cover_url,
                    'audio_url': t.audio_url,
                    'plays_count': t.plays_count,
                    'url': f'/track/{t.id}/',
                    'duration': t.duration,
                })
                suggestions.append({'type': 'track', 'title': t.title,
                                     'subtitle': f'от {t.user.username}', 'url': f'/track/{t.id}/'})

        if filter_type in ['all', 'artists']:
            users = User.objects.filter(
                Q(username__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            ).exclude(username='admin').select_related('profile')[:6]

            for u in users:
                avatar = u.profile.avatar_url if hasattr(u, 'profile') else '/static/images/default-avatar.png'
                track_count = u.track_set.filter(visibility='public').count()
                artists_data.append({
                    'id': u.id,
                    'username': u.username,
                    'full_name': f'{u.first_name} {u.last_name}'.strip(),
                    'avatar_url': avatar,
                    'track_count': track_count,
                    'url': f'/user/{u.username}/',
                })
                suggestions.append({'type': 'artist', 'title': u.username,
                                     'subtitle': f'{track_count} треков', 'url': f'/user/{u.username}/'})

        return JsonResponse({
            'success': True,
            'query': query,
            'tracks': tracks_data,
            'artists': artists_data,
            'suggestions': suggestions[:8],
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e), 'tracks': [], 'artists': [], 'suggestions': []})


# популярные поисковые запросы
def popular_searches_api(request):
    queries = list(SearchQuery.objects.order_by('-count').values('query', 'count')[:12])
    return JsonResponse({'queries': queries})


# удаление трека
@login_required(login_url='/login/')
def delete_track(request, pk):
    track = get_object_or_404(Track, pk=pk)

    if track.user != request.user:
        messages.error(request, "У вас нет прав для удаления этого трека.")
        return redirect('public_profile', username=track.user.username)

    if request.method == 'POST':
        try:
            track_title = track.title

            if track.audio_file:
                if os.path.isfile(track.audio_file.path):
                    os.remove(track.audio_file.path)

            if track.cover:
                if os.path.isfile(track.cover.path):
                    os.remove(track.cover.path)

            track.delete()

            messages.success(request, f'Трек "{track_title}" успешно удален!')
            return redirect('profile')

        except Exception as e:
            messages.error(request, f'Ошибка при удалении трека: {str(e)}')
            return redirect('profile')

    context = {
        'track': track,
    }
    return render(request, 'main/confirm_delete_track.html', context)


# редактирование профиля
@login_required(login_url='/login/')
def edit_profile(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        try:
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            bio = request.POST.get('bio', '').strip()
            location = request.POST.get('location', '').strip()
            website = request.POST.get('website', '').strip()
            is_private = request.POST.get('is_private') == 'on'

            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.save()

            profile.bio = bio[:500]
            profile.location = location[:100]
            profile.website = website
            profile.is_private = is_private
            profile.save()

            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')

        except Exception as e:
            messages.error(request, f'Ошибка при обновлении профиля: {str(e)}')

    context = {
        'profile': profile,
    }
    return render(request, 'main/edit_profile.html', context)


# смена имени пользователя
@login_required(login_url='/login/')
def change_username(request):
    if request.method == 'POST':
        try:
            new_username = request.POST.get('username', '').strip()

            if not new_username:
                messages.error(request, 'Имя пользователя не может быть пустым.')
                return redirect('edit_profile')

            if len(new_username) < 3:
                messages.error(request, 'Имя пользователя должно содержать минимум 3 символа.')
                return redirect('edit_profile')

            if User.objects.filter(username=new_username).exclude(id=request.user.id).exists():
                messages.error(request, 'Это имя пользователя уже занято.')
                return redirect('edit_profile')

            old_username = request.user.username
            request.user.username = new_username
            request.user.save()

            messages.success(request, f'Имя пользователя изменено с "{old_username}" на "{new_username}"!')
            return redirect('profile')

        except Exception as e:
            messages.error(request, f'Ошибка при изменении имени пользователя: {str(e)}')

    return redirect('edit_profile')


# вспомогательные функции для работы с премиум статусом

def get_user_premium_status(user):
    try:
        active_subscription = PremiumSubscription.objects.filter(
            user=user,
            admin_confirmed=True,
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()

        if active_subscription:
            return {
                'is_active': True,
                'premium_until': active_subscription.expires_at,
                'days_left': active_subscription.days_left,
                'plan_type': active_subscription.plan_type,
                'subscription': active_subscription
            }

        pending_subscription = PremiumSubscription.objects.filter(
            user=user,
            status__in=['payment_sent', 'payment_confirmed'],
            admin_confirmed=False
        ).first()

        if pending_subscription:
            return {
                'is_active': False,
                'is_pending': True,
                'pending_subscription': pending_subscription,
                'plan_type': pending_subscription.plan_type
            }

        return None

    except Exception as e:
        print(f"Ошибка получения премиум статуса: {e}")
        return None


def is_user_premium(user):
    if not user.is_authenticated:
        return False

    premium_status = get_user_premium_status(user)
    return premium_status and premium_status.get('is_active', False)


# лайк трека
@login_required
def toggle_like_track(request, track_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})

    try:
        track = get_object_or_404(Track, id=track_id)

        like, created = TrackLike.objects.get_or_create(
            user=request.user,
            track=track,
            defaults={'is_like': True}
        )

        if not created:
            if like.is_like:
                like.delete()
                liked = False
            else:
                like.is_like = True
                like.save()
                liked = True
        else:
            liked = True

        if liked:
            Activity.objects.get_or_create(
                user=request.user,
                activity_type='track_like',
                track=track
            )

        likes_count = TrackLike.objects.filter(track=track, is_like=True).count()

        return JsonResponse({
            'success': True,
            'liked': liked,
            'likes_count': likes_count
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при обработке лайка: {str(e)}'
        })

# добавление комментария к треку
@login_required
def add_track_comment(request, track_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})

    try:
        track = get_object_or_404(Track, id=track_id)
        content = request.POST.get('content', '').strip()

        if not content:
            return JsonResponse({'success': False, 'error': 'Комментарий не может быть пустым'})

        if len(content) > 500:
            return JsonResponse({'success': False, 'error': 'Комментарий слишком длинный'})

        comment = TrackComment.objects.create(
            user=request.user,
            track=track,
            content=content
        )

        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'username': comment.user.username,
                'user_avatar': comment.user.profile.avatar_url,
                'user_is_premium': comment.user.profile.is_premium,
                'created_at': comment.created_at.isoformat(),
                'likes_count': 0
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при добавлении комментария: {str(e)}'
        })

# лайк комментария
@login_required
def toggle_comment_like(request, comment_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})

    try:
        try:
            comment = TrackComment.objects.get(id=comment_id)
        except TrackComment.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Комментарий не найден'})

        existing_like = CommentLike.objects.filter(user=request.user, comment=comment).first()

        if existing_like:
            existing_like.delete()
            liked = False
        else:
            CommentLike.objects.create(user=request.user, comment=comment, is_like=True)
            liked = True

        likes_count = CommentLike.objects.filter(comment=comment, is_like=True).count()

        return JsonResponse({
            'success': True,
            'liked': liked,
            'likes_count': likes_count
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при обработке лайка: {str(e)}'
        })

# удаление комментария
@login_required
def delete_track_comment(request, comment_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})

    try:
        comment = get_object_or_404(TrackComment, id=comment_id)

        if comment.user != request.user:
            return JsonResponse({'success': False, 'error': 'Нет прав для удаления'})

        comment.delete()

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при удалении комментария: {str(e)}'
        })

# список чатов
@login_required
def chat_list(request):
    user_chats = Chat.objects.filter(
        participants=request.user,
        is_active=True
    ).annotate(
        last_message_time=Max('messages__created_at'),
        unread_messages_count=Count('messages', filter=Q(messages__is_read=False) & ~Q(messages__sender=request.user))
    ).order_by('-last_message_time')

    for chat in user_chats:
        if chat.chat_type == 'private':
            chat.other_participant = chat.participants.exclude(id=request.user.id).first()
        chat.unread_count_value = chat.unread_messages_count

    context = {
        'chats': user_chats,
        'active_chat_id': request.GET.get('chat_id'),
    }

    return render(request, 'main/chat_list.html', context)

# детальный просмотр чата
@login_required
def chat_detail(request, chat_id):
    return redirect(f'/chats/?chat_id={chat_id}')

# начать чат с пользователем
@login_required
def start_chat(request, username):
    other_user = get_object_or_404(User, username=username)

    if other_user == request.user:
        messages.error(request, "Нельзя создать чат с самим собой")
        return redirect('chat_list')

    if Block.objects.filter(
        Q(blocker=request.user, blocked=other_user) |
        Q(blocker=other_user, blocked=request.user)
    ).exists():
        messages.error(request, "Невозможно начать чат: пользователь заблокирован")
        return redirect('public_profile', username=username)

    existing_chat = Chat.objects.filter(
        chat_type='private',
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    if existing_chat:
        return redirect('chat_detail', chat_id=existing_chat.id)

    new_chat = Chat.objects.create(chat_type='private')
    new_chat.participants.add(request.user, other_user)

    return redirect('chat_detail', chat_id=new_chat.id)


@login_required
@require_http_methods(["POST"])
def block_user(request, username):
    target = get_object_or_404(User, username=username)
    if target != request.user:
        Block.objects.get_or_create(blocker=request.user, blocked=target)
    return redirect('public_profile', username=username)


@login_required
@require_http_methods(["POST"])
def unblock_user(request, username):
    target = get_object_or_404(User, username=username)
    Block.objects.filter(blocker=request.user, blocked=target).delete()
    return redirect('public_profile', username=username)


# отправка сообщения
@login_required
@require_http_methods(["POST"])
def send_message(request, chat_id):
    try:
        chat = get_object_or_404(Chat, id=chat_id, participants=request.user)

        message_type = request.POST.get('type', 'text')
        content = request.POST.get('content', '').strip()
        reply_to_id = request.POST.get('reply_to')

        if message_type == 'text' and not content:
            return JsonResponse({'success': False, 'error': 'Сообщение не может быть пустым'})

        if len(content) > 2000:
            return JsonResponse({'success': False, 'error': 'Сообщение слишком длинное'})

        message_data = {
            'chat': chat,
            'sender': request.user,
            'message_type': message_type,
        }

        if message_type == 'text':
            message_data['content'] = content

        if reply_to_id:
            try:
                reply_to = Message.objects.get(id=reply_to_id, chat=chat)
                message_data['reply_to'] = reply_to
            except Message.DoesNotExist:
                pass

        if 'image' in request.FILES:
            message_data['image'] = request.FILES['image']
            message_data['message_type'] = 'image'
        elif 'audio' in request.FILES:
            message_data['audio'] = request.FILES['audio']
            message_data['message_type'] = 'audio'
        elif 'file' in request.FILES:
            message_data['file'] = request.FILES['file']
            message_data['message_type'] = 'file'

        message = Message.objects.create(**message_data)

        response_data = {
            'success': True,
            'message': {
                'id': message.id,
                'content': message.content,
                'message_type': message.message_type,
                'sender': {
                    'id': message.sender.id,
                    'username': message.sender.username,
                    'avatar': message.sender.profile.avatar_url,
                    'is_premium': message.sender.profile.is_premium,
                },
                'created_at': message.created_at.isoformat(),
                'is_edited': message.is_edited,
                'is_read': message.is_read,
                'reply_to': None,
            }
        }

        if message.image:
            response_data['message']['image_url'] = message.image.url
        elif message.audio:
            response_data['message']['audio_url'] = message.audio.url
        elif message.file:
            response_data['message']['file_url'] = message.file.url
            response_data['message']['file_name'] = message.file_name
            response_data['message']['file_size'] = message.file_size

        if message.reply_to:
            response_data['message']['reply_to'] = {
                'id': message.reply_to.id,
                'content': message.reply_to.content,
                'sender_username': message.reply_to.sender.username,
                'message_type': message.reply_to.message_type,
            }

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при отправке сообщения: {str(e)}'
        })

# удаление сообщения
@login_required
@require_http_methods(["POST"])
def delete_message(request, message_id):
    try:
        message = get_object_or_404(Message, id=message_id, sender=request.user)

        message.is_deleted = True
        message.save()

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при удалении сообщения: {str(e)}'
        })

# редактирование сообщения
@login_required
@require_http_methods(["POST"])
def edit_message(request, message_id):
    try:
        message = get_object_or_404(Message, id=message_id, sender=request.user)

        if message.message_type != 'text':
            return JsonResponse({'success': False, 'error': 'Можно редактировать только текстовые сообщения'})

        new_content = request.POST.get('content', '').strip()

        if not new_content:
            return JsonResponse({'success': False, 'error': 'Сообщение не может быть пустым'})

        if len(new_content) > 2000:
            return JsonResponse({'success': False, 'error': 'Сообщение слишком длинное'})

        message.content = new_content
        message.is_edited = True
        message.save()

        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'content': message.content,
                'is_edited': True,
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при редактировании сообщения: {str(e)}'
        })

# получение сообщений чата
@login_required
def get_chat_messages(request, chat_id):
    try:
        chat = get_object_or_404(Chat, id=chat_id, participants=request.user)

        page = int(request.GET.get('page', 1))
        messages_list = chat.messages.filter(is_deleted=False).select_related('sender__profile', 'reply_to__sender')

        paginator = Paginator(messages_list, 50)
        messages_page = paginator.get_page(page)

        messages_data = []
        for message in messages_page:
            message_data = {
                'id': message.id,
                'content': message.content,
                'message_type': message.message_type,
                'sender': {
                    'id': message.sender.id,
                    'username': message.sender.username,
                    'avatar': message.sender.profile.avatar_url,
                    'is_premium': message.sender.profile.is_premium,
                },
                'created_at': message.created_at.isoformat(),
                'is_edited': message.is_edited,
                'reply_to': None,
            }

            if message.image:
                message_data['image_url'] = message.image.url
            elif message.audio:
                message_data['audio_url'] = message.audio.url
            elif message.file:
                message_data['file_url'] = message.file.url
                message_data['file_name'] = message.file_name
                message_data['file_size'] = message.file_size

            if message.reply_to:
                message_data['reply_to'] = {
                    'id': message.reply_to.id,
                    'content': message.reply_to.content,
                    'sender_username': message.reply_to.sender.username,
                    'message_type': message.reply_to.message_type,
                }

            messages_data.append(message_data)

        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'has_next': messages_page.has_next(),
            'has_previous': messages_page.has_previous(),
            'current_page': page,
            'total_pages': paginator.num_pages,
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при получении сообщений: {str(e)}'
        })

# поиск пользователей для чата
@login_required
def search_users_for_chat(request):
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'success': False, 'users': []})

    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    ).exclude(id=request.user.id)[:10]

    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'full_name': f"{user.first_name} {user.last_name}".strip(),
            'avatar': user.profile.avatar_url,
            'is_premium': user.profile.is_premium,
        })

    return JsonResponse({
        'success': True,
        'users': users_data
    })

# отметка чата как прочитанного
@login_required
@require_http_methods(["POST"])
def mark_chat_as_read(request, chat_id):
    try:
        chat = get_object_or_404(Chat, id=chat_id, participants=request.user)
        chat.mark_messages_as_read(request.user)

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при отметке как прочитанного: {str(e)}'
        })

# количество непрочитанных сообщений
@login_required
def get_unread_messages_count(request):
    try:
        unread_count = Message.objects.filter(
            chat__participants=request.user,
            is_read=False,
            is_deleted=False
        ).exclude(sender=request.user).count()

        return JsonResponse({
            'success': True,
            'unread_count': unread_count
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# новые сообщения (polling)
@login_required
def get_new_messages(request, chat_id):
    try:
        chat = get_object_or_404(Chat, id=chat_id, participants=request.user)
        after_id = int(request.GET.get('after', 0))

        qs = chat.messages.filter(
            is_deleted=False,
            id__gt=after_id
        ).select_related('sender__profile', 'reply_to__sender').order_by('created_at')

        # Отмечаем входящие сообщения как прочитанные
        qs.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

        # Получаем read-статус наших уже показанных сообщений (для обновления галочек)
        read_msg_ids = list(
            chat.messages.filter(sender=request.user, is_read=True)
            .values_list('id', flat=True)[:100]
        )

        messages_data = []
        for msg in qs:
            md = {
                'id': msg.id,
                'content': msg.content,
                'message_type': msg.message_type,
                'sender': {
                    'id': msg.sender.id,
                    'username': msg.sender.username,
                    'avatar': msg.sender.profile.avatar_url,
                    'is_premium': msg.sender.profile.is_premium,
                },
                'created_at': msg.created_at.isoformat(),
                'is_edited': msg.is_edited,
                'is_read': msg.is_read,
                'is_mine': msg.sender.id == request.user.id,
                'reply_to': None,
            }
            if msg.image:
                md['image_url'] = msg.image.url
            elif msg.audio:
                md['audio_url'] = msg.audio.url
            elif msg.file:
                md['file_url'] = msg.file.url
                md['file_name'] = getattr(msg, 'file_name', '')
            if msg.reply_to:
                md['reply_to'] = {
                    'id': msg.reply_to.id,
                    'content': msg.reply_to.content,
                    'sender_username': msg.reply_to.sender.username,
                    'message_type': msg.reply_to.message_type,
                }
            messages_data.append(md)

        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'read_msg_ids': read_msg_ids,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# публичные плейлисты
def public_playlists(request):
    playlists = Playlist.objects.filter(
        visibility='public'
    ).select_related('user__profile').annotate(
        tracks_count=Count('tracks')
    ).order_by('-updated_at')

    context = {
        'title': 'Публичные плейлисты',
        'playlists': playlists,
        'page_description': 'Все публичные плейлисты на платформе'
    }
    return render(request, 'main/public_playlists.html', context)

# детальный вид плейлиста
def playlist_detail(request, pk):
    playlist = get_object_or_404(Playlist, pk=pk)

    if playlist.visibility == 'private' and playlist.user != request.user:
        if not request.user.is_authenticated:
            return redirect('login')
        raise PermissionDenied("У вас нет доступа к этому плейлисту")

    playlist_tracks = PlaylistTrack.objects.filter(
        playlist=playlist
    ).select_related('track__user').order_by('position')

    user_liked = False
    if request.user.is_authenticated:
        pass

    playlist_track_ids = list(playlist_tracks.values_list('track_id', flat=True))

    context = {
        'playlist': playlist,
        'playlist_tracks': playlist_tracks,
        'tracks_count': playlist_tracks.count(),
        'playlist_track_ids': playlist_track_ids,
        'user_liked': user_liked,
        'is_owner': request.user == playlist.user if request.user.is_authenticated else False,
    }

    return render(request, 'main/playlist_detail.html', context)

# создание плейлиста
@login_required(login_url='/login/')
def create_playlist(request):
    if request.method == 'POST':
        try:
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            visibility = request.POST.get('visibility', 'public')
            cover = request.FILES.get('cover')

            if not title:
                messages.error(request, 'Название плейлиста обязательно!')
                return redirect('profile')

            if len(title) > 200:
                messages.error(request, 'Название плейлиста слишком длинное!')
                return redirect('profile')

            if visibility not in ['public', 'unlisted', 'private']:
                visibility = 'public'

            if cover and cover.size > 5 * 1024 * 1024:
                messages.error(request, 'Размер обложки не должен превышать 5MB!')
                return redirect('profile')

            playlist = Playlist.objects.create(
                title=title,
                description=description,
                visibility=visibility,
                cover=cover,
                user=request.user
            )

            Activity.objects.create(
                user=request.user,
                activity_type='playlist_create',
                playlist=playlist
            )

            messages.success(request, f'Плейлист "{title}" успешно создан!')
            return redirect('/profile/?tab=playlists')

        except Exception as e:
            messages.error(request, f'Ошибка при создании плейлиста: {str(e)}')
            return redirect('/profile/?tab=playlists')

    return redirect('/profile/?tab=playlists')

# редактирование плейлиста
@login_required(login_url='/login/')
def edit_playlist(request, pk):
    playlist = get_object_or_404(Playlist, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            visibility = request.POST.get('visibility', 'public')
            cover = request.FILES.get('cover')

            if not title:
                messages.error(request, 'Название плейлиста обязательно!')
                return redirect('playlist_detail', pk=playlist.pk)

            if len(title) > 200:
                messages.error(request, 'Название плейлиста слишком длинное!')
                return redirect('playlist_detail', pk=playlist.pk)

            if visibility not in ['public', 'unlisted', 'private']:
                visibility = 'public'

            if cover and cover.size > 5 * 1024 * 1024:
                messages.error(request, 'Размер обложки не должен превышать 5MB!')
                return redirect('playlist_detail', pk=playlist.pk)

            old_title = playlist.title
            playlist.title = title
            playlist.description = description
            playlist.visibility = visibility

            if cover:
                if playlist.cover:
                    try:
                        if os.path.isfile(playlist.cover.path):
                            os.remove(playlist.cover.path)
                    except:
                        pass
                playlist.cover = cover

            playlist.save()

            if old_title != title:
                messages.success(request, f'Плейлист "{old_title}" переименован в "{title}" и обновлен!')
            else:
                messages.success(request, f'Плейлист "{title}" успешно обновлен!')

            return redirect('/profile/?tab=playlists')

        except Exception as e:
            messages.error(request, f'Ошибка при обновлении плейлиста: {str(e)}')
            return redirect('/profile/?tab=playlists')

    context = {
        'playlist': playlist,
    }
    return render(request, 'main/edit_playlist.html', context)

# удаление плейлиста
@login_required(login_url='/login/')
def delete_playlist(request, pk):
    playlist = get_object_or_404(Playlist, pk=pk, user=request.user)

    if request.method == 'POST':
        try:
            playlist_title = playlist.title

            if playlist.cover:
                try:
                    if os.path.isfile(playlist.cover.path):
                        os.remove(playlist.cover.path)
                except:
                    pass

            playlist.delete()

            messages.success(request, f'Плейлист "{playlist_title}" успешно удален!')
            return redirect('/profile/?tab=playlists')

        except Exception as e:
            messages.error(request, f'Ошибка при удалении плейлиста: {str(e)}')
            return redirect('/profile/?tab=playlists')

    context = {
        'playlist': playlist,
    }
    return render(request, 'main/confirm_delete_playlist.html', context)

# добавление трека в плейлист
@login_required(login_url='/login/')
def add_track_to_playlist(request, playlist_pk, track_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})

    try:
        playlist = get_object_or_404(Playlist, pk=playlist_pk, user=request.user)
        track = get_object_or_404(Track, id=track_id)

        if PlaylistTrack.objects.filter(playlist=playlist, track=track).exists():
            return JsonResponse({'success': False, 'error': 'Трек уже добавлен в плейлист'})

        max_position = PlaylistTrack.objects.filter(playlist=playlist).aggregate(
            max_position=Max('position')
        )['max_position'] or 0

        PlaylistTrack.objects.create(
            playlist=playlist,
            track=track,
            position=max_position + 1
        )

        return JsonResponse({
            'success': True,
            'message': f'Трек "{track.title}" добавлен в плейлист "{playlist.title}"',
            'track': {
                'id': track.id,
                'title': track.title,
                'artist': track.user.username,
                'cover_url': track.cover_url,
                'track_url': f'/track/{track.id}/',
                'artist_url': f'/user/{track.user.username}/',
                'added_at': timezone.now().strftime('%d.%m.%Y'),
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при добавлении трека: {str(e)}'
        })

# удаление трека из плейлиста
@login_required(login_url='/login/')
def remove_track_from_playlist(request, playlist_pk, track_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})

    try:
        playlist = get_object_or_404(Playlist, pk=playlist_pk, user=request.user)
        track = get_object_or_404(Track, id=track_id)

        playlist_track = get_object_or_404(PlaylistTrack, playlist=playlist, track=track)
        removed_position = playlist_track.position
        playlist_track.delete()

        remaining_tracks = PlaylistTrack.objects.filter(
            playlist=playlist,
            position__gt=removed_position
        ).order_by('position')

        for i, pt in enumerate(remaining_tracks):
            pt.position = removed_position + i
            pt.save()

        return JsonResponse({
            'success': True,
            'message': f'Трек "{track.title}" удален из плейлиста'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при удалении трека: {str(e)}'
        })

# изменение порядка треков в плейлисте
@login_required(login_url='/login/')
def reorder_playlist_tracks(request, playlist_pk):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не поддерживается'})

    try:
        playlist = get_object_or_404(Playlist, pk=playlist_pk, user=request.user)

        track_ids = request.POST.getlist('track_ids[]')

        if not track_ids:
            return JsonResponse({'success': False, 'error': 'Не указан порядок треков'})

        for i, track_id in enumerate(track_ids):
            try:
                playlist_track = PlaylistTrack.objects.get(
                    playlist=playlist,
                    track_id=track_id
                )
                playlist_track.position = i + 1
                playlist_track.save()
            except PlaylistTrack.DoesNotExist:
                continue

        return JsonResponse({
            'success': True,
            'message': 'Порядок треков обновлен'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при изменении порядка: {str(e)}'
        })

# api плейлистов пользователя
@login_required(login_url='/login/')
def get_user_playlists_api(request):
    try:
        playlists = Playlist.objects.filter(user=request.user).annotate(
            tracks_count=Count('tracks')
        ).order_by('-updated_at')

        playlists_data = []
        for playlist in playlists:
            playlists_data.append({
                'id': playlist.id,
                'title': playlist.title,
                'slug': playlist.slug,
                'tracks_count': playlist.tracks_count,
                'cover_url': playlist.cover_url,
                'visibility': playlist.visibility,
                'visibility_display': playlist.get_visibility_display(),
            })

        return JsonResponse({
            'success': True,
            'playlists': playlists_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при получении плейлистов: {str(e)}'
        })

# плейлисты пользователя
def user_playlists(request, username):
    try:
        profile_user = get_object_or_404(User, username=username)
        is_own_profile = request.user.is_authenticated and request.user == profile_user

        if profile_user.profile.is_private and not is_own_profile:
            if not request.user.is_authenticated:
                return redirect('login')

            is_following = Follow.objects.filter(
                follower=request.user,
                following=profile_user
            ).exists()

            if not is_following:
                return render(request, 'main/private_profile.html', {
                    'profile_user': profile_user
                })

        if is_own_profile:
            playlists = Playlist.objects.filter(user=profile_user).annotate(
                tracks_count=Count('tracks')
            ).order_by('-updated_at')
        else:
            playlists = Playlist.objects.filter(
                user=profile_user,
                visibility='public'
            ).annotate(
                tracks_count=Count('tracks')
            ).order_by('-updated_at')

        is_following = False
        if request.user.is_authenticated and not is_own_profile:
            is_following = Follow.objects.filter(
                follower=request.user,
                following=profile_user
            ).exists()

        context = {
            'profile_user': profile_user,
            'playlists': playlists,
            'is_own_profile': is_own_profile,
            'is_following': is_following,
            'playlists_count': playlists.count(),
            'page_title': f'Плейлисты {profile_user.username}',
            'page_description': f'Все плейлисты пользователя {profile_user.username}'
        }

        return render(request, 'main/user_playlists.html', context)

    except Exception as e:
        messages.error(request, f'Ошибка при загрузке плейлистов: {str(e)}')
        return redirect('home')


# api треков плейлиста для плеера
def get_playlist_tracks_api(request, pk):
    playlist = get_object_or_404(Playlist, pk=pk)

    if playlist.visibility == 'private' and playlist.user != request.user:
        return JsonResponse({'success': False, 'error': 'Нет доступа'}, status=403)

    playlist_tracks = PlaylistTrack.objects.filter(
        playlist=playlist
    ).select_related('track__user').order_by('position')

    tracks_data = []
    for pt in playlist_tracks:
        track = pt.track
        tracks_data.append({
            'id': track.id,
            'title': track.title,
            'artist': track.user.username,
            'audio_url': track.audio_url,
            'cover_url': track.cover_url,
        })

    return JsonResponse({'success': True, 'tracks': tracks_data})
