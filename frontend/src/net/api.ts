const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function api(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json();
}

export async function createSession() {
  return api('/api/sessions', { method: 'POST' });
}

export async function getSession(sessionId: string) {
  return api(`/api/sessions/${sessionId}`);
}

export async function moveToken(sessionId: string, tokenId: string, x: number, y: number) {
  return api(`/api/sessions/${sessionId}/move`, {
    method: 'POST',
    body: JSON.stringify({ token_id: tokenId, x, y }),
  });
}
