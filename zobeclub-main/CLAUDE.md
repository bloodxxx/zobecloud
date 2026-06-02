# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All Django management commands must be run from `zobeclub/` (where `manage.py` lives):

```bash
cd zobeclub

# Run development server
python manage.py runserver

# Apply migrations
python manage.py migrate

# Create new migration after model changes
python manage.py makemigrations

# Run tests
python manage.py test main

# Run a single test class or method
python manage.py test main.tests.MyTestClass
python manage.py test main.tests.MyTestClass.test_method

# Open Django shell
python manage.py shell

# Collect static files (production)
python manage.py collectstatic
```

Install dependencies:
```bash
pip install -r requirements.txt
```

## Architecture

Single Django 5.2 app (`main`) inside the `zobeclub/` project directory. No external services — SQLite database, local media files.

**Project layout:**
- `zobeclub/zobeclub/` — Django project config (settings, root URLs, wsgi/asgi)
- `zobeclub/main/` — the only app: models, views, URLs, admin, middleware, crypto
- `zobeclub/templates/main/` — all HTML templates
- `zobeclub/static/` — CSS (`style.css`), JS (`track_player.js`, `chat.js`, `chat-detail.js`, `playlists.js`), images
- `zobeclub/media/` — user-uploaded files (avatars, banners, track audio/covers, album/playlist covers)

**Data model summary:**
- `UserProfile` — extends Django `User` 1-to-1; avatar/banner auto-resized on save; `is_premium` property checks `PremiumSubscription`; `is_online` based on `last_seen` (updated by `LastSeenMiddleware`, throttled to 1/min)
- `Track` — audio upload with genre/tags, visibility (public/unlisted/private), album association, play/download counters; slug auto-generated from title+username
- `Album` — groups tracks; supports scheduled `release_at`
- `Playlist` / `PlaylistTrack` — M2M through table with `position` ordering
- `Chat` / `Message` — private and group chats; `Message.content` is transparently encrypted at rest using Fernet via `main/crypto.py` (key derived from `SECRET_KEY`); `from_db()` decrypts on load, `save()` encrypts before write
- `PremiumSubscription` — manual confirmation flow (admin sets `admin_confirmed=True`); premium payment is coordinated through Telegram
- `Block` — bidirectional block enforcement; checked in views and chat

**Key patterns:**
- All API endpoints (like/unlike, play count, chat send/poll) return JSON; most page endpoints render templates
- Chat uses polling (`/api/chat/<id>/messages/` with `?after=<message_id>`) — no WebSockets
- Image uploads (avatar, banner, track cover) are resized server-side via Pillow in model `save()`
- `UserProfile` is auto-created on `User` creation via `post_save` signal
- Admin uses `django-unfold` with dark theme and green accent (`#59d344`)
- Language: `ru-ru`, timezone: `Europe/Moscow`
- File upload limit: 15 MB (`FILE_UPLOAD_MAX_MEMORY_SIZE`)
