/**
 * VibeDeCoder Frontend JavaScript
 * Handles interactive features and UI enhancements
 */

// Global application object
window.VibeDeCoder = {
    initialized: false,
    
    // Initialize the application
    init() {
        if (this.initialized) return;
        
        console.log('Initializing VibeDeCoder...');
        
        // Initialize components
        this.initTooltips();
        this.initFileUpload();
        this.initAnalysisRefresh();
        this.initDiagrams();
        this.initFormValidation();
        
        this.initialized = true;
        console.log('VibeDeCoder initialized successfully');
    },
    
    // Initialize Bootstrap tooltips
    initTooltips() {
        try {
            // Enable tooltips everywhere
            const tooltipTriggerList = [].slice.call(
                document.querySelectorAll('[data-bs-toggle="tooltip"]')
            );
            
            tooltipTriggerList.forEach(function (tooltipTriggerEl) {
                new bootstrap.Tooltip(tooltipTriggerEl);
            });
        } catch (error) {
            console.warn('Tooltips initialization failed:', error);
        }
    },
    
    // Enhanced file upload functionality
    initFileUpload() {
        const fileInput = document.getElementById('files');
        if (!fileInput) return;
        
        // File validation
        fileInput.addEventListener('change', this.handleFileSelection);
        
        // Drag and drop functionality
        this.initDragAndDrop();
    },
    
    // Handle file selection and validation
    handleFileSelection(event) {
        const files = Array.from(event.target.files);
        const maxFiles = 100;
        const maxFileSize = 16 * 1024 * 1024; // 16MB
        
        // Validate file count
        if (files.length > maxFiles) {
            VibeDeCoder.showAlert(`Too many files selected. Maximum ${maxFiles} files allowed.`, 'danger');
            event.target.value = '';
            return;
        }
        
        // Validate individual files
        const invalidFiles = [];
        const oversizedFiles = [];
        let totalSize = 0;
        
        files.forEach(file => {
            // Check file size
            if (file.size > maxFileSize) {
                oversizedFiles.push(`${file.name} (${VibeDeCoder.formatFileSize(file.size)})`);
                return;
            }
            
            // Check file type
            if (!VibeDeCoder.isValidFileType(file.name)) {
                invalidFiles.push(file.name);
                return;
            }
            
            totalSize += file.size;
        });
        
        // Show validation errors
        if (oversizedFiles.length > 0) {
            VibeDeCoder.showAlert(
                `The following files are too large (max 16MB each):\n${oversizedFiles.join('\n')}`, 
                'danger'
            );
        }
        
        if (invalidFiles.length > 0) {
            VibeDeCoder.showAlert(
                `The following files are not supported:\n${invalidFiles.join('\n')}`, 
                'warning'
            );
        }
        
        // Update file preview
        VibeDeCoder.updateFilePreview(files.filter(file => 
            file.size <= maxFileSize && VibeDeCoder.isValidFileType(file.name)
        ));
    },
    
    // Initialize drag and drop for file upload
    initDragAndDrop() {
        const uploadArea = document.querySelector('.card-body');
        if (!uploadArea) return;
        
        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, this.preventDefaults, false);
            document.body.addEventListener(eventName, this.preventDefaults, false);
        });
        
        // Highlight drop area when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.add('dragover');
            }, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.remove('dragover');
            }, false);
        });
        
        // Handle dropped files
        uploadArea.addEventListener('drop', this.handleDrop, false);
    },
    
    // Prevent default drag behaviors
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    },
    
    // Handle file drop
    handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        const fileInput = document.getElementById('files');
        
        if (fileInput && files.length > 0) {
            fileInput.files = files;
            fileInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
    },
    
    // Check if file type is valid
    isValidFileType(filename) {
        const validExtensions = [
            'py', 'js', 'jsx', 'ts', 'tsx', 'html', 'htm', 'css',
            'c', 'cpp', 'cc', 'cxx', 'h', 'hpp', 'cs', 'go',
            'java', 'php', 'rb', 'swift', 'kt', 'rs'
        ];
        
        const extension = filename.split('.').pop().toLowerCase();
        return validExtensions.includes(extension);
    },
    
    // Format file size for display
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    // Update file preview display
    updateFilePreview(files) {
        const filePreview = document.getElementById('filePreview');
        const fileList = document.getElementById('fileList');
        
        if (!filePreview || !fileList) return;
        
        if (files.length === 0) {
            filePreview.style.display = 'none';
            return;
        }
        
        filePreview.style.display = 'block';
        
        const fileItems = files.map(file => {
            const size = VibeDeCoder.formatFileSize(file.size);
            const language = VibeDeCoder.getLanguageFromFilename(file.name);
            
            return `
                <div class="d-flex justify-content-between align-items-center p-2 border-bottom">
                    <div class="d-flex align-items-center">
                        <i class="fas fa-file-code text-primary me-2"></i>
                        <span>${file.name}</span>
                    </div>
                    <div class="d-flex gap-2">
                        <span class="badge bg-secondary">${language}</span>
                        <span class="badge bg-outline-secondary">${size}</span>
                    </div>
                </div>
            `;
        }).join('');
        
        fileList.innerHTML = fileItems;
    },
    
    // Get programming language from filename
    getLanguageFromFilename(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const languageMap = {
            'py': 'Python',
            'js': 'JavaScript',
            'jsx': 'React',
            'ts': 'TypeScript',
            'tsx': 'React TS',
            'html': 'HTML',
            'htm': 'HTML',
            'css': 'CSS',
            'c': 'C',
            'h': 'C Header',
            'cpp': 'C++',
            'cc': 'C++',
            'cxx': 'C++',
            'hpp': 'C++ Header',
            'cs': 'C#',
            'go': 'Go',
            'java': 'Java',
            'php': 'PHP',
            'rb': 'Ruby',
            'swift': 'Swift',
            'kt': 'Kotlin',
            'rs': 'Rust'
        };
        
        return languageMap[ext] || 'Unknown';
    },
    
    // Initialize auto-refresh for analysis status (disabled for mind map stability)
    initAnalysisRefresh() {
        // Auto-refresh functionality disabled to prevent mind map interference
        // const analyzingElements = document.querySelectorAll('.fa-spinner, .spinner-border');
        
        // if (analyzingElements.length > 0) {
        //     // Set up periodic refresh
        //     setTimeout(() => {
        //         if (!document.hidden) {
        //             window.location.reload();
        //         }
        //     }, 5000);
        // }
        
        // // Page visibility API to pause refresh when tab is hidden
        // document.addEventListener('visibilitychange', () => {
        //     if (!document.hidden && analyzingElements.length > 0) {
        //         // Check if we should refresh when tab becomes visible again
        //         setTimeout(() => window.location.reload(), 1000);
        //     }
        // });
    },
    
    // Initialize diagram functionality
    initDiagrams() {
        // Configure Mermaid
        if (typeof mermaid !== 'undefined') {
            mermaid.initialize({
                theme: 'dark',
                startOnLoad: true,
                fontFamily: 'system-ui, -apple-system, sans-serif',
                flowchart: {
                    useMaxWidth: true,
                    htmlLabels: true,
                    curve: 'basis'
                },
                classDiagram: {
                    useMaxWidth: true
                },
                sequence: {
                    useMaxWidth: true
                }
            });
            
            // Re-render diagrams when tabs are switched
            this.setupDiagramTabHandling();
        }
    },
    
    // Setup diagram tab handling
    setupDiagramTabHandling() {
        const tabTriggers = document.querySelectorAll('#diagramTabs button[data-bs-toggle="tab"]');
        
        tabTriggers.forEach(trigger => {
            trigger.addEventListener('shown.bs.tab', (event) => {
                // Re-initialize mermaid diagrams in the active tab
                setTimeout(() => {
                    const activeTab = event.target.getAttribute('data-bs-target');
                    const activeTabContent = document.querySelector(activeTab);
                    
                    if (activeTabContent) {
                        const mermaidElements = activeTabContent.querySelectorAll('.mermaid');
                        mermaidElements.forEach(element => {
                            if (element.getAttribute('data-processed') !== 'true') {
                                mermaid.init(undefined, element);
                            }
                        });
                    }
                }, 100);
            });
        });
    },
    
    // Initialize form validation
    initFormValidation() {
        // GitHub URL validation
        const repoUrlInput = document.getElementById('repo_url');
        if (repoUrlInput) {
            repoUrlInput.addEventListener('input', this.validateGitHubUrl);
            repoUrlInput.addEventListener('blur', this.extractRepoName);
        }
        
        // Password confirmation validation
        const passwordInput = document.getElementById('password');
        const confirmPasswordInput = document.getElementById('confirm_password');
        
        if (passwordInput && confirmPasswordInput) {
            confirmPasswordInput.addEventListener('input', () => {
                this.validatePasswordConfirmation(passwordInput, confirmPasswordInput);
            });
            
            passwordInput.addEventListener('input', () => {
                if (confirmPasswordInput.value) {
                    this.validatePasswordConfirmation(passwordInput, confirmPasswordInput);
                }
            });
        }
    },
    
    // Validate GitHub URL format
    validateGitHubUrl(event) {
        const input = event.target;
        const url = input.value;
        
        if (url && !url.includes('github.com')) {
            input.setCustomValidity('Please enter a valid GitHub repository URL');
        } else {
            input.setCustomValidity('');
        }
    },
    
    // Extract repository name for analysis name
    extractRepoName(event) {
        const url = event.target.value;
        const analysisNameInput = document.getElementById('analysis_name');
        
        if (url && analysisNameInput && !analysisNameInput.value) {
            const match = url.match(/github\.com\/([^\/]+)\/([^\/\.]+)/);
            if (match) {
                const repoName = match[2];
                analysisNameInput.value = `${repoName} Analysis`;
            }
        }
    },
    
    // Validate password confirmation
    validatePasswordConfirmation(passwordInput, confirmPasswordInput) {
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        
        if (password !== confirmPassword) {
            confirmPasswordInput.setCustomValidity('Passwords do not match');
        } else {
            confirmPasswordInput.setCustomValidity('');
        }
    },
    
    // Show alert message
    showAlert(message, type = 'info') {
        // Create alert element
        const alertElement = document.createElement('div');
        alertElement.className = `alert alert-${type} alert-dismissible fade show`;
        alertElement.innerHTML = `
            <i class="fas fa-${this.getAlertIcon(type)} me-2"></i>
            ${message.replace(/\n/g, '<br>')}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Find container or create one
        let container = document.querySelector('.alert-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'alert-container container mt-3';
            
            const main = document.querySelector('main');
            if (main && main.firstChild) {
                main.insertBefore(container, main.firstChild);
            } else {
                document.body.appendChild(container);
            }
        }
        
        // Add alert to container
        container.appendChild(alertElement);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertElement.parentNode) {
                alertElement.remove();
            }
        }, 5000);
    },
    
    // Get appropriate icon for alert type
    getAlertIcon(type) {
        const icons = {
            'success': 'check-circle',
            'danger': 'exclamation-triangle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle',
            'primary': 'info-circle',
            'secondary': 'info-circle'
        };
        
        return icons[type] || 'info-circle';
    },
    
    // Copy text to clipboard
    copyToClipboard(text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(() => {
                this.showAlert('Copied to clipboard!', 'success');
            }).catch(() => {
                this.fallbackCopyToClipboard(text);
            });
        } else {
            this.fallbackCopyToClipboard(text);
        }
    },
    
    // Fallback copy method for older browsers
    fallbackCopyToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
            this.showAlert('Copied to clipboard!', 'success');
        } catch (err) {
            this.showAlert('Failed to copy to clipboard', 'danger');
        }
        
        document.body.removeChild(textArea);
    },
    
    // Loading overlay utilities
    showLoading(message = 'Loading...') {
        // Remove existing overlay
        this.hideLoading();
        
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="text-center">
                <div class="spinner-border text-primary mb-3" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="text-white">${message}</p>
            </div>
        `;
        overlay.id = 'loadingOverlay';
        
        document.body.appendChild(overlay);
    },
    
    hideLoading() {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            overlay.remove();
        }
    },
    
    // Progress Modal for Analysis
    showProgressModal(analysisId, onComplete) {
        // Remove existing modal if any
        this.hideProgressModal();
        
        // Store the completion callback
        this.progressModalOnComplete = onComplete || null;
        
        const modal = document.createElement('div');
        modal.id = 'analysisProgressModal';
        modal.className = 'analysis-progress-modal';
        modal.innerHTML = `
            <div class="progress-modal-content">
                <div class="progress-modal-header">
                    <h5><i class="fas fa-robot me-2"></i>Code Analysis in Progress</h5>
                    <div class="progress mb-2">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                             id="overallProgressBar" 
                             role="progressbar" 
                             style="width: 0%"></div>
                    </div>
                    <small class="text-muted" id="progressPercentage">0% Complete</small>
                </div>
                
                <div class="progress-modal-body">
                    <div class="progress-stages" id="progressStages">
                        <!-- Stages will be dynamically loaded -->
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Start polling for progress
        this.startProgressPolling(analysisId);
    },
    
    hideProgressModal() {
        const modal = document.getElementById('analysisProgressModal');
        if (modal) {
            modal.remove();
        }
        
        // Clear polling interval
        if (this.progressPollInterval) {
            clearInterval(this.progressPollInterval);
            this.progressPollInterval = null;
        }
    },
    
    startProgressPolling(analysisId) {
        // Clear any existing interval
        if (this.progressPollInterval) {
            clearInterval(this.progressPollInterval);
        }
        
        // Initial fetch
        this.fetchProgress(analysisId);
        
        // Poll every 1.5 seconds
        this.progressPollInterval = setInterval(() => {
            this.fetchProgress(analysisId);
        }, 1500);
    },
    
    fetchProgress(analysisId) {
        fetch(`/analysis/${analysisId}/progress`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    this.updateProgressUI(data);
                    
                    // Check if analysis is complete
                    if (data.analysis_status === 'completed') {
                        setTimeout(() => {
                            this.hideProgressModal();
                            
                            // Call completion callback if provided, otherwise redirect
                            if (this.progressModalOnComplete) {
                                this.progressModalOnComplete(analysisId);
                                this.progressModalOnComplete = null;
                            } else {
                                window.location.href = `/analysis/${analysisId}`;
                            }
                        }, 1000);
                    } else if (data.analysis_status === 'failed') {
                        this.hideProgressModal();
                        this.showAlert('Analysis failed. Please try again.', 'danger');
                    }
                }
            })
            .catch(error => {
                console.error('Progress fetch error:', error);
            });
    },
    
    updateProgressUI(data) {
        const { events, overall_progress } = data;
        
        // Update overall progress bar
        const progressBar = document.getElementById('overallProgressBar');
        const progressPercentage = document.getElementById('progressPercentage');
        
        if (progressBar) {
            progressBar.style.width = `${overall_progress}%`;
        }
        
        if (progressPercentage) {
            progressPercentage.textContent = `${overall_progress}% Complete`;
        }
        
        // Update stages
        const stagesContainer = document.getElementById('progressStages');
        if (stagesContainer && events) {
            stagesContainer.innerHTML = events.map(event => {
                const iconClass = this.getStageIcon(event.stage);
                const statusClass = this.getStageStatusClass(event.status);
                const statusIcon = this.getStageStatusIcon(event.status);
                
                return `
                    <div class="progress-stage ${statusClass}" data-stage="${event.stage}">
                        <div class="stage-icon">
                            <i class="${iconClass}"></i>
                        </div>
                        <div class="stage-content">
                            <div class="stage-label">${event.stage_label}</div>
                            ${event.message ? `<div class="stage-message">${event.message}</div>` : ''}
                        </div>
                        <div class="stage-status">
                            <i class="${statusIcon}"></i>
                        </div>
                    </div>
                `;
            }).join('');
        }
    },
    
    getStageIcon(stage) {
        const icons = {
            'team_ready': 'fas fa-users',
            'architect_analysis': 'fas fa-drafting-compass',
            'business_analyst': 'fas fa-chart-line',
            'app_architect': 'fas fa-layer-group',
            'data_flow_expert': 'fas fa-stream',
            'consolidation': 'fas fa-comments',
            'completed': 'fas fa-check-circle'
        };
        return icons[stage] || 'fas fa-circle';
    },
    
    getStageStatusClass(status) {
        const classes = {
            'pending': 'stage-pending',
            'in_progress': 'stage-in-progress',
            'completed': 'stage-completed',
            'error': 'stage-error'
        };
        return classes[status] || 'stage-pending';
    },
    
    getStageStatusIcon(status) {
        const icons = {
            'pending': 'fas fa-circle text-muted',
            'in_progress': 'fas fa-spinner fa-spin text-primary',
            'completed': 'fas fa-check-circle text-success',
            'error': 'fas fa-exclamation-circle text-danger'
        };
        return icons[status] || 'fas fa-circle';
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    VibeDeCoder.init();
});

// Handle form submissions with loading states
document.addEventListener('submit', (event) => {
    const form = event.target;
    
    if (form.id === 'uploadForm') {
        const submitBtn = form.querySelector('button[type="submit"]');
        const submitText = submitBtn.querySelector('#submitText') || submitBtn;
        const isGitHub = form.action.includes('github-import');
        
        // Show loading state
        submitBtn.disabled = true;
        
        if (submitText) {
            const loadingHtml = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                ${isGitHub ? 'Importing...' : 'Uploading...'}
            `;
            submitText.innerHTML = loadingHtml;
        }
        
        // Additional validation can be added here
    }
});

// Global error handler
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    
    // Only show user-friendly errors, not all JS errors
    if (event.error && event.error.message.includes('fetch')) {
        VibeDeCoder.showAlert('Network error. Please check your connection and try again.', 'danger');
    }
});


// Export for global access
window.VibeDeCoder = VibeDeCoder;
