const labelsContainer = document.getElementById('labels');
const form = document.getElementById('labelForm');
const disableDefaultFormHandlers = !!(form && form.dataset.disableDefaultHandlers === 'true');
const previewContainer = document.getElementById('previewContainer');
const previewImage = document.getElementById('livePreviewImage');
const previewStatus = document.getElementById('livePreviewStatus');
const themeSelect = document.getElementById('themeSelect');

let previewAbortController = null;
let previewTimerId = null;
let lastPreviewPayloadKey = '';
const PREVIEW_DEBOUNCE_MS = 250;
const THEME_STORAGE_KEY = 'printer-theme';
const THEME_OPTIONS = ['light', 'dark', 'system'];

function parseWarnings(payload) {
    if (!payload || !Array.isArray(payload.warnings)) {
        return [];
    }
    return payload.warnings.filter((item) => typeof item === 'string' && item.trim().length > 0);
}

function formatMetricsSummary(metrics) {
    if (!metrics) {
        return '';
    }
    const widthPx = metrics.width_px;
    const heightPx = metrics.height_px;
    if (typeof widthPx !== 'number' || typeof heightPx !== 'number') {
        return '';
    }
    const rawWidthIn = typeof metrics.width_in === 'number' ? metrics.width_in : parseFloat(metrics.width_in);
    const rawHeightIn = typeof metrics.height_in === 'number' ? metrics.height_in : parseFloat(metrics.height_in);
    const widthIn = Number.isFinite(rawWidthIn) ? rawWidthIn : null;
    const heightIn = Number.isFinite(rawHeightIn) ? rawHeightIn : null;
    if (widthIn === null || heightIn === null) {
        return `${widthPx}×${heightPx}px`;
    }
    return `${widthPx}×${heightPx}px (~${widthIn.toFixed(2)}"×${heightIn.toFixed(2)}")`;
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

async function fetchLabels() {
    const result = await requestJson('/labels');
    if (!result.ok) {
        return { ok: false, error: result.error || 'Failed to load labels.', labels: [] };
    }
    const labels = Array.isArray(result.data && result.data.labels) ? result.data.labels : [];
    return { ok: true, error: null, labels };
}

function formatTimestamp(seconds) {
    const date = new Date(seconds * 1000);
    return date.toLocaleString();
}

function renderLabels(labels) {
    if (!labels.length) {
        labelsContainer.classList.add('empty-state');
        labelsContainer.textContent = 'No labels yet.';
        return;
    }

    labelsContainer.classList.remove('empty-state');
    labelsContainer.textContent = '';

    labels.forEach((label) => {
        const card = document.createElement('div');
        card.className = 'label-card';

        const img = document.createElement('img');
        img.src = `${label.url}?v=${label.mtime}`;
        img.alt = label.name;
        img.title = 'Click to send to printer';
        img.addEventListener('click', () => confirmAndPrint(label));

        const timeElement = document.createElement('time');
        timeElement.dateTime = new Date(label.mtime * 1000).toISOString();
        timeElement.textContent = formatTimestamp(label.mtime);

        card.appendChild(img);
        card.appendChild(timeElement);
        labelsContainer.appendChild(card);
    });
}

async function confirmAndPrint(label) {
    const ok = window.confirm(`Send "${label.name}" to the printer?`);
    if (!ok) return;

    const result = await requestJson('/print', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: label.name }),
    });

    if (!result.ok) {
        window.alert(result.error || 'Unexpected error while printing.');
        return;
    }

    const payloadData = result.data || {};
    const warnings = parseWarnings(payloadData);
    const metricsSummary = formatMetricsSummary(payloadData.metrics);
    let message = 'Label sent to printer.';
    if (metricsSummary) {
        message += `\nSize: ${metricsSummary}.`;
    }
    if (warnings.length) {
        message += `\n\nWarnings:\n- ${warnings.join('\n- ')}`;
    }
    window.alert(message);
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
    previewStatus.textContent = 'Rendering preview…';
    previewStatus.classList.remove('preview-status--error');
    if (previewImage) {
        if (previewImage.dataset.hasPreview === 'true') {
            previewImage.hidden = false;
            previewImage.classList.add('preview-image--loading');
        } else {
            previewImage.hidden = true;
        }
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
    if (payloadKey === lastPreviewPayloadKey && previewImage && !previewImage.hidden) {
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

    const result = await requestJson('/labels/preview', fetchOptions);

    if (previewAbortController !== controller) {
        return;
    }

    if (result.aborted) {
        if (previewImage) {
            if (previewImage.dataset.hasPreview === 'true') {
                previewImage.hidden = false;
                previewImage.classList.remove('preview-image--loading');
            } else {
                previewImage.hidden = true;
            }
        }
        if (previewContainer) {
            previewContainer.removeAttribute('aria-busy');
        }
        previewAbortController = null;
        return;
    }

    if (!result.ok) {
        if (previewImage) {
            if (previewImage.dataset.hasPreview === 'true') {
                previewImage.hidden = false;
                previewImage.classList.remove('preview-image--loading');
            } else {
                previewImage.hidden = true;
            }
        }
        if (previewContainer) {
            previewContainer.removeAttribute('aria-busy');
        }
        if (previewStatus) {
            previewStatus.textContent = result.error || 'Preview unavailable.';
            previewStatus.classList.add('preview-status--error');
        }
        previewAbortController = null;
        return;
    }

    const previewData = result.data && result.data.image ? result.data.image : null;
    if (!previewData) {
        if (previewImage) {
            if (previewImage.dataset.hasPreview === 'true') {
                previewImage.hidden = false;
                previewImage.classList.remove('preview-image--loading');
            } else {
                previewImage.hidden = true;
            }
        }
        if (previewContainer) {
            previewContainer.removeAttribute('aria-busy');
        }
        if (previewStatus) {
            previewStatus.textContent = 'Preview response is missing an image.';
            previewStatus.classList.add('preview-status--error');
        }
        previewAbortController = null;
        return;
    }

    if (previewImage) {
        previewImage.src = previewData;
        previewImage.hidden = false;
        previewImage.dataset.hasPreview = 'true';
        previewImage.classList.remove('preview-image--loading');
    }
    if (previewContainer) {
        previewContainer.removeAttribute('aria-busy');
    }
    const warnings = parseWarnings(result.data);
    if (previewStatus) {
        previewStatus.textContent = '';
        previewStatus.classList.remove('preview-status--error');
        const label = document.createElement('span');
        label.className = 'preview-status__label';
        label.textContent = 'Preview';
        previewStatus.appendChild(label);
        if (warnings.length) {
            const warningNode = document.createElement('span');
            warningNode.className = 'preview-status__warnings';
            warningNode.textContent = warnings.join(' ');
            previewStatus.appendChild(warningNode);
        }
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
    const selector = '.preview-image, .label-card img, .bb-preview-trigger img';
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

async function handleSubmit(event) {
    event.preventDefault();
    const payload = buildTemplatePayload();
    if (!payload) {
        window.alert('Template information is missing from the form.');
        return;
    }

    const result = await requestJson('/labels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });

    if (!result.ok) {
        window.alert(result.error || 'Unexpected error while saving label.');
        return;
    }

    const payloadData = result.data || {};
    const warnings = parseWarnings(payloadData);
    const metricsSummary = formatMetricsSummary(payloadData.metrics);
    let message = 'Label saved.';
    if (metricsSummary) {
        message += `\nSize: ${metricsSummary}.`;
    }
    if (warnings.length) {
        message += `\n\nWarnings:\n- ${warnings.join('\n- ')}`;
    }
    window.alert(message);
    form.reset();
    const firstFocusable = form.querySelector('input, select, textarea');
    if (firstFocusable) {
        firstFocusable.focus();
    }
    lastPreviewPayloadKey = '';
    schedulePreview();
    await refreshLabels();
}

async function refreshLabels() {
    if (!labelsContainer) {
        return;
    }
    const result = await fetchLabels();
    if (!result.ok) {
        labelsContainer.classList.add('empty-state');
        labelsContainer.textContent = result.error || 'Unable to load labels.';
        return;
    }
    renderLabels(result.labels.slice(0, 100));
}

initTheme();
installHoverFilterReset();

document.addEventListener('DOMContentLoaded', () => {
    if (form && !disableDefaultFormHandlers) {
        form.addEventListener('submit', handleSubmit);
        form.addEventListener('input', schedulePreview);
        form.addEventListener('change', schedulePreview);
    }
    if (labelsContainer) {
        refreshLabels();
    }
    if (form && previewContainer && !disableDefaultFormHandlers) {
        schedulePreview();
    }
});
