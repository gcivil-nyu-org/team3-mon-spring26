/**
 * nomz API Utilities
 * Converted from frontend/src/app/api.ts
 * Preserves all API patterns from React version
 */

/**
 * Django API base URL.
 * Empty string for same-origin requests (Django serves everything).
 */
const API_BASE = '';

/**
 * Construct full API URL from path
 * @param {string} path - API endpoint path (e.g., '/api/restaurants/')
 * @returns {string} Full URL
 */
function apiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE}${p}`;
}

/**
 * Fetch wrapper with credentials included
 * Matches apiFetch from frontend/src/app/api.ts
 *
 * @param {string} path - API endpoint path
 * @param {RequestInit} [options] - Fetch options
 * @returns {Promise<Response>} Fetch response
 */
async function apiFetch(path, options = {}) {
  const url = apiUrl(path);
  const response = await fetch(url, {
    credentials: 'include', // Include cookies for Django auth
    cache: 'no-store',      // Ensure we always get fresh data
    ...options
  });
  return response;
}

/**
 * Map UI sort values to Django query params
 * Matches mapSortByToApi from frontend/src/app/api.ts
 *
 * @param {string} uiValue - Sort value from UI dropdown
 * @returns {string} Django sort_by query param value
 */
function mapSortByToApi(uiValue) {
  const mapping = {
    'composite-high-low': 'composite_desc',
    'composite-low-high': 'composite_asc',
    'name-a-z': 'name_asc',
    'name-z-a': 'name_desc',
  };
  return mapping[uiValue] || 'composite_desc';
}

/**
 * Show error message to user
 * @param {string} message - Error message to display
 * @param {number} [duration=5000] - Duration in milliseconds
 */
function showError(message, duration = 5000) {
  const errorDiv = document.getElementById('error-message');
  if (errorDiv) {
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    errorDiv.classList.remove('hidden');
    errorDiv.classList.add('visible');

    // Auto-hide after duration
    setTimeout(() => {
      errorDiv.style.display = 'none';
      errorDiv.classList.add('hidden');
      errorDiv.classList.remove('visible');
    }, duration);
  } else {
    // Fallback to alert if error div not found
    alert(`Error: ${message}`);
  }
}

/**
 * Show success message to user
 * @param {string} message - Success message to display
 * @param {number} [duration=3000] - Duration in milliseconds
 */
function showSuccess(message, duration = 3000) {
  const successDiv = document.getElementById('success-message');
  if (successDiv) {
    successDiv.textContent = message;
    successDiv.style.display = 'block';
    successDiv.classList.remove('hidden');
    successDiv.classList.add('visible');

    // Auto-hide after duration
    setTimeout(() => {
      successDiv.style.display = 'none';
      successDiv.classList.add('hidden');
      successDiv.classList.remove('visible');
    }, duration);
  }
}

/**
 * Show info message to user
 * @param {string} message - Info message to display
 * @param {number} [duration=3000] - Duration in milliseconds
 */
function showInfo(message, duration = 3000) {
  const infoDiv = document.getElementById('info-message');
  if (infoDiv) {
    infoDiv.textContent = message;
    infoDiv.style.display = 'block';
    infoDiv.classList.remove('hidden');
    infoDiv.classList.add('visible');

    setTimeout(() => {
      infoDiv.style.display = 'none';
      infoDiv.classList.add('hidden');
      infoDiv.classList.remove('visible');
    }, duration);
  }
}

/**
 * Logout user
 * Calls Django logout API and redirects to home page
 */
async function logout() {
  try {
    const response = await apiFetch('/api/auth/logout/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (response.ok) {
      window.location.href = '/home/';
    } else {
      showError('Logout failed. Please try again.');
    }
  } catch (error) {
    console.error('Logout error:', error);
    showError('Network error during logout.');
  }
}

/**
 * Show loading spinner
 * @param {HTMLElement|string} container - Container element or selector
 */
function showLoading(container) {
  const element = typeof container === 'string'
    ? document.querySelector(container)
    : container;

  if (element) {
    element.innerHTML = `
      <div class="loading-container">
        <div class="spinner"></div>
      </div>
    `;
  }
}

/**
 * Hide loading spinner and clear container
 * @param {HTMLElement|string} container - Container element or selector
 */
function hideLoading(container) {
  const element = typeof container === 'string'
    ? document.querySelector(container)
    : container;

  if (element) {
    element.innerHTML = '';
  }
}

/**
 * Get CSRF token from Django cookie
 * Required for POST/PUT/DELETE requests
 * @returns {string|null} CSRF token or null
 */
function getCSRFToken() {
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='));

  return cookieValue ? cookieValue.split('=')[1] : null;
}

/**
 * POST request helper with JSON body
 * @param {string} path - API endpoint path
 * @param {Object} data - Data to send as JSON
 * @returns {Promise<Response>} Fetch response
 */
async function apiPost(path, data) {
  const csrfToken = getCSRFToken();
  const headers = {
    'Content-Type': 'application/json'
  };

  if (csrfToken) {
    headers['X-CSRFToken'] = csrfToken;
  }

  return apiFetch(path, {
    method: 'POST',
    headers,
    body: JSON.stringify(data)
  });
}

/**
 * PUT request helper with JSON body
 * @param {string} path - API endpoint path
 * @param {Object} data - Data to send as JSON
 * @returns {Promise<Response>} Fetch response
 */
async function apiPut(path, data) {
  const csrfToken = getCSRFToken();
  const headers = {
    'Content-Type': 'application/json'
  };

  if (csrfToken) {
    headers['X-CSRFToken'] = csrfToken;
  }

  return apiFetch(path, {
    method: 'PUT',
    headers,
    body: JSON.stringify(data)
  });
}

/**
 * DELETE request helper
 * @param {string} path - API endpoint path
 * @returns {Promise<Response>} Fetch response
 */
async function apiDelete(path) {
  const csrfToken = getCSRFToken();
  const headers = {};

  if (csrfToken) {
    headers['X-CSRFToken'] = csrfToken;
  }

  return apiFetch(path, {
    method: 'DELETE',
    headers
  });
}

/**
 * Format date for display
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted date
 */
function formatDate(dateString) {
  const date = new Date(dateString);
  const options = { year: 'numeric', month: 'short', day: 'numeric' };
  return date.toLocaleDateString('en-US', options);
}

/**
 * Format time for display
 * @param {string} dateString - ISO date string
 * @returns {string} Formatted time
 */
function formatTime(dateString) {
  const date = new Date(dateString);
  const options = { hour: 'numeric', minute: '2-digit', hour12: true };
  return date.toLocaleTimeString('en-US', options);
}

/**
 * Debounce function to limit API calls
 * @param {Function} func - Function to debounce
 * @param {number} wait - Milliseconds to wait
 * @returns {Function} Debounced function
 */
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

/**
 * Validate form fields
 * @param {string} formId - Form element ID
 * @param {Object} rules - Validation rules object
 * @returns {boolean} True if valid
 */
function validateForm(formId, rules) {
  const form = document.getElementById(formId);
  if (!form) {
    console.error(`Form with id "${formId}" not found`);
    return false;
  }

  let isValid = true;

  for (const [fieldName, rule] of Object.entries(rules)) {
    const field = form.elements[fieldName];
    if (!field) {
      console.warn(`Field "${fieldName}" not found in form`);
      continue;
    }

    const value = field.value.trim();

    // Required check
    if (rule.required && !value) {
      showError(`${rule.label} is required.`);
      field.focus();
      isValid = false;
      break;
    }

    // Min length check
    if (rule.minLength && value.length < rule.minLength) {
      showError(`${rule.label} must be at least ${rule.minLength} characters.`);
      field.focus();
      isValid = false;
      break;
    }

    // Max length check
    if (rule.maxLength && value.length > rule.maxLength) {
      showError(`${rule.label} must be at most ${rule.maxLength} characters.`);
      field.focus();
      isValid = false;
      break;
    }

    // Email pattern check
    if (rule.email && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      showError(`Please enter a valid email address.`);
      field.focus();
      isValid = false;
      break;
    }

    // Custom pattern check
    if (rule.pattern && value && !rule.pattern.test(value)) {
      showError(rule.patternMessage || `${rule.label} format is invalid.`);
      field.focus();
      isValid = false;
      break;
    }
  }

  return isValid;
}

/**
 * Get query parameter from URL
 * @param {string} param - Parameter name
 * @returns {string|null} Parameter value or null
 */
function getQueryParam(param) {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(param);
}

/**
 * Set query parameter in URL (without page reload)
 * @param {string} param - Parameter name
 * @param {string} value - Parameter value
 */
function setQueryParam(param, value) {
  const url = new URL(window.location);
  url.searchParams.set(param, value);
  window.history.pushState({}, '', url);
}

/**
 * Remove query parameter from URL (without page reload)
 * @param {string} param - Parameter name
 */
function removeQueryParam(param) {
  const url = new URL(window.location);
  url.searchParams.delete(param);
  window.history.pushState({}, '', url);
}
