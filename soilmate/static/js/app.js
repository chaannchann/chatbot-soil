const chatFeed = document.getElementById('chatFeed');
const chatHistoryEl = document.getElementById('chatHistory');
const chatForm = document.getElementById('chatForm');
const userInput = document.getElementById('userInput');
const soilImageInput = document.getElementById('soilImageInput');
const imagePreviewContainer = document.getElementById('imagePreviewContainer');
const imagePreview = document.getElementById('imagePreview');
const analyzeBtn = document.getElementById('analyzeBtn');
const chatImageInput = document.getElementById('chatImageInput');
const chatCameraBtn = document.getElementById('chatCameraBtn');
const plantNowBtn = document.getElementById('plantNowBtn');
const langToggleBtn = document.getElementById('langToggleBtn');
const welcomeTitle = document.getElementById('welcomeTitle');
const welcomeText = document.getElementById('welcomeText');
const photoBtnLabel = document.getElementById('photoBtnLabel');
const sendBtnLabel = document.getElementById('sendBtnLabel');
const newChatBtn = document.getElementById('newChatBtn');

let selectedFile = null;
let lastSoilType = null;

// Chat language: "en" or "tl". The toggle also localizes the suggested
// questions, the welcome banner, and the planting calendar card.
const LANG_KEY = 'soilmate_lang';
let chatLanguage = localStorage.getItem(LANG_KEY) === 'tl' ? 'tl' : 'en';

// Stable per-browser id so the chatbot can remember context between turns
// (e.g. "how much compost for THIS soil?"). "New chat" rotates it so the
// conversation starts with clean context.
function createSessionId() {
    return (window.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : 's-' + Date.now() + '-' + Math.random().toString(16).slice(2);
}

let SESSION_ID = localStorage.getItem('soilmate_session');
if (!SESSION_ID) {
    SESSION_ID = createSessionId();
    localStorage.setItem('soilmate_session', SESSION_ID);
}

// Groups saved messages into reopenable conversations in the sidebar. It is
// separate from SESSION_ID so the chatbot can reset context without losing
// the conversation that is already saved.
const CONVERSATION_KEY = 'soilmate_conversation';
let CONVERSATION_ID = localStorage.getItem(CONVERSATION_KEY);
if (!CONVERSATION_ID) {
    CONVERSATION_ID = createSessionId();
    localStorage.setItem(CONVERSATION_KEY, CONVERSATION_ID);
}

// ------------------------- THEME -------------------------
const THEME_KEY = 'soilmate_theme';
const themeMedia = window.matchMedia('(prefers-color-scheme: dark)');

function themeIsDark() {
    return document.documentElement.classList.contains('dark');
}

function syncThemeButtons() {
    const dark = themeIsDark();
    const label = dark ? 'Switch to light mode' : 'Switch to dark mode';
    document.querySelectorAll('[data-theme-toggle]').forEach(btn => {
        btn.setAttribute('aria-pressed', String(dark));
        btn.setAttribute('aria-label', label);
        btn.title = label;
    });
}

// persist=false is used when following the OS preference instead of a user choice.
function setTheme(dark, persist = true) {
    document.documentElement.classList.toggle('dark', dark);
    if (persist) localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light');
    syncThemeButtons();
}

document.querySelectorAll('[data-theme-toggle]').forEach(btn => {
    btn.addEventListener('click', () => setTheme(!themeIsDark()));
});

themeMedia.addEventListener('change', (event) => {
    if (!localStorage.getItem(THEME_KEY)) setTheme(event.matches, false);
});

syncThemeButtons();

// Escape user-supplied text before adding the small amount of markdown we support.
function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatInline(text) {
    return text
        .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-slate-900 dark:text-slate-100">$1</strong>')
        .replace(/\*([^*\n]+)\*/g, '<em class="italic text-slate-600 dark:text-slate-300">$1</em>');
}

// Convert our small markdown subset into tidy paragraphs and lists.
function formatMarkdown(text) {
    if (!text) return '';

    const lines = escapeHtml(text).replace(/\r\n?/g, '\n').split('\n');
    const html = [];
    let paragraph = [];
    let listType = null;
    let listItems = [];

    const flushParagraph = () => {
        if (!paragraph.length) return;
        html.push(`<p class="mb-2 last:mb-0">${formatInline(paragraph.join(' '))}</p>`);
        paragraph = [];
    };

    const flushList = () => {
        if (!listType) return;
        const tag = listType === 'ol' ? 'ol' : 'ul';
        const className = listType === 'ol'
            ? 'list-decimal pl-5 space-y-1 my-2 marker:text-emerald-600 dark:marker:text-emerald-400'
            : 'list-disc pl-5 space-y-1 my-2 marker:text-emerald-600 dark:marker:text-emerald-400';
        html.push(
            `<${tag} class="${className}">` +
            listItems.map(item => `<li>${formatInline(item)}</li>`).join('') +
            `</${tag}>`
        );
        listType = null;
        listItems = [];
    };

    for (const rawLine of lines) {
        const line = rawLine.trim();

        if (!line) {
            flushParagraph();
            flushList();
            continue;
        }

        const unordered = line.match(/^[-*]\s+(.*)$/);
        const ordered = line.match(/^\d+[.)]\s+(.*)$/);

        if (unordered || ordered) {
            flushParagraph();
            const nextType = ordered ? 'ol' : 'ul';
            if (listType && listType !== nextType) flushList();
            listType = nextType;
            listItems.push((ordered || unordered)[1]);
            continue;
        }

        flushList();
        paragraph.push(line);
    }

    flushParagraph();
    flushList();
    return html.join('');
}

// Append message bubble to chat
function appendMessage(sender, content, isHtml = false) {
    const wrapper = document.createElement('div');
    wrapper.className = sender === 'user'
        ? 'flex gap-3 justify-end'
        : 'flex gap-3 max-w-2xl';

    const bubble = document.createElement('div');
    bubble.className = sender === 'user'
        ? 'bg-emerald-700 dark:bg-emerald-600 text-white p-3 sm:p-4 rounded-2xl rounded-tr-none text-sm shadow-xs break-words max-w-[85%]'
        : 'bg-white text-slate-800 p-3 sm:p-4 rounded-2xl rounded-tl-none border border-slate-200 text-sm shadow-xs leading-relaxed break-words min-w-0 dark:bg-slate-900 dark:text-slate-200 dark:border-slate-700';

    if (isHtml) {
        bubble.innerHTML = content;
    } else {
        bubble.innerHTML = formatMarkdown(content);
    }

    wrapper.appendChild(bubble);
    chatFeed.appendChild(wrapper);
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

// Compact, collapsible crop list shared by the analysis and planting cards.
let cropGroupCounter = 0;

function renderCropGrid(crops, emptyMessage, language = 'en') {
    if (!crops || !crops.length) {
        return `<p class="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-xl p-3 dark:text-slate-400 dark:bg-slate-800/60 dark:border-slate-700">${emptyMessage}</p>`;
    }

    const tl = language === 'tl';
    const groupId = `crop-group-${++cropGroupCounter}`;
    const visibleCount = 6;

    const cards = crops.map((c, index) => {
        const isExtra = index >= visibleCount;
        const extraClass = isExtra ? ' hidden' : '';
        const extraAttr = isExtra ? ` data-crop-extra="${groupId}"` : '';
        const local = escapeHtml(c.local_name || c.category || (tl ? 'Pananim sa Pilipinas' : 'Philippine crop'));
        const season = escapeHtml(c.ideal_planting_season || (tl ? 'Buong taon' : 'Year-round'));

        return `
            <div class="p-3 bg-emerald-50/60 rounded-xl border border-emerald-100 dark:bg-emerald-950/40 dark:border-emerald-900${extraClass}"${extraAttr}>
                <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0">
                        <p class="font-bold text-emerald-950 text-sm truncate dark:text-emerald-100">${escapeHtml(c.common_name)}</p>
                        <p class="text-[11px] text-emerald-700/80 truncate dark:text-emerald-300/80">${local}</p>
                    </div>
                    ${c.in_season_now ? `<span class="shrink-0 text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-semibold dark:bg-amber-900/50 dark:text-amber-200">${tl ? 'Kapanahunan' : 'In season'}</span>` : ''}
                </div>
                <div class="mt-2 space-y-0.5 text-[11px] text-slate-600 dark:text-slate-400">
                    <p><strong class="text-slate-700 dark:text-slate-300">${tl ? 'Ani:' : 'Harvest:'}</strong> ${c.harvest_days_min}–${c.harvest_days_max} ${tl ? 'araw' : 'days'}</p>
                    <p class="truncate" title="${season}"><strong class="text-slate-700 dark:text-slate-300">${tl ? 'Panahon:' : 'Season:'}</strong> ${season}</p>
                </div>
            </div>
        `;
    }).join('');

    const toggle = crops.length > visibleCount
        ? `<button type="button" data-show-crops="${groupId}" data-total="${crops.length}" aria-expanded="false"
                   class="mt-2 w-full sm:w-auto text-xs font-semibold text-emerald-700 hover:text-emerald-900 bg-emerald-50 hover:bg-emerald-100 border border-emerald-100 px-3 py-2 rounded-xl transition dark:text-emerald-300 dark:hover:text-emerald-200 dark:bg-emerald-900/40 dark:hover:bg-emerald-900/70 dark:border-emerald-800">
               ${tl ? `Ipakita lahat ng ${crops.length} pananim` : `Show all ${crops.length} crops`}
           </button>`
        : '';

    return `<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">${cards}</div>${toggle}`;
}

chatFeed.addEventListener('click', (event) => {
    const button = event.target.closest('[data-show-crops]');
    if (!button) return;

    const groupId = button.dataset.showCrops;
    const extras = chatFeed.querySelectorAll(`[data-crop-extra="${groupId}"]`);
    if (!extras.length) return;

    const willShow = extras[0].classList.contains('hidden');
    extras.forEach(item => item.classList.toggle('hidden', !willShow));
    const tl = chatLanguage === 'tl';
    button.textContent = willShow
        ? (tl ? 'Ipakita ang kaunti' : 'Show fewer crops')
        : (tl ? `Ipakita lahat ng ${button.dataset.total} pananim` : `Show all ${button.dataset.total} crops`);
    button.setAttribute('aria-expanded', String(willShow));
});

// Generate a clean HTML card for the soil analysis results
function renderSoilAnalysisCard(data) {
    const recommendations = data.recommendations || [];
    const cropsHtml = renderCropGrid(recommendations, 'No specific crops mapped to this profile yet.');

    return `
        <div class="space-y-3">
            <div class="flex items-center justify-between gap-2 flex-wrap border-b border-slate-100 pb-2 dark:border-slate-800">
                <span class="font-bold text-base text-slate-900 dark:text-white">Soil Analysis Result</span>
                <span class="bg-emerald-100 text-emerald-800 text-xs px-2.5 py-1 rounded-full font-semibold dark:bg-emerald-900/60 dark:text-emerald-200">
                    ${(data.confidence * 100).toFixed(0)}% Confidence
                </span>
            </div>

            <div>
                <span class="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Detected Soil</span>
                <p class="font-bold text-emerald-800 text-lg dark:text-emerald-300">${data.soil_type}</p>
                <p class="text-xs text-slate-600 mt-0.5 dark:text-slate-400">${data.description}</p>
            </div>

            <div class="bg-amber-50 border border-amber-200/80 p-3 rounded-xl text-xs text-amber-900 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-200">
                <strong class="font-bold block mb-1">Soil Improvement Tip:</strong>
                ${data.improvement_tips}
            </div>

            <div class="pt-1">
                <div class="flex items-center justify-between gap-2 flex-wrap mb-2">
                    <span class="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">Recommended Crops (Philippines)</span>
                    <span class="text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-full dark:text-emerald-300 dark:bg-emerald-900/40 dark:border-emerald-800">
                        ${recommendations.length} matches
                    </span>
                </div>
                ${cropsHtml}
            </div>
        </div>
    `;
}

const UNIDENTIFIED_TITLES = {
    low_confidence: 'Soil Unrecognized',
    too_small: 'Photo Too Small',
    too_dark: 'Photo Too Dark',
    too_bright: 'Photo Too Bright',
    flat: 'Photo Lacks Detail',
    not_soil: "This Doesn't Look Like Soil",
};

function renderUnidentifiedCard(data) {
    const title = UNIDENTIFIED_TITLES[data.reason] || 'Soil Unrecognized';

    const tips = (data.tips && data.tips.length)
        ? `<div class="bg-slate-50 border border-slate-200 p-2 rounded-lg dark:bg-slate-800/60 dark:border-slate-700">
               <p class="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-1 dark:text-slate-400">Try this</p>
               <ul class="text-xs text-slate-600 list-disc pl-4 space-y-0.5 dark:text-slate-300">
                   ${data.tips.map(t => `<li>${t}</li>`).join('')}
               </ul>
           </div>`
        : '';

    const confidence = data.reason === 'low_confidence'
        ? `<div class="text-[11px] text-slate-400 bg-slate-100 p-2 rounded-lg dark:text-slate-400 dark:bg-slate-800">
               Confidence score (${((data.confidence || 0) * 100).toFixed(1)}%) is below the required 75% threshold.
           </div>`
        : '';

    return `
        <div class="space-y-2">
            <div class="flex items-center gap-2 text-amber-700 font-bold dark:text-amber-300">
                <span>${title}</span>
            </div>
            <p class="text-xs text-slate-600 leading-relaxed dark:text-slate-400">${data.message}</p>
            ${tips}
            ${confidence}
        </div>
    `;
}

// Send one chat message to the bot (used by the form and by suggestion chips)
async function sendMessage(text) {
    text = (text || '').trim();
    if (!text) return;

    appendMessage('user', text);

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                session_id: SESSION_ID,
                conversation_id: CONVERSATION_ID,
                soil_type: lastSoilType,
                lang: chatLanguage
            })
        });
        const data = await res.json();
        appendMessage('bot', data.reply);
        appendSuggestions(data.suggestions);

        // Signed-in chats are saved, so clearing history becomes available.
        if (isAuthenticatedUser) {
            hasSavedChats = true;
            setClearHistoryVisible(true);
            fetchHistory().then(d => { if (d && d.conversations) renderConversations(d.conversations); });
        }
    } catch (err) {
        appendMessage('bot', chatLanguage === 'tl'
            ? 'Error sa pakikipag-usap sa server.'
            : 'Error communicating with server.');
    }
}

// Render clickable follow-up chips under a bot reply
function appendSuggestions(suggestions) {
    if (!suggestions || !suggestions.length) return;

    const row = document.createElement('div');
    row.className = 'flex flex-wrap gap-2 pl-11 pt-1';

    suggestions.forEach(text => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'text-xs bg-white border border-emerald-200 text-emerald-800 hover:bg-emerald-50 px-3 py-1.5 rounded-full transition shadow-xs dark:bg-slate-900 dark:border-emerald-800 dark:text-emerald-300 dark:hover:bg-emerald-900/40';
        btn.textContent = text;
        btn.addEventListener('click', () => sendMessage(text));
        row.appendChild(btn);
    });

    chatFeed.appendChild(row);
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

// Text Chat Submission
chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = userInput.value.trim();
    if (!text) return;
    userInput.value = '';
    sendMessage(text);
});

// Image Selection Preview
soilImageInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        selectedFile = file;
        imagePreview.src = URL.createObjectURL(file);
        imagePreviewContainer.classList.remove('hidden');
    }
});

function clearImageSelection() {
    selectedFile = null;
    if (soilImageInput) soilImageInput.value = '';
    if (chatImageInput) chatImageInput.value = '';
    if (imagePreview) {
        if (imagePreview.src && imagePreview.src.startsWith('blob:')) {
            URL.revokeObjectURL(imagePreview.src);
        }
        imagePreview.src = '';
    }
    if (imagePreviewContainer) {
        imagePreviewContainer.classList.add('hidden');
    }
}

// Image Analysis Trigger (sidebar button and chat camera button share this)
// Image Analysis Trigger (sidebar button and chat camera button share this)
// Image Analysis Trigger (sidebar button and chat camera button share this)
async function analyzeSelectedImage() {
    if (!selectedFile) return;

    closeSidebar();

    // 1. Save file to a local variable FIRST before clearing the sidebar UI
    const fileToUpload = selectedFile;
    clearImageSelection();

    // 2. Show the photo in the chat bubble
    const previewUrl = URL.createObjectURL(fileToUpload);
    const userPhotoHtml = `
        <div class="space-y-1.5">
            <img src="${previewUrl}" alt="Soil sample" 
                 class="w-48 sm:w-64 h-36 sm:h-48 object-cover rounded-xl shadow-md border border-white/20">
            <p class="text-[11px] text-emerald-100/90 font-semibold flex items-center gap-1">
                <span>📷</span> Soil sample submitted
            </p>
        </div>
    `;
    appendMessage('user', userPhotoHtml, true);

    // 3. Bot loading indicator with spinner
    const loadingWrapper = document.createElement('div');
    loadingWrapper.className = 'flex gap-3 max-w-2xl message-enter';
    loadingWrapper.innerHTML = `
        <div class="bg-white text-slate-800 p-3 sm:p-4 rounded-2xl rounded-tl-none border border-slate-200 text-sm shadow-xs flex items-center gap-2.5 dark:bg-slate-900 dark:text-slate-200 dark:border-slate-700">
            <svg class="animate-spin h-4 w-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
            <span class="text-xs sm:text-sm font-medium">Analyzing soil texture using trained neural network...</span>
        </div>
    `;
    chatFeed.appendChild(loadingWrapper);
    chatFeed.scrollTop = chatFeed.scrollHeight;

    // 4. Send the actual file in FormData
    const formData = new FormData();
    formData.append('image', fileToUpload);
    formData.append('session_id', SESSION_ID);

    try {
        const res = await fetch('/api/predict-soil', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        // Remove spinner
        if (loadingWrapper.parentNode) {
            loadingWrapper.parentNode.removeChild(loadingWrapper);
        }

        if (!res.ok || data.error) {
            appendMessage('bot', `<strong>Server Error:</strong> ${data.error || 'Server returned an error'}`, true);
            return;
        }

        if (data.identified === false) {
            appendMessage('bot', renderUnidentifiedCard(data), true);
            refreshScans();
            return;
        }

        lastSoilType = data.soil_type;
        const cardHtml = renderSoilAnalysisCard(data);
        appendMessage('bot', cardHtml, true);
        refreshScans();

    } catch (err) {
        if (loadingWrapper.parentNode) {
            loadingWrapper.parentNode.removeChild(loadingWrapper);
        }
        appendMessage('bot', `Failed to communicate with server: ${err.message}`);
    }
}

analyzeBtn.addEventListener('click', analyzeSelectedImage);

// ------------------------- WEBCAM CAPTURE -------------------------
const cameraModal = document.getElementById('cameraModal');
const cameraVideo = document.getElementById('cameraVideo');
const cameraCanvas = document.getElementById('cameraCanvas');
const cameraStatus = document.getElementById('cameraStatus');
const cameraCaptureBtn = document.getElementById('cameraCaptureBtn');
const cameraUploadBtn = document.getElementById('cameraUploadBtn');
const cameraCloseBtn = document.getElementById('cameraCloseBtn');

// Phones and tablets keep their native camera sheet; desktops use the webcam modal.
const useNativeCamera = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
let cameraStream = null;

function closeCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    cameraVideo.srcObject = null;
    cameraCaptureBtn.disabled = true;
    cameraModal.classList.add('hidden');
    cameraModal.classList.remove('flex');
}

async function openCamera() {
    // No getUserMedia, or a plain-http LAN address: fall back to the file picker.
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        chatImageInput.click();
        return;
    }

    cameraModal.classList.remove('hidden');
    cameraModal.classList.add('flex');
    cameraStatus.textContent = 'Starting camera...';
    cameraStatus.classList.remove('hidden');
    cameraCaptureBtn.disabled = true;

    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
            audio: false
        });

        // The modal may have been closed while the permission prompt was open.
        if (cameraModal.classList.contains('hidden')) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
            return;
        }

        cameraVideo.srcObject = cameraStream;
        await cameraVideo.play();
        cameraStatus.classList.add('hidden');
        cameraCaptureBtn.disabled = false;
    } catch (err) {
        // No webcam, permission denied, or the camera is busy.
        closeCamera();
        chatImageInput.click();
    }
}

function capturePhoto() {
    if (!cameraStream || !cameraVideo.videoWidth) return;

    cameraCanvas.width = cameraVideo.videoWidth;
    cameraCanvas.height = cameraVideo.videoHeight;
    cameraCanvas.getContext('2d').drawImage(cameraVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);

    cameraCanvas.toBlob((blob) => {
        if (!blob) return;

        const file = new File([blob], `soil-photo-${Date.now()}.jpg`, { type: 'image/jpeg' });
        closeCamera();

        selectedFile = file;
        imagePreview.src = URL.createObjectURL(file);
        imagePreviewContainer.classList.remove('hidden');
        analyzeSelectedImage();
    }, 'image/jpeg', 0.92);
}

// Camera option before the chat input: take/select a photo and analyze immediately.
chatCameraBtn.addEventListener('click', () => {
    if (useNativeCamera) {
        chatImageInput.click();
    } else {
        openCamera();
    }
});
cameraCaptureBtn.addEventListener('click', capturePhoto);
cameraUploadBtn.addEventListener('click', () => { closeCamera(); chatImageInput.click(); });
cameraCloseBtn.addEventListener('click', closeCamera);
cameraModal.addEventListener('click', (event) => {
    if (event.target === cameraModal) closeCamera();
});
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !cameraModal.classList.contains('hidden')) closeCamera();
});
window.addEventListener('pagehide', closeCamera);

chatImageInput.addEventListener('change', (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    selectedFile = file;
    imagePreview.src = URL.createObjectURL(file);
    imagePreviewContainer.classList.remove('hidden');
    analyzeSelectedImage();
    chatImageInput.value = '';
});

// Generate a card for the monthly planting calendar
function renderPlantingCard(data) {
    const crops = data.crops || [];
    const tl = data.language === 'tl';
    const cropsHtml = renderCropGrid(
        crops,
        tl ? 'Wala pang nakalista na pananim para sa buwang ito.' : 'No crops are listed for this month yet.',
        data.language,
    );

    return `
        <div class="space-y-3">
            <div class="flex items-center justify-between gap-2 flex-wrap border-b border-slate-100 pb-2 dark:border-slate-800">
                <span class="font-bold text-base text-slate-900 dark:text-white">${tl ? 'Ano ang Itatanim sa' : 'What to Plant in'} ${data.month_name}</span>
                <span class="bg-emerald-100 text-emerald-800 text-xs px-2.5 py-1 rounded-full font-semibold dark:bg-emerald-900/60 dark:text-emerald-200">${data.season}</span>
            </div>

            ${data.filtered_by_soil ? `<p class="text-xs text-slate-500 dark:text-slate-400">${tl ? 'Nasala para sa iyong' : 'Filtered for your'} <strong>${data.soil_type}</strong>.</p>` : ''}
            ${data.note ? `<p class="text-xs text-amber-700 bg-amber-50 border border-amber-200 p-2 rounded-lg dark:text-amber-200 dark:bg-amber-950/40 dark:border-amber-900">${data.note}</p>` : ''}

            <div class="flex items-center justify-between gap-2 flex-wrap mb-2">
                <span class="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">${tl ? 'Mga inirerekomendang pananim' : 'Recommended crops'}</span>
                <span class="text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-full dark:text-emerald-300 dark:bg-emerald-900/40 dark:border-emerald-800">
                    ${crops.length} ${tl ? 'na opsyon' : 'options'}
                </span>
            </div>
            ${cropsHtml}

            <div class="bg-amber-50 border border-amber-200/80 p-3 rounded-xl text-xs text-amber-900 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-200">
                <strong class="font-bold block mb-1">${tl ? 'Tip para sa season:' : 'Season Tip:'}</strong>
                ${data.season_tip}
            </div>
        </div>
    `;
}

// Monthly planting calendar (shared by the sidebar button and the chip)
async function askPlantNow() {
    closeSidebar();
    const tl = chatLanguage === 'tl';
    appendMessage('user', tl ? 'Ano ang puwedeng itanim ngayong buwan?' : 'What can I plant this month?');

    try {
        const params = new URLSearchParams();
        if (lastSoilType) params.set('soil', lastSoilType);
        params.set('lang', chatLanguage);
        const res = await fetch('/api/plant-now?' + params.toString());
        const data = await res.json();

        if (!res.ok || data.error) {
            const message = data.error || (tl
                ? 'Hindi ma-load ang planting calendar.'
                : 'Could not load the planting calendar.');
            appendMessage('bot', `<strong>${tl ? 'Error sa server' : 'Server Error'}:</strong> ${message}`, true);
            return;
        }

        appendMessage('bot', renderPlantingCard(data), true);
    } catch (err) {
        appendMessage('bot', tl
            ? `Hindi ma-load ang planting calendar: ${err.message}`
            : `Failed to load the planting calendar: ${err.message}`);
    }
}

plantNowBtn.addEventListener('click', askPlantNow);

// ------------------------- MOBILE SIDEBAR DRAWER -------------------------
const sidebarEl = document.getElementById('sidebar');
const sidebarBackdrop = document.getElementById('sidebarBackdrop');
const sidebarOpenBtn = document.getElementById('sidebarOpenBtn');
const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');

function isMobileLayout() {
    return window.matchMedia('(max-width: 767.98px)').matches;
}

function openSidebar() {
    if (!isMobileLayout()) return;
    sidebarEl.classList.remove('-translate-x-full');
    sidebarEl.classList.add('translate-x-0');
    sidebarBackdrop.classList.remove('hidden');
    sidebarOpenBtn.setAttribute('aria-expanded', 'true');
}

function closeSidebar() {
    if (!isMobileLayout()) return;
    sidebarEl.classList.add('-translate-x-full');
    sidebarEl.classList.remove('translate-x-0');
    sidebarBackdrop.classList.add('hidden');
    sidebarOpenBtn.setAttribute('aria-expanded', 'false');
}

sidebarOpenBtn.addEventListener('click', openSidebar);
sidebarCloseBtn.addEventListener('click', closeSidebar);
sidebarBackdrop.addEventListener('click', closeSidebar);

// Start a fresh conversation: clear the feed back to the welcome bubble and
// rotate the session id so earlier soil/context does not carry over.
function startNewChat() {
    SESSION_ID = createSessionId();
    localStorage.setItem('soilmate_session', SESSION_ID);
    CONVERSATION_ID = createSessionId();
    localStorage.setItem(CONVERSATION_KEY, CONVERSATION_ID);
    lastSoilType = null;
    clearImageSelection(); // <--- ADD THIS LINE
    resetFeed();
    highlightActiveConversation();
    userInput.value = '';
    closeSidebar();
    userInput.focus();
}

if (newChatBtn) {
    newChatBtn.addEventListener('click', startNewChat);
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeSidebar();
});

// Returning to desktop must never leave the drawer in a half-open state.
window.addEventListener('resize', () => {
    if (isMobileLayout()) return;
    sidebarEl.classList.add('-translate-x-full');
    sidebarEl.classList.remove('translate-x-0');
    sidebarBackdrop.classList.add('hidden');
    sidebarOpenBtn.setAttribute('aria-expanded', 'false');
});

// ------------------------- QUICK SUGGESTION CHIPS -------------------------
const QUICK_PROMPTS = {
    en: [
        { label: 'What can I plant this month?', action: 'plant' },
        { label: 'How do I test pH?', text: 'How do I test soil pH?' },
        { label: 'How to make compost?', text: 'How do I make compost?' },
        { label: 'Best organic fertilizer?', text: 'What organic fertilizer is best for sandy soil in the Philippines?' },
        { label: 'Watering schedule', text: 'How often should I water my plants?' },
    ],
    tl: [
        { label: 'Ano ang puwedeng itanim ngayong buwan?', action: 'plant' },
        { label: 'Paano i-test ang pH?', text: 'Paano ko susuriin ang pH ng lupa?' },
        { label: 'Paano gumawa ng compost?', text: 'Paano gumawa ng compost?' },
        { label: 'Best organic fertilizer?', text: 'Ano ang pinakamagandang organic fertilizer para sa buhangin na lupa sa Pilipinas?' },
        { label: 'Iskedyul ng pagdidilig', text: 'Gaano kadalas akong magdidilig ng halaman?' },
    ],
};

const UI_TEXT = {
    en: {
        welcomeTitle: "Mabuhay! I'm SoilMate.",
        welcomeText: "Your AI agriculture assistant for Philippine soil and crops. Ask me a question, explore this month's planting guide, or upload a soil photo for analysis.",
        inputPlaceholder: 'Ask anything about soil or crops...',
        plantNow: 'What can I plant now?',
        photo: 'Photo',
        send: 'Send',
        switchLabel: 'Switch to Filipino',
    },
    tl: {
        welcomeTitle: 'Mabuhay! Ako si SoilMate.',
        welcomeText: 'Ang iyong AI agriculture assistant para sa lupa at pananim sa Pilipinas. Magtanong, tingnan ang planting guide ngayong buwan, o mag-upload ng larawan ng lupa para masuri.',
        inputPlaceholder: 'Magtanong tungkol sa lupa o pananim...',
        plantNow: 'Ano ang puwedeng itanim ngayon?',
        photo: 'Larawan',
        send: 'Ipadala',
        switchLabel: 'Switch to English',
    },
};

function renderQuickPrompts() {
    const wrap = document.getElementById('suggestionChips');
    if (!wrap) return;

    wrap.innerHTML = '';
    QUICK_PROMPTS[chatLanguage].forEach(prompt => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'text-xs md:text-sm whitespace-nowrap flex-shrink-0 bg-slate-100 hover:bg-emerald-50 border border-slate-200 hover:border-emerald-300 text-slate-700 hover:text-emerald-800 px-3 py-1.5 rounded-full transition dark:bg-slate-800 dark:hover:bg-emerald-900/40 dark:border-slate-700 dark:hover:border-emerald-700 dark:text-slate-300 dark:hover:text-emerald-200';
        btn.textContent = prompt.label;
        btn.addEventListener('click', () => {
            if (prompt.action === 'plant') askPlantNow();
            else sendMessage(prompt.text);
        });
        wrap.appendChild(btn);
    });
}

function applyLanguage() {
    const text = UI_TEXT[chatLanguage];
    document.documentElement.lang = chatLanguage === 'tl' ? 'fil' : 'en';

    if (langToggleBtn) {
        langToggleBtn.textContent = chatLanguage === 'tl' ? 'TL' : 'EN';
        langToggleBtn.setAttribute('aria-label', text.switchLabel);
        langToggleBtn.title = text.switchLabel;
    }
    if (welcomeTitle) welcomeTitle.textContent = text.welcomeTitle;
    if (welcomeText) welcomeText.textContent = text.welcomeText;
    if (userInput) userInput.placeholder = text.inputPlaceholder;
    if (plantNowBtn) plantNowBtn.textContent = text.plantNow;
    if (photoBtnLabel) photoBtnLabel.textContent = text.photo;
    if (sendBtnLabel) sendBtnLabel.textContent = text.send;

    renderQuickPrompts();
}

if (langToggleBtn) {
    langToggleBtn.addEventListener('click', () => {
        chatLanguage = chatLanguage === 'tl' ? 'en' : 'tl';
        localStorage.setItem(LANG_KEY, chatLanguage);
        applyLanguage();
    });
}

applyLanguage();

// ------------------------- SCAN & CHAT HISTORY -------------------------
const scanHistoryEl = document.getElementById('scanHistory');
const clearHistoryBtn = document.getElementById('clearHistoryBtn');

// Whether the signed-in account has at least one saved chat message.
let hasSavedChats = false;

function setClearHistoryVisible(visible) {
    if (!clearHistoryBtn) return;
    clearHistoryBtn.classList.toggle('hidden', !visible);
    clearHistoryBtn.classList.toggle('inline-flex', visible);
}

function renderScanHistory(scans, hasChats = hasSavedChats) {
    const hasScans = !!(scans && scans.length);
    setClearHistoryVisible(hasScans || hasChats);

    if (!hasScans) {
        scanHistoryEl.innerHTML = '<p class="text-xs text-emerald-400">No scans yet.</p>';
        return;
    }

    scanHistoryEl.innerHTML = scans.map(s => {
        const label = escapeHtml(s.identified ? s.predicted_soil : 'Unidentified');
        const pct = Math.round((s.confidence || 0) * 100);
        const date = new Date(s.created_at).toLocaleDateString();
        return `
            <div class="scan-item relative" data-scan-id="${s.id}">
                <button type="button"
                        class="scan-open w-full flex items-center gap-2 bg-emerald-800/60 hover:bg-emerald-800 rounded-lg p-2 pr-9 text-left transition"
                        data-scan-id="${s.id}">
                    <img src="/static/uploads/${encodeURIComponent(s.filename)}" alt=""
                         class="w-10 h-10 object-cover rounded flex-shrink-0">
                    <span class="flex-1 min-w-0">
                        <span class="block text-xs font-semibold text-white truncate">${label}</span>
                        <span class="block text-[11px] text-emerald-300">${pct}% • ${date}</span>
                    </span>
                </button>
                <button type="button"
                        class="scan-menu-btn absolute top-1.5 right-1.5 p-1 rounded-md text-emerald-200/70 hover:text-white hover:bg-white/15 transition"
                        data-scan-menu="${s.id}" aria-label="Options for this scan"
                        aria-haspopup="true" aria-expanded="false">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <circle cx="12" cy="5" r="1.7"/>
                        <circle cx="12" cy="12" r="1.7"/>
                        <circle cx="12" cy="19" r="1.7"/>
                    </svg>
                </button>
                <div class="scan-menu hidden absolute right-1.5 top-8 z-20 w-36 rounded-lg bg-white border border-slate-200 shadow-lg py-1"
                     data-scan-menu-panel="${s.id}">
                    <button type="button"
                            class="w-full text-left px-3 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 transition"
                            data-delete-scan="${s.id}">
                        Delete scan
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

// ------------------------- CONVERSATION HISTORY RENDERING -------------------------
function highlightActiveConversation() {
    if (!chatHistoryEl) return;
    chatHistoryEl.querySelectorAll('.chat-convo-item').forEach(item => {
        const isActive = item.dataset.convoId === CONVERSATION_ID;
        item.classList.toggle('bg-emerald-800', isActive);
        item.classList.toggle('bg-emerald-900/40', !isActive);
    });
}

const clearChatsBtn = document.getElementById('clearChatsBtn');

function setClearChatsVisible(visible) {
    if (!clearChatsBtn) return;
    clearChatsBtn.classList.toggle('hidden', !visible);
    clearChatsBtn.classList.toggle('inline-flex', visible);
}

function renderConversations(conversations) {
    if (!chatHistoryEl) return;

    const hasConvos = !!(conversations && conversations.length);
    setClearChatsVisible(hasConvos);

    if (!hasConvos) {
        chatHistoryEl.innerHTML = '<p class="text-xs text-emerald-400">No conversations yet.</p>';
        return;
    }

    chatHistoryEl.innerHTML = conversations.map(c => {
        const title = escapeHtml(c.title || 'Chat conversation');
        const count = c.message_count || 0;
        const convoId = escapeHtml(c.conversation_id);
        const isActive = c.conversation_id === CONVERSATION_ID;

        return `
            <div class="chat-convo-item relative rounded-lg transition mb-1.5 ${isActive ? 'bg-emerald-800' : 'bg-emerald-900/40 hover:bg-emerald-800/70'}" data-convo-id="${convoId}">
                <button type="button" class="convo-open w-full text-left p-2.5 pr-8 flex flex-col gap-0.5" data-convo-id="${convoId}">
                    <span class="text-xs font-semibold text-white truncate block">${title}</span>
                    <span class="text-[10px] text-emerald-300 block">${count} messages</span>
                </button>
                <button type="button"
                        class="convo-menu-btn absolute top-2 right-1.5 p-1 rounded-md text-emerald-200/70 hover:text-white hover:bg-white/15 transition"
                        data-convo-menu="${convoId}" aria-label="Options for this conversation"
                        aria-haspopup="true" aria-expanded="false">
                    <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <circle cx="12" cy="5" r="1.7"/>
                        <circle cx="12" cy="12" r="1.7"/>
                        <circle cx="12" cy="19" r="1.7"/>
                    </svg>
                </button>
                <div class="convo-menu hidden absolute right-1.5 top-8 z-20 w-40 rounded-lg bg-white border border-slate-200 shadow-lg py-1 dark:bg-slate-900 dark:border-slate-700"
                     data-convo-menu-panel="${convoId}">
                    <button type="button"
                            class="w-full text-left px-3 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 transition dark:text-rose-400 dark:hover:bg-slate-800"
                            data-delete-convo="${convoId}">
                        Delete conversation
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function closeConvoMenus() {
    if (!chatHistoryEl) return;
    chatHistoryEl.querySelectorAll('[data-convo-menu-panel]').forEach(panel => {
        panel.classList.add('hidden');
    });
    chatHistoryEl.querySelectorAll('[data-convo-menu]').forEach(btn => {
        btn.setAttribute('aria-expanded', 'false');
    });
}

// Conversation menu & clicks
if (chatHistoryEl) {
    chatHistoryEl.addEventListener('click', (event) => {
        const menuBtn = event.target.closest('[data-convo-menu]');
        if (menuBtn) {
            const id = menuBtn.dataset.convoMenu;
            const panel = chatHistoryEl.querySelector(`[data-convo-menu-panel="${id}"]`);
            const willOpen = !!panel && panel.classList.contains('hidden');
            closeConvoMenus();
            if (willOpen) {
                panel.classList.remove('hidden');
                menuBtn.setAttribute('aria-expanded', 'true');
            }
            return;
        }

        const deleteBtn = event.target.closest('[data-delete-convo]');
        if (deleteBtn) {
            closeConvoMenus();
            deleteSingleConversation(deleteBtn.dataset.deleteConvo);
            return;
        }

        const openBtn = event.target.closest('.convo-open');
        if (openBtn) {
            closeConvoMenus();
            openConversation(openBtn.dataset.convoId);
        }
    });
}

document.addEventListener('click', (event) => {
    if (chatHistoryEl && !chatHistoryEl.contains(event.target)) closeConvoMenus();
});

// Delete single conversation
async function deleteSingleConversation(convoId) {
    const confirmed = window.confirm('Delete this conversation?\n\nThis cannot be undone.');
    if (!confirmed) return;

    try {
        const res = await fetch(`/api/conversations/${encodeURIComponent(convoId)}`, { method: 'DELETE' });
        const data = await res.json();

        if (!res.ok || !data.deleted) {
            appendMessage('bot', `<strong>Could not delete conversation:</strong> ${data.error || 'Please try again.'}`, true);
            return;
        }

        // If currently open conversation was deleted, start fresh
        if (CONVERSATION_ID === convoId) {
            startNewChat();
        }

        const hist = await fetchHistory();
        if (hist && hist.conversations) renderConversations(hist.conversations);
    } catch (err) {
        appendMessage('bot', `Failed to delete conversation: ${err.message}`);
    }
}

// Clear all conversations
if (clearChatsBtn) {
    clearChatsBtn.addEventListener('click', async () => {
        const confirmed = window.confirm('Delete all your saved conversations?\n\nThis cannot be undone.');
        if (!confirmed) return;

        clearChatsBtn.disabled = true;
        try {
            const res = await fetch('/api/chats', { method: 'DELETE' });
            const data = await res.json();

            if (!res.ok || !data.deleted) {
                appendMessage('bot', `<strong>Could not clear chats:</strong> ${data.error || 'Please try again.'}`, true);
                return;
            }

            startNewChat();
            renderConversations([]);
        } catch (err) {
            appendMessage('bot', `Failed to clear chats: ${err.message}`);
        } finally {
            clearChatsBtn.disabled = false;
        }
    });
}

async function openConversation(convoId) {
    closeSidebar();
    try {
        const res = await fetch(`/api/conversations/${encodeURIComponent(convoId)}`);
        const data = await res.json();

        if (!res.ok || data.error) {
            console.error('Could not load conversation:', data.error);
            return;
        }

        CONVERSATION_ID = convoId;
        localStorage.setItem(CONVERSATION_KEY, convoId);
        highlightActiveConversation();

        resetFeed();
        (data.messages || []).forEach(m => {
            appendMessage(m.role === 'user' ? 'user' : 'bot', m.message);
        });
    } catch (err) {
        console.error('Failed to open conversation:', err);
    }
}

function closeScanMenus() {
    scanHistoryEl.querySelectorAll('[data-scan-menu-panel]').forEach(panel => {
        panel.classList.add('hidden');
    });
    scanHistoryEl.querySelectorAll('[data-scan-menu]').forEach(btn => {
        btn.setAttribute('aria-expanded', 'false');
    });
}

scanHistoryEl.addEventListener('click', (event) => {
    const menuBtn = event.target.closest('[data-scan-menu]');
    if (menuBtn) {
        const id = menuBtn.dataset.scanMenu;
        const panel = scanHistoryEl.querySelector(`[data-scan-menu-panel="${id}"]`);
        const willOpen = !!panel && panel.classList.contains('hidden');
        closeScanMenus();
        if (willOpen) {
            panel.classList.remove('hidden');
            menuBtn.setAttribute('aria-expanded', 'true');
        }
        return;
    }

    const deleteBtn = event.target.closest('[data-delete-scan]');
    if (deleteBtn) {
        closeScanMenus();
        deleteSingleScan(deleteBtn.dataset.deleteScan);
        return;
    }

    const openBtn = event.target.closest('.scan-open');
    if (openBtn) {
        closeScanMenus();
        openScan(openBtn.dataset.scanId);
    }
});

// Any click elsewhere, or Escape, dismisses an open row menu.
document.addEventListener('click', (event) => {
    if (!scanHistoryEl.contains(event.target)) closeScanMenus();
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeScanMenus();
});

function renderHistoryLoginPrompt() {
    setClearHistoryVisible(false);
    scanHistoryEl.innerHTML = `
        <div class="rounded-xl border border-dashed border-white/15 py-4 px-3 text-center space-y-2">
            <p class="text-xs text-emerald-100/60">Log in to save your scan and chat history.</p>
            <button id="historyLoginBtn" type="button"
                    class="bg-white/12 hover:bg-white/20 border border-white/15 text-white font-semibold text-xs py-1.5 px-3 rounded-lg transition">
                Log in
            </button>
        </div>
    `;

    const historyLoginBtn = document.getElementById('historyLoginBtn');
    if (historyLoginBtn) {
        historyLoginBtn.addEventListener('click', () => {
            localStorage.removeItem(GUEST_KEY);
            showGate('login');
        });
    }
}

async function openScan(scanId) {
    closeSidebar();
    try {
        const res = await fetch(`/api/scans/${scanId}`);
        const data = await res.json();

        if (res.status === 401) {
            renderHistoryLoginPrompt();
            showGate('login');
            appendMessage('bot', 'Please log in to view saved scans.', true);
            return;
        }

        if (!res.ok || data.error) {
            appendMessage('bot', `<strong>Could not open scan:</strong> ${data.error || 'Unknown error'}`, true);
            return;
        }

        // 1. Clean the feed so previous chats don't linger
        resetFeed();

        // 2. Display the saved photo if available
        if (data.filename) {
            const photoHtml = `
                <div class="space-y-1.5">
                    <img src="/static/uploads/${encodeURIComponent(data.filename)}" alt="Saved scan photo"
                         class="w-48 sm:w-64 h-36 sm:h-48 object-cover rounded-xl shadow-md border border-white/20">
                    <p class="text-[11px] text-emerald-100/90 font-semibold">📷 Saved soil sample</p>
                </div>
            `;
            appendMessage('user', photoHtml, true);
        }

        // 3. Render the specific result card
        if (data.identified === false) {
            const pct = ((data.confidence || 0) * 100).toFixed(1);
            appendMessage('bot', `<strong>Previous scan could not be identified.</strong><br>${data.message}<br><span class="text-xs text-slate-400">Confidence: ${pct}%</span>`, true);
            return;
        }

        lastSoilType = data.soil_type;
        appendMessage('bot', renderSoilAnalysisCard(data), true);
    } catch (err) {
        appendMessage('bot', `Failed to open scan: ${err.message}`);
    }
}

async function deleteSingleScan(scanId) {
    const confirmed = window.confirm(
        'Delete this scan from your history?\n\nThis cannot be undone.'
    );
    if (!confirmed) return;

    try {
        const res = await fetch(`/api/scans/${scanId}`, { method: 'DELETE' });
        let data = {};
        try { data = await res.json(); } catch (err) { /* empty body */ }

        if (res.status === 401) {
            renderHistoryLoginPrompt();
            showGate('login');
            return;
        }

        if (!res.ok || !data.deleted) {
            appendMessage('bot', `<strong>Could not delete scan:</strong> ${data.error || 'Please try again.'}`, true);
            return;
        }

        await refreshScans();
        appendMessage('bot', 'That scan has been removed from your history.');
    } catch (err) {
        appendMessage('bot', `Failed to delete scan: ${err.message}`);
    }
}

async function clearHistory() {
    const confirmed = window.confirm(
        'Delete all your saved scans and chat history?\n\nThis cannot be undone.'
    );
    if (!confirmed) return;

    clearHistoryBtn.disabled = true;
    try {
        const res = await fetch('/api/history', { method: 'DELETE' });
        let data = {};
        try { data = await res.json(); } catch (err) { /* empty body */ }

        if (res.status === 401) {
            renderHistoryLoginPrompt();
            showGate('login');
            return;
        }

        if (!res.ok || !data.deleted) {
            appendMessage('bot', `<strong>Could not clear history:</strong> ${data.error || 'Please try again.'}`, true);
            return;
        }

        hasSavedChats = false;
        lastSoilType = null;
        resetFeed();
        renderScanHistory([]);
        renderConversations([]);
    } catch (err) {
        appendMessage('bot', `Failed to clear history: ${err.message}`);
    } finally {
        clearHistoryBtn.disabled = false;
    }
}

if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener('click', clearHistory);
}

async function fetchHistory() {
    try {
        const res = await fetch(`/api/history?session_id=${SESSION_ID}`);
        if (!res.ok) return null;
        return await res.json();
    } catch (err) {
        console.error('Could not load history:', err);
        return null;
    }
}

async function refreshScans() {
    const data = await fetchHistory();
    if (!data) return;
    if (data.requires_login) {
        renderHistoryLoginPrompt();
        return;
    }
    renderScanHistory(data.scans);
}

async function loadHistory() {
    const data = await fetchHistory();
    if (!data) return;

    if (data.requires_login) {
        renderHistoryLoginPrompt();
        return;
    }

    hasSavedChats = !!(data.chats && data.chats.length);
    renderScanHistory(data.scans, hasSavedChats);
    renderConversations(data.conversations);

    // If an active conversation exists in localStorage, open only THAT conversation
    const activeConvoId = localStorage.getItem(CONVERSATION_KEY);
    if (activeConvoId && data.conversations && data.conversations.some(c => c.conversation_id === activeConvoId)) {
        await openConversation(activeConvoId);
    } else if (data.conversations && data.conversations.length > 0) {
        // Otherwise open the newest conversation
        await openConversation(data.conversations[0].conversation_id);
    } else {
        resetFeed();
    }
}
// ------------------------- ACCOUNT -------------------------
const authGate = document.getElementById('authGate');
const authForm = document.getElementById('authForm');
const tabLogin = document.getElementById('tabLogin');
const tabRegister = document.getElementById('tabRegister');
const gateLoginFields = document.getElementById('gateLoginFields');
const gateRegisterFields = document.getElementById('gateRegisterFields');
const gateIdentifier = document.getElementById('gateIdentifier');
const gateUsername = document.getElementById('gateUsername');
const gateEmail = document.getElementById('gateEmail');
const gatePassword = document.getElementById('gatePassword');
const gateMessage = document.getElementById('gateMessage');
const gateSubmit = document.getElementById('gateSubmit');
const guestBtn = document.getElementById('guestBtn');
const headerLoginBtn = document.getElementById('headerLoginBtn');
const headerLogoutBtn = document.getElementById('headerLogoutBtn');
const accountAvatar = document.getElementById('accountAvatar');
const accountName = document.getElementById('accountName');
const accountState = document.getElementById('accountState');
const accountBtn = document.getElementById('accountBtn');
const profileModal = document.getElementById('profileModal');
const profileForm = document.getElementById('profileForm');
const profileAvatarPreview = document.getElementById('profileAvatarPreview');
const profileAvatarInput = document.getElementById('profileAvatarInput');
const profileAvatarBtn = document.getElementById('profileAvatarBtn');
const profileAvatarRemoveBtn = document.getElementById('profileAvatarRemoveBtn');
const profileUsername = document.getElementById('profileUsername');
const profileEmail = document.getElementById('profileEmail');
const profileMessage = document.getElementById('profileMessage');
const profileSaveBtn = document.getElementById('profileSaveBtn');
const profileCloseBtn = document.getElementById('profileCloseBtn');
const profileCancelBtn = document.getElementById('profileCancelBtn');

const GUEST_KEY = 'soilmate_guest';
const TAB_ACTIVE = 'flex-1 text-sm font-semibold py-2 rounded-lg transition bg-white text-emerald-800 shadow-xs dark:bg-slate-700 dark:text-emerald-200';
const TAB_INACTIVE = 'flex-1 text-sm font-semibold py-2 rounded-lg transition text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200';

let authMode = 'login';

function setGateMessage(text, isError = true) {
    gateMessage.textContent = text || '';
    gateMessage.className = text
        ? (isError ? 'text-xs text-rose-600 min-h-[1rem] dark:text-rose-400' : 'text-xs text-emerald-700 min-h-[1rem] dark:text-emerald-300')
        : 'text-xs text-rose-600 min-h-[1rem] dark:text-rose-400';
}

function setAuthMode(mode) {
    authMode = mode === 'register' ? 'register' : 'login';
    const isRegister = authMode === 'register';

    tabLogin.className = isRegister ? TAB_INACTIVE : TAB_ACTIVE;
    tabRegister.className = isRegister ? TAB_ACTIVE : TAB_INACTIVE;
    gateLoginFields.classList.toggle('hidden', isRegister);
    gateRegisterFields.classList.toggle('hidden', !isRegister);
    gateSubmit.textContent = isRegister ? 'Create account' : 'Log in';
    gatePassword.setAttribute('autocomplete', isRegister ? 'new-password' : 'current-password');

    setGateMessage('');
}

function showGate(mode) {
    setAuthMode(mode || 'login');
    authGate.classList.remove('hidden');
    (authMode === 'register' ? gateUsername : gateIdentifier).focus();
}

function hideGate() {
    authGate.classList.add('hidden');
}

// Signed-in state lives in the chat header only, never in the sidebar.
let isAuthenticatedUser = false;

// Avatar currently shown for the account (null means "use the initial").
let currentAvatarUrl = null;
let pendingAvatarFile = null;
let pendingAvatarPreviewUrl = null;
let avatarRemovalRequested = false;

const AVATAR_AUTH_CLASS = 'w-9 h-9 rounded-full overflow-hidden bg-emerald-700 text-white flex items-center justify-center font-bold text-sm dark:bg-emerald-600';
const AVATAR_GUEST_CLASS = 'w-9 h-9 rounded-full overflow-hidden bg-emerald-100 text-emerald-800 border border-emerald-200/70 flex items-center justify-center font-bold text-sm dark:bg-emerald-900 dark:text-emerald-300 dark:border-emerald-800';

function renderAvatarInto(element, avatarUrl, name) {
    if (avatarUrl) {
        element.innerHTML = `<img src="${escapeHtml(avatarUrl)}" alt="" class="w-full h-full object-cover">`;
    } else {
        element.textContent = (name || '?').charAt(0).toUpperCase();
    }
}

function updateAccountUI(authenticated, username, avatar) {
    isAuthenticatedUser = !!authenticated;
    currentAvatarUrl = avatar || null;
    if (authenticated) {
        const name = username || '';
        accountName.textContent = name;
        accountAvatar.className = AVATAR_AUTH_CLASS;
        renderAvatarInto(accountAvatar, currentAvatarUrl, name);
        accountState.textContent = 'Signed in';
        headerLoginBtn.classList.add('hidden');
        headerLogoutBtn.classList.remove('hidden');
    } else {
        accountName.textContent = 'Guest';
        accountAvatar.className = AVATAR_GUEST_CLASS;
        renderAvatarInto(accountAvatar, null, 'Guest');
        accountState.textContent = 'Not signed in';
        headerLoginBtn.classList.remove('hidden');
        headerLogoutBtn.classList.add('hidden');
    }
}

// ------------------------- EDIT PROFILE -------------------------
function setProfileMessage(text, isError = true) {
    profileMessage.textContent = text || '';
    profileMessage.className = text
        ? (isError
            ? 'text-xs text-rose-600 min-h-[1rem] dark:text-rose-400'
            : 'text-xs text-emerald-700 min-h-[1rem] dark:text-emerald-300')
        : 'text-xs text-rose-600 min-h-[1rem] dark:text-rose-400';
}

function renderProfileAvatar() {
    let url = currentAvatarUrl;
    if (pendingAvatarFile) {
        url = pendingAvatarPreviewUrl;
    } else if (avatarRemovalRequested) {
        url = null;
    }
    renderAvatarInto(profileAvatarPreview, url, profileUsername.value.trim());
}

function closeProfile() {
    profileModal.classList.add('hidden');
    if (pendingAvatarPreviewUrl) {
        URL.revokeObjectURL(pendingAvatarPreviewUrl);
        pendingAvatarPreviewUrl = null;
    }
    pendingAvatarFile = null;
    avatarRemovalRequested = false;
    profileAvatarInput.value = '';
}

async function openProfile() {
    if (!isAuthenticatedUser) {
        showGate('login');
        return;
    }

    pendingAvatarFile = null;
    avatarRemovalRequested = false;
    profileAvatarInput.value = '';
    setProfileMessage('');

    profileModal.classList.remove('hidden');
    profileUsername.value = accountName.textContent === 'Guest' ? '' : accountName.textContent;
    profileEmail.value = '';
    renderProfileAvatar();

    try {
        const res = await fetch('/api/profile');
        const data = await res.json();
        if (!res.ok) {
            setProfileMessage(data.error || 'Could not load your profile.');
            return;
        }
        profileUsername.value = data.username || '';
        profileEmail.value = data.email || '';
        currentAvatarUrl = data.avatar || null;
        renderProfileAvatar();
    } catch (err) {
        setProfileMessage('Could not reach the server. Please try again.');
    }
}

profileForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const username = profileUsername.value.trim();
    const email = profileEmail.value.trim();
    if (!username || !email) {
        setProfileMessage('Username and email are required.');
        return;
    }

    const formData = new FormData();
    formData.append('username', username);
    formData.append('email', email);
    if (pendingAvatarFile) formData.append('avatar', pendingAvatarFile);
    if (avatarRemovalRequested) formData.append('remove_avatar', '1');

    profileSaveBtn.disabled = true;
    setProfileMessage('Saving...', false);

    try {
        const res = await fetch('/api/profile', { method: 'POST', body: formData });
        let data = {};
        try { data = await res.json(); } catch (err) { /* empty body */ }

        if (!res.ok) {
            setProfileMessage(data.error || 'Could not save your profile.');
            return;
        }

        currentAvatarUrl = data.avatar || null;
        updateAccountUI(true, data.username, data.avatar);
        closeProfile();
        appendMessage('bot', `Profile updated. Hello, **${data.username}**!`);
    } catch (err) {
        setProfileMessage('Could not reach the server. Please try again.');
    } finally {
        profileSaveBtn.disabled = false;
    }
});

profileAvatarBtn.addEventListener('click', () => profileAvatarInput.click());

profileAvatarInput.addEventListener('change', (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        setProfileMessage('Please choose an image file.');
        profileAvatarInput.value = '';
        return;
    }
    if (file.size > 6 * 1024 * 1024) {
        setProfileMessage('Avatar image must be smaller than 6 MB.');
        profileAvatarInput.value = '';
        return;
    }

    if (pendingAvatarPreviewUrl) URL.revokeObjectURL(pendingAvatarPreviewUrl);
    pendingAvatarFile = file;
    pendingAvatarPreviewUrl = URL.createObjectURL(file);
    avatarRemovalRequested = false;
    setProfileMessage('');
    renderProfileAvatar();
    profileAvatarInput.value = '';
});

profileAvatarRemoveBtn.addEventListener('click', () => {
    pendingAvatarFile = null;
    if (pendingAvatarPreviewUrl) {
        URL.revokeObjectURL(pendingAvatarPreviewUrl);
        pendingAvatarPreviewUrl = null;
    }
    avatarRemovalRequested = true;
    setProfileMessage('');
    renderProfileAvatar();
});

accountBtn.addEventListener('click', openProfile);
profileCloseBtn.addEventListener('click', closeProfile);
profileCancelBtn.addEventListener('click', closeProfile);
profileUsername.addEventListener('input', renderProfileAvatar);
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !profileModal.classList.contains('hidden')) closeProfile();
});

async function postJson(url, payload) {
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {})
    });
    let data = {};
    try { data = await res.json(); } catch (err) { /* empty body */ }
    return { res, data };
}

// Keep the welcome bubble, drop everything else, then replay from the server.
function resetFeed() {
    while (chatFeed.children.length > 1) {
        chatFeed.removeChild(chatFeed.lastChild);
    }
}

async function refreshAfterAuth() {
    resetFeed();
    await loadHistory();
}

async function submitAuth() {
    const password = gatePassword.value;
    let url, payload;

    if (authMode === 'login') {
        const identifier = gateIdentifier.value.trim();
        if (!identifier || !password) {
            setGateMessage('Enter your username or email and password.');
            return;
        }
        url = '/api/login';
        payload = { username: identifier, password };
    } else {
        const username = gateUsername.value.trim();
        const email = gateEmail.value.trim();
        if (!username || !email || !password) {
            setGateMessage('Username, email, and password are all required.');
            return;
        }
        url = '/api/register';
        payload = { username, email, password };
    }

    gateSubmit.disabled = true;
    try {
        const { res, data } = await postJson(url, payload);
        if (!res.ok) {
            setGateMessage(data.error || 'Something went wrong. Please try again.');
            return;
        }
        await onAuthSuccess(data);
    } catch (err) {
        setGateMessage('Could not reach the server. Please try again.');
    } finally {
        gateSubmit.disabled = false;
    }
}

async function onAuthSuccess(data) {
    localStorage.removeItem(GUEST_KEY);
    gateIdentifier.value = '';
    gateUsername.value = '';
    gateEmail.value = '';
    gatePassword.value = '';
    hideGate();
    clearImageSelection(); // <--- ADD THIS LINE
    updateAccountUI(true, data.username, data.avatar);
    await refreshAfterAuth();
    appendMessage('bot', `Welcome, **${data.username}**! Your scans and chats are saved to this account.`);
}

async function continueAsGuest() {
    localStorage.setItem(GUEST_KEY, '1');
    hideGate();
    updateAccountUI(false);
    await refreshAfterAuth();
}

async function logout() {
    try {
        await postJson('/api/logout', {});
    } catch (err) { /* clear the local view regardless */ }

    localStorage.removeItem(GUEST_KEY);
    updateAccountUI(false);
    resetFeed();
    lastSoilType = null;
    clearImageSelection(); // <--- ADD THIS LINE

    renderHistoryLoginPrompt();
    showGate('login');
}

authForm.addEventListener('submit', (e) => {
    e.preventDefault();
    submitAuth();
});
tabLogin.addEventListener('click', () => setAuthMode('login'));
tabRegister.addEventListener('click', () => setAuthMode('register'));
guestBtn.addEventListener('click', continueAsGuest);
headerLoginBtn.addEventListener('click', () => {
    localStorage.removeItem(GUEST_KEY);
    showGate('login');
});
headerLogoutBtn.addEventListener('click', logout);

// Start: the login panel comes first unless we already know who this is.
(async function init() {
    let authenticated = false;
    let username = null;
    let avatar = null;

    try {
        const res = await fetch('/api/me');
        const data = await res.json();
        authenticated = !!data.authenticated;
        username = data.username;
        avatar = data.avatar;
    } catch (err) {
        console.error('Could not load account:', err);
    }

    updateAccountUI(authenticated, username, avatar);

    if (authenticated || localStorage.getItem(GUEST_KEY) === '1') {
        hideGate();
        // Only load history when user is authenticated or is a guest
        await loadHistory();
    } else {
        showGate('login');
        renderHistoryLoginPrompt();
    }
})();