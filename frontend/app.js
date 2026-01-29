/**
 * Code Review Assistant - Frontend Application
 * Handles UI interactions and API communication
 */

// API Base URL (update for production)
const API_BASE = 'http://localhost:8000';

// State
let currentTab = 'zip';
let selectedFile = null;
let tempDir = null;
let allFiles = [];
let reviewResults = [];

// DOM Elements
const elements = {
    // Tabs
    tabButtons: document.querySelectorAll('.tab-btn'),
    zipTab: document.getElementById('zip-tab'),
    gitTab: document.getElementById('git-tab'),

    // Upload
    dropzone: document.getElementById('dropzone'),
    zipInput: document.getElementById('zip-input'),
    fileInfo: document.getElementById('file-info'),
    fileName: document.getElementById('file-name'),
    removeFile: document.getElementById('remove-file'),

    // Git
    gitUrl: document.getElementById('git-url'),
    gitBranch: document.getElementById('git-branch'),

    // Ruleset & Submit
    rulesetSelect: document.getElementById('ruleset-select'),
    submitBtn: document.getElementById('submit-btn'),
    btnText: document.querySelector('.btn-text'),
    btnLoader: document.querySelector('.btn-loader'),

    // Results
    resultsSection: document.getElementById('results-section'),
    resultsSummary: document.getElementById('results-summary'),
    issuesList: document.getElementById('issues-list'),

    // Filters
    severityFilter: document.getElementById('severity-filter'),
    fileFilter: document.getElementById('file-filter'),
    categoryFilter: document.getElementById('category-filter'),

    // Loading
    loadingOverlay: document.getElementById('loading-overlay'),
    loadingStatus: document.getElementById('loading-status'),

    // Nav
    docsLink: document.getElementById('docs-link'),

    // Export buttons
    exportGithubBtn: document.getElementById('export-github-btn'),
    exportPatchBtn: document.getElementById('export-patch-btn'),
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initDropzone();
    initFilters();
    initExportButtons();
    loadRulesets();

    // Set docs link
    elements.docsLink.href = `${API_BASE}/docs`;
});

// Tab Switching
function initTabs() {
    elements.tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchTab(tab);
        });
    });
}

function switchTab(tab) {
    currentTab = tab;

    // Update buttons
    elements.tabButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    // Update content
    elements.zipTab.classList.toggle('active', tab === 'zip');
    elements.gitTab.classList.toggle('active', tab === 'git');

    // Reset state
    resetUploadState();
    updateSubmitButton();
}

// Dropzone
function initDropzone() {
    const dropzone = elements.dropzone;

    // Click to browse
    dropzone.addEventListener('click', () => {
        elements.zipInput.click();
    });

    // File selection
    elements.zipInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    // Drag and drop
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');

        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            if (file.name.endsWith('.zip')) {
                handleFileSelect(file);
            } else {
                alert('Please upload a ZIP file');
            }
        }
    });

    // Remove file
    elements.removeFile.addEventListener('click', (e) => {
        e.stopPropagation();
        resetUploadState();
        updateSubmitButton();
    });

    // Git URL input
    elements.gitUrl.addEventListener('input', updateSubmitButton);

    // Submit button
    elements.submitBtn.addEventListener('click', handleSubmit);
}

function handleFileSelect(file) {
    selectedFile = file;
    elements.fileName.textContent = file.name;
    elements.dropzone.classList.add('hidden');
    elements.fileInfo.classList.remove('hidden');
    updateSubmitButton();
}

function resetUploadState() {
    selectedFile = null;
    tempDir = null;
    allFiles = [];
    elements.zipInput.value = '';
    elements.dropzone.classList.remove('hidden');
    elements.fileInfo.classList.add('hidden');
    elements.gitUrl.value = '';
    elements.gitBranch.value = '';
}

function updateSubmitButton() {
    let canSubmit = false;

    if (currentTab === 'zip' && selectedFile) {
        canSubmit = true;
    } else if (currentTab === 'git' && elements.gitUrl.value.trim()) {
        canSubmit = true;
    }

    elements.submitBtn.disabled = !canSubmit;
}

// Rulesets
async function loadRulesets() {
    try {
        const response = await fetch(`${API_BASE}/rulesets`);
        if (response.ok) {
            const data = await response.json();
            data.rulesets.forEach(rs => {
                const option = document.createElement('option');
                option.value = rs.id;
                option.textContent = `${rs.name} (${rs.language})`;
                elements.rulesetSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load rulesets:', error);
    }
}

// Submit
async function handleSubmit() {
    showLoading('Preparing...');

    try {
        // Step 1: Upload/Clone
        if (currentTab === 'zip') {
            updateLoadingStatus('Uploading ZIP file...');
            const formData = new FormData();
            formData.append('file', selectedFile);

            const uploadResponse = await fetch(`${API_BASE}/upload-zip/`, {
                method: 'POST',
                body: formData,
            });

            if (!uploadResponse.ok) {
                throw new Error('Upload failed');
            }

            const uploadData = await uploadResponse.json();
            tempDir = uploadData.temp_dir;
            allFiles = uploadData.files;

        } else {
            updateLoadingStatus('Cloning repository...');
            const cloneResponse = await fetch(`${API_BASE}/clone-repo/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    repo_url: elements.gitUrl.value.trim(),
                    branch: elements.gitBranch.value.trim() || null,
                }),
            });

            if (!cloneResponse.ok) {
                const error = await cloneResponse.json();
                throw new Error(error.detail || 'Clone failed');
            }

            const cloneData = await cloneResponse.json();
            tempDir = cloneData.temp_dir;
            allFiles = cloneData.files;
        }

        // Step 2: Run Review
        updateLoadingStatus('Analyzing code...');

        // Filter to supported files (Python, JS)
        const filesToReview = allFiles.filter(f =>
            f.endsWith('.py') || f.endsWith('.js') || f.endsWith('.jsx')
        );

        if (filesToReview.length === 0) {
            hideLoading();
            alert('No supported files found (Python or JavaScript)');
            return;
        }

        const reviewResponse = await fetch(`${API_BASE}/review`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                temp_dir: tempDir,
                files: filesToReview,
                ruleset: elements.rulesetSelect.value || null,
            }),
        });

        if (!reviewResponse.ok) {
            const error = await reviewResponse.json();
            throw new Error(error.detail || 'Review failed');
        }

        const reviewData = await reviewResponse.json();
        reviewResults = reviewData.ranked_issues;

        // Step 3: Display Results
        displayResults(reviewData);
        hideLoading();

    } catch (error) {
        hideLoading();
        alert(`Error: ${error.message}`);
        console.error(error);
    }
}

// Loading
function showLoading(status) {
    elements.loadingOverlay.classList.remove('hidden');
    elements.loadingStatus.textContent = status;
}

function updateLoadingStatus(status) {
    elements.loadingStatus.textContent = status;
}

function hideLoading() {
    elements.loadingOverlay.classList.add('hidden');
}

// Results Display
function displayResults(data) {
    // Show section
    elements.resultsSection.classList.remove('hidden');

    // Summary
    elements.resultsSummary.innerHTML = `
    <span class="summary-badge high">
      <strong>${data.summary.high_severity}</strong> High
    </span>
    <span class="summary-badge medium">
      <strong>${data.summary.medium_severity}</strong> Medium
    </span>
    <span class="summary-badge low">
      <strong>${data.summary.low_severity}</strong> Low
    </span>
  `;

    // Populate file filter from ALL reviewed files (not just those with issues)
    const reviewedFiles = data.file_results ? data.file_results.map(fr => fr.file) : [];
    const filesWithIssues = [...new Set(data.ranked_issues.map(i => i.file))];
    const allReviewedFiles = [...new Set([...reviewedFiles, ...filesWithIssues])];

    elements.fileFilter.innerHTML = '<option value="">All Files</option>';
    allReviewedFiles.forEach(file => {
        const opt = document.createElement('option');
        opt.value = file;
        opt.textContent = file;
        elements.fileFilter.appendChild(opt);
    });

    // Render issues
    renderIssues(data.ranked_issues);

    // Scroll to results
    elements.resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function renderIssues(issues) {
    elements.issuesList.innerHTML = '';

    if (issues.length === 0) {
        elements.issuesList.innerHTML = `
      <div class="no-issues">
        <p>No issues found! 🎉</p>
      </div>
    `;
        return;
    }

    issues.forEach((issue, index) => {
        const card = document.createElement('div');
        card.className = 'issue-card';
        card.dataset.severity = issue.severity;
        card.dataset.file = issue.file;
        card.dataset.category = issue.category;

        const hasSnippet = issue.snippet && issue.snippet.trim();
        const hasFix = issue.fix && issue.fix.trim();

        card.innerHTML = `
      <div class="issue-header">
        <div class="issue-meta">
          <span class="severity-badge ${issue.severity}">${issue.severity}</span>
          <span class="category-tag">${issue.category}</span>
          <span class="file-tag">
            <code>${issue.file}</code>${issue.line ? `:${issue.line}` : ''}
          </span>
        </div>
        <span class="impact-score">Impact: ${issue.impact}</span>
      </div>
      <p class="issue-message">${escapeHtml(issue.message)}</p>
      ${(hasSnippet || hasFix) ? `
        <div class="issue-details">
          ${hasSnippet ? `
            <div class="code-block snippet">
              <div class="code-block-label">Problematic Code</div>
              <pre>${escapeHtml(issue.snippet)}</pre>
            </div>
          ` : ''}
          ${hasFix ? `
            <div class="code-block fix">
              <div class="code-block-label">Suggested Fix</div>
              <pre>${escapeHtml(issue.fix)}</pre>
              <button class="copy-btn" onclick="copyToClipboard(this, \`${escapeHtml(issue.fix).replace(/`/g, '\\`')}\`)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                </svg>
                Copy Fix
              </button>
            </div>
          ` : ''}
          ${issue.rule ? `
            <a href="${issue.rule.link}" target="_blank" class="rule-link">
              📖 ${issue.rule.id} - View Rule Documentation
            </a>
          ` : ''}
        </div>
      ` : ''}
    `;

        elements.issuesList.appendChild(card);
    });
}

// Filters
function initFilters() {
    elements.severityFilter.addEventListener('change', applyFilters);
    elements.fileFilter.addEventListener('change', applyFilters);
    elements.categoryFilter.addEventListener('change', applyFilters);
}

function applyFilters() {
    const severity = elements.severityFilter.value;
    const file = elements.fileFilter.value;
    const category = elements.categoryFilter.value;

    let filtered = [...reviewResults];

    if (severity) {
        filtered = filtered.filter(i => i.severity === severity);
    }
    if (file) {
        filtered = filtered.filter(i => i.file === file);
    }
    if (category) {
        filtered = filtered.filter(i => i.category === category);
    }

    renderIssues(filtered);
}

// Utilities
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function copyToClipboard(btn, text) {
    navigator.clipboard.writeText(text).then(() => {
        const originalText = btn.innerHTML;
        btn.innerHTML = '✓ Copied!';
        btn.style.background = 'var(--success)';
        btn.style.borderColor = 'var(--success)';
        btn.style.color = 'white';

        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.style.background = '';
            btn.style.borderColor = '';
            btn.style.color = '';
        }, 2000);
    }).catch(err => {
        console.error('Copy failed:', err);
    });
}

// Export Button Handlers
function initExportButtons() {
    if (elements.exportGithubBtn) {
        elements.exportGithubBtn.addEventListener('click', exportGitHubPRComments);
    }
    if (elements.exportPatchBtn) {
        elements.exportPatchBtn.addEventListener('click', exportPatchFile);
    }
}

async function exportGitHubPRComments() {
    if (!reviewResults || reviewResults.length === 0) {
        alert('No review results to export');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/export/github-pr-comments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ranked_issues: reviewResults,
                repo_owner: 'owner',
                repo_name: 'repo',
                pull_number: 1,
                commit_sha: 'HEAD'
            })
        });

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const data = await response.json();

        // Create and download JSON file
        const blob = new Blob([JSON.stringify(data.content, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'github-pr-comments.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

    } catch (error) {
        console.error('Export failed:', error);
        alert('Failed to export GitHub PR comments');
    }
}

async function exportPatchFile() {
    if (!reviewResults || reviewResults.length === 0) {
        alert('No review results to export');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/export/patch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ranked_issues: reviewResults
            })
        });

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const data = await response.json();

        if (!data.content || data.content.trim() === '') {
            alert(data.message || 'No fixable issues found. Issues need both snippet and fix fields.');
            return;
        }

        // Create and download patch file
        const blob = new Blob([data.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'autofix.patch';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

    } catch (error) {
        console.error('Export failed:', error);
        alert('Failed to export patch file');
    }
}
