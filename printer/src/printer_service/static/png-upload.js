const pngForm = document.getElementById('labelForm');
const pngFileInput = document.getElementById('pngFile');
const pngDropZone = document.getElementById('pngDropZone');
const pngUploadStatus = document.getElementById('pngUploadStatus');
const pngPrintTrigger = document.getElementById('pngPrintTrigger');
const pngPreviewImage = document.getElementById('labelPreviewImage');
const pngPreviewSummary = document.getElementById('labelPreviewSummary');
const pngPreviewWarnings = document.getElementById('labelPreviewWarnings');
const pngArchivePanel = document.getElementById('pngArchivePanel');
const pngArchiveStatus = document.getElementById('pngArchiveStatus');
const pngArchiveListBody = document.getElementById('pngArchiveListBody');
const pngArchiveEmpty = document.getElementById('pngArchiveEmpty');
const pngArchiveSortButtons = Array.from(document.querySelectorAll('[data-png-archive-sort]'));
const pngArchiveSortHeaders = Array.from(document.querySelectorAll('[data-png-archive-sort-header]'));
const pngUploadPrintUrl = pngForm && pngForm.dataset.printUrl
    ? pngForm.dataset.printUrl
    : '/png/print';

let selectedPNG = null;
let selectedArchivedLabel = null;
let pngPreviewSequence = 0;
const pngArchiveSortState = { key: 'created', direction: 'desc' };

function setPNGStatus(message, isError = false) {
    if (!pngUploadStatus) {
        return;
    }
    pngUploadStatus.textContent = message || '';
    pngUploadStatus.classList.toggle('preview-status--error', isError);
}

function clearPNGPreview() {
    if (pngPreviewImage) {
        pngPreviewImage.removeAttribute('src');
        pngPreviewImage.hidden = true;
        pngPreviewImage.dataset.hasPreview = 'false';
    }
    if (pngPrintTrigger) {
        pngPrintTrigger.disabled = true;
    }
    if (pngPreviewSummary) {
        pngPreviewSummary.textContent = 'Choose a PNG to preview it.';
    }
    if (pngPreviewWarnings) {
        pngPreviewWarnings.textContent = '';
    }
}

function restorePNGUploadPrintUrl() {
    if (pngForm) {
        pngForm.dataset.printUrl = pngUploadPrintUrl;
    }
}

function pngFormData(file) {
    const body = new FormData();
    body.append('file', file, file.name || 'upload.png');
    return body;
}

async function previewPNG(file) {
    selectedPNG = file || null;
    selectedArchivedLabel = null;
    restorePNGUploadPrintUrl();
    clearPNGPreview();
    const sequence = ++pngPreviewSequence;
    if (!selectedPNG) {
        setPNGStatus('Choose a PNG to continue.', false);
        return;
    }

    setPNGStatus('Validating and preparing preview…', false);
    const previewUrl = pngForm && pngForm.dataset.previewUrl
        ? pngForm.dataset.previewUrl
        : '/png/preview';
    const result = await requestJson(previewUrl, {
        method: 'POST',
        body: pngFormData(selectedPNG),
    });
    if (sequence !== pngPreviewSequence) {
        return;
    }
    if (!result.ok) {
        setPNGStatus(result.error || 'PNG preview failed.', true);
        return;
    }

    const payload = result.data || {};
    const metrics = payload.metrics || {};
    const source = payload.source || {};
    if (pngPreviewImage && payload.image) {
        pngPreviewImage.src = payload.image;
        pngPreviewImage.hidden = false;
        pngPreviewImage.dataset.hasPreview = 'true';
    }
    if (pngPrintTrigger) {
        pngPrintTrigger.disabled = false;
    }
    if (pngPreviewSummary) {
        const rotation = payload.rotated ? ' · rotated to landscape' : '';
        pngPreviewSummary.textContent = `${payload.filename || selectedPNG.name} · ${source.width_px || '?'}×${source.height_px || '?'} px${rotation} · ${metrics.width_in || 2.4}″×${metrics.height_in || 1.3}″ label`;
    }
    const warnings = Array.isArray(metrics.warnings) ? metrics.warnings : [];
    if (pngPreviewWarnings) {
        pngPreviewWarnings.textContent = warnings.length ? `Warnings: ${warnings.join(' ')}` : '';
    }
    setPNGStatus('PNG is valid. Click the preview to open the print control.', false);
}

window.printerBuildPrintFormData = () => {
    if (selectedArchivedLabel) {
        return new FormData();
    }
    return selectedPNG ? pngFormData(selectedPNG) : null;
};

function setPNGArchiveStatus(message, isError = false) {
    if (!pngArchiveStatus) {
        return;
    }
    pngArchiveStatus.textContent = message || '';
    pngArchiveStatus.classList.toggle('preset-status--error', isError);
}

function setPNGArchiveEmpty(isEmpty, message = 'No PNG labels saved yet.') {
    if (!pngArchiveEmpty) {
        return;
    }
    pngArchiveEmpty.textContent = message;
    pngArchiveEmpty.hidden = !isEmpty;
}

function formatPNGArchiveDate(value) {
    if (!value) {
        return '—';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
    }).format(date);
}

function createPNGArchiveCell(content, className = '') {
    const cell = document.createElement('td');
    cell.textContent = content;
    if (className) {
        cell.className = className;
    }
    return cell;
}

function showArchivedLabel(label) {
    if (!label || !label.id) {
        return;
    }
    selectedPNG = null;
    selectedArchivedLabel = label;
    pngPreviewSequence += 1;
    if (pngFileInput) {
        pngFileInput.value = '';
    }
    clearPNGPreview();
    if (pngForm) {
        pngForm.dataset.printUrl = label.print_url;
    }
    if (pngPreviewImage) {
        pngPreviewImage.src = label.image_url;
        pngPreviewImage.hidden = false;
        pngPreviewImage.dataset.hasPreview = 'true';
    }
    if (pngPrintTrigger) {
        pngPrintTrigger.disabled = false;
    }
    if (pngPreviewSummary) {
        pngPreviewSummary.textContent = `${label.name || 'Saved label'} · printed ${Number(label.print_count) || 0} time(s)`;
    }
    setPNGStatus(`Ready to reprint ${label.name || 'the saved label'}.`, false);
    transitionToPrintState('label');
}

async function deleteArchivedLabel(label) {
    if (!label || !label.id) {
        return;
    }
    const name = label.name || label.id;
    if (!window.confirm(`Delete saved PNG "${name}"?`)) {
        return;
    }
    setPNGArchiveStatus(`Deleting "${name}"…`, false);
    const result = await requestJson(label.delete_url, { method: 'DELETE' });
    if (!result.ok) {
        setPNGArchiveStatus(result.error || 'Failed to delete saved PNG.', true);
        return;
    }
    if (selectedArchivedLabel && selectedArchivedLabel.id === label.id) {
        selectedArchivedLabel = null;
        restorePNGUploadPrintUrl();
        clearPNGPreview();
        setPNGStatus('Saved PNG deleted. Choose another PNG to continue.', false);
    }
    setPNGArchiveStatus(`Deleted "${name}".`, false);
    loadPNGArchive();
}

function createPNGArchiveActions(label) {
    const cell = document.createElement('td');
    const actions = document.createElement('div');
    actions.className = 'preset-row__actions';

    const reprintButton = document.createElement('button');
    reprintButton.type = 'button';
    reprintButton.className = 'preset-action';
    reprintButton.textContent = 'Reprint';
    reprintButton.addEventListener('click', () => showArchivedLabel(label));

    const downloadButton = document.createElement('button');
    downloadButton.type = 'button';
    downloadButton.className = 'preset-action';
    downloadButton.textContent = 'Download';
    downloadButton.addEventListener('click', () => {
        window.location.assign(label.download_url);
    });

    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'preset-action preset-action--danger';
    deleteButton.textContent = 'Delete';
    deleteButton.addEventListener('click', () => deleteArchivedLabel(label));

    actions.appendChild(reprintButton);
    actions.appendChild(downloadButton);
    actions.appendChild(deleteButton);
    cell.appendChild(actions);
    return cell;
}

function createPNGArchiveRow(label) {
    const row = document.createElement('tr');
    row.className = 'preset-row';

    const previewCell = document.createElement('td');
    const previewLink = document.createElement('a');
    previewLink.href = label.image_url;
    previewLink.target = '_blank';
    previewLink.rel = 'noreferrer noopener';
    previewLink.ariaLabel = `Open ${label.name || 'saved PNG'}`;
    const thumbnail = document.createElement('img');
    thumbnail.className = 'png-archive-thumbnail';
    thumbnail.src = label.image_url;
    thumbnail.alt = '';
    thumbnail.loading = 'lazy';
    previewLink.appendChild(thumbnail);
    previewCell.appendChild(previewLink);
    row.appendChild(previewCell);
    row.appendChild(createPNGArchiveCell(label.name || 'label.png', 'png-archive-name'));
    row.appendChild(createPNGArchiveCell(formatPNGArchiveDate(label.created_at)));
    row.appendChild(createPNGArchiveCell(String(Number(label.print_count) || 0)));
    row.appendChild(createPNGArchiveActions(label));
    return row;
}

function renderPNGArchive(labels) {
    if (!pngArchiveListBody) {
        return;
    }
    pngArchiveListBody.innerHTML = '';
    if (!Array.isArray(labels) || labels.length === 0) {
        setPNGArchiveEmpty(true);
        return;
    }
    setPNGArchiveEmpty(false);
    labels.forEach((label) => {
        pngArchiveListBody.appendChild(createPNGArchiveRow(label));
    });
}

function updatePNGArchiveSortHeaders() {
    pngArchiveSortHeaders.forEach((header) => {
        const isActive = header.dataset.pngArchiveSortHeader === pngArchiveSortState.key;
        header.setAttribute('aria-sort', isActive
            ? (pngArchiveSortState.direction === 'asc' ? 'ascending' : 'descending')
            : 'none');
        const indicator = header.querySelector('.preset-sort__indicator');
        if (indicator) {
            indicator.textContent = isActive
                ? (pngArchiveSortState.direction === 'asc' ? '↑' : '↓')
                : '↕';
        }
    });
}

function changePNGArchiveSort(key) {
    if (!key) {
        return;
    }
    if (pngArchiveSortState.key === key) {
        pngArchiveSortState.direction = pngArchiveSortState.direction === 'asc' ? 'desc' : 'asc';
    } else {
        pngArchiveSortState.key = key;
        pngArchiveSortState.direction = 'asc';
    }
    updatePNGArchiveSortHeaders();
    loadPNGArchive();
}

async function loadPNGArchive() {
    if (!pngArchivePanel) {
        return;
    }
    setPNGArchiveStatus('Loading saved PNG labels…', false);
    const listUrl = pngArchivePanel.dataset.listUrl || '/png/labels';
    const query = new URLSearchParams({
        sort: pngArchiveSortState.key,
        direction: pngArchiveSortState.direction,
    });
    const separator = listUrl.includes('?') ? '&' : '?';
    const result = await requestJson(`${listUrl}${separator}${query.toString()}`);
    if (!result.ok) {
        const message = result.error || 'Saved PNG labels are unavailable.';
        setPNGArchiveStatus(message, true);
        setPNGArchiveEmpty(true, message);
        if (pngArchiveListBody) {
            pngArchiveListBody.innerHTML = '';
        }
        return;
    }
    setPNGArchiveStatus('', false);
    renderPNGArchive((result.data && result.data.labels) || []);
}

window.addEventListener('printer:print-success', (event) => {
    const reprintedName = selectedArchivedLabel && selectedArchivedLabel.name;
    const savedLabel = event.detail && event.detail.printed_label;
    selectedPNG = null;
    selectedArchivedLabel = null;
    pngPreviewSequence += 1;
    if (pngFileInput) {
        pngFileInput.value = '';
    }
    restorePNGUploadPrintUrl();
    clearPNGPreview();
    if (reprintedName) {
        setPNGStatus(`Reprinted ${reprintedName}.`, false);
    } else if (savedLabel && savedLabel.name) {
        setPNGStatus(`Printed and saved ${savedLabel.name}.`, false);
    } else {
        setPNGStatus('Printed and saved. The PNG has been cleared from this page.', false);
    }
    loadPNGArchive();
});

document.addEventListener('DOMContentLoaded', () => {
    pngArchiveSortButtons.forEach((button) => {
        button.addEventListener('click', () => {
            changePNGArchiveSort(button.dataset.pngArchiveSort);
        });
    });
    updatePNGArchiveSortHeaders();
    loadPNGArchive();
    if (pngFileInput) {
        pngFileInput.addEventListener('change', () => {
            const file = pngFileInput.files && pngFileInput.files[0];
            previewPNG(file || null);
        });
    }
    if (!pngDropZone) {
        return;
    }
    ['dragenter', 'dragover'].forEach((eventName) => {
        pngDropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            pngDropZone.classList.add('is-dragging');
        });
    });
    ['dragleave', 'drop'].forEach((eventName) => {
        pngDropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            pngDropZone.classList.remove('is-dragging');
        });
    });
    pngDropZone.addEventListener('drop', (event) => {
        const files = event.dataTransfer && event.dataTransfer.files;
        previewPNG(files && files[0] ? files[0] : null);
    });
});
