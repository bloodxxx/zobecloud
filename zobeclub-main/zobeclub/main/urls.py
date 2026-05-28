from django.urls import path
from . import views

urlpatterns = [
    # Основные страницы
    path('', views.home, name='home'),
    path('profile/', views.profile, name='profile'),
    path('user/<str:username>/', views.public_profile, name='public_profile'),
    path('user/<str:username>/block/', views.block_user, name='block_user'),
    path('user/<str:username>/unblock/', views.unblock_user, name='unblock_user'),
    path('search/', views.search_view, name='search'),
    
    # Аутентификация
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('register/', views.register, name='register'),
    
    # Треки
    path('upload/', views.upload_track, name='upload_track'),
    path('album/create/', views.upload_album, name='upload_album'),
    path('album/<int:pk>/', views.album_detail, name='album_detail'),
    path('album/<int:pk>/delete/', views.delete_album, name='delete_album'),
    path('album/<int:pk>/edit/', views.edit_album, name='edit_album'),
    path('album/<int:album_pk>/add-track/<int:track_id>/', views.add_track_to_album, name='add_track_to_album'),
    path('album/<int:album_pk>/remove-track/<int:track_id>/', views.remove_track_from_album, name='remove_track_from_album'),
    path('api/album/<int:album_pk>/reorder/', views.reorder_album_tracks, name='reorder_album_tracks'),
    path('track/<int:pk>/', views.track_detail, name='track_detail'),
    path('track/<int:pk>/edit/', views.edit_track, name='edit_track'),
    path('track/<int:pk>/delete/', views.delete_track, name='delete_track'),
    
    # Профиль
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('change-username/', views.change_username, name='change_username'),
    
    # Премиум подписка
    path('premium/', views.premium_ord, name='premium_ord'),
    path('premium/checkout/<str:plan_id>/', views.premium_checkout, name='premium_checkout'),
    path('premium/process-payment/', views.process_premium_payment, name='process_premium_payment'),
    path('premium/success/', views.premium_success, name='premium_success'),
    path('premium/status/', views.premium_status, name='premium_status'),
    path('premium/cancel/', views.cancel_premium, name='cancel_premium'),
    path('premium/analytics/', views.premium_analytics, name='premium_analytics'),
    
    path('docs/license/', views.download_license, name='download_license'),
    # API endpoints
    path('api/check-username/', views.check_username_availability, name='check_username_availability'),
    path('api/upload-avatar/', views.upload_avatar, name='upload_avatar'),
    path('api/upload-banner/', views.upload_banner, name='upload_banner'),
    path('api/premium-status/', views.premium_status_api, name='premium_status_api'),
    path('api/live-search/', views.live_search_api, name='live_search_api'),
    path('api/popular-searches/', views.popular_searches_api, name='popular_searches_api'),
    path('api/platform-stats/', views.get_platform_stats_api, name='platform_stats_api'),
    path('api/user-tracks/<str:username>/', views.get_user_tracks_api, name='user_tracks_api'),
    path('api/increment-play/<int:track_id>/', views.increment_play_count, name='increment_play_count'),
    
   # API для лайков и комментариев треков
    path('api/track/<int:track_id>/like/', views.toggle_like_track, name='track_like_api'),
    path('api/track/<int:track_id>/comment/', views.add_track_comment, name='add_track_comment'),
    path('api/comment/<int:comment_id>/delete/', views.delete_track_comment, name='delete_track_comment'),
    path('api/comment/<int:comment_id>/like/', views.toggle_comment_like, name='toggle_comment_like'),

    # Дополнительные страницы
    path('tracks/latest/', views.get_latest_tracks, name='latest_tracks'),
    path('tracks/popular/', views.get_popular_tracks, name='popular_tracks'),
    path('users/', views.user_list, name='user_list'),
    
    # Плейлисты
    path('playlists/', views.playlist_list, name='playlist_list'),
    path('playlists/public/', views.public_playlists, name='public_playlists'),
    path('playlists/create/', views.create_playlist, name='create_playlist'),
    path('playlist/<int:pk>/', views.playlist_detail, name='playlist_detail'),
    path('playlist/<int:pk>/edit/', views.edit_playlist, name='edit_playlist'),
    path('playlist/<int:pk>/delete/', views.delete_playlist, name='delete_playlist'),
    path('user/<str:username>/playlists/', views.user_playlists, name='user_playlists'),
    
    # API для плейлистов
    path('api/playlist/<int:playlist_pk>/add-track/<int:track_id>/', views.add_track_to_playlist, name='add_track_to_playlist'),
    path('api/playlist/<int:playlist_pk>/remove-track/<int:track_id>/', views.remove_track_from_playlist, name='remove_track_from_playlist'),
    path('api/playlist/<int:playlist_pk>/reorder/', views.reorder_playlist_tracks, name='reorder_playlist_tracks'),
    path('api/user/playlists/', views.get_user_playlists_api, name='get_user_playlists_api'),
    path('api/playlist/<int:pk>/tracks/', views.get_playlist_tracks_api, name='get_playlist_tracks_api'),
    
    # Вкладки профиля
    path('profile/tab/<str:tab_name>/', views.profile_tab_content, name='profile_tab_content'),
    
    # Чаты и сообщения
    path('chats/', views.chat_list, name='chat_list'),
    path('chat/<int:chat_id>/', views.chat_detail, name='chat_detail'),
    path('chat/start/<str:username>/', views.start_chat, name='start_chat'),
    path('api/chat/<int:chat_id>/send/', views.send_message, name='send_message'),
    path('api/message/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('api/message/<int:message_id>/edit/', views.edit_message, name='edit_message'),
    path('api/users/search/', views.search_users_for_chat, name='search_users_for_chat'),
    path('api/chat/unread-count/', views.get_unread_messages_count, name='get_unread_messages_count'),
    path('api/chat/<int:chat_id>/messages/', views.get_new_messages, name='get_new_messages'),
]