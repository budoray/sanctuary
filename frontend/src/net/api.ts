const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
const SITE_URL = 'https://tenshinarts.com';

export interface ApiError extends Error {
  status?: number;
}

async function api(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    credentials: 'include',
    ...options,
  });
  if (res.status === 401) {
    const next = encodeURIComponent(window.location.href);
    window.location.href = `${SITE_URL}/?next=${next}`;
    const err: ApiError = new Error('Not authenticated');
    err.status = 401;
    throw err;
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    const err: ApiError = new Error(`API ${path} failed: ${res.status} ${body}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function whoami() {
  return api('/api/whoami');
}

export async function getRulesetOptions() {
  return api('/api/ruleset/osric/options') as Promise<{
    abilities: string[];
    ancestries: string[];
    classes: string[];
    modes: { id: string; roll: string; arrange: boolean }[];
  }>;
}

export interface PreviewRequest {
  mode: string;
  ancestry: string;
  classes: string[];
  name: string;
  seed?: number;
  arrangement?: Record<string, number>;
}

export interface CharacterState {
  id: string | null;
  name: string;
  ancestry: string;
  classes: string[];
  levels: Record<string, number>;
  scores: Record<string, number>;
  hit_points: number;
  max_hp: number;
  armour_class: number;
  saves: Record<string, number>;
  modifiers: Record<string, number>;
  seed: number;
  log: RollRecord[];
}

export interface RollRecord {
  index: number;
  expr: string;
  faces: number[];
  kept: number[];
  mods: number;
  total: number;
  reason: string;
  tags: string[];
}

export async function previewCharacter(character: PreviewRequest) {
  return api('/api/characters/preview', {
    method: 'POST',
    body: JSON.stringify(character),
  }) as Promise<{ character: CharacterState }>;
}

export async function createCharacter(character: PreviewRequest) {
  return api('/api/characters', {
    method: 'POST',
    body: JSON.stringify(character),
  }) as Promise<{ character: CharacterState }>;
}

export async function listCharacters() {
  return api('/api/characters') as Promise<{ characters: CharacterState[] }>;
}

export async function deleteCharacter(characterId: string) {
  return api(`/api/characters/${characterId}`, { method: 'DELETE' }) as Promise<{ deleted: boolean }>;
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
