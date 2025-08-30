// Main JavaScript file for hn.fm web UI

// Global state
let appState = {
    isConnected: false,
    refreshInterval: null
};

// Utility functions
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 z-50 p-4 rounded-md shadow-lg transition-all duration-300 transform translate-x-full`;

    // Set notification styles based on type
    const typeStyles = {
        success: 'bg-green-500 text-white',
        error: 'bg-red-500 text-white',
        warning: 'bg-yellow-500 text-white',
        info: 'bg-blue-500 text-white'
    };

    notification.className += ` ${typeStyles[type] || typeStyles.info}`;
    notification.innerHTML = `
        <div class="flex items-center">
            <span class="mr-2">${getNotificationIcon(type)}</span>
            <span>${message}</span>
            <button class="ml-4 text-white hover:text-gray-200" onclick="this.parentElement.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;

    // Add to DOM
    document.body.appendChild(notification);

    // Animate in
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 100);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.classList.add('translate-x-full');
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 300);
    }, 5000);
}

function getNotificationIcon(type) {
    const icons = {
        success: '<i class="fas fa-check-circle"></i>',
        error: '<i class="fas fa-exclamation-circle"></i>',
        warning: '<i class="fas fa-exclamation-triangle"></i>',
        info: '<i class="fas fa-info-circle"></i>'
    };
    return icons[type] || icons.info;
}

function formatDate(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const now = new Date();
    const diffInHours = (now - date) / (1000 * 60 * 60);

    if (diffInHours < 1) {
        return 'Just now';
    } else if (diffInHours < 24) {
        return `${Math.floor(diffInHours)}h ago`;
    } else if (diffInHours < 48) {
        return 'Yesterday';
    } else {
        return date.toLocaleDateString();
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// API functions
async function apiRequest(endpoint, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
        ...options
    };

    try {
        const response = await fetch(`/api${endpoint}`, defaultOptions);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API request failed for ${endpoint}:`, error);
        throw error;
    }
}

// Health check
async function checkHealth() {
    try {
        const health = await apiRequest('/health');
        appState.isConnected = health.redis_status === 'healthy';
        updateConnectionStatus();
        return health;
    } catch (error) {
        appState.isConnected = false;
        updateConnectionStatus();
        throw error;
    }
}

function updateConnectionStatus() {
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');

    if (!indicator || !text) return;

    if (appState.isConnected) {
        indicator.className = 'w-2 h-2 bg-green-500 rounded-full';
        text.textContent = 'Connected';
    } else {
        indicator.className = 'w-2 h-2 bg-red-500 rounded-full';
        text.textContent = 'Disconnected';
    }
}

// Content management
async function createContent(contentData) {
    return await apiRequest('/content', {
        method: 'POST',
        body: JSON.stringify(contentData)
    });
}

async function updateContent(contentId, updates) {
    return await apiRequest(`/content/${contentId}`, {
        method: 'PUT',
        body: JSON.stringify(updates)
    });
}

async function deleteContent(contentId) {
    return await apiRequest(`/content/${contentId}`, {
        method: 'DELETE'
    });
}

async function getContent(contentId) {
    return await apiRequest(`/content/${contentId}`);
}

async function listContent(page = 1, perPage = 20, filters = {}) {
    const params = new URLSearchParams({
        page: page.toString(),
        per_page: perPage.toString(),
        ...filters
    });

    return await apiRequest(`/content?${params}`);
}

// Pipeline management
async function getPipelineStatus() {
    return await apiRequest('/pipeline/status');
}

async function processContent(contentData) {
    return await apiRequest('/pipeline/process', {
        method: 'POST',
        body: JSON.stringify(contentData)
    });
}

// UI helpers
function showLoading(elementId, show = true) {
    const element = document.getElementById(elementId);
    if (!element) return;

    if (show) {
        element.innerHTML = '<div class="loading-spinner mx-auto"></div>';
        element.disabled = true;
    } else {
        element.innerHTML = element.dataset.originalText || 'Submit';
        element.disabled = false;
    }
}

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

// Search functionality
const searchInputs = document.querySelectorAll('[data-search]');
searchInputs.forEach(input => {
    const debouncedSearch = debounce(async (searchTerm) => {
        // Implement search logic here
        console.log('Searching for:', searchTerm);
    }, 300);

    input.addEventListener('input', (e) => {
        debouncedSearch(e.target.value);
    });
});

// Initialize app
document.addEventListener('DOMContentLoaded', async function() {
    try {
        // Check initial health
        await checkHealth();

        // Set up periodic health checks
        setInterval(checkHealth, 30000);

        // Initialize any page-specific functionality
        if (typeof initializePage === 'function') {
            initializePage();
        }

    } catch (error) {
        console.error('Failed to initialize app:', error);
        showNotification('Failed to connect to server', 'error');
    }
});

// Export functions for use in templates
window.hnfm = {
    apiRequest,
    createContent,
    updateContent,
    deleteContent,
    getContent,
    listContent,
    getPipelineStatus,
    processContent,
    showNotification,
    formatDate,
    formatFileSize,
    checkHealth
};
