/**
 * Generate a secure random UUID session ID.
 */
export function generateSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return `s-${crypto.randomUUID()}`;
  }
  // Fallback for older environments
  return `s-${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`;
}

/**
 * Format a friendly error message from an API error.
 */
export function formatError(err) {
  if (!err) return 'An unexpected error occurred.';

  if (err.status === 503) {
    return '⚠️ All AI providers are currently unavailable. Please try again later.';
  }
  if (err.status === 422) {
    const detail = err.detail;
    if (Array.isArray(detail)) {
      return `Validation error: ${detail.map(d => d.msg).join(', ')}`;
    }
    return `Validation error: ${detail || 'Invalid request'}`;
  }
  if (err.message === 'Failed to fetch' || err.message?.includes('NetworkError')) {
    return '🔌 Cannot reach the backend server. Make sure it is running at the expected URL.';
  }
  return err.message || 'An unexpected error occurred.';
}
