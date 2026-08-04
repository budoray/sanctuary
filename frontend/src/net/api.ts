const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const SITE_URL = 'https://tenshinarts.com';

async function api(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (res.status === 401) {
    // Send the player to the Tenshin Arts hub to log in, then come back.
    const next = encodeURIComponent(window.location.href);
    window.location.href = `${SITE_URL}/?next=${next}`;
    throw new Error('Not authenticated');
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${path} failed: ${res.status} ${body}`);
  }
  return res.json();
}

export async function whoami() {
  return api('/api/whoami');
}

export async function createCharacter(character: { name: string; race: string; class: string }) {
  return api('/api/characters', {
    method: 'POST',
    body: JSON.stringify(character),
  });
}

export async function listCharacters() {
  return api('/api/characters');
}

export async function createSession(characterId?: string) {
  return api('/api/sessions', {
    method: 'POST',
    body: JSON.stringify(characterId ? { character_id: characterId } : {}),
  });
}

export async function listSessions() {
  return api('/api/sessions');
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

export async function attackToken(sessionId: string, tokenId: string, targetId: string) {
  return api(`/api/sessions/${sessionId}/attack`, {
    method: 'POST',
    body: JSON.stringify({ token_id: tokenId, target_id: targetId }),
  });
}
