// WhisperX Web Interface JavaScript

class WhisperXInterface {
    constructor() {
        this.apiBaseUrl = 'http://localhost:8042';
        this.currentResults = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.checkServerHealth();
    }

    bindEvents() {
        // File upload form
        const uploadForm = document.getElementById('uploadForm');
        uploadForm.addEventListener('submit', (e) => this.handleUpload(e));

        // File input change
        const audioFileInput = document.getElementById('audioFile');
        audioFileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        // Export button
        const exportBtn = document.getElementById('exportBtn');
        exportBtn.addEventListener('click', () => this.exportResults());

        // New file button
        const newFileBtn = document.getElementById('newFileBtn');
        newFileBtn.addEventListener('click', () => this.resetToUpload());

        // Drag and drop functionality
        this.setupDragAndDrop();
    }

    setupDragAndDrop() {
        const uploadCard = document.querySelector('.upload-card');

        uploadCard.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadCard.style.border = '2px dashed #667eea';
            uploadCard.style.backgroundColor = '#f8f9fa';
        });

        uploadCard.addEventListener('dragleave', (e) => {
            e.preventDefault();
            uploadCard.style.border = 'none';
            uploadCard.style.backgroundColor = 'white';
        });

        uploadCard.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadCard.style.border = 'none';
            uploadCard.style.backgroundColor = 'white';

            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].type.startsWith('audio/')) {
                document.getElementById('audioFile').files = files;
                this.handleFileSelect({ target: { files: files } });
            }
        });
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            // Update the file input label to show selected file
            const label = document.querySelector('.file-input-label');
            label.innerHTML = `<i class="fas fa-check"></i> ${file.name}`;
            label.style.background = 'linear-gradient(135deg, #27ae60 0%, #2ecc71 100%)';
        }
    }

    async handleUpload(event) {
        event.preventDefault();

        const formData = new FormData(event.target);
        const audioFile = formData.get('audio_file');
        const modelSize = formData.get('model_size');
        const minSpeakers = formData.get('min_speakers');
        const maxSpeakers = formData.get('max_speakers');

        // Debug logging
        console.log('Form data received:');
        console.log('audioFile:', audioFile);
        console.log('modelSize:', modelSize);
        console.log('minSpeakers:', minSpeakers);
        console.log('maxSpeakers:', maxSpeakers);

        if (!audioFile) {
            this.showToast('Please select an audio file', 'error');
            return;
        }

        // Show processing section
        this.showProcessingSection();

        try {
            // Prepare form data for API
            const apiFormData = new FormData();
            apiFormData.append('audio_file', audioFile);
            apiFormData.append('model_size', modelSize);

            if (minSpeakers) apiFormData.append('min_speakers', minSpeakers);
            if (maxSpeakers) apiFormData.append('max_speakers', maxSpeakers);

            // Debug logging for API data
            console.log('API FormData being sent:');
            for (let [key, value] of apiFormData.entries()) {
                console.log(`${key}:`, value);
            }

            // Simulate progress updates
            this.simulateProgress();

            // Make API request
            const response = await fetch(`${this.apiBaseUrl}/process-audio`, {
                method: 'POST',
                body: apiFormData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to process audio');
            }

            const results = await response.json();
            this.currentResults = results;

            // Show results
            this.showResults(results);
            this.showToast('Audio processed successfully!', 'success');

        } catch (error) {
            console.error('Error processing audio:', error);
            this.showToast(`Error: ${error.message}`, 'error');
            this.showUploadSection();
        }
    }

    simulateProgress() {
        const progressFill = document.getElementById('progressFill');
        const steps = document.querySelectorAll('.step');
        let currentStep = 0;

        const progressInterval = setInterval(() => {
            if (currentStep < 3) {
                // Update progress bar
                const progress = ((currentStep + 1) / 3) * 100;
                progressFill.style.width = `${progress}%`;

                // Update steps
                if (currentStep > 0) {
                    steps[currentStep - 1].classList.remove('active');
                    steps[currentStep - 1].classList.add('completed');
                }
                if (currentStep < 3) {
                    steps[currentStep].classList.add('active');
                }

                currentStep++;
            } else {
                clearInterval(progressInterval);
            }
        }, 2000);
    }

    showProcessingSection() {
        document.getElementById('uploadSection').style.display = 'none';
        document.getElementById('processingSection').style.display = 'block';
        document.getElementById('resultsSection').style.display = 'none';
    }

    showResults(results) {
        // Update metadata
        document.getElementById('language').textContent = results.language || 'Unknown';
        document.getElementById('duration').textContent = `${(results.metadata?.audio_duration || 0).toFixed(2)}s`;
        document.getElementById('speakers').textContent = results.metadata?.num_speakers || 0;
        document.getElementById('segments').textContent = results.metadata?.num_segments || 0;

        // Display transcription segments
        this.displayTranscriptionSegments(results.segments);

        // Show results section
        document.getElementById('uploadSection').style.display = 'none';
        document.getElementById('processingSection').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'block';
    }

    displayTranscriptionSegments(segments) {
        const container = document.getElementById('transcriptionContent');
        container.innerHTML = '';

        if (!segments || segments.length === 0) {
            container.innerHTML = '<p class="no-results">No transcription segments found.</p>';
            return;
        }

        segments.forEach((segment, index) => {
            const segmentElement = document.createElement('div');
            segmentElement.className = 'transcript-segment';

            const startTime = this.formatTime(segment.start);
            const endTime = this.formatTime(segment.end);
            const speaker = segment.speaker || 'UNKNOWN';
            const text = segment.text || '';

            segmentElement.innerHTML = `
                <div class="segment-header">
                    <span class="segment-time">${startTime} → ${endTime}</span>
                    <span class="segment-speaker">Speaker ${speaker}</span>
                </div>
                <div class="segment-text">${text}</div>
            `;

            container.appendChild(segmentElement);
        });
    }

    formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = (seconds % 60).toFixed(2);
        return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.padStart(5, '0')}`;
    }

    exportResults() {
        if (!this.currentResults) {
            this.showToast('No results to export', 'error');
            return;
        }

        try {
            // Create export data
            const exportData = {
                timestamp: new Date().toISOString(),
                language: this.currentResults.language,
                metadata: this.currentResults.metadata,
                segments: this.currentResults.segments
            };

            // Convert to JSON
            const jsonData = JSON.stringify(exportData, null, 2);

            // Create and download file
            const blob = new Blob([jsonData], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `whisperx_transcription_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.showToast('Results exported successfully!', 'success');
        } catch (error) {
            console.error('Error exporting results:', error);
            this.showToast('Error exporting results', 'error');
        }
    }

    resetToUpload() {
        // Reset form
        document.getElementById('uploadForm').reset();
        document.querySelector('.file-input-label').innerHTML = '<i class="fas fa-folder-open"></i> Choose Audio File';
        document.querySelector('.file-input-label').style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';

        // Reset progress
        document.getElementById('progressFill').style.width = '0%';
        document.querySelectorAll('.step').forEach(step => {
            step.classList.remove('active', 'completed');
        });
        document.querySelector('#step1').classList.add('active');

        // Show upload section
        document.getElementById('uploadSection').style.display = 'block';
        document.getElementById('processingSection').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'none';

        this.currentResults = null;
    }

    showUploadSection() {
        document.getElementById('uploadSection').style.display = 'block';
        document.getElementById('processingSection').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'none';
    }

    async checkServerHealth() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/health`);
            if (response.ok) {
                const health = await response.json();
                console.log('Server health:', health);
            }
        } catch (error) {
            console.warn('Server health check failed:', error);
        }
    }

    showToast(message, type = 'info', title = null) {
        const toastContainer = document.getElementById('toastContainer');

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icon = type === 'success' ? 'fas fa-check-circle' :
                    type === 'error' ? 'fas fa-exclamation-circle' :
                    'fas fa-info-circle';

        const toastTitle = title || (type === 'success' ? 'Success' :
                                   type === 'error' ? 'Error' : 'Info');

        toast.innerHTML = `
            <i class="${icon}"></i>
            <div class="toast-content">
                <div class="toast-title">${toastTitle}</div>
                <div class="toast-message">${message}</div>
            </div>
        `;

        toastContainer.appendChild(toast);

        // Auto-remove toast after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
    }
}

// Initialize the interface when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new WhisperXInterface();
});

// Add some utility functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Add smooth scrolling for better UX
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});
