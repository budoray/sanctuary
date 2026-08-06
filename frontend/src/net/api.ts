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

export interface GameSession {
  id: string;
  module_id: string;
  turn: number;
  phase: 'player' | 'dm';
  status: 'active' | 'won' | 'lost';
  player: Token;
  monsters: Token[];
  log: string[];
  turn_timer_seconds: number;
  turn_deadline: string | null;
}

export interface Token {
  id: string;
  name: string;
  type: 'player' | 'monster';
  x: number;
  y: number;
  hp: number;
  max_hp: number;
  ac: number;
  color: string;
  alive?: boolean;
}

export interface Campaign {
  id: string;
  name: string;
  ruleset_id: string;
  module_ids: string[];
  dm_account_id: number;
  is_member?: boolean;
  is_dm?: boolean;
}

export async function createCampaign(campaign: { name: string; password: string; ruleset_id?: string; module_ids?: string[] }) {
  return api('/api/campaigns', {
    method: 'POST',
    body: JSON.stringify(campaign),
  }) as Promise<{ campaign: Campaign }>;
}

export async function listCampaigns() {
  return api('/api/campaigns') as Promise<{ campaigns: Campaign[] }>;
}

export async function getCampaign(campaignId: string) {
  return api(`/api/campaigns/${campaignId}`) as Promise<{ campaign: Campaign }>;
}

export async function joinCampaign(campaignId: string, password: string) {
  return api(`/api/campaigns/${campaignId}/join`, {
    method: 'POST',
    body: JSON.stringify({ password }),
  }) as Promise<{ campaign: Campaign }>;
}

export async function createSession(
  characterId: string,
  moduleId = 'sample_lair',
  campaignId?: string,
  turnTimerSeconds = 0,
) {
  return api('/sessions', {
    method: 'POST',
    body: JSON.stringify({
      character_id: characterId,
      module_id: moduleId,
      campaign_id: campaignId,
      turn_timer_seconds: turnTimerSeconds,
    }),
  }) as Promise<{ session: GameSession }>;
}

export async function listSessions() {
  return api('/api/sessions') as Promise<{ sessions: { id: string; name: string; module_id: string; character_id: string; status: string; turn: number; phase: string }[] }>;
}

export async function getActiveSession() {
  return api('/api/sessions/active') as Promise<{ session: GameSession }>;
}

export async function getSession(sessionId: string) {
  return api(`/api/sessions/${sessionId}`) as Promise<{ session: GameSession }>;
}

export async function getModule(moduleId: string) {
  return api(`/api/modules/${moduleId}`) as Promise<{
    module: {
      id: string;
      name: string;
      ruleset: string;
      description: string;
      map: {
        width: number;
        height: number;
        tile_size: number;
        tiles: string[];
      };
    };
  }>;
}

export async function actInSession(sessionId: string, action: string, payload: Record<string, any> = {}) {
  return api(`/api/sessions/${sessionId}/act`, {
    method: 'POST',
    body: JSON.stringify({ action, ...payload }),
  }) as Promise<{ session: GameSession }>;
}
