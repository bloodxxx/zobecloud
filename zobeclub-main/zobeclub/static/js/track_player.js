// ════════════════════════════════════════════════════════════════════════
// ZobeClub Player — версия 2 (Blob-based)
// ────────────────────────────────────────────────────────────────────────
//
// ПРОБЛЕМА которую решает этот код:
//   Django runserver плохо обрабатывает HTTP Range Requests для медиа.
//   Когда браузер пытается перемотать трек в нескачанную часть, он
//   отправляет Range-запрос, сервер отвечает некорректно — и seek
//   тихо проваливается, трек начинает играть с начала.
//
// РЕШЕНИЕ:
//   1. Качаем весь mp3-файл через fetch() как Blob (один обычный GET).
//   2. Создаём Blob URL через URL.createObjectURL(blob).
//   3. Назначаем audio.src = blobUrl. Теперь файл целиком в памяти.
//   4. audio.currentTime = X работает мгновенно для ЛЮБОЙ позиции,
//      потому что seek идёт по локальному blob, без сетевых запросов.
//
// ТРЕЙДОФФ:
//   Воспроизведение начинается после полной загрузки трека (3-10 МБ).
//   На быстром интернете задержка 0.5-2 сек. Зато перемотка работает
//   идеально для всех треков с первого клика.
//
// ════════════════════════════════════════════════════════════════════════


// ── SPA роутер ──────────────────────────────────────────────────────────
// Перехватывает клики по ссылкам и грузит страницы через fetch,
// чтобы плеер не прерывался при навигации.
class SPARouter {
  constructor() {
    this._busy = false;
    document.addEventListener('click', e => {
      const a = e.target.closest('a[href]');
      if (a && this._intercept(a)) { e.preventDefault(); this.go(a.href); }
    });
    window.addEventListener('popstate', () => this.go(location.href, false));
  }

  _intercept(a) {
    try {
      const u = new URL(a.href);
      if (u.origin !== location.origin)   return false;
      if (a.target === '_blank')           return false;
      if (a.hasAttribute('download'))      return false;
      if (u.pathname.startsWith('/admin')) return false;
      if (u.pathname === '/logout/')       return false;
      if (/\.(mp3|mp4|jpg|jpeg|png|gif|webp|pdf|zip|svg)$/i.test(u.pathname)) return false;
      if (u.pathname === location.pathname && u.hash) return false;
      return true;
    } catch { return false; }
  }

  async go(url, push = true) {
    if (this._busy) return;
    this._busy = true;
    this._loader(true);
    try {
      const res = await fetch(url, { headers: { 'X-SPA-Request': '1' }, credentials: 'same-origin' });
      if (!res.ok) throw new Error(res.status);
      const html = await res.text();
      const doc  = new DOMParser().parseFromString(html, 'text/html');

      const newMain = doc.getElementById('page-main');
      const curMain = document.getElementById('page-main');
      if (newMain && curMain) {
        curMain.innerHTML = newMain.innerHTML;
        curMain.querySelectorAll('script').forEach(old => {
          const s = document.createElement('script');
          s.textContent = old.textContent;
          document.body.appendChild(s);
          document.body.removeChild(s);
        });
      }

      const newMsg = doc.getElementById('page-messages');
      if (newMsg) {
        newMsg.querySelectorAll('[data-msg]').forEach(el => {
          showToast(el.dataset.msg, el.dataset.type || 'success');
        });
      }

      document.querySelectorAll('style[data-spa-page]').forEach(el => el.remove());
      doc.querySelectorAll('head style').forEach(s => {
        if (!s.textContent.trim()) return;
        const el = document.createElement('style');
        el.setAttribute('data-spa-page', '1');
        el.textContent = s.textContent;
        document.head.appendChild(el);
      });

      const newScripts = doc.getElementById('__page_scripts');
      if (newScripts) {
        const cur = document.getElementById('__page_scripts');
        if (cur) cur.innerHTML = newScripts.innerHTML;
        newScripts.querySelectorAll('script').forEach(old => {
          const s = document.createElement('script');
          if (old.src) { s.src = old.src; s.async = false; }
          else s.textContent = old.textContent;
          document.body.appendChild(s);
          if (!old.src) document.body.removeChild(s);
        });
      }

      document.title = doc.title;
      if (push) history.pushState({}, '', url);
      window.scrollTo(0, 0);

      document.querySelectorAll('.navbar-nav .nav-link').forEach(a => {
        try {
          const u = new URL(a.href);
          a.classList.toggle('active', u.pathname !== '/' && url.includes(u.pathname));
        } catch {}
      });
    } catch {
      location.href = url;
    } finally {
      this._busy = false;
      this._loader(false);
    }
  }

  _loader(start) {
    const bar = document.getElementById('spa-loader');
    if (!bar) return;
    if (start) {
      bar.style.transition = 'none';
      bar.style.width = '0%';
      bar.style.opacity = '1';
      requestAnimationFrame(() => { bar.style.transition = 'width 8s linear'; bar.style.width = '88%'; });
    } else {
      bar.style.transition = 'width .2s ease';
      bar.style.width = '100%';
      setTimeout(() => { bar.style.opacity = '0'; setTimeout(() => { bar.style.width = '0%'; }, 300); }, 200);
    }
  }
}


// ════════════════════════════════════════════════════════════════════════
// ZobePlayer — основной класс плеера
// ════════════════════════════════════════════════════════════════════════
class ZobePlayer {
  constructor() {
    // ── DOM элементы ────────────────────────────────────────────────────
    const $ = id => document.getElementById(id);
    this.audio = $('zpAudio');
    this.bar   = $('miniPlayer');
    this.el = {
      cover:  $('zpCover'),  img:    $('zpCoverImg'), fb:     $('zpCoverFb'),
      title:  $('zpTitle'),  artist: $('zpArtist'),
      play:   $('zpPlay'),   playI:  $('zpPlayIcon'),
      prev:   $('zpPrev'),   next:   $('zpNext'),
      cur:    $('zpCur'),    dur:    $('zpDur'),
      bar:    $('zpProgress'), fill: $('zpFill'),     thumb:  $('zpThumb'),
      vol:    $('zpVol'),    volI:   $('zpVolIcon'),
      close:  $('zpClose'),
    };

    // ── Публичное состояние ─────────────────────────────────────────────
    this.track     = null;     // текущий трек {id,title,artist,audioUrl,coverUrl}
    this.playlist  = [];
    this.idx       = 0;
    this.volume    = 0.4;
    this.isPlaying = false;

    // ── Внутреннее состояние ────────────────────────────────────────────
    this._blobUrl     = null;  // текущий Blob URL (для revoke)
    this._abort       = null;  // AbortController текущего fetch
    this._loadedUrl   = null;  // URL который сейчас загружен в audio (исходный)
    this._pendingSeek = null;  // {sec} — применить когда duration появится
    this._wantPlay    = false; // запустить play() как только canplay сработает

    this._bindUI();
    this._bindAudio();
    this._setVolume(this.volume);
    this._restoreFromStorage();
  }

  // ════════════════════════════════════════════════════════════════════
  // ПУБЛИЧНЫЙ API
  // ════════════════════════════════════════════════════════════════════

  playTrack(data) {
    if (!data || !data.audioUrl) return;
    this.track = data;

    const i = this.playlist.findIndex(t => t.id === data.id);
    if (i === -1) { this.playlist = [data]; this.idx = 0; }
    else this.idx = i;

    this._renderInfo();
    this._show();
    this._loadAndPlay(data.audioUrl, 0, /*autoplay*/ true);

    // Считаем прослушивание
    if (data.id) {
      fetch(`/api/increment-play/${data.id}/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': this._csrf() },
        credentials: 'same-origin',
      }).catch(() => {});
    }
    this._save();
  }

  togglePlay() {
    if (!this.track) return;
    if (this.audio.paused) this.audio.play().catch(() => {});
    else                    this.audio.pause();
  }

  prev() {
    if (!this.playlist.length) return;
    this.idx = this.idx > 0 ? this.idx - 1 : this.playlist.length - 1;
    this.playTrack(this.playlist[this.idx]);
  }

  next() {
    if (!this.playlist.length) return;
    this.idx = this.idx < this.playlist.length - 1 ? this.idx + 1 : 0;
    this.playTrack(this.playlist[this.idx]);
  }

  setPlaylist(tracks, startIdx = 0) {
    if (!tracks || !tracks.length) return;
    this.playlist = tracks;
    this.idx = Math.max(0, Math.min(startIdx, tracks.length - 1));
    this.playTrack(tracks[this.idx]);
  }

  addToPlaylist(data) {
    if (!this.playlist.find(t => t.id === data.id)) this.playlist.push(data);
    this._save();
  }

  getCurrentTrack()  { return this.track; }
  getIsPlaying()     { return this.isPlaying; }
  getPlaylist()      { return this.playlist; }
  forceUpdateState() { this._restoreFromStorage(); }

  // ════════════════════════════════════════════════════════════════════
  // ЗАГРУЗКА ТРЕКА (КЛЮЧЕВОЙ МЕТОД)
  // ════════════════════════════════════════════════════════════════════
  // Скачивает весь файл как Blob и подсовывает audio-элементу.
  // Если url совпадает с уже загруженным — не перезагружает.
  async _loadAndPlay(url, startSec, autoplay) {
    // Тот же трек уже загружен в audio? Просто seek + play.
    if (this._loadedUrl === url && this._blobUrl) {
      if (startSec > 0 && isFinite(this.audio.duration)) {
        this.audio.currentTime = startSec;
      }
      if (autoplay) this.audio.play().catch(() => {});
      return;
    }

    // Отменяем предыдущую загрузку (если идёт)
    this._abort?.abort();
    this._abort = new AbortController();
    const signal = this._abort.signal;

    this._pendingSeek = startSec > 0 ? { sec: startSec } : null;
    this._wantPlay    = autoplay;
    this.bar.classList.add('loading');

    try {
      const res = await fetch(url, { signal, credentials: 'same-origin' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const blob = await res.blob();
      if (signal.aborted) return;

      // Освобождаем предыдущий blob URL
      if (this._blobUrl) URL.revokeObjectURL(this._blobUrl);
      this._blobUrl   = URL.createObjectURL(blob);
      this._loadedUrl = url;

      this.audio.src = this._blobUrl;
      this.audio.load();
    } catch (e) {
      if (e.name === 'AbortError') return;
      this.bar.classList.remove('loading');
      this._error('Не удалось загрузить трек');
    }
  }

  // ════════════════════════════════════════════════════════════════════
  // ПЕРЕМОТКА
  // ════════════════════════════════════════════════════════════════════
  // Работает мгновенно для любой позиции, потому что данные в blob.
  _seek(pct) {
    if (!this.track) return;
    pct = Math.max(0, Math.min(1, pct));
    const d = this.audio.duration;

    if (isFinite(d) && d > 0) {
      this.audio.currentTime = pct * d;
      this._pendingSeek = null;
      this._renderProgress();
    } else {
      // Длительность ещё не известна — запомним и применим в loadedmetadata
      this._pendingSeek = { pct };
    }
  }

  // ════════════════════════════════════════════════════════════════════
  // UI EVENTS
  // ════════════════════════════════════════════════════════════════════
  _bindUI() {
    this.el.play.addEventListener('click',  () => this.togglePlay());
    this.el.prev.addEventListener('click',  () => this.prev());
    this.el.next.addEventListener('click',  () => this.next());
    this.el.close.addEventListener('click', () => this._hide());
    this.el.vol.addEventListener('input',   e  => this._setVolume(e.target.value / 100));
    this.el.volI.addEventListener('click',  () => this._mute());
    document.addEventListener('keydown',    e  => this._key(e));

    // Перемотка через Pointer Events с capture (надёжнее mouse+touch)
    const pctOf = e => {
      const r = this.el.bar.getBoundingClientRect();
      return r.width ? Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) : 0;
    };
    this.el.bar.addEventListener('pointerdown', e => {
      if (!this.track) return;
      e.preventDefault();
      this.el.bar.setPointerCapture(e.pointerId);
      this._seek(pctOf(e));
    });
    this.el.bar.addEventListener('pointermove', e => {
      if (!this.track || !e.buttons) return;
      this._seek(pctOf(e));
    });
  }

  // ════════════════════════════════════════════════════════════════════
  // AUDIO EVENTS
  // ════════════════════════════════════════════════════════════════════
  _bindAudio() {
    this.audio.addEventListener('loadedmetadata', () => {
      this.el.dur.textContent = this._fmt(this.audio.duration);
      // Применяем отложенный seek (если был pct — сейчас знаем duration)
      if (this._pendingSeek) {
        const { pct, sec } = this._pendingSeek;
        const t = sec !== undefined ? sec : pct * this.audio.duration;
        this.audio.currentTime = Math.max(0, Math.min(this.audio.duration, t));
        this._pendingSeek = null;
      }
      this._renderProgress();
    });

    this.audio.addEventListener('canplay', () => {
      this.bar.classList.remove('loading');
      if (this._wantPlay) {
        this._wantPlay = false;
        this.audio.play().catch(err => {
          if (err.name !== 'NotAllowedError') this._error('Не получилось запустить');
        });
      }
    });

    this.audio.addEventListener('timeupdate', () => {
      this._renderProgress();
      // Сохраняем позицию каждые 5 секунд воспроизведения
      if (this.isPlaying && Math.floor(this.audio.currentTime) % 5 === 0) this._save();
    });

    this.audio.addEventListener('seeked', () => this._renderProgress());
    this.audio.addEventListener('ended',  () => this._onEnd());
    this.audio.addEventListener('error',  () => {
      this.bar.classList.remove('loading');
      this._error('Ошибка воспроизведения');
      this.isPlaying = false;
      this._renderControls();
    });

    this.audio.addEventListener('play', () => {
      this.isPlaying = true;
      this._renderControls();
      this._save();
      document.dispatchEvent(new CustomEvent('zp:playstate', { detail: { playing: true } }));
    });
    this.audio.addEventListener('pause', () => {
      this.isPlaying = false;
      this._renderControls();
      this._save();
      document.dispatchEvent(new CustomEvent('zp:playstate', { detail: { playing: false } }));
    });

    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && this.track) this._renderControls();
    });
  }

  // ════════════════════════════════════════════════════════════════════
  // РЕНДЕР UI
  // ════════════════════════════════════════════════════════════════════
  _renderInfo() {
    if (!this.track) return;
    const t = this.track;
    this.el.title.textContent  = t.title;
    this.el.artist.textContent = t.artist;

    if (t.coverUrl) {
      this.el.img.src = t.coverUrl;
      this.el.img.style.display = 'block';
      this.el.fb.style.display  = 'none';
    } else {
      this.el.img.style.display = 'none';
      this.el.fb.style.display  = 'flex';
    }

    if (t.id) {
      this.el.cover.onclick  = () => location.href = `/track/${t.id}/`;
      this.el.title.onclick  = () => location.href = `/track/${t.id}/`;
      this.el.artist.onclick = () => location.href = `/user/${t.artist}/`;
    }
    document.title = `${t.title} — ${t.artist} | ZobeCloud`;
    document.dispatchEvent(new CustomEvent('zp:trackchange', { detail: { track: t } }));
  }

  _renderProgress() {
    const d = this.audio.duration;
    if (!isFinite(d) || d <= 0) {
      this.el.fill.style.width = '0%';
      this.el.thumb.style.left = '0%';
      this.el.cur.textContent  = '0:00';
      return;
    }
    const pct = (this.audio.currentTime / d) * 100;
    this.el.fill.style.width = pct + '%';
    this.el.thumb.style.left = pct + '%';
    this.el.cur.textContent  = this._fmt(this.audio.currentTime);
  }

  _renderControls() {
    if (this.isPlaying) {
      this.el.playI.className = 'bi bi-pause-fill';
      this.bar.classList.add('playing');
    } else {
      this.el.playI.className = 'bi bi-play-fill';
      this.bar.classList.remove('playing');
    }
  }

  // ════════════════════════════════════════════════════════════════════
  // ПРОЧЕЕ
  // ════════════════════════════════════════════════════════════════════
  _onEnd() {
    if (this.playlist.length > 1) this.next();
    else { this.audio.currentTime = 0; this._renderControls(); }
  }

  _show() {
    this.bar.style.display = 'flex';
    this.bar.classList.add('show');
    this.bar.classList.remove('hide');
  }

  _hide() {
    this.bar.classList.add('hide');
    this.bar.classList.remove('show');
    setTimeout(() => {
      this.bar.style.display = 'none';
      this.audio.pause();
      this.audio.removeAttribute('src');
      this.audio.load();
      if (this._blobUrl) { URL.revokeObjectURL(this._blobUrl); this._blobUrl = null; }
      this._loadedUrl = null;
      this.track = null;
      this._clearStorage();
    }, 300);
  }

  _setVolume(v) {
    if (typeof v === 'string') v = parseFloat(v);
    if (v > 1) v = v / 100; // принимаем и 0..1, и 0..100
    this.volume = v;
    this.audio.volume = v;
    this.el.vol.value = Math.round(v * 100);
    if      (v === 0)   this.el.volI.className = 'bi bi-volume-mute zp-vol-icon';
    else if (v < 0.5)   this.el.volI.className = 'bi bi-volume-down zp-vol-icon';
    else                this.el.volI.className = 'bi bi-volume-up zp-vol-icon';
    this._save();
  }

  _mute() {
    if (this.volume > 0) { this._prevVol = this.volume; this._setVolume(0); }
    else this._setVolume(this._prevVol || 0.4);
  }

  _key(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (!this.track) return;
    const d = this.audio.duration || 1;
    switch (e.code) {
      case 'Space':      e.preventDefault(); this.togglePlay(); break;
      case 'ArrowLeft':  e.preventDefault(); this._seek((this.audio.currentTime - 10) / d); break;
      case 'ArrowRight': e.preventDefault(); this._seek((this.audio.currentTime + 10) / d); break;
      case 'ArrowUp':    e.preventDefault(); this._setVolume(Math.min(1, this.volume + 0.1)); break;
      case 'ArrowDown':  e.preventDefault(); this._setVolume(Math.max(0, this.volume - 0.1)); break;
      case 'KeyM':       e.preventDefault(); this._mute(); break;
      case 'KeyN':       e.preventDefault(); this.next(); break;
      case 'KeyP':       e.preventDefault(); this.prev(); break;
    }
  }

  _fmt(s) {
    if (!s || isNaN(s)) return '0:00';
    return Math.floor(s / 60) + ':' + String(Math.floor(s % 60)).padStart(2, '0');
  }

  _error(msg) {
    const el = document.createElement('div');
    el.style.cssText = 'position:fixed;top:20px;right:20px;background:#c0392b;color:#fff;padding:.55rem 1rem;border-radius:10px;font-size:.84rem;font-weight:600;z-index:9999;';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }

  _csrf() {
    const m = document.cookie.match(/(?:^|;)\s*csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  // ════════════════════════════════════════════════════════════════════
  // localStorage
  // ════════════════════════════════════════════════════════════════════
  _save() {
    try {
      localStorage.setItem('zp_state_v2', JSON.stringify({
        track:    this.track,
        playlist: this.playlist,
        idx:      this.idx,
        volume:   this.volume,
        playing:  this.isPlaying,
        time:     this.audio.currentTime || 0,
      }));
    } catch {}
  }

  _restoreFromStorage() {
    try {
      const raw = localStorage.getItem('zp_state_v2');
      if (!raw) return;
      const s = JSON.parse(raw);

      this.track    = s.track    || null;
      this.playlist = s.playlist || [];
      this.idx      = s.idx      || 0;
      this.isPlaying = false;
      if (s.volume !== undefined) this._setVolume(s.volume);

      if (this.track) {
        this._renderInfo();
        this._show();
        this._renderControls();
        // autoplay браузер заблокирует — упадёт тихо, кнопка останется paused
        this._loadAndPlay(this.track.audioUrl, s.time || 0, !!s.playing);
      }
    } catch {}
  }

  _clearStorage() {
    try { localStorage.removeItem('zp_state_v2'); } catch {}
  }
}


// ════════════════════════════════════════════════════════════════════════
// Инициализация
// ════════════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  window.ZobePlayer = new ZobePlayer();
  window.ZobeSPA    = new SPARouter();
});

window.addEventListener('beforeunload', () => window.ZobePlayer?._save());
window.addEventListener('pagehide',     () => window.ZobePlayer?._save());
window.addEventListener('pageshow', e => {
  if (e.persisted && window.ZobePlayer) window.ZobePlayer._restoreFromStorage();
});

// Хелперы для шаблонов (обратная совместимость)
function playTrackInMiniPlayer(data)  { window.ZobePlayer?.playTrack(data); }
function addTrackToPlaylist(data)     { window.ZobePlayer?.addToPlaylist(data); }
function setPlaylist(tracks, idx = 0) { window.ZobePlayer?.setPlaylist(tracks, idx); }
function updatePlayerState()          { window.ZobePlayer?.forceUpdateState(); }


// ════════════════════════════════════════════════════════════════════════
// Toast уведомления
// ════════════════════════════════════════════════════════════════════════
window.showToast = function(message, type) {
  type = type || 'success';
  const container = document.getElementById('toast-container');
  if (!container) return;
  const icons  = { success: 'bi-check-circle', error: 'bi-exclamation-circle', warning: 'bi-exclamation-triangle', info: 'bi-info-circle' };
  const colors = { success: 'var(--accent-green)', error: '#e74c3c', warning: '#f39c12', info: '#3498db' };
  const icon  = icons[type]  || icons.info;
  const color = colors[type] || colors.info;
  const el = document.createElement('div');
  el.className = 'toast-item toast-' + type;
  el.innerHTML =
    '<div class="toast-body"><i class="bi ' + icon + '" style="color:' + color + ';flex-shrink:0;font-size:1rem;"></i>' +
    '<span>' + message + '</span>' +
    '<button class="toast-close" onclick="this.closest(\'.toast-item\').remove()"><i class="bi bi-x"></i></button></div>' +
    '<div class="toast-timer" style="background:' + color + ';"></div>';
  container.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateX(110%)'; }, 3800);
  setTimeout(() => el.remove(), 4200);
};

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('#page-messages [data-msg]').forEach(el => {
    showToast(el.dataset.msg, el.dataset.type || 'success');
  });
});
