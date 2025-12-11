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
const printTriggers = Array.from(document.querySelectorAll('.print-trigger'));

let previewAbortController = null;
let previewTimerId = null;
let lastPreviewPayloadKey = '';
let lastLabelPrintUrl = '';
let lastQrPrintUrl = '';
const PREVIEW_DEBOUNCE_MS = 250;
const THEME_STORAGE_KEY = 'printer-theme';
const THEME_OPTIONS = ['light', 'dark', 'system'];

// Countdown functionality
let countdownTimer = null;
let countdownSeconds = 0;
let currentPrintTarget = 'label'; // 'label' or 'qr'
let countdownPrintData = null; // Store the print data for the countdown

function getCountdownDuration() {
    // Allow override via URL parameter for testing
    const urlParams = new URLSearchParams(window.location.search);
    const testDuration = urlParams.get('countdown_duration');
    return testDuration ? parseInt(testDuration, 10) : 5; // default 5 seconds
}

// Countdown functionality
function checkForPrintParameter() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('print') === 'true') {
        const target = urlParams.get('qr') === 'true' ? 'qr' : 'label';
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
        previewImage.src = sourceImage.src;
        previewImage.style.display = 'block';
        previewStatus.style.display = 'none';
    } else {
        // If preview not available yet, try to wait for it
        previewImage.style.display = 'none';
        previewStatus.style.display = 'block';
        previewStatus.textContent = 'Loading preview...';

        // Try to trigger preview generation if form data is available
        if (typeof generatePreviews === 'function') {
            generatePreviews();
        }

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
    if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
    }

    // Hide the countdown timer in the button
    const countdownTimerElement = document.getElementById('countdownTimer');
    if (countdownTimerElement) {
        countdownTimerElement.style.display = 'none';
    }

    // Reset print data but keep dialog visible
    countdownPrintData = null;
    currentPrintTarget = 'label';

    // Remove print parameter from URL
    removeUrlParameter('print');
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

        // Execute the print via POST request
        const response = await fetch(printUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();

        if (!response.ok) {
            window.alert(result.error || 'Print failed');
            resetCountdownDialog();
            return;
        }

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

function resetCountdownDialog() {
    const countdownTimerElement = document.getElementById('countdownTimer');
    const countdownSecondsElement = document.getElementById('countdownSeconds');
    const printButtonText = document.getElementById('printButtonText');
    const printNowButton = document.getElementById('printNowButton');
    const cancelButton = document.getElementById('cancelCountdown');

    // Reset UI to initial state
    countdownSeconds = getCountdownDuration();
    if (countdownSecondsElement) {
        countdownSecondsElement.textContent = countdownSeconds;
    }
    if (countdownTimerElement) {
        countdownTimerElement.style.display = 'inline';
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

    // Restart countdown for next print
    if (countdownTimer) {
        clearInterval(countdownTimer);
    }
    countdownTimer = setInterval(() => {
        countdownSeconds--;
        if (countdownTimerElement) {
            countdownTimerElement.textContent = countdownSeconds;
        }

        if (countdownSeconds <= 0) {
            clearInterval(countdownTimer);
            executeCountdownPrint();
        }
    }, 1000);
}

function removeUrlParameter(parameter) {
    const url = new URL(window.location);
    url.searchParams.delete(parameter);
    // Also remove countdown_duration if it was used for testing
    if (parameter === 'print') {
        url.searchParams.delete('countdown_duration');
    }
    window.history.replaceState({}, '', url);
}

function makePreviewClickable() {
    const previewTriggers = document.querySelectorAll('.bb-preview-trigger');
    previewTriggers.forEach((trigger) => {
        trigger.addEventListener('click', (event) => {
            event.preventDefault();
            const target = trigger.dataset.printTarget === 'qr' ? 'qr' : 'label';
            navigateToPrintUrl(target);
        });
    });
}

function navigateToPrintUrl(target) {
    const url = new URL(window.location);
    url.searchParams.set('print', 'true');

    if (target === 'qr') {
        url.searchParams.set('qr', 'true');
    } else {
        url.searchParams.delete('qr');
        url.searchParams.delete('qr_label');
    }

    window.location.href = url.toString();
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

    lastLabelPrintUrl = typeof data.print_url === 'string' ? data.print_url : '';
    lastQrPrintUrl = typeof data.qr_print_url === 'string' ? data.qr_print_url : '';
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
    printTriggers.forEach((node) => {
        node.addEventListener('click', (event) => {
            event.preventDefault();
            const target = node.dataset.printTarget === 'qr' ? 'qr' : 'label';
            sendPrint(target);
        });
    });
}

async function handleSubmit(event) {
    event.preventDefault();
    await sendPrint('label');
}

async function sendPrint(target) {
    const useQr = target === 'qr';
    const printUrl = useQr ? lastQrPrintUrl : lastLabelPrintUrl;
    let result = null;
    if (printUrl) {
        result = await requestJson(printUrl);
    } else {
        const payload = buildTemplatePayload();
        if (!payload) {
            window.alert('Template information is missing from the form.');
            return;
        }
        payload.qr_label = useQr;
        result = await requestJson('/bb/print', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
    }

    if (!result || !result.ok) {
        window.alert((result && result.error) || 'Unexpected error while printing.');
        return;
    }

    const payloadData = result.data || {};
    const warnings = parseWarnings(payloadData);
    let message = useQr ? 'QR label sent.' : 'Label sent.';
    if (warnings.length) {
        message += `\n\nWarnings:\n- ${warnings.join('\n- ')}`;
    }
    window.alert(message);
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
    makePreviewClickable();
});
