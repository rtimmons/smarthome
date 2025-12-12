const form = document.getElementById('labelForm');
const disableDefaultFormHandlers = !!(form && form.dataset.disableDefaultHandlers === 'true');
const previewContainer = document.getElementById('previewContainer');
const labelPreviewImage = document.getElementById('labelPreviewImage');
const qrPreviewImage = document.getElementById('qrPreviewImage');
const previewStatus = document.getElementById('livePreviewStatus');
const labelPreviewWarnings = document.getElementById('labelPreviewWarnings');
const qrPreviewWarnings = document.getElementById('qrPreviewWarnings');
const qrCaptionNode = document.getElementById('qrCaption');
const qrPreviewUrlRow = document.getElementById('qrPreviewUrl');
const qrPreviewUrlLink = document.getElementById('qrPreviewUrlLink');
const labelPreviewSummary = document.getElementById('labelPreviewSummary');
const bestByDateValue = document.getElementById('bestByDateValue');
const themeSelect = document.getElementById('themeSelect');

let previewAbortController = null;
let previewTimerId = null;
let lastPreviewPayloadKey = '';
const PREVIEW_DEBOUNCE_MS = 250;
const THEME_STORAGE_KEY = 'printer-theme';
const THEME_OPTIONS = ['light', 'dark', 'system'];

// Countdown functionality
let countdownTimer = null;
let countdownSeconds = 0;
let currentPrintTarget = 'label'; // 'label' or 'qr'
function getCountdownDuration() {
    // Allow override via URL parameter for testing
    const urlParams = new URLSearchParams(window.location.search);
    const testDuration = urlParams.get('countdown_duration');
    return testDuration ? parseInt(testDuration, 10) : 5; // default 5 seconds
}

// Countdown functionality
function checkForPrintParameter() {
    if (URLState.isPrintState()) {
        const target = URLState.isQRMode() ? 'qr' : 'label';
        startCountdown(target);
    }
}

function startCountdown(printTarget = 'label') {
    const countdownContainer = document.getElementById('printCountdownContainer');
    const countdownTimerElement = document.getElementById('countdownTimer');
    const countdownSecondsElement = document.getElementById('countdownSeconds');
    const cancelButton = document.getElementById('cancelCountdown');
    const printNowButton = document.getElementById('printNowButton');

    if (!countdownContainer || !countdownTimerElement || !countdownSecondsElement || !cancelButton || !printNowButton) {
        return;
    }

    currentPrintTarget = printTarget;
    countdownSeconds = getCountdownDuration();
    countdownContainer.style.display = 'block';

    // Show the countdown timer inside the button
    countdownSecondsElement.textContent = countdownSeconds;
    countdownTimerElement.style.display = 'inline';

    // Set up button event listeners (remove any existing ones first)
    cancelButton.removeEventListener('click', cancelCountdown);
    printNowButton.removeEventListener('click', executePrintNow);
    cancelButton.addEventListener('click', cancelCountdown);
    printNowButton.addEventListener('click', executePrintNow);

    // Update preview in countdown dialog
    updateCountdownPreview(printTarget);

    // Start the countdown
    countdownTimer = setInterval(() => {
        countdownSeconds--;
        countdownSecondsElement.textContent = countdownSeconds;

        if (countdownSeconds <= 0) {
            clearInterval(countdownTimer);
            executeCountdownPrint();
        }
    }, 1000);
}

function updateCountdownPreview(printTarget) {
    const previewImage = document.getElementById('countdownPreviewImage');
    const previewTitle = document.getElementById('countdownPreviewTitle');
    const previewStatus = document.getElementById('countdownPreviewStatus');

    if (!previewImage || !previewTitle || !previewStatus) {
        return;
    }

    // Update title based on target
    previewTitle.textContent = printTarget === 'qr' ? 'QR Label Preview' : 'Label Preview';

    // Get the appropriate preview image source from DOM (fresh lookup)
    const sourceImageId = printTarget === 'qr' ? 'qrPreviewImage' : 'labelPreviewImage';
    const sourceImage = document.getElementById(sourceImageId);

    if (sourceImage && sourceImage.src && !sourceImage.hidden && sourceImage.dataset.hasPreview === 'true') {
        // Preview is ready - show it immediately
        previewImage.src = sourceImage.src;
        previewImage.style.display = 'block';
        previewStatus.style.display = 'none';
    } else {
        // Preview not ready - show loading state and try to generate it
        previewImage.style.display = 'none';
        previewStatus.style.display = 'block';
        previewStatus.textContent = 'Generating preview...';

        // Ensure previews are generated
        ensurePreviewsGenerated().then(() => {
            // After generation, try to update preview again
            updateCountdownPreviewImage(printTarget);
        }).catch((error) => {
            console.warn('Preview generation failed:', error);
            previewStatus.textContent = 'Preview unavailable';
        });
    }
}

function updateCountdownPreviewImage(printTarget) {
    const previewImage = document.getElementById('countdownPreviewImage');
    const previewStatus = document.getElementById('countdownPreviewStatus');

    if (!previewImage || !previewStatus) {
        return;
    }

    const sourceImageId = printTarget === 'qr' ? 'qrPreviewImage' : 'labelPreviewImage';
    const sourceImage = document.getElementById(sourceImageId);

    if (sourceImage && sourceImage.src && !sourceImage.hidden && sourceImage.dataset.hasPreview === 'true') {
        previewImage.src = sourceImage.src;
        previewImage.style.display = 'block';
        previewStatus.style.display = 'none';
    } else {
        // Set up a retry mechanism to check for preview availability
        let retryCount = 0;
        const maxRetries = 10;
        const retryInterval = setInterval(() => {
            const updatedSourceImage = document.getElementById(sourceImageId);
            if (updatedSourceImage && updatedSourceImage.src && !updatedSourceImage.hidden && updatedSourceImage.dataset.hasPreview === 'true') {
                previewImage.src = updatedSourceImage.src;
                previewImage.style.display = 'block';
                previewStatus.style.display = 'none';
                clearInterval(retryInterval);
            } else if (++retryCount >= maxRetries) {
                previewStatus.textContent = 'Preview not available';
                clearInterval(retryInterval);
            }
        }, 200);
    }
}

function executePrintNow() {
    // Stop the countdown
    if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
    }

    // Execute the print immediately
    executeCountdownPrint();
}

function cancelCountdown() {
    resetCountdownDialog({ hideCountdown: false });
}

async function executeCountdownPrint() {
    const countdownContainer = document.getElementById('printCountdownContainer');
    const countdownTimerElement = document.getElementById('countdownTimer');
    const printButtonText = document.getElementById('printButtonText');
    const printNowButton = document.getElementById('printNowButton');
    const cancelButton = document.getElementById('cancelCountdown');

    // Update UI to show printing state
    if (countdownTimerElement) {
        countdownTimerElement.style.display = 'none';
    }
    if (printButtonText) {
        printButtonText.textContent = 'Printing...';
    }
    if (printNowButton) {
        printNowButton.disabled = true;
    }

    try {
        // Build the print request URL with current parameters
        const url = new URL(window.location);
        const printUrl = '/bb/execute-print?' + url.searchParams.toString();

        // Execute the print via POST request (no body needed, parameters are in URL)
        const response = await fetch(printUrl, {
            method: 'POST'
        });

        if (!response.ok) {
            let errorMessage = 'Print failed';
            try {
                const result = await response.json();
                errorMessage = result.error || errorMessage;
            } catch (e) {
                // If response is not JSON, use status text
                errorMessage = response.statusText || errorMessage;
            }
            window.alert(errorMessage);
            resetCountdownDialog();
            return;
        }

        const result = await response.json();

        // Print was successful - show success state and keep dialog open for multiple copies
        showPrintSuccess();

    } catch (error) {
        console.error('Print error:', error);
        window.alert('Print failed: ' + error.message);
        resetCountdownDialog();
    }
}

function showPrintSuccess() {
    const countdownTimerElement = document.getElementById('countdownTimer');
    const printButtonText = document.getElementById('printButtonText');
    const printNowButton = document.getElementById('printNowButton');
    const cancelButton = document.getElementById('cancelCountdown');

    // Update UI to show success state
    if (countdownTimerElement) {
        countdownTimerElement.style.display = 'none';
    }
    if (printButtonText) {
        printButtonText.textContent = 'Print Again ✓';
    }
    if (printNowButton) {
        printNowButton.disabled = false;
    }
    if (cancelButton) {
        cancelButton.textContent = 'Done';
    }

    // Auto-reset after a short delay to allow for multiple prints
    setTimeout(() => {
        resetCountdownDialog();
    }, 2000);
}

function resetCountdownDialog(options = {}) {
    const { hideCountdown = true } = options;
    const countdownTimerElement = document.getElementById('countdownTimer');
    const countdownSecondsElement = document.getElementById('countdownSeconds');
    const printButtonText = document.getElementById('printButtonText');
    const printNowButton = document.getElementById('printNowButton');
    const cancelButton = document.getElementById('cancelCountdown');

    // Stop any existing countdown
    if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
    }

    // Reset UI to initial state
    countdownSeconds = getCountdownDuration();
    if (countdownSecondsElement) {
        countdownSecondsElement.textContent = countdownSeconds;
    }
    if (countdownTimerElement) {
        countdownTimerElement.style.display = 'none';
    }
    if (printButtonText) {
        printButtonText.textContent = 'Print Now';
    }
    if (printNowButton) {
        printNowButton.disabled = false;
    }
    if (cancelButton) {
        cancelButton.textContent = 'Cancel';
    }

    currentPrintTarget = 'label';

    // Transition back to form state
    transitionToFormState({ hideCountdown });
}

// Centralized URL state management
const URLState = {
    // Get current form data from URL parameters
    getFormDataFromURL() {
        const params = new URLSearchParams(window.location.search);
        const formData = {};

        // Extract all non-control parameters
        const controlParams = new Set(['tpl', 'template', 'template_slug', 'print', 'qr', 'qr_label', 'countdown_duration']);

        for (const [key, value] of params.entries()) {
            if (!controlParams.has(key.toLowerCase())) {
                formData[key] = value;
            }
        }

        return formData;
    },

    // Get current template from URL
    getTemplate() {
        const params = new URLSearchParams(window.location.search);
        return params.get('tpl') || params.get('template') || params.get('template_slug') || 'bluey_label';
    },

    // Check if currently in print state
    isPrintState() {
        const params = new URLSearchParams(window.location.search);
        return params.get('print') === 'true';
    },

    // Check if QR mode is active
    isQRMode() {
        const params = new URLSearchParams(window.location.search);
        return params.get('qr') === 'true' || params.get('qr_label') === 'true';
    },

    // Build URL with form data and state
    buildURL(formData = {}, options = {}) {
        const url = new URL(window.location.origin + window.location.pathname);

        // Add template
        const template = options.template || this.getTemplate();
        url.searchParams.set('tpl', template);

        const appendValue = (key, rawValue) => {
            const value = rawValue != null ? String(rawValue) : '';
            if (!value) {
                return;
            }
            url.searchParams.append(key, value);
        };

        // Add form data
        Object.entries(formData).forEach(([key, value]) => {
            if (value === null || value === undefined || value === '') {
                url.searchParams.delete(key);
                return;
            }
            if (Array.isArray(value)) {
                url.searchParams.delete(key);
                value.forEach((entry) => appendValue(key, entry));
                return;
            }
            url.searchParams.set(key, value);
        });

        // Add state parameters
        if (options.print) {
            url.searchParams.set('print', 'true');
        }
        if (options.qr) {
            url.searchParams.set('qr', 'true');
        }
        if (options.countdown_duration) {
            url.searchParams.set('countdown_duration', options.countdown_duration);
        }

        return url;
    },

    // Update URL with new state
    updateURL(formData = {}, options = {}, useHistory = false) {
        const url = this.buildURL(formData, options);

        if (useHistory) {
            window.history.pushState({
                printState: !!options.print,
                target: options.qr ? 'qr' : 'label'
            }, '', url.toString());
        } else {
            window.history.replaceState({}, '', url.toString());
        }
    }
};

function transitionToPrintState(target) {
    const formData = getFormStateForUrl();
    const templateSlug = form && form.dataset.template ? form.dataset.template : URLState.getTemplate();

    URLState.updateURL(formData, {
        template: templateSlug,
        print: true,
        qr: target === 'qr'
    }, true);

    startCountdown(target);
}

function transitionToFormState(options = {}) {
    const { hideCountdown = true } = options;
    const formData = getFormStateForUrl();
    const templateSlug = form && form.dataset.template ? form.dataset.template : URLState.getTemplate();

    URLState.updateURL(formData, {
        template: templateSlug
    }, false);

    const countdownContainer = document.getElementById('printCountdownContainer');
    if (countdownContainer) {
        countdownContainer.style.display = hideCountdown ? 'none' : 'block';
    }
}

function ensurePreviewsGenerated() {
    // Return a promise that resolves when previews are generated
    return new Promise((resolve, reject) => {
        // Check if previews already exist
        const labelImage = document.getElementById('labelPreviewImage');
        const qrImage = document.getElementById('qrPreviewImage');

        if (labelImage && labelImage.dataset.hasPreview === 'true' &&
            qrImage && qrImage.dataset.hasPreview === 'true') {
            resolve();
            return;
        }

        // Try to trigger preview generation
        if (typeof schedulePreview === 'function') {
            try {
                schedulePreview();
            } catch (error) {
                console.warn('Error calling schedulePreview:', error);
            }
        }

        // Wait for previews to be generated (with timeout)
        let attempts = 0;
        const maxAttempts = 25; // 5 seconds max
        const checkInterval = setInterval(() => {
            attempts++;

            const labelReady = labelImage && labelImage.dataset.hasPreview === 'true';
            const qrReady = qrImage && qrImage.dataset.hasPreview === 'true';

            if (labelReady && qrReady) {
                clearInterval(checkInterval);
                resolve();
            } else if (attempts >= maxAttempts) {
                clearInterval(checkInterval);
                reject(new Error('Preview generation timeout'));
            }
        }, 200);
    });
}

function parseWarnings(payload) {
    if (!payload || !Array.isArray(payload.warnings)) {
        return [];
    }
    return payload.warnings.filter((item) => typeof item === 'string' && item.trim().length > 0);
}



function combineHeaders(defaults, overrides) {
    if (!overrides) {
        return Object.assign({}, defaults);
    }
    if (typeof Headers !== 'undefined' && overrides instanceof Headers) {
        const headers = Object.assign({}, defaults);
        overrides.forEach((value, key) => {
            headers[key] = value;
        });
        return headers;
    }
    return Object.assign({}, defaults, overrides);
}

function normalizeRequestOptions(options) {
    const defaultHeaders = { Accept: 'application/json' };
    if (!options) {
        return { fetchOptions: { headers: combineHeaders(defaultHeaders) }, expectJson: true };
    }

    const fetchOptions = Object.assign({}, options);
    const expectJson = options.expectJson === false ? false : true;
    delete fetchOptions.expectJson;
    fetchOptions.headers = combineHeaders(defaultHeaders, options.headers);
    return { fetchOptions, expectJson };
}

const BASE_PATH = (() => {
    const path = (window.location && window.location.pathname) || '';
    const marker = '/templates/';
    const idx = path.indexOf(marker);
    if (idx > 0) {
        return path.slice(0, idx);
    }
    const bbIdx = path.indexOf('/bb');
    if (bbIdx > 0) {
        return path.slice(0, bbIdx);
    }
    if (path.startsWith('/api/hassio_ingress/')) {
        // Fallback: strip trailing component to keep ingress prefix.
        const parts = path.split('/');
        return parts.slice(0, 4).join('/');
    }
    return '';
})();

async function requestJson(url, options) {
    const normalized = normalizeRequestOptions(options);
    const prefix = BASE_PATH || '';
    const requestUrl = url.startsWith('http')
        ? url
        : `${prefix}${url.startsWith('/') ? '' : '/'}${url}`;
    let response;
    try {
        response = await fetch(requestUrl, normalized.fetchOptions);
    } catch (networkError) {
        if (networkError && networkError.name === 'AbortError') {
            return { ok: false, aborted: true, status: null, data: null, error: null };
        }
        const message = networkError && networkError.message ? networkError.message : 'Network request failed.';
        return { ok: false, aborted: false, status: null, data: null, error: message };
    }

    const contentType = response.headers && response.headers.get ? response.headers.get('content-type') || '' : '';
    const isJson = contentType.indexOf('application/json') !== -1;
    let data = null;

    if (isJson) {
        data = await response.json().catch(() => null);
    }

    if (!response.ok) {
        const message = data && data.error ? data.error : 'Request failed.';
        return { ok: false, aborted: false, status: response.status, data, error: message };
    }

    if (normalized.expectJson && !isJson) {
        return { ok: false, aborted: false, status: response.status, data: null, error: 'Unexpected response format.' };
    }

    return { ok: true, aborted: false, status: response.status, data };
}

function createAbortController() {
    if (typeof window !== 'undefined' && window.AbortController) {
        return new window.AbortController();
    }
    return null;
}

function formDataToObject(formElement) {
    const formData = new FormData(formElement);
    const data = {};
    for (const [key, value] of formData.entries()) {
        if (Object.prototype.hasOwnProperty.call(data, key)) {
            const existing = data[key];
            if (Array.isArray(existing)) {
                existing.push(value);
            } else {
                data[key] = [existing, value];
            }
        } else {
            data[key] = value;
        }
    }
    return data;
}

function getFormStateForUrl() {
    if (form) {
        return formDataToObject(form);
    }
    return URLState.getFormDataFromURL();
}

function buildTemplatePayload() {
    if (!form) {
        return null;
    }
    const templateSlug = form.dataset.template;
    if (!templateSlug) {
        return null;
    }
    return {
        template: templateSlug,
        data: formDataToObject(form),
    };
}

function setPreviewLoading() {
    if (previewContainer) {
        previewContainer.setAttribute('aria-busy', 'true');
    }
    if (!previewStatus) {
        return;
    }
    previewStatus.textContent = 'Rendering previews…';
    previewStatus.classList.remove('preview-status--error');
    [labelPreviewImage, qrPreviewImage].forEach((image) => {
        if (!image) {
            return;
        }
        if (image.dataset.hasPreview === 'true') {
            image.hidden = false;
            image.classList.add('preview-image--loading');
        } else {
            image.hidden = true;
        }
    });
}

function updatePreviewImage(target, payload) {
    if (!target) {
        return;
    }
    const imageData = payload && payload.image;
    if (imageData) {
        target.src = imageData;
        target.hidden = false;
        target.dataset.hasPreview = 'true';
        target.classList.remove('preview-image--loading');
    } else {
        target.hidden = true;
        target.dataset.hasPreview = 'false';
    }
}

function updateWarnings(target, warnings) {
    if (!target) {
        return;
    }
    const safeWarnings = parseWarnings({ warnings });
    target.textContent = safeWarnings.length ? `Warnings: ${safeWarnings.join(' ')}` : '';
}

function updateQrPreviewUrl(url) {
    if (!qrPreviewUrlRow || !qrPreviewUrlLink) {
        return;
    }
    const normalized = typeof url === 'string' ? url.trim() : '';
    if (normalized) {
        qrPreviewUrlRow.hidden = false;
        qrPreviewUrlLink.textContent = normalized;
        qrPreviewUrlLink.href = normalized;
    } else {
        qrPreviewUrlRow.hidden = true;
        qrPreviewUrlLink.textContent = '';
        qrPreviewUrlLink.removeAttribute('href');
    }
}

async function requestPreview() {
    if (!form || !previewContainer || disableDefaultFormHandlers) {
        return;
    }
    const payload = buildTemplatePayload();
    if (!payload) {
        if (previewStatus) {
            previewStatus.textContent = 'Template information is missing from the form.';
            previewStatus.classList.add('preview-status--error');
        }
        return;
    }

    const payloadKey = JSON.stringify(payload);
    if (
        payloadKey === lastPreviewPayloadKey &&
        labelPreviewImage &&
        labelPreviewImage.dataset.hasPreview === 'true' &&
        qrPreviewImage &&
        qrPreviewImage.dataset.hasPreview === 'true'
    ) {
        return;
    }
    lastPreviewPayloadKey = payloadKey;

    if (previewAbortController && typeof previewAbortController.abort === 'function') {
        previewAbortController.abort();
    }
    const controller = createAbortController();
    previewAbortController = controller;
    setPreviewLoading();

    const fetchOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    };

    if (controller && controller.signal) {
        fetchOptions.signal = controller.signal;
    }

    const result = await requestJson('/bb/preview', fetchOptions);

    if (previewAbortController !== controller) {
        return;
    }

    const clearLoadingState = () => {
        [labelPreviewImage, qrPreviewImage].forEach((image) => {
            if (!image) {
                return;
            }
            if (image.dataset.hasPreview === 'true') {
                image.hidden = false;
                image.classList.remove('preview-image--loading');
            } else {
                image.hidden = true;
            }
        });
        if (previewContainer) {
            previewContainer.removeAttribute('aria-busy');
        }
    };

    if (result.aborted) {
        clearLoadingState();
        previewAbortController = null;
        return;
    }

    if (!result.ok) {
        clearLoadingState();
        if (previewStatus) {
            previewStatus.textContent = result.error || 'Preview unavailable.';
            previewStatus.classList.add('preview-status--error');
        }
        updateQrPreviewUrl('');
        previewAbortController = null;
        return;
    }

    const data = result.data || {};
    const labelPayload = data.label || {};
    const qrPayload = data.qr || {};

    const qrTargetUrl = typeof data.print_url === 'string' ? data.print_url : '';

    updatePreviewImage(labelPreviewImage, labelPayload);
    updatePreviewImage(qrPreviewImage, qrPayload);
    updateWarnings(labelPreviewWarnings, labelPayload.warnings || []);
    updateWarnings(qrPreviewWarnings, qrPayload.warnings || []);
    updateQrPreviewUrl(qrTargetUrl);
    clearLoadingState();

    if (previewStatus) {
        previewStatus.textContent = '';
        previewStatus.classList.remove('preview-status--error');
    }
    if (qrCaptionNode) {
        qrCaptionNode.textContent = data.qr_caption || 'Scan to trigger the label.';
    }
    if (labelPreviewSummary) {
        labelPreviewSummary.textContent = 'Click to print the label.';
    }
    if (bestByDateValue && data.best_by && data.best_by.best_by_date) {
        bestByDateValue.textContent = data.best_by.best_by_date;
    }

    previewAbortController = null;
}

function schedulePreview() {
    if (!form || disableDefaultFormHandlers) {
        return;
    }
    if (previewTimerId) {
        window.clearTimeout(previewTimerId);
    }
    previewTimerId = window.setTimeout(() => {
        previewTimerId = null;
        requestPreview();
    }, PREVIEW_DEBOUNCE_MS);
}

function getStoredThemePreference() {
    try {
        const saved = localStorage.getItem(THEME_STORAGE_KEY);
        if (saved && THEME_OPTIONS.includes(saved)) {
            return saved;
        }
    } catch (storageError) {
        // Ignore storage issues and fall back to system.
    }
    return 'system';
}

function getSystemTheme() {
    if (typeof window !== 'undefined' && window.matchMedia) {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'light';
}

function applyTheme(preference) {
    const resolvedTheme = preference === 'system' ? getSystemTheme() : preference;
    const root = document.documentElement;
    root.dataset.theme = resolvedTheme;
    root.dataset.themePreference = preference;
    root.style.colorScheme = resolvedTheme;
    root.classList.toggle('theme-dark', resolvedTheme === 'dark');
    root.classList.toggle('theme-light', resolvedTheme === 'light');
    if (themeSelect && themeSelect.value !== preference) {
        themeSelect.value = preference;
    }
}

function persistTheme(preference) {
    try {
        localStorage.setItem(THEME_STORAGE_KEY, preference);
    } catch (storageError) {
        // Storage may be unavailable; ignore and continue.
    }
}

function handleThemeChange(event) {
    const preference = event && event.target ? event.target.value : 'system';
    const next = THEME_OPTIONS.includes(preference) ? preference : 'system';
    persistTheme(next);
    applyTheme(next);
}

function bindSystemThemeListener() {
    if (typeof window === 'undefined' || !window.matchMedia) {
        return;
    }
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const listener = () => {
        const preference = getStoredThemePreference();
        if (preference === 'system') {
            applyTheme('system');
        }
    };
    if (typeof media.addEventListener === 'function') {
        media.addEventListener('change', listener);
    } else if (typeof media.addListener === 'function') {
        media.addListener(listener);
    }
}

function initTheme() {
    const initialPreference = getStoredThemePreference();
    applyTheme(initialPreference);
    if (themeSelect) {
        themeSelect.value = initialPreference;
        themeSelect.addEventListener('change', handleThemeChange);
    }
    bindSystemThemeListener();
}

function installHoverFilterReset() {
    const selector = '.preview-image, .bb-preview-trigger img';
    function handleEnter(event) {
        const target = event.target && event.target.closest ? event.target.closest(selector) : null;
        if (target) {
            target.classList.add('no-filter');
        }
    }
    function handleLeave(event) {
        const target = event.target && event.target.closest ? event.target.closest(selector) : null;
        if (target) {
            target.classList.remove('no-filter');
        }
    }
    document.addEventListener('pointerover', handleEnter);
    document.addEventListener('pointerout', handleLeave);
    document.addEventListener('focusin', handleEnter);
    document.addEventListener('focusout', handleLeave);
}

function bindPrintTriggers() {
    document.querySelectorAll('.print-trigger').forEach((node) => {
        node.addEventListener('click', (event) => {
            event.preventDefault();
            const target = node.dataset.printTarget === 'qr' ? 'qr' : 'label';
            transitionToPrintState(target);
        });
    });
}

function handleSubmit(event) {
    event.preventDefault();
    transitionToPrintState('label');
}

initTheme();
installHoverFilterReset();

document.addEventListener('DOMContentLoaded', () => {
    if (form && !disableDefaultFormHandlers) {
        form.addEventListener('submit', handleSubmit);
        form.addEventListener('input', schedulePreview);
        form.addEventListener('change', schedulePreview);
    }
    bindPrintTriggers();
    if (form && previewContainer && !disableDefaultFormHandlers) {
        schedulePreview();
    }

    // Initialize countdown functionality
    checkForPrintParameter();

    // Handle browser back/forward navigation
    window.addEventListener('popstate', handlePopState);
});

function handlePopState(event) {
    // Handle browser back/forward navigation using centralized URL state
    if (URLState.isPrintState()) {
        // User navigated to a print URL - show countdown
        const target = URLState.isQRMode() ? 'qr' : 'label';
        startCountdown(target);
    } else {
        // User navigated away from print URL - hide countdown
        const countdownContainer = document.getElementById('printCountdownContainer');
        if (countdownContainer) {
            countdownContainer.style.display = 'none';
        }

        // Stop any running countdown
        if (countdownTimer) {
            clearInterval(countdownTimer);
            countdownTimer = null;
        }
    }
}
