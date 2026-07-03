/**
 * InsightFlow — Autonomous BI Agent
 * Application Logic
 */

(function () {
    'use strict';

    // =====================
    // State Management
    // =====================
    const STATES = {
        UPLOAD: 'upload-state',
        LOADING: 'loading-state',
        REPORT: 'report-state',
        ERROR: 'error-state'
    };

    let currentFile = null;
    let currentSessionId = null; // Store for follow-up questions
    let loadingInterval = null;
    let loadingStartTime = 0;

    // =====================
    // DOM References
    // =====================
    const elements = {
        uploadState: document.getElementById('upload-state'),
        loadingState: document.getElementById('loading-state'),
        reportState: document.getElementById('report-state'),
        errorState: document.getElementById('error-state'),
        dropZone: document.getElementById('drop-zone'),
        fileInput: document.getElementById('file-input'),
        fileInfo: document.getElementById('file-info'),
        fileName: document.getElementById('file-name'),
        fileSize: document.getElementById('file-size'),
        removeFileBtn: document.getElementById('remove-file'),
        analyzeBtn: document.getElementById('analyze-btn'),
        loadingMessage: document.getElementById('loading-message'),
        reportContainer: document.getElementById('report-container'),
        errorMessage: document.getElementById('error-message'),
        retryBtn: document.getElementById('retry-btn'),
        newAnalysisBtn: document.getElementById('new-analysis-btn'),
        chatInput: document.getElementById('chat-input'),
        sendChatBtn: document.getElementById('send-chat-btn'),
        chatMessages: document.getElementById('chat-messages')
    };

    // =====================
    // Loading Messages
    // =====================
    const LOADING_MESSAGES = [
        'Profiling dataset...',
        'Generating hypotheses...',
        'Running analysis...',
        'Writing report...',
        'Synthesizing insights...',
        'Validating findings...'
    ];

    // =====================
    // Utility Functions
    // =====================
    function switchState(stateName) {
        // Hide all states
        Object.values(STATES).forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });

        // Show target state
        const target = document.getElementById(stateName);
        if (target) {
            target.classList.remove('hidden');
            // Trigger reflow for animation restart
            void target.offsetWidth;
        }
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i];
    }

    function updateFileInfo(file) {
        if (!file) {
            elements.fileInfo.classList.add('hidden');
            elements.fileName.textContent = '';
            elements.fileSize.textContent = '';
            elements.analyzeBtn.disabled = true;
            return;
        }

        elements.fileName.textContent = file.name;
        elements.fileSize.textContent = formatFileSize(file.size);
        elements.fileInfo.classList.remove('hidden');
        elements.analyzeBtn.disabled = false;
    }

    function clearFile() {
        currentFile = null;
        elements.fileInput.value = '';
        updateFileInfo(null);
    }

    // =====================
    // Loading Animation
    // =====================
    function startLoadingAnimation() {
        let messageIndex = 0;
        loadingStartTime = Date.now();

        elements.loadingMessage.textContent = LOADING_MESSAGES[0];
        elements.loadingMessage.style.opacity = '1';

        loadingInterval = setInterval(() => {
            messageIndex = (messageIndex + 1) % LOADING_MESSAGES.length;

            // Fade out, change text, fade in
            elements.loadingMessage.style.opacity = '0';

            setTimeout(() => {
                elements.loadingMessage.textContent = LOADING_MESSAGES[messageIndex];
                elements.loadingMessage.style.opacity = '1';
            }, 300);
        }, 3000);
    }

    function stopLoadingAnimation() {
        if (loadingInterval) {
            clearInterval(loadingInterval);
            loadingInterval = null;
        }
    }

    // =====================
    // Report Parser
    // =====================
    /**
     * Parse report text into structured sections.
     * Splits on numbered section headers like "1. Executive Summary"
     */
    function parseReport(text) {
        if (!text || typeof text !== 'string') {
            return [{
                number: '',
                title: 'Report',
                body: 'No content available.'
            }];
        }

        // Regex to match section headers: "1. Title", "2. Title", etc.
        const sectionRegex = /(?:^|\n)(\d+)\.\s+(.+?)(?:\n|$)/g;
        const sections = [];
        let match;
        const matches = [];

        while ((match = sectionRegex.exec(text)) !== null) {
            matches.push({
                index: match.index,
                number: match[1].trim(),
                title: match[2].trim(),
                fullMatch: match[0]
            });
        }

        if (matches.length === 0) {
            // No numbered sections found, return whole text as single section
            return [{
                number: '',
                title: 'Analysis Report',
                body: text.trim()
            }];
        }

        for (let i = 0; i < matches.length; i++) {
            const current = matches[i];
            const next = matches[i + 1];
            const startIndex = current.index + current.fullMatch.length;
            const endIndex = next ? next.index : text.length;
            const body = text.slice(startIndex, endIndex).trim();

            sections.push({
                number: current.number,
                title: current.title,
                body: body
            });
        }

        return sections;
    }

    /**
     * Convert plain text body into HTML with proper formatting.
     * - Bullet points (lines starting with -, *, or \u2022) become <li>
     * - Blank lines create paragraph breaks
     * - Bold text with **text** becomes <strong>
     * - Italic text with *text* becomes <em>
     */
    function formatBodyToHtml(body) {
        if (!body) return '';

        const lines = body.split('\n');
        const groups = [];
        let currentGroup = [];
        let inList = false;

        for (const rawLine of lines) {
            const line = rawLine.trim();
            if (!line) {
                if (currentGroup.length > 0) {
                    groups.push({ type: inList ? 'list' : 'text', items: [...currentGroup] });
                    currentGroup = [];
                    inList = false;
                }
                continue;
            }

            const isBullet = /^[-\*\u2022\u2023\u25E6\u2043]\s+/.test(line);

            if (isBullet) {
                if (!inList && currentGroup.length > 0) {
                    groups.push({ type: 'text', items: [...currentGroup] });
                    currentGroup = [];
                }
                inList = true;
                currentGroup.push(line.replace(/^[-\*\u2022\u2023\u25E6\u2043]\s+/, ''));
            } else {
                if (inList && currentGroup.length > 0) {
                    groups.push({ type: 'list', items: [...currentGroup] });
                    currentGroup = [];
                }
                inList = false;
                currentGroup.push(line);
            }
        }

        if (currentGroup.length > 0) {
            groups.push({ type: inList ? 'list' : 'text', items: [...currentGroup] });
        }

        // Build HTML
        let html = '';
        for (const group of groups) {
            if (group.type === 'list') {
                html += '<ul>';
                for (const item of group.items) {
                    html += '<li>' + inlineFormat(item) + '</li>';
                }
                html += '</ul>';
            } else {
                for (const item of group.items) {
                    html += '<p>' + inlineFormat(item) + '</p>';
                }
            }
        }

        return html;
    }

    function inlineFormat(text) {
        return text
            .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>');
    }

    // =====================
    // Report Renderer
    // =====================
    function renderReport(data) {
        elements.reportContainer.innerHTML = '';

        // 1. One card per hypothesis FIRST (as requested)
        if (data.hypotheses && data.hypotheses.length > 0) {
            data.hypotheses.forEach((h, i) => {
                const card = document.createElement('div');
                card.className = 'report-card hypothesis-card';
                const codeId = `code-block-${i}`;
                const outputId = `output-block-${i}`;

                card.innerHTML = `
                    <div class="report-card-header">
                        <span class="report-card-number">${i + 1}</span>
                        <h3 class="report-card-title">${h.question}</h3>
                    </div>
                    <div class="report-card-body">
                        <div class="hypothesis-status ${h.status}">
                            <span class="status-dot"></span>
                            <span class="status-label">${h.status}</span>
                        </div>
                        <div class="hypothesis-discussion">
                            ${h.discussion ? formatBodyToHtml(h.discussion) : (h.result ? formatBodyToHtml(h.result) : (h.status === 'tested' ? '<p class="status-note">Analysis complete. View execution output for details.</p>' : '<p class="status-note">No discussion available yet.</p>'))}
                        </div>
                        
                        <div class="toggle-container">
                            <button class="view-code-btn" data-target="${codeId}">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></button>
                                View Code
                            </button>
                            <button class="view-output-btn" data-target="${outputId}">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                                Show Output
                            </button>
                        </div>

                        <pre id="${codeId}" class="code-block hidden"><code>${h.code ? h.code.trim() : '# No code generated'}</code></pre>
                        <pre id="${outputId}" class="output-block hidden"><code>${h.result ? h.result.trim() : 'No execution output available'}</code></pre>
                    </div>
                `;
                elements.reportContainer.appendChild(card);
            });

            // Re-attach listeners for the new buttons
            elements.reportContainer.querySelectorAll('.view-code-btn, .view-output-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const targetId = this.getAttribute('data-target');
                    const block = document.getElementById(targetId);
                    
                    // Toggle this block
                    const isHidden = block.classList.toggle('hidden');
                    this.classList.toggle('active', !isHidden);
                    
                    // If showing code, hide output (and vice-versa) to keep it clean
                    const siblingClass = this.classList.contains('view-code-btn') ? '.view-output-btn' : '.view-code-btn';
                    const siblingBtn = this.parentElement.querySelector(siblingClass);
                    const siblingTarget = document.getElementById(siblingBtn.getAttribute('data-target'));
                    
                    if (!isHidden) {
                        siblingTarget.classList.add('hidden');
                        siblingBtn.classList.remove('active');
                        // Update text
                        if (this.classList.contains('view-code-btn')) {
                            this.innerHTML = this.innerHTML.replace('View Code', 'Hide Code');
                            siblingBtn.innerHTML = siblingBtn.innerHTML.replace('Hide Output', 'Show Output');
                        } else {
                            this.innerHTML = this.innerHTML.replace('Show Output', 'Hide Output');
                            siblingBtn.innerHTML = siblingBtn.innerHTML.replace('Hide Code', 'View Code');
                        }
                    } else {
                        // Restore text when hiding
                        if (this.classList.contains('view-code-btn')) {
                            this.innerHTML = this.innerHTML.replace('Hide Code', 'View Code');
                        } else {
                            this.innerHTML = this.innerHTML.replace('Hide Output', 'Show Output');
                        }
                    }
                });
            });
        }

        // 2. Executive summary / Report sections LAST
        const reportSection = document.createElement('section');
        reportSection.className = 'report-section';
        
        // Parse the report into the 3 requested segments
        const segments = splitReportText(data.report);
        
        reportSection.innerHTML = `
            <div class="report-section-header">
                <div class="report-section-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                </div>
                <h2 class="report-section-title">Analysis Summary</h2>
            </div>
            
            <div class="report-sub-card report-sub-card--summary">
                <h4>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                    Executive Summary
                </h4>
                <div class="content">${formatBodyToHtml(segments.summary)}</div>
            </div>
            
            <div class="report-sub-card report-sub-card--findings">
                <h4>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                    Key Findings
                </h4>
                <div class="content">${formatBodyToHtml(segments.findings)}</div>
            </div>
            
            <div class="report-sub-card report-sub-card--actions">
                <h4>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"></path></svg>
                    Recommended Next Actions
                </h4>
                <div class="content">${formatBodyToHtml(segments.actions)}</div>
            </div>
        `;
        
        elements.reportContainer.appendChild(reportSection);
    }

    /**
     * Splits the full report text into 3 parts based on keywords or structure.
     */
    function splitReportText(text) {
        if (!text) return { summary: '', findings: '', actions: '' };

        const result = {
            summary: '',
            findings: '',
            actions: ''
        };

        // Try to split based on markdown headings or specific patterns
        const sections = text.split(/(?=#{1,4}\s+|Executive Summary|Key Findings|Recommended Next Actions)/i);
        
        let currentSection = 'summary';
        
        sections.forEach(s => {
            const lower = s.toLowerCase();
            if (lower.includes('key findings')) {
                currentSection = 'findings';
            } else if (lower.includes('next actions') || lower.includes('recommendations')) {
                currentSection = 'actions';
            } else if (lower.includes('executive summary')) {
                currentSection = 'summary';
            }
            
            // Append content, stripping the header if it matches exactly
            const content = s.replace(/#{1,4}\s+(Executive Summary|Key Findings|Recommended Next Actions|Next Actions|Recommendations)/i, '').trim();
            if (content) {
                result[currentSection] += (result[currentSection] ? '\n\n' : '') + content;
            }
        });

        // Fallback if splitting didn't work well
        if (!result.findings && !result.actions) {
            // If it's one big block, we'll just put it all in summary and provide empty shells
            result.summary = text;
        }

        return result;
    }

    // =====================
    // API Call
    // =====================
    async function analyzeFile(file) {
        if (!file) return;

        switchState(STATES.LOADING);
        startLoadingAnimation();

        const formData = new FormData();
        formData.append('file', file);

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 300000); 

            const response = await fetch('/analyze/', {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });

            clearTimeout(timeoutId);
            stopLoadingAnimation();

            if (!response.ok) {
                let errorText = 'The server returned an error. Please try again.';
                try {
                    const errorData = await response.json();
                    if (errorData.detail) errorText = errorData.detail;
                } catch (e) {
                    // Non-JSON response, use default message
                }
                throw new Error(errorText);
            }

            const data = await response.json();

            if (!data.report || typeof data.report !== 'string') {
                throw new Error('The server response was not in the expected format.');
            }

            currentSessionId = data.session_id; // Capture session for follow-ups
            renderReport(data);
            switchState(STATES.REPORT);

        } catch (error) {
            stopLoadingAnimation();

            let message = 'We couldn\'t complete the analysis. Please try again.';

            if (error.name === 'AbortError') {
                message = 'The request timed out. Please check that the server is running and try again.';
            } else if (error.message) {
                message = error.message;
            }

            elements.errorMessage.textContent = message;
            switchState(STATES.ERROR);
        }
    }

    // =====================
    // Event Handlers
    // =====================
    function handleFileSelect(file) {
        if (!file) return;

        if (!file.name.toLowerCase().endsWith('.csv')) {
            alert('Please select a CSV file (.csv)');
            clearFile();
            return;
        }

        if (file.size > 50 * 1024 * 1024) {
            alert('File size must be less than 50MB');
            clearFile();
            return;
        }

        currentFile = file;
        updateFileInfo(file);
    }

    // File input change
    elements.fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            handleFileSelect(e.target.files[0]);
        }
    });

    // Remove file button
    elements.removeFileBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        clearFile();
    });

    // Analyze button
    elements.analyzeBtn.addEventListener('click', () => {
        if (currentFile) {
            analyzeFile(currentFile);
        }
    });

    // Drag and drop
    elements.dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        elements.dropZone.classList.add('drag-active');
    });

    elements.dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!elements.dropZone.contains(e.relatedTarget)) {
            elements.dropZone.classList.remove('drag-active');
        }
    });

    elements.dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        elements.dropZone.classList.remove('drag-active');

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    // Keyboard support for drop zone
    elements.dropZone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            elements.fileInput.click();
        }
    });

    // Retry button
    elements.retryBtn.addEventListener('click', () => {
        if (currentFile) {
            analyzeFile(currentFile);
        } else {
            switchState(STATES.UPLOAD);
        }
    });

    // New analysis button
    elements.newAnalysisBtn.addEventListener('click', () => {
        clearFile();
        elements.reportContainer.innerHTML = '';
        switchState(STATES.UPLOAD);
    });

    // Prevent default drag behavior on document
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', (e) => {
        // Only handle if not dropping on the drop zone
        if (!elements.dropZone.contains(e.target)) {
            e.preventDefault();
        }
    });

    // =====================
    // Chat Logic
    // =====================
    async function sendFollowUp() {
        const question = elements.chatInput.value.trim();
        if (!question || !currentSessionId) return;

        // Clear input
        elements.chatInput.value = '';

        // Add user message
        appendMessage('user', question);

        // Add thinking indicator
        const loadingId = appendMessage('assistant', '', true);

        try {
            const response = await fetch(`/followup/?session_id=${currentSessionId}&question=${encodeURIComponent(question)}`, {
                method: 'POST'
            });

            if (!response.ok) throw new Error('Failed to get response');

            const data = await response.json();
            
            // Remove loading indicator
            const loadingEl = document.getElementById(loadingId);
            if (loadingEl) loadingEl.remove();

            if (data.status === 'tested') {
                appendMessage('assistant', data.result);
                // If there's code, we can optionally show it, but for chat we usually keep it text-focused
                console.log('Follow-up code executed:', data.code);
            } else {
                appendMessage('error', data.result || 'Analysis failed for this question.');
            }
        } catch (error) {
            const loadingEl = document.getElementById(loadingId);
            if (loadingEl) loadingEl.remove();
            appendMessage('error', 'Connection lost. Please try again.');
        }
    }

    function appendMessage(role, text, isLoading = false) {
        const id = 'msg-' + Date.now();
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role} ${role === 'error' ? 'error' : ''}`;
        msgDiv.id = id;

        let content = '';
        if (isLoading) {
            content = `<div class="message-content"><div class="typing-dots"><span></span><span></span><span></span></div></div>`;
        } else {
            // Basic formatting for results (newlines to <br>)
            const formattedText = text.replace(/\n/g, '<br>');
            content = `<div class="message-content"><p>${formattedText}</p></div>`;
        }

        msgDiv.innerHTML = content;
        elements.chatMessages.appendChild(msgDiv);
        
        // Auto scroll
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
        
        return id;
    }

    // Chat Event Listeners
    elements.sendChatBtn.addEventListener('click', sendFollowUp);
    elements.chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendFollowUp();
    });

    // =====================
    // Initialize
    // =====================
    switchState(STATES.UPLOAD);
})();
