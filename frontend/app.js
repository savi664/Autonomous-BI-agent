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
    function renderReport(sections) {
        elements.reportContainer.innerHTML = '';

        for (const section of sections) {
            const card = document.createElement('div');
            card.className = 'report-card';

            const header = document.createElement('div');
            header.className = 'report-card-header';

            const numberBadge = document.createElement('span');
            numberBadge.className = 'report-card-number';
            numberBadge.textContent = section.number || '•';

            const title = document.createElement('h3');
            title.className = 'report-card-title';
            title.textContent = section.title;

            header.appendChild(numberBadge);
            header.appendChild(title);

            const body = document.createElement('div');
            body.className = 'report-card-body';
            body.innerHTML = formatBodyToHtml(section.body);

            card.appendChild(header);
            card.appendChild(body);
            elements.reportContainer.appendChild(card);
        }
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
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

            const response = await fetch('http://127.0.0.1:8000/analyze/', {
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

            const sections = parseReport(data.report);
            renderReport(sections);
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
