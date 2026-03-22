// Функции для работы с плейлистами
function loadUserPlaylists() {
  const container = document.getElementById('playlistsContainer');
  if (!container) return;
  
  console.log('Loading playlists...');
  
  fetch('/api/user/playlists/')
    .then(response => {
      console.log('Response status:', response.status);
      return response.json();
    })
    .then(data => {
      console.log('Playlists data:', data);
      if (data.success) {
        if (data.playlists && data.playlists.length > 0) {
          container.innerHTML = '';
          data.playlists.forEach(playlist => {
            const playlistCard = createPlaylistCard(playlist);
            container.appendChild(playlistCard);
          });
        } else {
          container.innerHTML = `
            <div class="text-center py-5">
              <i class="bi bi-collection-play" style="font-size: 4rem; color: #6c757d;"></i>
              <h5 class="text-white mt-3">Пока нет плейлистов</h5>
              <p class="text-muted">Создайте свой первый плейлист, чтобы организовать треки</p>
              <button type="button" class="btn btn-success" data-bs-toggle="modal" data-bs-target="#createPlaylistModal">
                <i class="bi bi-plus-circle me-1"></i>Создать первый плейлист
              </button>
            </div>
          `;
        }
      } else {
        container.innerHTML = '<p class="text-muted text-center">Ошибка загрузки плейлистов: ' + (data.error || 'Неизвестная ошибка') + '</p>';
      }
    })
    .catch(error => {
      console.error('Error loading playlists:', error);
      container.innerHTML = '<p class="text-muted text-center">Ошибка загрузки плейлистов: ' + error.message + '</p>';
    });
}

function createPlaylistCard(playlist) {
  const card = document.createElement('div');
  card.className = 'playlist-card';
  card.style.cssText = `
    background: #2a2a2a;
    border: 1px solid #444;
    border-radius: 16px;
    overflow: hidden;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  `;
  
  card.innerHTML = `
    <div style="position: relative; width: 100%; height: 200px; overflow: hidden;">
      <img src="${playlist.cover_url}" alt="${playlist.title}" style="width: 100%; height: 100%; object-fit: cover;">
      <div style="position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.7); display: flex; align-items: center; justify-content: center; opacity: 0; transition: all 0.3s ease;" class="playlist-overlay">
        <button onclick="window.location.href='/playlist/${playlist.id}/'" style="background: none; border: none; color: #39ff14; font-size: 3rem; cursor: pointer;">
          <i class="bi bi-play-circle-fill"></i>
        </button>
      </div>
      ${playlist.visibility !== 'public' ? `
        <div style="position: absolute; top: 10px; right: 10px; background: rgba(0, 0, 0, 0.7); color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8rem;">
          <i class="bi bi-${playlist.visibility === 'private' ? 'lock' : 'link'}"></i>
        </div>
      ` : ''}
    </div>
    <div style="padding: 1rem;">
      <h6 style="margin: 0 0 0.5rem 0; font-size: 1rem; font-weight: 600;">
        <a href="/playlist/${playlist.id}/" style="color: white; text-decoration: none;">${playlist.title}</a>
      </h6>
      <p style="margin: 0; color: #aaa; font-size: 0.9rem;">${playlist.tracks_count} трек${getTrackWordEnding(playlist.tracks_count)}</p>
    </div>
  `;
  
  // Добавляем hover эффект
  card.addEventListener('mouseenter', function() {
    this.style.borderColor = '#39ff14';
    this.style.transform = 'translateY(-4px)';
    this.style.boxShadow = '0 8px 25px rgba(0, 0, 0, 0.2)';
    this.querySelector('.playlist-overlay').style.opacity = '1';
  });
  
  card.addEventListener('mouseleave', function() {
    this.style.borderColor = '#444';
    this.style.transform = 'translateY(0)';
    this.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1)';
    this.querySelector('.playlist-overlay').style.opacity = '0';
  });
  
  return card;
}

function getTrackWordEnding(count) {
  if (count % 10 === 1 && count % 100 !== 11) {
    return '';
  } else if ([2, 3, 4].includes(count % 10) && ![12, 13, 14].includes(count % 100)) {
    return 'а';
  } else {
    return 'ов';
  }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM loaded, setting up playlist functionality...');
  
  // Добавляем стили для сетки плейлистов
  const style = document.createElement('style');
  style.textContent = `
    .playlists-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 1.5rem;
    }
    @media (max-width: 768px) {
      .playlists-grid {
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
      }
    }
    @media (max-width: 576px) {
      .playlists-grid {
        grid-template-columns: 1fr;
      }
    }
  `;
  document.head.appendChild(style);
  
  // Обработчик переключения на вкладку плейлистов
  const playlistsTab = document.querySelector('button[data-bs-target="#playlists"]');
  if (playlistsTab) {
    console.log('Found playlists tab, adding event listener...');
    playlistsTab.addEventListener('shown.bs.tab', function() {
      console.log('Playlists tab shown, loading playlists...');
      loadUserPlaylists();
    });
  } else {
    console.log('Playlists tab not found');
  }
  
  // Переопределяем функцию loadTabContent для плейлистов
  if (typeof window.loadTabContent !== 'undefined') {
    const originalLoadTabContent = window.loadTabContent;
    window.loadTabContent = function(tabName) {
      console.log('Loading tab content for:', tabName);
      if (tabName === 'playlists') {
        loadUserPlaylists();
      } else if (originalLoadTabContent) {
        originalLoadTabContent(tabName);
      }
    };
  } else {
    // Создаем функцию loadTabContent если её н��т
    window.loadTabContent = function(tabName) {
      console.log('Loading tab content for:', tabName);
      if (tabName === 'playlists') {
        loadUserPlaylists();
      }
    };
  }
  
  // Обработчики событий для переключения вкладок
  const tabButtons = document.querySelectorAll('#profileTabs button[data-bs-toggle="pill"]');
  tabButtons.forEach(button => {
    button.addEventListener('shown.bs.tab', function(e) {
      const targetTab = e.target.getAttribute('data-bs-target').substring(1);
      console.log('Tab switched to:', targetTab);
      if (typeof window.loadTabContent === 'function') {
        window.loadTabContent(targetTab);
      }
    });
  });
});