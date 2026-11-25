// API base URL — configurable via env variable for deployment
const BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * POST /chat
 */
export async function sendMessage({ sessionId, message, systemPrompt }) {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      ...(systemPrompt ? { system_prompt: systemPrompt } : {}),
    }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || `HTTP ${res.status}`);
    err.status = res.status;
    err.detail = body.detail;
    throw err;
  }

  return res.json();
}

/**
 * GET /health
 */
export async function fetchHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error('health check failed');
  return res.json();
}

/**
 * GET /sessions/{session_id}/messages
 */
export async function fetchSession(sessionId) {
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}/messages`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
