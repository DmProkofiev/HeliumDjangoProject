(function () {
    'use strict';

    const root = document.querySelector('.chat-detail');
    if (!root) return;

    const chatId = root.dataset.chatId;
    const currentUserId = parseInt(root.dataset.userId, 10);
    const messagesDiv = document.getElementById('messages');
    const input = document.getElementById('message-input');
    const form = document.getElementById('send-form');

    if (!messagesDiv || !input || !form || !chatId) {
        console.warn('[chat] не хватает элементов для инициализации');
        return;
    }

    // WEBSOCKET
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/chat/${chatId}/`);


    function scrollToBottom() {
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatTime(isoString) {
        const date = new Date(isoString);
        return date.toLocaleString('ru-RU', {
            day: '2-digit', month: '2-digit',
            hour: '2-digit', minute: '2-digit',
        });
    }

    function appendMessage(data) {
        const empty = messagesDiv.querySelector('.messages-empty');
        if (empty) empty.remove();

        const isOwn = parseInt(data.author_id, 10) === currentUserId;
        const el = document.createElement('div');
        el.className = 'message ' + (isOwn ? 'message-own' : 'message-other');
        el.dataset.messageId = data.message_id;

        const authorHtml = isOwn
            ? ''
            : `<span class="message-author">${escapeHtml(data.author)}</span>`;

        el.innerHTML = `
            <div class="message-bubble">
                ${authorHtml}
                <span class="message-text">${escapeHtml(data.text)}</span>
                <span class="message-time">${formatTime(data.created_at)}</span>
            </div>
        `;

        messagesDiv.appendChild(el);
        scrollToBottom();
    }

    // СОБЫТИЯ WEBSOCKET
    socket.onopen = () => {
        console.log('[chat] WebSocket открыт');
    };

    socket.onmessage = (e) => {
        try {
            appendMessage(JSON.parse(e.data));
        } catch (err) {
            console.error('[chat] ошибка парсинга сообщения:', err);
        }
    };

    socket.onerror = (e) => {
        console.error('[chat] WebSocket ошибка:', e);
    };

    socket.onclose = (e) => {
        if (e.wasClean) {
            console.log('[chat] WebSocket закрыт');
        } else {
            console.warn('[chat] WebSocket оборван. Обновите страницу.');
        }
    };

    function sendMessage() {
        const text = input.value.trim();
        if (!text) return;

        if (socket.readyState !== WebSocket.OPEN) {
            alert('Соединение потеряно. Обновите страницу.');
            return;
        }

        socket.send(JSON.stringify({ text: text }));
        input.value = '';
        input.style.height = 'auto';
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        sendMessage();
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    });

    scrollToBottom();
    input.focus();
})();