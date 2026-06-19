// AI Quotation Builder - Frontend Logic

let uploadedFile = null;
let requirements = null;
let quotationData = null;
let currentTemplate = 'type1';

// Tracks which format the user last clicked (for the modal callback)
let _pendingEmailFormat = null; // 'pdf' | 'word'

// DOM Elements
const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const generateBtn = document.getElementById('generateBtn');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const previewSection = document.getElementById('previewSection');
const previewContent = document.getElementById('previewContent');
const downloadSection = document.getElementById('downloadSection');
const downloadPdfBtn = document.getElementById('downloadPdf');
const downloadWordBtn = document.getElementById('downloadWord');
const sendEmailPdfBtn = document.getElementById('sendEmailPdf');
const sendEmailWordBtn = document.getElementById('sendEmailWord');
const alertBox = document.getElementById('alertBox');

// Email modal elements
const emailModal = document.getElementById('emailModal');
const modalEmailInput = document.getElementById('modalEmailInput');
const emailModalError = document.getElementById('emailModalError');
const emailModalSend = document.getElementById('emailModalSend');
const emailModalCancel = document.getElementById('emailModalCancel');

// Template toggle
const templateOptions = document.querySelectorAll('.template-option');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
});

function setupEventListeners() {
    // File upload
    uploadArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);

    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    // Template toggle
    templateOptions.forEach(option => {
        option.addEventListener('click', () => {
            templateOptions.forEach(opt => opt.classList.remove('active'));
            option.classList.add('active');
            currentTemplate = option.dataset.template;
        });
    });

    // Generate button
    generateBtn.addEventListener('click', generateQuotation);

    // Download buttons
    downloadPdfBtn.addEventListener('click', () => downloadDocument('pdf'));
    downloadWordBtn.addEventListener('click', () => downloadDocument('word'));

    // Email buttons — always open the modal so users can choose / change email
    if (sendEmailPdfBtn) {
        sendEmailPdfBtn.addEventListener('click', () => {
            _pendingEmailFormat = 'pdf';
            openEmailModal();
        });
    }
    if (sendEmailWordBtn) {
        sendEmailWordBtn.addEventListener('click', () => {
            _pendingEmailFormat = 'word';
            openEmailModal();
        });
    }

    // Modal buttons
    if (emailModalCancel) emailModalCancel.addEventListener('click', closeEmailModal);
    if (emailModalSend)   emailModalSend.addEventListener('click', handleModalSend);

    // Close modal on backdrop click
    if (emailModal) {
        emailModal.addEventListener('click', (e) => {
            if (e.target === emailModal) closeEmailModal();
        });
    }

    // Allow Enter key in modal input
    if (modalEmailInput) {
        modalEmailInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') handleModalSend();
        });
    }
}

// ─── Email Modal Helpers ───────────────────────────────────────────────────────

function openEmailModal(prefillEmail = '') {
    if (!emailModal) return;
    modalEmailInput.value = prefillEmail;
    emailModalError.style.display = 'none';
    emailModalError.textContent = '';
    emailModal.style.display = 'flex';
    // Reinitialize Lucide icons inside modal (they might not have been rendered yet)
    if (window.lucide) lucide.createIcons();
    setTimeout(() => modalEmailInput.focus(), 100);
}

function closeEmailModal() {
    if (!emailModal) return;
    emailModal.style.display = 'none';
    _pendingEmailFormat = null;
}

function showModalError(msg) {
    emailModalError.textContent = msg;
    emailModalError.style.display = 'block';
}

async function handleModalSend() {
    const email = (modalEmailInput.value || '').trim();
    if (!email) {
        showModalError('Please enter an email address.');
        return;
    }
    // Basic email format check
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        showModalError('Please enter a valid email address (e.g. name@example.com).');
        return;
    }
    closeEmailModal();
    await sendQuotationEmail(_pendingEmailFormat || 'word', email);
}

// ─── Email Send ───────────────────────────────────────────────────────────────

/**
 * Send the quotation via email.
 * @param {'pdf'|'word'} format
 * @param {string|null}  overrideEmail  — explicit email to use (from modal)
 */
async function sendQuotationEmail(format, overrideEmail = null) {
    if (!quotationData) {
        showAlert('No quotation data available. Please generate a quotation first.', 'error');
        return;
    }

    const endpoint = format === 'pdf' ? '/send-quotation-email' : '/send-quotation-word';
    const btn      = format === 'pdf' ? sendEmailPdfBtn : sendEmailWordBtn;
    const label    = format === 'pdf' ? 'PDF' : 'Word';
    const origHTML = btn ? btn.innerHTML : '';

    if (btn) {
        btn.innerHTML = `<span class="spinner"></span> Sending ${label}…`;
        btn.disabled = true;
    }

    try {
        const body = {
            quotation_data: quotationData,
            template_type:  currentTemplate,
        };
        if (overrideEmail) body.override_email = overrideEmail;

        const response = await fetch(endpoint, {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(body),
        });

        const data = await response.json();

        if (data.success) {
            showAlert(`✅ ${data.message}`, 'success');
        } else if (data.needs_email) {
            // Server says no email on file — open modal to collect it
            _pendingEmailFormat = format;
            openEmailModal();
            showAlert('Please enter the email address to send the quotation to.', 'warning');
        } else {
            showAlert(`Failed to send email: ${data.error}`, 'error');
        }
    } catch (error) {
        showAlert(`Email send failed: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.innerHTML = origHTML;
            btn.disabled  = false;
            if (window.lucide) lucide.createIcons();
        }
    }
}

// ─── Existing Functions ────────────────────────────────────────────────────────

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
}

async function handleFile(file) {
    // Validate file type
    const validExtensions = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.png', '.jpg', '.jpeg', '.tiff'];
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!validExtensions.includes(ext)) {
        showAlert('Please upload a valid file type (Word, PDF, Excel, Image)', 'error');
        return;
    }

    // Show file info
    fileName.textContent = file.name;
    fileInfo.classList.add('show');
    uploadedFile = file;

    // Upload file
    await uploadFile(file);
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        showProgress('Uploading and parsing document...', 30);

        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            requirements = data.requirements;
            showAlert('Document uploaded and parsed successfully!', 'success');
            hideProgress();
            checkReadyToGenerate();
        } else {
            showAlert(`Error: ${data.error}`, 'error');
            hideProgress();
        }
    } catch (error) {
        showAlert(`Upload failed: ${error.message}`, 'error');
        hideProgress();
    }
}

function checkReadyToGenerate() {
    if (requirements) {
        generateBtn.disabled = false;
    } else {
        generateBtn.disabled = true;
    }
}

async function generateQuotation() {

    if (!requirements) {
        showAlert('Please upload a requirement document first', 'warning');
        return;
    }

    try {
        showProgress('Generating quotation with AI...', 50);
        generateBtn.disabled = true;

        const response = await fetch('/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                requirements: requirements,
                template_type: currentTemplate
            })
        });

        const data = await response.json();

        if (data.success) {
            quotationData = data.quotation_data;
            showProgress('Quotation generated successfully!', 100);

            setTimeout(() => {
                hideProgress();
                showPreview(quotationData);
                showDownloadSection();
            }, 1000);

            showAlert('Quotation generated successfully!', 'success');
        } else {
            showAlert(`Error: ${data.error}`, 'error');
            hideProgress();
            generateBtn.disabled = false;
        }
    } catch (error) {
        showAlert(`Generation failed: ${error.message}`, 'error');
        hideProgress();
        generateBtn.disabled = false;
    }
}

function showPreview(data) {
    let previewHtml = `
        <h4 style="color: var(--brand-primary, #667eea); margin-bottom: 15px;">${data.project_title || 'Quotation Preview'}</h4>
        <p><strong>Client:</strong> ${data.client_name || 'N/A'}</p>
        <p><strong>Date:</strong> ${data.date || 'N/A'}</p>
        <p><strong>Reference:</strong> ${data.reference_number || 'N/A'}</p>
        <hr style="margin: 15px 0; border: none; border-top: 2px solid #e2e8f0;">
        <p><strong>Executive Summary:</strong></p>
        <p style="color: #4a5568;">${data.executive_summary || 'N/A'}</p>
        <hr style="margin: 15px 0; border: none; border-top: 2px solid #e2e8f0;">
        <p><strong>Total Investment:</strong> <span style="color: #667eea; font-size: 1.2rem; font-weight: bold;">₹${data.grand_total || '0'}</span></p>
    `;

    if (data.pricing_table && data.pricing_table.length > 0) {
        previewHtml += `
            <hr style="margin: 15px 0; border: none; border-top: 2px solid #e2e8f0;">
            <p><strong>Pricing Items:</strong> ${data.pricing_table.length} items</p>
        `;
    }

    previewContent.innerHTML = previewHtml;
    previewSection.classList.add('show');
}

function showDownloadSection() {
    downloadSection.classList.add('show');
}

async function downloadDocument(format) {
    if (!quotationData) {
        showAlert('No quotation data available', 'error');
        return;
    }

    try {
        const endpoint = format === 'pdf' ? '/download/pdf' : '/download/word';
        const btnText = format === 'pdf' ? 'Downloading PDF...' : 'Downloading Word...';

        if (format === 'pdf') {
            downloadPdfBtn.innerHTML = `<span class="spinner"></span> ${btnText}`;
            downloadPdfBtn.disabled = true;
        } else {
            downloadWordBtn.innerHTML = `<span class="spinner"></span> ${btnText}`;
            downloadWordBtn.disabled = true;
        }

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                quotation_data: quotationData,
                template_type: currentTemplate
            })
        });

        const data = await response.json();

        if (data.success) {
            // Download the file
            window.location.href = `/download/file/${data.filename}`;
            showAlert(`${format.toUpperCase()} downloaded successfully!`, 'success');
        } else {
            showAlert(`Download failed: ${data.error}`, 'error');
        }
    } catch (error) {
        showAlert(`Download failed: ${error.message}`, 'error');
    } finally {
        // Reset buttons
        downloadPdfBtn.innerHTML = '<i data-lucide="file-text" class="icon-sm"></i> Download PDF';
        downloadPdfBtn.disabled = false;
        downloadWordBtn.innerHTML = '<i data-lucide="file-text" class="icon-sm"></i> Download Word';
        downloadWordBtn.disabled = false;
        if (window.lucide) lucide.createIcons();
    }
}

function showProgress(text, percent) {
    progressText.textContent = text;
    progressFill.style.width = `${percent}%`;
    progressSection.classList.add('show');
}

function hideProgress() {
    progressSection.classList.remove('show');
    progressFill.style.width = '0%';
}

function showAlert(message, type) {
    alertBox.textContent = message;
    alertBox.className = `alert alert-${type} show`;

    setTimeout(() => {
        alertBox.classList.remove('show');
    }, 5000);
}

