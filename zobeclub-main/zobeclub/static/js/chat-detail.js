// Глобальные переменные для чата
let currentChatId = null;
let currentUserId = null;
let replyToMessageId = null;
let editingMessageId = null;
let isLoadingMessages = false;

// Основная функция инициализации чата
window.initializeChatDetail = function(chatId, userId) {
    console.log('Initializing chat detail:', chatId, userId);
    
    currentChatId = chatId;
    currentUserId = userId;
    
    // Очищаем предыдущие обработчики
    clearEventListeners();
    
    // Инициализируем новые обработчики
    setupEventListeners();
    
    // Прокручиваем к последнему сообщению
    scrollToBottom();
    
    // Отмечаем сообщения как прочитанные
    markMessagesAsRead();
};

function clearEventListeners() {
    // Удаляем старые обработчики событий
    const messageForm = document.getElementById('messageForm');
    const messageInput = document.getElementById('messageInput');
    
    if (messageForm) {
        messageForm.replaceWith(messageForm.cloneNode(true));
    }
    
    if (messageInput) {
        messageInput.replaceWith(messageInput.cloneNode(true));
    }
}

function setupEventListeners() {
    const messageInput = document.getElementById('messageInput');
    const messageForm = document.getElementById('messageForm');
    const sendBtn = document.getElementById('sendBtn');
    
    if (!messageInput || !messageForm || !sendBtn) {
        console.error('Chat elements not found');
        return;
    }
    
    // Автоматическое изменение высоты textarea
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        
        const length = this.value.length;
        
        // Активируем/деактивируем кнопку отправки
        if (length > 0 || hasAttachments()) {
            sendBtn.disabled = false;
        } else {
            sendBtn.disabled = true;
        }
    });
    
    // Отправка по Enter
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) {
                sendMessage();
            }
        }
    });
    
    // Обработка формы
    messageForm.addEventListener('submit', function(e) {
        e.preventDefault();
        sendMessage();
        return false;
    });
    
    // Обработчик скролла для загрузки старых сообщений
    const messagesList = document.getElementById('messagesList');
    if (messagesList) {
        messagesList.addEventListener('scroll', function() {
            if (this.scrollTop === 0 && !isLoadingMessages) {
                loadMoreMessages();
            }
        });
    }
}

function sendMessage() {
    console.log('Sending message...');
    
    const messageInput = document.getElementById('messageInput');
    const messageForm = document.getElementById('messageForm');
    const sendBtn = document.getElementById('sendBtn');
    
    if (!messageInput || !messageForm || !sendBtn || !currentChatId) {
        console.error('Required elements not found');
        return;
    }
    
    const content = messageInput.value.trim();
    const replyToId = document.getElementById('replyToId')?.value || '';
    const editMessageId = document.getElementById('editMessageId')?.value || '';
    
    if (!content && !hasAttachments()) {
        return;
    }
    
    // Блокируем кнопку
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div>';
    
    const formData = new FormData(messageForm);
    
    let url = `/api/chat/${currentChatId}/send/`;
    if (editMessageId) {
        url = `/api/message/${editMessageId}/edit/`;
    }
    
    fetch(url, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (editMessageId) {
                updateMessageInDOM(data.message);
                cancelEdit();
            } else {
                addMessageToDOM(data.message);
                clearForm();
                scrollToBottom();
            }
        } else {
            alert('Ошибка: ' + (data.error || 'Не удалось отправить сообщение'));
        }
    })
    .catch(error => {
        console.error('Error sending message:', error);
        alert('Произошла ошибка при отправке сообщения');
    })
    .finally(() => {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="bi bi-send-fill"></i>';
    });
}

function addMessageToDOM(messageData) {
    const messagesList = document.getElementById('messagesList');
    const noMessages = messagesList?.querySelector('.no-messages');
    
    if (noMessages) {
        noMessages.remove();
    }
    
    if (messagesList) {
        const messageElement = createMessageElement(messageData);
        messagesList.appendChild(messageElement);
    }
}

function createMessageElement(messageData) {
    const messageDiv = document.createElement('div');
    const isOwnMessage = messageData.sender.id === currentUserId;
    
    messageDiv.className = `message-item ${isOwnMessage ? 'own-message' : 'other-message'} ${messageData.sender.is_premium ? 'premium-message' : ''}`;
    messageDiv.dataset.messageId = messageData.id;
    
    let avatarHtml = '';
    if (!isOwnMessage) {
        avatarHtml = `
            <div class="message-avatar">
                <img src="${messageData.sender.avatar}" alt="${messageData.sender.username}" class="avatar-small">
                ${messageData.sender.is_premium ? '<div class="message-avatar-premium"><i class="bi bi-star-fill"></i></div>' : ''}
            </div>
        `;
    }
    
    let senderNameHtml = '';
    if (!isOwnMessage) {
        senderNameHtml = `
            <div class="message-sender-name">
                ${messageData.sender.username}
                ${messageData.sender.is_premium ? '<i class="bi bi-star-fill premium-sender-badge"></i>' : ''}
            </div>
        `;
    }
    
    let contentHtml = '';
    if (messageData.message_type === 'text') {
        contentHtml = `<div class="message-text">${messageData.content.replace(/\n/g, '<br>')}</div>`;
    }
    
    const now = new Date();
    const timeString = now.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    
    messageDiv.innerHTML = `
        ${avatarHtml}
        <div class="message-content">
            ${senderNameHtml}
            <div class="message-body">
                ${contentHtml}
            </div>
            <div class="message-meta">
                <span class="message-time">${timeString}</span>
                ${isOwnMessage ? '<span class="message-status"><i class="bi bi-check2 sent-indicator" title="Отправлено"></i></span>' : ''}
            </div>
        </div>
    `;
    
    return messageDiv;
}

function clearForm() {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    
    if (messageInput) {
        messageInput.value = '';
        messageInput.style.height = 'auto';
    }
    
    if (sendBtn) {
        sendBtn.disabled = true;
    }
    
    cancelReply();
    cancelEdit();
}

function scrollToBottom() {
    const messagesList = document.getElementById('messagesList');
    if (messagesList) {
        setTimeout(() => {
            messagesList.scrollTop = messagesList.scrollHeight;
        }, 100);
    }
}

function hasAttachments() {
    const imageInput = document.getElementById('imageInput');
    const fileInput = document.getElementById('fileInput');
    return (imageInput?.files.length > 0) || (fileInput?.files.length > 0);
}

function markMessagesAsRead() {
    if (!currentChatId) return;
    
    fetch(`/api/chat/${currentChatId}/mark-read/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
        }
    })
    .catch(error => {
        console.error('Error marking messages as read:', error);
    });
}

// Остальные функции (replyToMessage, cancelReply, editMessage, cancelEdit, deleteMessage, etc.)
function replyToMessage(messageId, senderUsername, content) {
    const replyPreview = document.getElementById('replyPreview');
    const replyAuthor = document.getElementById('replyAuthor');
    const replyText = document.getElementById('replyText');
    const replyToInput = document.getElementById('replyToId');
    
    if (replyPreview && replyAuthor && replyText && replyToInput) {
        replyAuthor.textContent = senderUsername;
        replyText.textContent = content || '[Файл]';
        replyToInput.value = messageId;
        replyPreview.style.display = 'block';
        
        const messageInput = document.getElementById('messageInput');
        if (messageInput) {
            messageInput.focus();
        }
    }
}

function cancelReply() {
    const replyPreview = document.getElementById('replyPreview');
    const replyToInput = document.getElementById('replyToId');
    
    if (replyPreview) {
        replyPreview.style.display = 'none';
    }
    
    if (replyToInput) {
        replyToInput.value = '';
    }
}

function editMessage(messageId, content) {
    // Реализация редактирования
}

function cancelEdit() {
    // Реализация отмены редактирования
}

function deleteMessage(messageId) {
    // Реализация удаления
}

function updateMessageInDOM(messageData) {
    // Реализация обновления сообщения
}

function loadMoreMessages() {
    // Реализация загрузки старых сообщений
}

function openImageModal(imageUrl) {
    const modalImage = document.getElementById('modalImage');
    if (modalImage) {
        modalImage.src = imageUrl;
        const imageModal = new bootstrap.Modal(document.getElementById('imageModal'));
        imageModal.show();
    }
}

function handleFileSelect(input, type) {
    // Реализация обработки файлов
}

function removeAttachment(button, type) {
    // Реализация удаления вложений
}

function toggleChatInfo() {
    alert('Информация о чате (функция в разработке)');
}

// Сигнализируем о загрузке скрипта
document.dispatchEvent(new Event('chatScriptLoaded'));