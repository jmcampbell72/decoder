(function () {
    'use strict';

    const ANALYSES_URL = '/chat/analyses';
    const CHAT_URL = '/chat';

    const modalEl = document.getElementById('chatModal');
    const analysisList = document.getElementById('chatAnalysisList');
    const messagesEl = document.getElementById('chatMessages');
    const warningEl = document.getElementById('chatWarning');
    const inputEl = document.getElementById('chatInput');
    const sendBtn = document.getElementById('chatSendBtn');
    const sendLabel = document.getElementById('chatSendLabel');
    const sendSpinner = document.getElementById('chatSendSpinner');
    const clearBtn = document.getElementById('chatClearBtn');

    if (!modalEl) return;

    let analysesLoaded = false;

    // -----------------------------------------------------------------------
    // Load analyses into the sidebar on first modal open
    // -----------------------------------------------------------------------
    modalEl.addEventListener('show.bs.modal', function () {
        if (analysesLoaded) return;
        fetch(ANALYSES_URL, { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (analyses) {
                analysesLoaded = true;
                renderAnalysisList(analyses);
            })
            .catch(function () {
                analysisList.innerHTML =
                    '<div class="chat-sidebar-error"><i class="fas fa-exclamation-circle me-1"></i>Failed to load analyses.</div>';
            });
    });

    // -----------------------------------------------------------------------
    // Render checkbox list
    // -----------------------------------------------------------------------
    function renderAnalysisList(analyses) {
        if (!analyses || analyses.length === 0) {
            analysisList.innerHTML =
                '<div class="chat-sidebar-empty"><i class="fas fa-inbox me-1"></i>No completed analyses found.</div>';
            return;
        }

        var html = '';
        analyses.forEach(function (a) {
            var icon = a.source_type === 'github' ? 'fa-code-branch' : 'fa-file-archive';
            html +=
                '<label class="chat-analysis-item">' +
                '<input type="checkbox" class="chat-analysis-checkbox" value="' + a.id + '">' +
                '<span class="chat-analysis-info">' +
                '<span class="chat-analysis-name"><i class="fas ' + icon + ' me-1"></i>' + escHtml(a.name) + '</span>' +
                '<span class="chat-analysis-date">' + escHtml(a.created_at) + '</span>' +
                '</span>' +
                '</label>';
        });
        analysisList.innerHTML = html;
    }

    // -----------------------------------------------------------------------
    // Get selected analysis IDs
    // -----------------------------------------------------------------------
    function getSelectedIds() {
        var checked = analysisList.querySelectorAll('.chat-analysis-checkbox:checked');
        return Array.from(checked).map(function (c) { return parseInt(c.value, 10); });
    }

    // -----------------------------------------------------------------------
    // Prompt chips — fill textarea and auto-send
    // -----------------------------------------------------------------------
    document.querySelectorAll('.prompt-chip').forEach(function (chip) {
        chip.addEventListener('click', function () {
            inputEl.value = chip.getAttribute('data-prompt');
            sendMessage();
        });
    });

    // -----------------------------------------------------------------------
    // Send on button click or Enter (without Shift)
    // -----------------------------------------------------------------------
    sendBtn.addEventListener('click', sendMessage);

    inputEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // -----------------------------------------------------------------------
    // Clear conversation
    // -----------------------------------------------------------------------
    clearBtn.addEventListener('click', function () {
        messagesEl.innerHTML =
            '<div class="chat-welcome">' +
            '<i class="fas fa-robot fa-2x mb-2 d-block"></i>' +
            'Select one or more analyses on the left, then ask a question below or choose a quick prompt above.' +
            '</div>';
        inputEl.value = '';
        hideWarning();
    });

    // -----------------------------------------------------------------------
    // Core send logic
    // -----------------------------------------------------------------------
    function sendMessage() {
        var message = inputEl.value.trim();
        var ids = getSelectedIds();

        hideWarning();

        if (!ids.length) {
            showWarning();
            return;
        }
        if (!message) return;

        appendBubble('user', message);
        inputEl.value = '';
        setLoading(true);

        fetch(CHAT_URL, {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ analysis_ids: ids, message: message }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                setLoading(false);
                if (data.error) {
                    appendBubble('ai', '\u26a0\ufe0f ' + data.error);
                } else {
                    appendBubble('ai', data.response);
                }
            })
            .catch(function () {
                setLoading(false);
                appendBubble('ai', '\u26a0\ufe0f Something went wrong. Please try again.');
            });
    }

    // -----------------------------------------------------------------------
    // Append a chat bubble
    // -----------------------------------------------------------------------
    function appendBubble(role, text) {
        var welcome = messagesEl.querySelector('.chat-welcome');
        if (welcome) welcome.remove();

        var bubble = document.createElement('div');
        bubble.className = role === 'user' ? 'chat-bubble chat-bubble-user' : 'chat-bubble chat-bubble-ai';
        bubble.innerHTML = renderMarkdown(text);
        messagesEl.appendChild(bubble);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    // -----------------------------------------------------------------------
    // Minimal markdown renderer (bold, bullet lists, line breaks)
    // -----------------------------------------------------------------------
    function renderMarkdown(text) {
        var escaped = escHtml(text);
        escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        escaped = escaped.replace(/\n•\s?/g, '\n\u2022 ');

        var lines = escaped.split('\n');
        var output = '';
        var inList = false;

        lines.forEach(function (line) {
            var trimmed = line.trimStart();
            var isBullet = trimmed.startsWith('\u2022') || trimmed.startsWith('-') || trimmed.startsWith('*') || /^\d+\./.test(trimmed);

            if (isBullet) {
                if (!inList) { output += '<ul class="chat-list">'; inList = true; }
                var content = trimmed.replace(/^[\u2022\-\*]\s*/, '').replace(/^\d+\.\s*/, '');
                output += '<li>' + content + '</li>';
            } else {
                if (inList) { output += '</ul>'; inList = false; }
                if (trimmed === '') {
                    output += '<br>';
                } else {
                    output += '<p class="mb-1">' + line + '</p>';
                }
            }
        });

        if (inList) output += '</ul>';
        return output;
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------
    function setLoading(on) {
        sendBtn.disabled = on;
        inputEl.disabled = on;
        sendLabel.classList.toggle('d-none', on);
        sendSpinner.classList.toggle('d-none', !on);
    }

    function showWarning() {
        warningEl.classList.remove('d-none');
    }

    function hideWarning() {
        warningEl.classList.add('d-none');
    }

    function escHtml(str) {
        var d = document.createElement('div');
        d.appendChild(document.createTextNode(String(str)));
        return d.innerHTML;
    }
})();
