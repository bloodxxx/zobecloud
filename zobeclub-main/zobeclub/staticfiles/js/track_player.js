// ══════════════════════════════════════════
// ZobeClub — плеер + SPA навигация
// ══════════════════════════════════════════

// ── SPA роутер ─────────────────────────────────────────────────────────────
// перехватывает клики по ссылкам внутри сайта и загружает страницы через fetch
// чтобы аудио не прерывалось при переходах
class SPARouter {
  constructor() {
    this._busy = false;
    this._init();
  }

  _init() {
    // перехватываем клики по ссылкам
    document.addEventListener('click', e => {
      const a = e.target.closest('a[href]');
      if (a && this._ok(a)) {
        e.preventDefault();
        this.go(a.href);
      }
    });

    // кнопки «назад/вперёд» браузера
    window.addEventListener('popstate', () => this.go(location.href, false));
  }

  // нужно ли перехватывать ссылку
  _ok(a) {
    try {
      const u = new URL(a.href);
      if (u.origin !== location.origin)   return false; // внешняя ссылка
      if (a.target === '_blank')           return false;
      if (a.hasAttribute('download'))      return false;
      if (u.pathname.startsWith('/admin')) return false;
      // медиафайлы — без SPA
      if (/\.(mp3|mp4|jpg|jpeg|png|gif|webp|pdf|zip|svg)$/i.test(u.pathname)) return false;
      // чистый якорь на той же странице
      if (u.pathname === location.pathname && u.hash) return false;
      return true;
    } catch { return false; }
  }

  async go(url, push = true) {
    if (this._busy) return;
    this._busy = true;
    this._load(true);

    try {
      const res = await fetch(url, {
        headers: { 'X-SPA-Request': '1' },
        credentials: 'same-origin',
      });

      // нестандартный ответ — fallback на обычную навигацию
      if (!res.ok) throw new Error(res.status);

      const html = await res.text();
      const doc  = new DOMParser().parseFromString(html, 'text/html');

      // заменяем основной контент страницы
      const newMain = doc.getElementById('page-main');
      const curMain = document.getElementById('page-main');
      if (newMain && curMain) curMain.innerHTML = newMain.innerHTML;

      // flash-сообщения Django
      const newMsg = doc.getElementById('page-messages');
      const curMsg = document.getElementById('page-messages');
      if (newMsg && curMsg) curMsg.innerHTML = newMsg.innerHTML;

      // инжектируем CSS новой страницы (page-specific стили из extra_css блока)
      // старые page-css удаляем, добавляем новые
      document.querySelectorAll('style[data-spa-page]').forEach(el => el.remove());
      doc.querySelectorAll('head style').forEach(s => {
        if (!s.textContent.trim()) return;
        const el = document.createElement('style');
        el.setAttribute('data-spa-page', '1');
        el.textContent = s.textContent;
        document.head.appendChild(el);
      });

      // запускаем скрипты из блока extra_js новой страницы
      const newScripts = doc.getElementById('__page_scripts');
      if (newScripts) {
        // обновляем контейнер
        const cur = document.getElementById('__page_scripts');
        if (cur) cur.innerHTML = newScripts.innerHTML;

        // выполняем каждый скрипт
        newScripts.querySelectorAll('script').forEach(old => {
          const s = document.createElement('script');
          if (old.src) {
            s.src = old.src;
            s.async = false;
          } else {
            s.textContent = old.textContent;
          }
          document.body.appendChild(s);
          if (!old.src) document.body.removeChild(s);
        });
      }

      // обновляем заголовок и URL
      document.title = doc.title;
      if (push) history.pushState({}, '', url);

      window.scrollTo(0, 0);
      this._updateNav(url);

    } catch {
      // если что-то пошло не так — обычная навигация
      location.href = url;
    } finally {
      this._busy = false;
      this._load(false);
    }
  }

  // подсвечиваем активный пункт навигации
  _updateNav(url) {
    document.querySelectorAll('.navbar-nav .nav-link').forEach(a => {
      try {
        const u = new URL(a.href);
        a.classList.toggle(
          'active',
          u.pathname !== '/' && url.includes(u.pathname)
        );
      } catch {}
    });
  }

  // полоска загрузки сверху страницы
  _load(start) {
    const bar = document.getElementById('spa-loader');
    if (!bar) return;
    if (start) {
      bar.style.transition = 'none';
      bar.style.width = '0%';
      bar.style.opacity = '1';
      requestAnimationFrame(() => {
        bar.style.transition = 'width 8s linear';
        bar.style.width = '88%';
      });
    } else {
      bar.style.transition = 'width .2s ease';
      bar.style.width = '100%';
      setTimeout(() => {
        bar.style.opacity = '0';
        setTimeout(() => { bar.style.width = '0%'; }, 300);
      }, 200);
    }
  }
}


// ── Плеер ──────────────────────────────────────────────────────────────────
class ZobePlayerClass {
  constructor() {
    this.audio    = document.getElementById('zpAudio');
    this.bar      = document.getElementById('miniPlayer');
    this.isPlaying  = false;
    this.track      = null;
    this.playlist   = [];
    this.idx        = 0;
    this.volume     = 0.4;
    this._restoreTime = 0;
    this._wasPlaying  = false;

    this.el = {
      cover:    document.getElementById('zpCover'),
      img:      document.getElementById('zpCoverImg'),
      fb:       document.getElementById('zpCoverFb'),
      title:    document.getElementById('zpTitle'),
      artist:   document.getElementById('zpArtist'),
      playBtn:  document.getElementById('zpPlay'),
      playIcon: document.getElementById('zpPlayIcon'),
      prev:     document.getElementById('zpPrev'),
      next:     document.getElementById('zpNext'),
      cur:      document.getElementById('zpCur'),
      dur:      document.getElementById('zpDur'),
      progress: document.getElementById('zpProgress'),
      fill:     document.getElementById('zpFill'),
      thumb:    document.getElementById('zpThumb'),
      vol:      document.getElementById('zpVol'),
      volIcon:  document.getElementById('zpVolIcon'),
      close:    document.getElementById('zpClose'),
    };

    this._bindUI();
    this._bindAudio();
    this._loadState();
    this._setVol(this.volume * 100);
  }

  // ── привязка событий UI ────────────────────────────────────────────────
  _bindUI() {
    this.el.playBtn.addEventListener('click', () => this.togglePlay());
    this.el.prev.addEventListener('click', () => this.prev());
    this.el.next.addEventListener('click', () => this.next());
    this.el.close.addEventListener('click', () => this._hide());
    this.el.vol.addEventListener('input', e => this._setVol(e.target.value));
    this.el.volIcon.addEventListener('click', () => this._mute());
    document.addEventListener('keydown', e => this._key(e));

    // прогресс — drag
    let drag = false;
    const seek = e => {
      if (!this.audio.duration) return;
      const r   = this.el.progress.getBoundingClientRect();
      const pct = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
      this.audio.currentTime = pct * this.audio.duration;
      this._updateProg();
    };
    const seekT = e => e.touches[0] && seek({ clientX: e.touches[0].clientX });

    this.el.progress.addEventListener('mousedown',  e => { drag = true; seek(e); });
    document.addEventListener('mousemove',   e => { if (drag) seek(e); });
    document.addEventListener('mouseup',     ()  => { drag = false; });
    this.el.progress.addEventListener('touchstart', e => { drag = true; seekT(e); }, { passive: true });
    document.addEventListener('touchmove',   e => { if (drag) seekT(e); }, { passive: true });
    document.addEventListener('touchend',    ()  => { drag = false; });
  }

  // ── привязка аудио событий ────────────────────────────────────────────
  _bindAudio() {
    this.audio.addEventListener('loadedmetadata', () => {
      this.el.dur.textContent = this._fmt(this.audio.duration);
      if (this._restoreTime > 0) {
        this.audio.currentTime = this._restoreTime;
        this._restoreTime = 0;
        if (this._wasPlaying) { this._wasPlaying = false; this._tryResume(); }
      }
    });

    this.audio.addEventListener('canplay', () => {
      this.bar.classList.remove('loading');
      if (this._wasPlaying) { this._wasPlaying = false; this._tryResume(); }
    });

    this.audio.addEventListener('timeupdate', () => {
      this._updateProg();
      if (this.isPlaying && Math.floor(this.audio.currentTime) % 5 === 0) this._save();
    });

    this.audio.addEventListener('ended',     () => this._onEnd());
    this.audio.addEventListener('loadstart', () => this.bar.classList.add('loading'));
    this.audio.addEventListener('error',     () => {
      this.bar.classList.remove('loading');
      this._err('Ошибка загрузки трека');
      this.isPlaying = false;
      this._syncUI();
    });
    this.audio.addEventListener('play',  () => { this.isPlaying = true;  this._syncUI(); this._save(); });
    this.audio.addEventListener('pause', () => { this.isPlaying = false; this._syncUI(); this._save(); });

    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && this.track) this._syncUI();
    });
  }

  // ── пытаемся возобновить после перехода страницы ──────────────────────
  // браузер может заблокировать autoplay — тогда показываем паузу без ошибки
  _tryResume() {
    this.audio.play().then(() => {
      this.bar.classList.remove('paused-restore');
    }).catch(() => {
      this.isPlaying = false;
      this._syncUI();
      // мигаем кнопкой play — «нажмите для продолжения»
      this.bar.classList.add('paused-restore');
      setTimeout(() => this.bar.classList.remove('paused-restore'), 3000);
    });
  }

  // ── публичные методы ──────────────────────────────────────────────────

  // воспроизвести трек; trackData = { id, title, artist, audioUrl, coverUrl }
  playTrack(data) {
    this.track = data;
    this.audio.src = data.audioUrl;
    this._restoreTime = 0;
    this._wasPlaying  = false;
    this._updateInfo();
    this._show();
    this.bar.classList.add('loading');
    this.audio.play().catch(err => {
      if (err.name !== 'NotAllowedError') this._err('Ошибка воспроизведения');
    });
    this._save();
  }

  // добавить трек в очередь
  addToPlaylist(data) {
    if (!this.playlist.find(t => t.id === data.id)) this.playlist.push(data);
    this._save();
  }

  // установить плейлист и начать воспроизведение
  setPlaylist(tracks, startIdx = 0) {
    this.playlist = tracks;
    this.idx = startIdx;
    if (tracks.length) this.playTrack(tracks[startIdx]);
    this._save();
  }

  togglePlay() {
    if (!this.track) return;
    if (this.isPlaying) this.audio.pause();
    else this.audio.play().catch(() => {});
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

  getCurrentTrack() { return this.track; }
  getIsPlaying()    { return this.isPlaying; }
  getPlaylist()     { return this.playlist; }
  forceUpdateState() { this._loadState(); }

  // ── приватные методы ──────────────────────────────────────────────────

  _setVol(v) {
    this.volume = v / 100;
    this.audio.volume = this.volume;
    this.el.vol.value = v;
    if      (this.volume === 0) this.el.volIcon.className = 'bi bi-volume-mute zp-vol-icon';
    else if (this.volume < 0.5) this.el.volIcon.className = 'bi bi-volume-down zp-vol-icon';
    else                        this.el.volIcon.className = 'bi bi-volume-up zp-vol-icon';
    this._save();
  }

  _mute() {
    if (this.volume > 0) { this._prevVol = this.volume; this._setVol(0); }
    else this._setVol((this._prevVol || 0.4) * 100);
  }

  // обновляем отображение трека + делаем элементы кликабельными
  _updateInfo() {
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

    // кликабельность: обложка + название → трек, автор → профиль
    if (t.id) {
      const tUrl = `/track/${t.id}/`;
      const aUrl = `/user/${t.artist}/`;
      this.el.cover.onclick  = () => window.location.href = tUrl;
      this.el.title.onclick  = () => window.location.href = tUrl;
      this.el.artist.onclick = () => window.location.href = aUrl;
    }

    document.title = `${t.title} — ${t.artist} | ZobeCloud`;
  }

  _updateProg() {
    if (!this.audio.duration) return;
    const pct = (this.audio.currentTime / this.audio.duration) * 100;
    this.el.fill.style.width  = `${pct}%`;
    this.el.thumb.style.left  = `${pct}%`;
    this.el.cur.textContent   = this._fmt(this.audio.currentTime);
  }

  _syncUI() {
    if (this.isPlaying) {
      this.el.playIcon.className = 'bi bi-pause-fill';
      this.bar.classList.add('playing');
    } else {
      this.el.playIcon.className = 'bi bi-play-fill';
      this.bar.classList.remove('playing');
    }
  }

  _onEnd() {
    if (this.playlist.length > 1) this.next();
    else { this.audio.currentTime = 0; this._syncUI(); }
  }

  _show() {
    this.bar.style.display = 'flex';
    this.bar.classList.add('show');
    this.bar.classList.remove('hide');
    document.body.style.paddingBottom = '80px';
  }

  _hide() {
    this.bar.classList.add('hide');
    this.bar.classList.remove('show');
    setTimeout(() => {
      this.bar.style.display = 'none';
      document.body.style.paddingBottom = '0';
      this.audio.pause();
      this.track = null;
      this._clearState();
    }, 300);
  }

  _fmt(s) {
    if (!s || isNaN(s)) return '0:00';
    return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  }

  _err(msg) {
    const el = document.createElement('div');
    el.style.cssText = 'position:fixed;top:20px;right:20px;background:#c0392b;color:#fff;padding:.55rem 1rem;border-radius:10px;font-size:.84rem;font-weight:600;z-index:9999;';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 4000);
  }

  _key(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    switch (e.code) {
      case 'Space':      e.preventDefault(); this.togglePlay(); break;
      case 'ArrowLeft':  e.preventDefault(); if (this.track) this.audio.currentTime = Math.max(0, this.audio.currentTime - 10); break;
      case 'ArrowRight': e.preventDefault(); if (this.track) this.audio.currentTime = Math.min(this.audio.duration, this.audio.currentTime + 10); break;
      case 'ArrowUp':    e.preventDefault(); this._setVol(Math.min(100, this.volume * 100 + 10)); break;
      case 'ArrowDown':  e.preventDefault(); this._setVol(Math.max(0, this.volume * 100 - 10)); break;
      case 'KeyM':       e.preventDefault(); this._mute(); break;
      case 'KeyN':       e.preventDefault(); this.next(); break;
      case 'KeyP':       e.preventDefault(); this.prev(); break;
    }
  }

  // ── localStorage ─────────────────────────────────────────────────────

  _save() {
    try {
      localStorage.setItem('zp_state', JSON.stringify({
        track:    this.track,
        playlist: this.playlist,
        idx:      this.idx,
        volume:   this.volume,
        playing:  this.isPlaying,
        time:     this.audio.currentTime || 0,
      }));
    } catch {}
  }

  _loadState() {
    try {
      const raw = localStorage.getItem('zp_state');
      if (!raw) { this.volume = 0.4; return; }
      const s = JSON.parse(raw);

      this.track    = s.track    || null;
      this.playlist = s.playlist || [];
      this.idx      = s.idx      || 0;
      this.volume   = s.volume !== undefined ? s.volume : 0.4;
      this._wasPlaying  = s.playing || false;
      this._restoreTime = s.time    || 0;
      this.isPlaying    = false; // true выставится только после успешного play()

      if (this.track) {
        this.audio.src = this.track.audioUrl;
        this._show();
        this._updateInfo();
        this._syncUI(); // показываем паузу пока не возобновим
      }
    } catch {
      this.volume = 0.4;
    }
  }

  _clearState() {
    try { localStorage.removeItem('zp_state'); } catch {}
  }
}


// ── Инициализация ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  window.ZobePlayer = new ZobePlayerClass();
  window.ZobeSPA    = new SPARouter();
});

// сохраняем состояние при любом уходе со страницы
window.addEventListener('beforeunload', () => window.ZobePlayer?._save());
window.addEventListener('pagehide',     () => window.ZobePlayer?._save());

// восстановление при bfcache (кэш браузера)
window.addEventListener('pageshow', e => {
  if (e.persisted && window.ZobePlayer) window.ZobePlayer._loadState();
});


// ── Хелперы для шаблонов ──────────────────────────────────────────────────
function playTrackInMiniPlayer(data)    { window.ZobePlayer?.playTrack(data); }
function addTrackToPlaylist(data)       { window.ZobePlayer?.addToPlaylist(data); }
function setPlaylist(tracks, idx = 0)  { window.ZobePlayer?.setPlaylist(tracks, idx); }
function updatePlayerState()            { window.ZobePlayer?.forceUpdateState(); }
