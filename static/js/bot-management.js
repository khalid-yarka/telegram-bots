// static/js/bot-management.js
// Dedicated JavaScript file for bot management functions

// ==================== API CONFIGURATION ====================
const API_KEY = 'change-this-in-production'; // Must match the API_KEY in your environment variables

// Bot management state
let allBots = [];
let filteredBots = [];
let currentPage = 1;
let currentBotToken = null;
const itemsPerPage = 10;

// ==================== API HELPER ====================

async function apiFetch(url, options = {}) {
    const defaultOptions = {
        headers: {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json',
            ...options.headers
        }
    };
    
    const response = await fetch(url, { ...defaultOptions, ...options });
    return response;
}

// ==================== LOAD AND FILTER BOTS ====================

export async function loadBots() {
    try {
        const res = await apiFetch('/api/bots');
        const data = await res.json();
        
        if (data.success) {
            allBots = data.bots;
            filteredBots = [...allBots];
            
            // Update bot count in sidebar if function exists
            if (typeof window.updateBotCount === 'function') {
                window.updateBotCount(allBots.length);
            }
            
            return {
                success: true,
                bots: allBots,
                count: allBots.length
            };
        } else {
            throw new Error(data.error || 'Failed to load bots');
        }
    } catch (error) {
        console.error('Failed to load bots:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

export function filterBots(typeFilter, statusFilter, searchTerm) {
    filteredBots = allBots.filter(bot => {
        // Type filter
        if (typeFilter !== 'all' && bot.bot_type !== typeFilter) {
            return false;
        }
        
        // Status filter
        if (statusFilter !== 'all') {
            const isActive = statusFilter === 'active';
            if (bot.is_active !== isActive) {
                return false;
            }
        }
        
        // Search filter
        if (searchTerm) {
            const name = (bot.bot_name || '').toLowerCase();
            const type = (bot.bot_type || '').toLowerCase();
            const token = (bot.bot_token || '').toLowerCase();
            
            return name.includes(searchTerm) || 
                   type.includes(searchTerm) || 
                   token.includes(searchTerm);
        }
        
        return true;
    });
    
    return filteredBots;
}

export function getPaginatedBots(page = 1) {
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    return filteredBots.slice(start, end);
}

export function getTotalPages() {
    return Math.ceil(filteredBots.length / itemsPerPage);
}

// ==================== BOT OPERATIONS ====================

export async function addBot(botData) {
    try {
        const res = await apiFetch('/api/bots/add', {
            method: 'POST',
            body: JSON.stringify(botData)
        });
        
        const data = await res.json();
        return data;
    } catch (error) {
        console.error('Add bot error:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

export async function deleteBot(botToken) {
    try {
        const res = await apiFetch(`/api/bots/${botToken}/delete`, {
            method: 'POST'
        });
        
        const data = await res.json();
        return data;
    } catch (error) {
        console.error('Delete bot error:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

export async function toggleBotStatus(botToken, activate) {
    try {
        const res = await apiFetch(`/api/bots/${botToken}/toggle`, {
            method: 'POST',
            body: JSON.stringify({ active: activate })
        });
        
        const data = await res.json();
        return data;
    } catch (error) {
        console.error('Toggle bot error:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

export async function renameBot(botToken, newName) {
    try {
        const res = await apiFetch(`/api/bots/${botToken}/rename`, {
            method: 'POST',
            body: JSON.stringify({ new_name: newName })
        });
        
        const data = await res.json();
        return data;
    } catch (error) {
        console.error('Rename bot error:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

// ==================== WEBHOOK OPERATIONS ====================

export async function checkWebhook(botToken) {
    try {
        const res = await apiFetch(`/api/webhook/check/${botToken}`, {
            method: 'POST'
        });
        
        const data = await res.json();
        return data;
    } catch (error) {
        console.error('Webhook check error:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

export async function setupWebhook(botToken, botType) {
    try {
        const res = await apiFetch(`/api/bots/${botToken}/webhook`, {
            method: 'POST',
            body: JSON.stringify({ bot_type: botType })
        });
        
        const data = await res.json();
        return data;
    } catch (error) {
        console.error('Webhook setup error:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

export async function bulkWebhookCheck() {
    try {
        const res = await apiFetch('/api/bulk/webhook-check', {
            method: 'POST'
        });
        
        const data = await res.json();
        return data;
    } catch (error) {
        console.error('Bulk webhook check error:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

// ==================== STATISTICS ====================

export async function getSystemStats() {
    try {
        const res = await apiFetch('/api/stats');
        const data = await res.json();
        return data;
    } catch (error) {
        console.error('Stats error:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

// ==================== LOGS ====================

export async function getLogs(limit = 100, botToken = null, actionType = null) {
    try {
        let url = `/api/logs?limit=${limit}`;
        if (botToken) url += `&bot_token=${botToken}`;
        if (actionType) url += `&action_type=${actionType}`;
        
        const res = await apiFetch(url);
        const data = await res.json();
        return data;
    } catch (error) {
        console.error('Logs error:', error);
        return {
            success: false,
            error: error.message
        };
    }
}

// ==================== UTILITY FUNCTIONS ====================

export function maskToken(token) {
    if (!token) return 'N/A';
    if (token.length <= 15) return token;
    return `${token.substring(0, 10)}...${token.substring(token.length - 5)}`;
}

export function getBotTypeIcon(type) {
    const icons = {
        'master': '🤖',
        'ardayda': '📚',
        'dhalinyaro': '👥'
    };
    return icons[type] || '🤖';
}

export function getStatusBadge(isActive) {
    return isActive ? 
        '<span class="badge badge-success"><i class="fas fa-circle"></i> Active</span>' : 
        '<span class="badge badge-danger"><i class="fas fa-circle"></i> Inactive</span>';
}

export function getWebhookBadge(status) {
    const badges = {
        'active': '<span class="badge badge-success"><i class="fas fa-check-circle"></i> Active</span>',
        'pending': '<span class="badge badge-warning"><i class="fas fa-clock"></i> Pending</span>',
        'failed': '<span class="badge badge-danger"><i class="fas fa-exclamation-circle"></i> Failed</span>'
    };
    return badges[status] || '<span class="badge badge-info">Unknown</span>';
}

export function formatDate(dateString) {
    if (!dateString) return 'Unknown';
    try {
        const date = new Date(dateString);
        return date.toLocaleString();
    } catch {
        return dateString;
    }
}

export function formatRelativeTime(dateString) {
    if (!dateString) return 'Never';
    
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);
        
        if (diffDay > 30) {
            return `${Math.floor(diffDay / 30)} month(s) ago`;
        } else if (diffDay > 0) {
            return `${diffDay} day(s) ago`;
        } else if (diffHour > 0) {
            return `${diffHour} hour(s) ago`;
        } else if (diffMin > 0) {
            return `${diffMin} minute(s) ago`;
        } else {
            return 'Just now';
        }
    } catch {
        return 'Unknown';
    }
}

// ==================== VALIDATION ====================

export function validateBotToken(token) {
    // Format: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
    const tokenRegex = /^\d+:[A-Za-z0-9_-]{30,}$/;
    return tokenRegex.test(token);
}

export function validateBotName(name) {
    return name && name.length >= 3 && name.length <= 100;
}

// ==================== EXPORT FOR BROWSER ====================

// Make functions available globally if needed
if (typeof window !== 'undefined') {
    window.BotManagement = {
        loadBots,
        filterBots,
        addBot,
        deleteBot,
        toggleBotStatus,
        renameBot,
        checkWebhook,
        setupWebhook,
        bulkWebhookCheck,
        getSystemStats,
        getLogs,
        maskToken,
        getBotTypeIcon,
        getStatusBadge,
        getWebhookBadge,
        formatDate,
        formatRelativeTime,
        validateBotToken,
        validateBotName
    };
}