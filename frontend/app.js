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
        newAnalysisBtn: document.getElementById('new-analysis-btn')
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

    // Executive summary card at the top
    const summaryCard = document.createElement('div');
    summaryCard.className = 'report-card';
    summaryCard.innerHTML = `
        <div class="report-card-header">
            <span class="report-card-number">✦</span>
            <h3 class="report-card-title">Executive Summary</h3>
        </div>
        <div class="report-card-body">
            ${formatBodyToHtml(data.report)}
        </div>
    `;
    elements.reportContainer.appendChild(summaryCard);

    // One card per hypothesis
    data.hypotheses.forEach((h, i) => {
        const card = document.createElement('div');
        card.className = 'report-card hypothesis-card';
        const codeId = 'code-block-' + i;
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
                <div class="hypothesis-result">
                    <p>${h.result ? h.result.replace(/\n/g, '<br>') : 'No result recorded.'}</p>
                </div>
                <pre id="${codeId}" class="code-block hidden"><code>${h.code ? h.code.replace(/</g, '&lt;').replace(/>/g, '&gt;') : ''}</code></pre>
            </div>
        `;
        const btn = document.createElement('button');
        btn.className = 'view-code-btn';
        btn.textContent = 'View Code';
        btn.addEventListener('click', function() {
            const block = document.getElementById(codeId);
            block.classList.toggle('hidden');
            this.textContent = block.classList.contains('hidden') ? 'View Code' : 'Hide Code';
        });
        const cardBody = card.querySelector('.report-card-body');
        const preBlock = card.querySelector('.code-block');
        cardBody.insertBefore(btn, preBlock);
        elements.reportContainer.appendChild(card);
    });
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
    // Initialize
    // =====================
    switchState(STATES.UPLOAD);
})();
