// Функции для работы с чатом

// Глобальные переменные
let currentChatId = null;
let messageContainer = null;
let messageInput = null;

// Инициализация чата
function initializeChat() {
    messageContainer = document.getElementById('messagesContainer');
    messageInput = document.getElementById('messageInput');
    
    // Прокручиваем к последнему сообщению
    if (messageContainer) {
        messageContainer.scrollTop = messageContainer.scrollHeight;
    }
    
    // Обработчик отправки формы
    const messageForm = document.getElementById('messageForm');
    if (messageForm) {
        messageForm.removeEventListener('submit', sendMessage); // Удаляем старый обработчик
        messageForm.addEventListener('submit', function(e) {
            e.preventDefault();
            sendMessage();
        });
    }
    
    // Обработчик Enter в поле ввода
    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
}

// Отправка сообщения
function sendMessage() {
    if (!messageInput || !currentChatId) {
        console.error('Message input or chat ID not found');
        return;
    }
    
    const content = messageInput.value.trim();
    if (!content) {
        return;
    }
    
    // Блокируем кнопку отправки
    const sendButton = document.getElementById('sendBtn');
    if (sendButton) {
        sendButton.disabled = true;
        sendButton.innerHTML = '<i class="bi bi-hourglass-split"></i>';
    }
    
    // Создаем FormData
    const formData = new FormData();
    formData.append('content', content);
    formData.append('type', 'text');
    
    // Получаем CSRF token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch(`/api/chat/${currentChatId}/send/`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': csrfToken,
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Очищаем поле ввода
            messageInput.value = '';
            
            // Добавляем сообщение в контейнер
            addMessageToContainer(data.message);
            
            // Прокручиваем к новому сообщению
            if (messageContainer) {
                messageContainer.scrollTop = messageContainer.scrollHeight;
            }
        } else {
            alert('Ошибка отправки сообщения: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error sending message:', error);
        alert('Ошибка отправки сообщения');
    })
    .finally(() => {
        // Разблокируем кнопку отправки
        if (sendButton) {
            sendButton.disabled = false;
            sendButton.innerHTML = '<i class="bi bi-send-fill"></i>';
        }
    });
}

// Добавление сообщения в контейнер
function addMessageToContainer(message) {
    if (!messageContainer) return;
    
    const messageElement = createMessageElement(message);
    messageContainer.appendChild(messageElement);
}

// Создание элемента сообщения
function createMessageElement(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${message.sender.id === currentUserId ? 'message-own' : 'message-other'}`;
    messageDiv.dataset.messageId = message.id;
    
    const avatarImg = message.sender.avatar ? 
        `<img src="${message.sender.avatar}" alt="${message.sender.username}" class="message-avatar">` :
        `<div class="message-avatar-placeholder">${message.sender.username[0].toUpperCase()}</div>`;
    
    const premiumBadge = message.sender.is_premium ? 
        '<span class="premium-badge"><i class="bi bi-star-fill"></i></span>' : '';
    
    const messageTime = new Date(message.created_at).toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    let messageContent = '';
    
    if (message.message_type === 'text') {
        messageContent = `<div class="message-text">${escapeHtml(message.content)}</div>`;
    } else if (message.message_type === 'image') {
        messageContent = `
            <div class="message-image">
                <img src="${message.image_url}" alt="Изображение" onclick="openImageModal('${message.image_url}')">
            </div>
        `;
    } else if (message.message_type === 'file') {
        messageContent = `
            <div class="message-file">
                <i class="bi bi-file-earmark"></i>
                <div class="file-info">
                    <a href="${message.file_url}" download="${message.file_name}">${message.file_name}</a>
                    <small>${message.file_size}</small>
                </div>
            </div>
        `;
    }
    
    messageDiv.innerHTML = `
        <div class="message-header">
            ${avatarImg}
            <div class="message-info">
                <span class="message-sender">${message.sender.username}${premiumBadge}</span>
                <span class="message-time">${messageTime}</span>
                ${message.is_edited ? '<span class="message-edited">(изменено)</span>' : ''}
            </div>
        </div>
        <div class="message-content">
            ${message.reply_to ? createReplyElement(message.reply_to) : ''}
            ${messageContent}
        </div>
        <div class="message-actions">
            <button class="btn-reply" onclick="replyToMessage(${message.id}, '${message.sender.username}')">
                <i class="bi bi-reply"></i>
            </button>
            ${message.sender.id === currentUserId ? `
                <button class="btn-edit" onclick="editMessage(${message.id})">
                    <i class="bi bi-pencil"></i>
                </button>
                <button class="btn-delete" onclick="deleteMessage(${message.id})">
                    <i class="bi bi-trash"></i>
                </button>
            ` : ''}
        </div>
    `;
    
    return messageDiv;
}

// Создание элемента ответа на сообщение
function createReplyElement(replyTo) {
    return `
        <div class="message-reply">
            <div class="reply-line"></div>
            <div class="reply-content">
                <span class="reply-author">${replyTo.sender_username}</span>
                <span class="reply-text">${escapeHtml(replyTo.content)}</span>
            </div>
        </div>
    `;
}

// Загрузка чата
function loadChat(chatId) {
    currentChatId = chatId;
    
    const chatContent = document.getElementById('chatContent');
    if (!chatContent) return;
    
    chatContent.innerHTML = `
        <div class="loading-chat">
            <div class="spinner-border text-success" role="status">
                <span class="visually-hidden">Загрузка...</span>
            </div>
            <p>Загрузка чата...</p>
        </div>
    `;
    
    fetch(`/chat/${chatId}/`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.text();
        })
        .then(html => {
            chatContent.innerHTML = html;
            // Инициализируем функциональность чата после загрузки
            setTimeout(() => {
                initializeChat();
            }, 100);
        })
        .catch(error => {
            console.error('Error loading chat:', error);
            chatContent.innerHTML = `
                <div class="chat-error">
                    <div class="error-icon">
                        <i class="bi bi-exclamation-triangle"></i>
                    </div>
                    <h4>Ошибка загрузки</h4>
                    <p>Не удалось загрузить чат. Попробуйте еще раз.</p>
                    <button class="btn btn-outline-success" onclick="loadChat(${chatId})">
                        Повторить
                    </button>
                </div>
            `;
        });
}

// Открытие чата
function openChat(chatId) {
    console.log('Opening chat:', chatId);
    
    // Обновляем активный чат в списке
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const chatItem = document.querySelector(`[data-chat-id="${chatId}"]`);
    if (chatItem) {
        chatItem.classList.add('active');
    }
    
    // Загружаем чат
    loadChat(chatId);
    
    // Обновляем URL без перезагрузки страницы
    const newUrl = new URL(window.location);
    newUrl.searchParams.set('chat_id', chatId);
    window.history.pushState({chatId: chatId}, '', newUrl);
}

// Удаление сообщения
function deleteMessage(messageId) {
    if (!confirm('Вы уверены, что хотите удалить это сообщение?')) {
        return;
    }
    
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch(`/api/message/${messageId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
            if (messageElement) {
                messageElement.remove();
            }
        } else {
            alert('Ошибка удаления сообщения: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error deleting message:', error);
        alert('Ошибка удаления сообщения');
    });
}

// Редактирование сообщения
function editMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    if (!messageElement) return;
    
    const messageTextElement = messageElement.querySelector('.message-text');
    if (!messageTextElement) return;
    
    const currentText = messageTextElement.textContent;
    
    // Создаем поле для редактирования
    const editInput = document.createElement('textarea');
    editInput.className = 'form-control';
    editInput.value = currentText;
    editInput.rows = 3;
    
    const editButtons = document.createElement('div');
    editButtons.className = 'edit-buttons mt-2';
    editButtons.innerHTML = `
        <button class="btn btn-sm btn-success me-2" onclick="saveEditedMessage(${messageId}, this)">
            <i class="bi bi-check"></i> Сохранить
        </button>
        <button class="btn btn-sm btn-secondary" onclick="cancelEditMessage(${messageId})">
            <i class="bi bi-x"></i> Отмена
        </button>
    `;
    
    // Заменяем текст на поле редактирования
    messageTextElement.style.display = 'none';
    messageTextElement.parentNode.insertBefore(editInput, messageTextElement.nextSibling);
    messageTextElement.parentNode.insertBefore(editButtons, editInput.nextSibling);
    
    editInput.focus();
}

// Сохранение отредактированного сообщения
function saveEditedMessage(messageId, button) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const editInput = messageElement.querySelector('textarea');
    const newContent = editInput.value.trim();
    
    if (!newContent) {
        alert('Сообщение не может быть пустым');
        return;
    }
    
    button.disabled = true;
    
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const formData = new FormData();
    formData.append('content', newContent);
    
    fetch(`/api/message/${messageId}/edit/`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': csrfToken,
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const messageTextElement = messageElement.querySelector('.message-text');
            messageTextElement.textContent = data.message.content;
            messageTextElement.style.display = 'block';
            
            // Добавляем отметку об изменении
            const messageInfo = messageElement.querySelector('.message-info');
            let editedSpan = messageInfo.querySelector('.message-edited');
            if (!editedSpan) {
                editedSpan = document.createElement('span');
                editedSpan.className = 'message-edited';
                editedSpan.textContent = '(изменено)';
                messageInfo.appendChild(editedSpan);
            }
            
            // Удаляем элементы редактирования
            editInput.remove();
            messageElement.querySelector('.edit-buttons').remove();
        } else {
            alert('Ошибка редактирования сообщения: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error editing message:', error);
        alert('Ошибка редактирования сообщения');
    })
    .finally(() => {
        button.disabled = false;
    });
}

// Отмена редактирования сообщения
function cancelEditMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    const messageTextElement = messageElement.querySelector('.message-text');
    const editInput = messageElement.querySelector('textarea');
    const editButtons = messageElement.querySelector('.edit-buttons');
    
    if (messageTextElement) {
        messageTextElement.style.display = 'block';
    }
    
    if (editInput) {
        editInput.remove();
    }
    
    if (editButtons) {
        editButtons.remove();
    }
}

// Ответ на сообщение
function replyToMessage(messageId, senderUsername) {
    const replyPreview = document.getElementById('replyPreview');
    const replyAuthor = document.getElementById('replyAuthor');
    const replyText = document.getElementById('replyText');
    const replyToInput = document.getElementById('replyToId');
    
    if (replyPreview && replyAuthor && replyText && replyToInput) {
        replyAuthor.textContent = senderUsername;
        replyText.textContent = 'Сообщение';
        replyToInput.value = messageId;
        replyPreview.style.display = 'block';
        
        // Фокусируемся на поле ввода
        if (messageInput) {
            messageInput.focus();
        }
    }
}

// Отмена ответа на сообщение
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

// Открытие модального окна с изображением
function openImageModal(imageUrl) {
    const modalImage = document.getElementById('modalImage');
    if (modalImage) {
        modalImage.src = imageUrl;
        const imageModal = new bootstrap.Modal(document.getElementById('imageModal'));
        imageModal.show();
    }
}

// Экранирование HTML
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

// Обработка файлов
function handleFileSelect(input, type) {
    const file = input.files[0];
    if (!file) return;
    
    // Проверяем размер файла (максимум 10MB)
    if (file.size > 10 * 1024 * 1024) {
        alert('Файл слишком большой. Максимальный размер: 10MB');
        input.value = '';
        return;
    }
    
    const fileAttachments = document.getElementById('fileAttachments');
    const attachmentPreview = document.getElementById('attachmentPreview');
    
    if (!fileAttachments || !attachmentPreview) return;
    
    // Создаем превью файла
    const attachmentItem = document.createElement('div');
    attachmentItem.className = 'attachment-item';
    
    if (type === 'image') {
        const reader = new FileReader();
        reader.onload = function(e) {
            attachmentItem.innerHTML = `
                <img src="${e.target.result}" alt="Превью" style="width: 60px; height: 60px; object-fit: cover; border-radius: 4px;">
                <button type="button" class="attachment-remove" onclick="removeAttachment(this, '${type}')">
                    <i class="bi bi-x"></i>
                </button>
            `;
        };
        reader.readAsDataURL(file);
    } else {
        attachmentItem.innerHTML = `
            <div class="file-preview">
                <i class="bi bi-file-earmark" style="font-size: 2rem; color: var(--accent-green);"></i>
                <div class="file-name" style="font-size: 0.8rem; max-width: 100px; overflow: hidden; text-overflow: ellipsis;">${file.name}</div>
            </div>
            <button type="button" class="attachment-remove" onclick="removeAttachment(this, '${type}')">
                <i class="bi bi-x"></i>
            </button>
        `;
    }
    
    attachmentPreview.appendChild(attachmentItem);
    fileAttachments.style.display = 'block';
}

// Удаление вложения
function removeAttachment(button, type) {
    const attachmentItem = button.parentElement;
    const attachmentPreview = document.getElementById('attachmentPreview');
    const fileAttachments = document.getElementById('fileAttachments');
    
    // Очищаем input
    if (type === 'image') {
        const imageInput = document.getElementById('imageInput');
        if (imageInput) imageInput.value = '';
    } else {
        const fileInput = document.getElementById('fileInput');
        if (fileInput) fileInput.value = '';
    }
    
    // Удаляем превью
    attachmentItem.remove();
    
    // Скрываем область вложений если она пустая
    if (attachmentPreview && attachmentPreview.children.length === 0) {
        fileAttachments.style.display = 'none';
    }
}

// Проверка наличия вложений
function hasAttachments() {
    const imageInput = document.getElementById('imageInput');
    const fileInput = document.getElementById('fileInput');
    return (imageInput && imageInput.files.length > 0) || (fileInput && fileInput.files.length > 0);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Получаем ID активного чата из URL
    const urlParams = new URLSearchParams(window.location.search);
    const activeChatId = urlParams.get('chat_id');
    
    if (activeChatId) {
        currentChatId = activeChatId;
        loadChat(activeChatId);
    }
});

// Глобальная переменная для ID текущего пользователя
let currentUserId = null;

// Функция для установки ID текущего пользователя
function setCurrentUserId(userId) {
    currentUserId = userId;
}