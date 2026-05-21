from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
import os


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True, verbose_name="О себе")
    location = models.CharField(max_length=100, blank=True, verbose_name="Местоположение")
    website = models.URLField(blank=True, verbose_name="Веб-сайт")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватар")
    banner = models.ImageField(upload_to='banners/', blank=True, null=True, verbose_name="Баннер")
    is_private = models.BooleanField(default=False, verbose_name="Приватный профиль")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Последнее посещение")
    terms_accepted_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата принятия лицензионного соглашения")

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"Профиль {self.user.username}"

    @property
    def avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            try:
                return self.avatar.url
            except ValueError:
                return self.get_default_avatar()
        return self.get_default_avatar()

    def get_default_avatar(self):
        return f"{settings.STATIC_URL}images/default-avatar.png"

    @property
    def banner_url(self):
        if self.banner and hasattr(self.banner, 'url'):
            try:
                return self.banner.url
            except ValueError:
                return None
        return None

    def get_default_banner(self):
        return f"{settings.STATIC_URL}images/default-banner.jpg"

    @property
    def is_online(self):
        if self.last_seen is None:
            return False
        return self.last_seen >= timezone.now() - timedelta(minutes=10)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.avatar and hasattr(self.avatar, 'path'):
            try:
                from PIL import Image
                img_path = self.avatar.path
                if os.path.exists(img_path):
                    img = Image.open(img_path)
                    if img.height > 300 or img.width > 300:
                        output_size = (300, 300)
                        img.thumbnail(output_size)
                        img.save(img_path)
            except Exception as e:
                print(f"Ошибка при обработке аватара: {e}")
        if self.banner and hasattr(self.banner, 'path'):
            try:
                from PIL import Image
                img_path = self.banner.path
                if os.path.exists(img_path):
                    img = Image.open(img_path)
                    if img.height > 400 or img.width > 1200:
                        output_size = (1200, 400)
                        img.thumbnail(output_size)
                        img.save(img_path)
            except Exception as e:
                print(f"Ошибка при обработке баннера: {e}")

    @property
    def followers_count(self):
        return self.user.followers.count()

    @property
    def following_count(self):
        return self.user.following.count()

    @property
    def total_plays(self):
        return sum(track.plays_count for track in self.user.track_set.all())

    @property
    def is_premium(self):
        try:
            subscription = self.user.premium_subscriptions.filter(
                admin_confirmed=True,
                is_active=True,
                expires_at__gt=timezone.now()
            ).first()
            return subscription is not None
        except:
            return False

class PremiumSubscription(models.Model):
    PLAN_CHOICES = [
        ('monthly', 'Месячная подписка'),
        ('quarterly', 'Квартальная подписка'),
        ('yearly', 'Годовая подписка'),
    ]
    STATUS_CHOICES = [
        ('pending_payment', 'Ожидает оплаты'),
        ('payment_sent', 'Отправлен в Telegram'),
        ('payment_confirmed', 'Оплата подтверждена'),
        ('active', 'Активна'),
        ('expired', 'Истекла'),
        ('cancelled', 'Отменена'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='premium_subscriptions')
    plan_type = models.CharField(max_length=20, choices=PLAN_CHOICES, verbose_name="Тип плана")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment', verbose_name="Статус")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    activated_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата активации")
    expires_at = models.DateTimeField(verbose_name="Дата окончания")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата отмены")
    telegram_username = models.CharField(max_length=100, blank=True, verbose_name="Telegram username")
    telegram_payment_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Отправлено в Telegram")
    telegram_message = models.TextField(blank=True, verbose_name="Сообщение для админа")
    admin_confirmed = models.BooleanField(default=False, verbose_name="Пользователь оплатил!")
    admin_notes = models.TextField(blank=True, verbose_name="Заметки администратора")
    confirmed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_payments', verbose_name="Подтверждено администратором")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата подтверждения")
    auto_renewal = models.BooleanField(default=False, verbose_name="Автопродление")
    is_active = models.BooleanField(default=False, verbose_name="Активна")

    class Meta:
        verbose_name = "Премиум подписка"
        verbose_name_plural = "Премиум подписки"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_plan_type_display()} ({self.get_status_display()})"

    @property
    def days_left(self):
        if self.is_active and self.expires_at:
            delta = self.expires_at - timezone.now()
            return max(0, delta.days)
        return 0

    @property
    def is_expired(self):
        return self.expires_at < timezone.now()

    def activate(self):
        self.status = 'active'
        self.is_active = True
        self.activated_at = timezone.now()
        self.save()

    def cancel(self):
        self.status = 'cancelled'
        self.is_active = False
        self.cancelled_at = timezone.now()
        self.save()

    def expire(self):
        self.status = 'expired'
        self.is_active = False
        self.save()

    def confirm_payment(self, admin_user):
        self.admin_confirmed = True
        self.confirmed_by = admin_user
        self.confirmed_at = timezone.now()
        self.status = 'payment_confirmed'
        self.activate()
        self.save()

class Genre(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    color = models.CharField(max_length=7, default="#39FF14", verbose_name="Цвет (HEX)")

    class Meta:
        verbose_name = "Жанр"
        verbose_name_plural = "Жанры"
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def tracks_count(self):
        return self.tracks.count()

class Tag(models.Model):
    name = models.CharField(max_length=30, unique=True, verbose_name="Название")
    color = models.CharField(max_length=7, default="#6c757d", verbose_name="Цвет")

    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"
        ordering = ['name']

    def __str__(self):
        return f"#{self.name}"

class Track(models.Model):
    VISIBILITY_CHOICES = [
        ('public', 'Публичный'),
        ('unlisted', 'По ссылке'),
        ('private', 'Приватный'),
    ]

    title = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    audio_file = models.FileField(upload_to='tracks/audio/', verbose_name="Аудиофайл")
    cover = models.ImageField(upload_to='tracks/covers/', blank=True, null=True, verbose_name="Обложка")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, blank=True, related_name='tracks', verbose_name="Жанр")
    tags = models.ManyToManyField(Tag, blank=True, related_name='tracks', verbose_name="Теги")
    duration = models.PositiveIntegerField(null=True, blank=True, verbose_name="Длительность (секунды)")
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='public', verbose_name="Видимость")
    allow_downloads = models.BooleanField(default=False, verbose_name="Разрешить скачивание")
    allow_comments = models.BooleanField(default=True, verbose_name="Разрешить комментарии")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")
    plays_count = models.PositiveIntegerField(default=0, verbose_name="Количество прослушиваний")
    downloads_count = models.PositiveIntegerField(default=0, verbose_name="Количество скачиваний")
    slug = models.SlugField(max_length=250, blank=True, verbose_name="URL")
    album = models.ForeignKey('Album', on_delete=models.SET_NULL, null=True, blank=True, related_name='tracks', verbose_name="Альбом")
    release_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата релиза")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок в альбоме")

    class Meta:
        verbose_name = "Трек"
        verbose_name_plural = "Треки"
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    @property
    def cover_url(self):
        if self.cover and hasattr(self.cover, 'url'):
            try:
                return self.cover.url
            except ValueError:
                return self.get_default_cover()
        return self.get_default_cover()

    def get_default_cover(self):
        return f"{settings.STATIC_URL}images/default-track-cover.png"

    @property
    def audio_url(self):
        if self.audio_file and hasattr(self.audio_file, 'url'):
            try:
                return self.audio_file.url
            except ValueError:
                return None
        return None

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(f"{self.title}-{self.user.username}")
        super().save(*args, **kwargs)
        if self.cover and hasattr(self.cover, 'path'):
            try:
                from PIL import Image
                img_path = self.cover.path
                if os.path.exists(img_path):
                    img = Image.open(img_path)
                    if img.height > 800 or img.width > 800:
                        output_size = (800, 800)
                        img.thumbnail(output_size)
                        img.save(img_path)
            except Exception as e:
                print(f"Ошибка при обработке обложки: {e}")
                
        @property
        def likes_count(self):
            """Возвращает количество лайков трека"""
            return self.likes.count()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        UserProfile.objects.get_or_create(user=instance)

class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following', verbose_name="Подписчик")
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers', verbose_name="На кого подписан")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата подписки")

    class Meta:
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        unique_together = ('follower', 'following')

    def __str__(self):
        return f"{self.follower.username} подписан на {self.following.username}"

class TrackLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    is_like = models.BooleanField(default=True)
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='likes', verbose_name="Трек")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата лайка")

    class Meta:
        verbose_name = "Лайк трека"
        verbose_name_plural = "Лайки треков"
        unique_together = ('user', 'track')

    def __str__(self):
        return f"{self.user.username} лайкнул {self.track.title}"


class TrackPlay(models.Model):
    # запись каждого прослушивания — используется для топ за период
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='plays')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Прослушивание"
        verbose_name_plural = "Прослушивания"


class Album(models.Model):
    VISIBILITY_CHOICES = [
        ('public', 'Публичный'),
        ('unlisted', 'По ссылке'),
        ('private', 'Приватный'),
    ]

    title = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    cover = models.ImageField(upload_to='albums/covers/', blank=True, null=True, verbose_name="Обложка")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='albums', verbose_name="Артист")
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='public', verbose_name="Видимость")
    release_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата релиза")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Альбом"
        verbose_name_plural = "Альбомы"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.user.username}"

    @property
    def is_released(self):
        return self.release_at is None or self.release_at <= timezone.now()

    @property
    def cover_url(self):
        if self.cover and hasattr(self.cover, 'url'):
            try:
                return self.cover.url
            except ValueError:
                pass
        return f"{settings.STATIC_URL}images/default-track-cover.png"

    @property
    def tracks_count(self):
        return self.tracks.count()

    @property
    def plays_total(self):
        return self.tracks.aggregate(total=Sum('plays_count'))['total'] or 0

class Playlist(models.Model):
    VISIBILITY_CHOICES = [
        ('public', 'Публичный'),
        ('unlisted', 'По ссылке'),
        ('private', 'Приватный'),
    ]

    title = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    cover = models.ImageField(upload_to='playlists/covers/', blank=True, null=True, verbose_name="Обложка")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='playlists', verbose_name="Пользователь")
    tracks = models.ManyToManyField(Track, through='PlaylistTrack', related_name='playlists', verbose_name="Треки")
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='public', verbose_name="Видимость")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    slug = models.SlugField(max_length=250, blank=True, verbose_name="URL")

    class Meta:
        verbose_name = "Плейлист"
        verbose_name_plural = "Плейлисты"
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    @property
    def cover_url(self):
        if self.cover and hasattr(self.cover, 'url'):
            try:
                return self.cover.url
            except ValueError:
                return self.get_default_cover()
        return self.get_default_cover()

    def get_default_cover(self):
        return f"{settings.STATIC_URL}images/default-playlist-cover.png"

    @property
    def total_duration(self):
        return sum(track.duration or 0 for track in self.tracks.all())

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(f"{self.title}-{self.user.username}")
        super().save(*args, **kwargs)

class PlaylistTrack(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, verbose_name="Плейлист")
    track = models.ForeignKey(Track, on_delete=models.CASCADE, verbose_name="Трек")
    position = models.PositiveIntegerField(verbose_name="Позиция")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")

    class Meta:
        verbose_name = "Трек в плейлисте"
        verbose_name_plural = "Треки в плейлистах"
        unique_together = ('playlist', 'track')
        ordering = ['position']

    def __str__(self):
        return f"{self.track.title} в {self.playlist.title}"

class Activity(models.Model):
    ACTIVITY_TYPES = [
        ('track_upload', 'Загрузил трек'),
        ('track_like', 'Лайкнул трек'),
        ('user_follow', 'Подписался на пользователя'),
        ('playlist_create', 'Создал плейлист'),
        ('comment_add', 'Добавил комментарий'),
        ('album_upload', 'Загрузил альбом'),
        ('album_release', 'Запланировал релиз'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities', verbose_name="Пользователь")
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES, verbose_name="Тип активности")
    track = models.ForeignKey(Track, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Трек")
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='target_activities', verbose_name="Целевой пользователь")
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Плейлист")
    album = models.ForeignKey(Album, on_delete=models.CASCADE, null=True, blank=True, related_name='activities', verbose_name="Альбом")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Активность"
        verbose_name_plural = "Активности"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()}"

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('like', 'Лайк'),
        ('comment', 'Комментарий'),
        ('follow', 'Подписка'),
        ('mention', 'Упоминание'),
        ('system', 'Системное'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="Пользователь")
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, verbose_name="Тип уведомления")
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    message = models.TextField(verbose_name="Сообщение")
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='sent_notifications', verbose_name="От пользователя")
    track = models.ForeignKey(Track, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Трек")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ['-created_at']

    def __str__(self):
        return f"Уведомление для {self.user.username}: {self.title}"

    def mark_as_read(self):
        self.is_read = True
        self.save()
        
class TrackComment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField() 
    created_at = models.DateTimeField(auto_now_add=True)

    
    class Meta:
        verbose_name = "Комментарий к треку"
        verbose_name_plural = "Комментарии к трекам"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username}: {self.content[:50]}"
    
    @property
    def likes_count(self):
        """Возвращает количество лайков комментария"""
        return self.comment_likes.filter(is_like=True).count()
    
class CommentLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_likes')
    comment = models.ForeignKey(TrackComment, on_delete=models.CASCADE, related_name='comment_likes')
    is_like = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'comment')
        verbose_name = "Лайк комментария"
        verbose_name_plural = "Лайки комментариев"
    
    def __str__(self):
        action = "лайкнул" if self.is_like else "дизлайкнул"
        return f"{self.user.username} {action} комментарий {self.comment.id}"
    
    
# Добавьте эти модели в ваш models.py

class Chat(models.Model):
    CHAT_TYPES = [
        ('private', 'Личный чат'),
        ('group', 'Групповой чат'),
    ]
    
    chat_type = models.CharField(max_length=10, choices=CHAT_TYPES, default='private', verbose_name="Тип чата")
    name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Название чата")
    participants = models.ManyToManyField(User, related_name='chats', verbose_name="Участники")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    
    # Для групповых чатов
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                             related_name='admin_chats', verbose_name="Администратор")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    avatar = models.ImageField(upload_to='chat_avatars/', blank=True, null=True, verbose_name="Аватар чата")
    
    class Meta:
        verbose_name = "Чат"
        verbose_name_plural = "Чаты"
        ordering = ['-updated_at']
    
    def __str__(self):
        if self.chat_type == 'private':
            participants = list(self.participants.all())
            if len(participants) >= 2:
                return f"Чат: {participants[0].username} - {participants[1].username}"
            elif len(participants) == 1:
                return f"Чат: {participants[0].username}"
            return "Пустой чат"
        else:
            return self.name or f"Групповой чат #{self.id}"
    
    @property
    def last_message(self):
        """Возвращает последнее сообщение в чате"""
        return self.messages.first()
    
    @property
    def unread_count(self):
        """Возвращает количество непрочитанных сообщений"""
        return self.messages.filter(is_read=False).count()
    
    def get_other_participant(self, user):
        """Возвращает другого участника в приватном чате"""
        if self.chat_type == 'private':
            return self.participants.exclude(id=user.id).first()
        return None
    
    def mark_messages_as_read(self, user):
        """Отмечает все сообщения как прочитанные для пользователя"""
        self.messages.exclude(sender=user).filter(is_read=False).update(is_read=True)


class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Текст'),
        ('image', 'Изображение'),
        ('audio', 'Аудио'),
        ('file', 'Файл'),
        ('system', 'Системное'),
    ]
    
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages', verbose_name="Чат")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages', verbose_name="Отправитель")
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text', verbose_name="Тип сообщения")
    
    # Текстовое содержимое
    content = models.TextField(blank=True, null=True, verbose_name="Содержимое")
    
    # Файлы
    image = models.ImageField(upload_to='message_images/', blank=True, null=True, verbose_name="Изображение")
    audio = models.FileField(upload_to='message_audio/', blank=True, null=True, verbose_name="Аудио")
    file = models.FileField(upload_to='message_files/', blank=True, null=True, verbose_name="Файл")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отправки")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата редактирования")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    is_edited = models.BooleanField(default=False, verbose_name="Отредактировано")
    is_deleted = models.BooleanField(default=False, verbose_name="Удалено")
    
    # Ответ на сообщение
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='replies', verbose_name="Ответ на сообщение")
    
    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        ordering = ['-created_at']

    # ── Прозрачное шифрование at-rest ─────────────────────────────────────
    # from_db() расшифровывает content при загрузке из БД;
    # save() шифрует content перед записью в БД.
    # Весь остальной код работает с обычным текстом — шифрование невидимо.

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        if instance.content:
            from .crypto import decrypt_text
            instance.content = decrypt_text(instance.content)
        return instance

    def save(self, *args, **kwargs):
        from .crypto import encrypt_text, decrypt_text, ENC_PREFIX
        # Шифруем content перед записью, если он ещё не зашифрован
        plaintext = None
        if self.content:
            if not self.content.startswith(ENC_PREFIX):
                plaintext = self.content          # запоминаем оригинал
                self.content = encrypt_text(self.content)
        super().save(*args, **kwargs)
        # Возвращаем plaintext обратно в объект — чтобы код после save()
        # получал нормальный текст, а не зашифрованный токен
        if plaintext is not None:
            self.content = plaintext
        elif self.content and self.content.startswith(ENC_PREFIX):
            self.content = decrypt_text(self.content)
        # Обновляем время последнего обновления чата
        self.chat.updated_at = timezone.now()
        self.chat.save(update_fields=['updated_at'])

    def __str__(self):
        if self.message_type == 'text':
            txt = self.content or ''
            content_preview = txt[:50] + '...' if len(txt) > 50 else txt
            return f"{self.sender.username}: {content_preview}"
        else:
            return f"{self.sender.username}: [{self.get_message_type_display()}]"
    
    @property
    def file_name(self):
        """Возвращает имя файла"""
        if self.file:
            return self.file.name.split('/')[-1]
        elif self.image:
            return self.image.name.split('/')[-1]
        elif self.audio:
            return self.audio.name.split('/')[-1]
        return None
    
    @property
    def file_size(self):
        """Возвращает размер файла в читаемом формате"""
        file_obj = self.file or self.image or self.audio
        if file_obj:
            size = file_obj.size
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return None
    


class ChatMembership(models.Model):
    """Модель для управления участниками чата с дополнительными правами"""
    ROLE_CHOICES = [
        ('member', 'Участник'),
        ('admin', 'Администратор'),
        ('owner', 'Владелец'),
    ]
    
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member', verbose_name="Роль")
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата присоединения")
    is_muted = models.BooleanField(default=False, verbose_name="Заглушен")
    last_read_message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='read_by', verbose_name="Последнее прочитанное сообщение")
    
    class Meta:
        unique_together = ('chat', 'user')
        verbose_name = "Участие в чате"
        verbose_name_plural = "Участия в чатах"
    
    def __str__(self):
        return f"{self.user.username} в {self.chat}"
    
    @property
    def unread_count(self):
        """Количество непрочитанных сообщений для пользователя"""
        if self.last_read_message:
            return self.chat.messages.filter(
                created_at__gt=self.last_read_message.created_at
            ).exclude(sender=self.user).count()
        else:
            return self.chat.messages.exclude(sender=self.user).count()


class SearchQuery(models.Model):
    query = models.CharField(max_length=200, db_index=True, verbose_name="Поисковый запрос")
    count = models.PositiveIntegerField(default=1, verbose_name="Количество поисков")
    last_searched = models.DateTimeField(auto_now=True, verbose_name="Последний поиск")

    class Meta:
        verbose_name = "Поисковый запрос"
        verbose_name_plural = "Поисковые запросы"
        ordering = ['-count']

    def __str__(self):
        return f"{self.query} ({self.count})"

    @classmethod
    def record(cls, query):
        query = query.strip().lower()
        if not query or len(query) < 2:
            return
        obj, created = cls.objects.get_or_create(query=query)
        if not created:
            cls.objects.filter(pk=obj.pk).update(count=models.F('count') + 1)
