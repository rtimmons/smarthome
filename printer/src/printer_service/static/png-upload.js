const pngForm = document.getElementById('labelForm');
const pngFileInput = document.getElementById('pngFile');
const pngDropZone = document.getElementById('pngDropZone');
const pngUploadStatus = document.getElementById('pngUploadStatus');
const pngPrintTrigger = document.getElementById('pngPrintTrigger');
const pngPreviewImage = document.getElementById('labelPreviewImage');
const pngPreviewSummary = document.getElementById('labelPreviewSummary');
const pngPreviewWarnings = document.getElementById('labelPreviewWarnings');

let selectedPNG = null;
let pngPreviewSequence = 0;

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

function pngFormData(file) {
    const body = new FormData();
    body.append('file', file, file.name || 'upload.png');
    return body;
}

async function previewPNG(file) {
    selectedPNG = file || null;
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
    return selectedPNG ? pngFormData(selectedPNG) : null;
};

window.addEventListener('printer:print-success', () => {
    selectedPNG = null;
    pngPreviewSequence += 1;
    if (pngFileInput) {
        pngFileInput.value = '';
    }
    clearPNGPreview();
    setPNGStatus('Printed. The PNG has been cleared from this page.', false);
});

document.addEventListener('DOMContentLoaded', () => {
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
