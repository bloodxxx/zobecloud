from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    Track, UserProfile, PremiumSubscription, Genre, Tag, 
    TrackLike, Follow, Playlist, PlaylistTrack, 
    Activity, Notification, TrackComment, CommentLike  # Добавили новые модели
)
@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'tracks_count', 'description']
    search_fields = ['name', 'description']
    list_editable = ['color']

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color']
    search_fields = ['name']
    list_editable = ['color']

@admin.register(TrackLike)
class TrackLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'track', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'track__title']

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ['follower', 'following', 'created_at']
    list_filter = ['created_at']
    search_fields = ['follower__username', 'following__username']

@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'visibility', 'get_tracks_count', 'created_at']
    list_filter = ['visibility', 'created_at']
    search_fields = ['title', 'user__username', 'description']
    readonly_fields = ['created_at', 'updated_at']

    def get_tracks_count(self, obj):
        return obj.tracks.count()
    get_tracks_count.short_description = 'Треков'

@admin.register(PlaylistTrack)
class PlaylistTrackAdmin(admin.ModelAdmin):
    list_display = ['playlist', 'track', 'position', 'added_at']
    list_filter = ['added_at']
    search_fields = ['playlist__title', 'track__title']

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity_type', 'track', 'target_user', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['user__username', 'track__title', 'target_user__username']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        updated = queryset.update(is_read=True)
        self.message_user(request, f'Отмечено как прочитанное: {updated}')
    mark_as_read.short_description = "Отметить как прочитанное"
    
    def mark_as_unread(self, request, queryset):
        updated = queryset.update(is_read=False)
        self.message_user(request, f'Отмечено как непрочитанное: {updated}')
    mark_as_unread.short_description = "Отметить как непрочитанное"

@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'visibility', 'plays_count', 'uploaded_at']
    list_filter = ['visibility', 'uploaded_at', 'allow_downloads', 'genre']
    search_fields = ['title', 'user__username', 'description']
    readonly_fields = ['plays_count', 'uploaded_at', 'slug']
    filter_horizontal = ['tags']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_private', 'is_premium', 'created_at']
    list_filter = ['is_private', 'created_at']
    search_fields = ['user__username', 'user__email', 'bio']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(PremiumSubscription)
class PremiumSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'plan_type', 'status_badge', 'price', 
        'telegram_username', 'payment_status', 'created_at', 'admin_actions'
    ]
    list_filter = [
        'status', 'plan_type', 'admin_confirmed', 'created_at', 
        'telegram_payment_sent_at', 'is_active'
    ]
    search_fields = [
        'user__username', 'user__email', 'telegram_username', 
        'telegram_message', 'admin_notes'
    ]
    readonly_fields = [
        'created_at', 'activated_at', 'cancelled_at', 
        'telegram_payment_sent_at', 'confirmed_at'
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'plan_type', 'price', 'status')
        }),
        ('Даты', {
            'fields': ('created_at', 'activated_at', 'expires_at', 'cancelled_at'),
            'classes': ('collapse',)
        }),
        ('Telegram платеж', {
            'fields': ('telegram_username', 'telegram_payment_sent_at', 'telegram_message'),
            'classes': ('wide',)
        }),
        ('Административное подтверждение', {
            'fields': ('admin_confirmed', 'confirmed_by', 'confirmed_at', 'admin_notes'),
            'classes': ('wide',)
        }),
        ('Дополнительно', {
            'fields': ('auto_renewal', 'is_active'),
            'classes': ('collapse',)
        }),
    )

    actions = ['confirm_payments', 'activate_subscriptions', 'cancel_subscriptions']

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'Пользователь'

    def status_badge(self, obj):
        colors = {
            'pending_payment': '#ffc107',
            'payment_sent': '#17a2b8',
            'payment_confirmed': '#28a745',
            'active': '#28a745',
            'expired': '#6c757d',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Статус'

    def payment_status(self, obj):
        if obj.admin_confirmed:
            return format_html(
                '<span style="color: green;">✅ Подтверждено</span><br>'
                '<small>Администратор: {}</small>',
                obj.confirmed_by.username if obj.confirmed_by else 'Неизвестно'
            )
        elif obj.telegram_payment_sent_at:
            return format_html(
                '<span style="color: orange;">⏳ Ожидает подтверждения</span><br>'
                '<small>Отправлено: {}</small>',
                obj.telegram_payment_sent_at.strftime('%d.%m.%Y %H:%M')
            )
        else:
            return format_html('<span style="color: red;">❌ Не оплачено</span>')
    payment_status.short_description = 'Статус оплаты'

    def admin_actions(self, obj):
        if not obj.admin_confirmed and obj.status == 'payment_sent':
            return format_html(
                '<a href="javascript:void(0)" onclick="if(confirm(\'Подтвердить оплату?\')) {{ window.location.href=\'/admin/main/premiumsubscription/{}/change/?confirm_payment=1\' }}" class="button" style="background: #28a745; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; text-decoration: none;">Подтвердить оплату</a>',
                obj.pk
            )
        elif obj.admin_confirmed and not obj.is_active:
            return format_html(
                '<a href="javascript:void(0)" onclick="if(confirm(\'Активировать подписку?\')) {{ window.location.href=\'/admin/main/premiumsubscription/{}/change/?activate=1\' }}" class="button" style="background: #17a2b8; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer; text-decoration: none;">Активировать</a>',
                obj.pk
            )
        return '-'
    admin_actions.short_description = 'Действия'

    def confirm_payments(self, request, queryset):
        updated = 0
        for subscription in queryset.filter(admin_confirmed=False):
            subscription.confirm_payment(request.user)
            updated += 1
        
        self.message_user(
            request,
            f'Подтверждено платежей: {updated}',
            level='SUCCESS' if updated > 0 else 'WARNING'
        )
    confirm_payments.short_description = "Подтвердить выбранные платежи"

    def activate_subscriptions(self, request, queryset):
        updated = queryset.filter(admin_confirmed=True, is_active=False).update(
            is_active=True,
            status='active',
            activated_at=timezone.now()
        )
        self.message_user(
            request,
            f'Активировано подписок: {updated}',
            level='SUCCESS' if updated > 0 else 'WARNING'
        )
    activate_subscriptions.short_description = "Активировать выбранные подписки"

    def cancel_subscriptions(self, request, queryset):
        updated = 0
        for subscription in queryset.filter(is_active=True):
            subscription.cancel()
            updated += 1
        
        self.message_user(
            request,
            f'Отменено подписок: {updated}',
            level='SUCCESS' if updated > 0 else 'WARNING'
        )
    cancel_subscriptions.short_description = "Отменить выбранные подписки"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        total_subscriptions = PremiumSubscription.objects.count()
        pending_confirmations = PremiumSubscription.objects.filter(
            status='payment_sent', 
            admin_confirmed=False
        ).count()
        active_subscriptions = PremiumSubscription.objects.filter(is_active=True).count()
        
        extra_context['premium_stats'] = {
            'total': total_subscriptions,
            'pending': pending_confirmations,
            'active': active_subscriptions,
        }
        
        return super().changelist_view(request, extra_context)

    def response_change(self, request, obj):
        if 'confirm_payment' in request.GET:
            obj.confirm_payment(request.user)
            self.message_user(request, f'Оплата для {obj.user.username} подтверждена!')
        elif 'activate' in request.GET:
            obj.activate()
            self.message_user(request, f'Подписка для {obj.user.username} активирована!')
        
        return super().response_change(request, obj)
    
# Добавьте в конец файла admin.py:

@admin.register(TrackComment)
class TrackCommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'track', 'content_preview', 'created_at', 'likes_count']
    list_filter = ['created_at']
    search_fields = ['user__username', 'track__title', 'content']
    readonly_fields = ['created_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Содержание'

@admin.register(CommentLike)
class CommentLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'comment', 'is_like', 'created_at']
    list_filter = ['is_like', 'created_at']
    search_fields = ['user__username', 'comment__content']