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
    let detail = body;
    try {
      const parsed = JSON.parse(body);
      if (parsed.detail) detail = parsed.detail;
      else if (parsed.message) detail = parsed.message;
    } catch {
      // keep raw body
    }
    const err: ApiError = new Error(detail || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function whoami() {
  return api('/api/whoami');
}

export async function getAppConfig() {
  return api('/api/config') as Promise<{ pixellab_host: boolean; ollama_enabled: boolean }>;
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

export interface Item {
  instance_id: string;
  item_id: string;
  name: string;
  type: string;
  slot: string;
  effects: Record<string, any>;
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
  portrait_url?: string;
  log: RollRecord[];
  xp?: number;
  level?: number;
  gold?: number;
  inventory?: Item[];
  equipment?: Record<string, Item>;
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

export async function regeneratePortrait(characterId: string) {
  return api(`/api/characters/${characterId}/portrait`, {
    method: 'POST',
  }) as Promise<{ job_id: string; portrait_url: string }>;
}

export async function listCharacters() {
  return api('/api/characters') as Promise<{ characters: CharacterState[] }>;
}

export async function deleteCharacter(characterId: string) {
  return api(`/api/characters/${characterId}`, { method: 'DELETE' }) as Promise<{ deleted: boolean }>;
}

export async function equipItem(characterId: string, instanceId: string) {
  return api(`/api/characters/${characterId}/equip`, {
    method: 'POST',
    body: JSON.stringify({ instance_id: instanceId }),
  }) as Promise<{ character: CharacterState }>;
}

export async function useItem(characterId: string, instanceId: string) {
  return api(`/api/characters/${characterId}/use`, {
    method: 'POST',
    body: JSON.stringify({ instance_id: instanceId }),
  }) as Promise<{ character: CharacterState; restored: number }>;
}

export interface GameSession {
  id: string;
  module_id: string;
  account_id: number | null;
  character_id: string | null;
  campaign_id: string | null;
  dm_account_id: number | null;
  turn: number;
  phase: 'player' | 'dm';
  status: 'active' | 'won' | 'lost';
  mode?: 'campaign' | 'arena';
  players: Token[];
  active_player_index: number;
  player: Token;
  monsters: Token[];
  log: string[];
  turn_timer_seconds: number;
  turn_deadline: string | null;
  dm_revealed?: string[];
}

export interface Token {
  id: string;
  name: string;
  type: 'player' | 'monster';
  monster?: string;
  x: number;
  y: number;
  hp: number;
  max_hp: number;
  ac: number;
  color: string;
  alive?: boolean;
  down?: boolean;
  statuses?: { type: string; duration: number; damage?: number }[];
  inventory?: Item[];
  classes?: string[];
  account_id?: number;
  character_id?: string;
  xp?: number;
  level?: number;
  gold?: number;
}

export interface Campaign {
  id: string;
  name: string;
  ruleset_id: string;
  module_ids: string[];
  cleared_module_ids?: string[];
  current_module_index?: number;
  current_module_id?: string | null;
  completed?: boolean;
  dm_account_id: number;
  is_member?: boolean;
  is_dm?: boolean;
}

export interface CampaignMember {
  account_id: number;
  role: string;
  joined_at?: string;
}

export interface Presence {
  account_id: number | null;
  name: string;
}

export interface User {
  id: number;
  name: string;
  is_admin?: boolean;
}

export interface Friend {
  account_id: number;
  status: string;
  online?: boolean;
}

export interface FriendListResponse {
  friends: Friend[];
  pending: Friend[];
}

export interface AnalyticsSummary {
  sessions: number;
  wins: number;
  losses: number;
  level_ups: number;
  deaths: number;
  boss_kills: number;
}

export interface AnalyticsEvent {
  id: string;
  account_id: number | null;
  session_id: string | null;
  event_type: string;
  payload: Record<string, any>;
  created_at: string;
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
  return api('/api/sessions', {
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

export interface ModuleInfo {
  id: string;
  name: string;
  ruleset: string;
  description: string;
  theme?: string;
  width: number;
  height: number;
  tiles: string[];
}

export async function listModules() {
  return api('/api/modules') as Promise<{ modules: ModuleInfo[] }>;
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
        theme?: string;
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

export async function advanceSession(sessionId: string) {
  return api(`/api/sessions/${sessionId}/advance`, {
    method: 'POST',
  }) as Promise<{ session: GameSession }>;
}

export async function restInSession(sessionId: string) {
  return api(`/api/sessions/${sessionId}/rest`, {
    method: 'POST',
  }) as Promise<{ session: GameSession }>;
}

export async function saveProgress(sessionId: string) {
  return api(`/api/sessions/${sessionId}/save`, {
    method: 'POST',
  }) as Promise<{ saved: boolean; character_ids: string[] }>;
}

export async function buyItem(characterId: string, itemId: string, cost = 15) {
  return api(`/api/characters/${characterId}/buy`, {
    method: 'POST',
    body: JSON.stringify({ item_id: itemId, cost }),
  }) as Promise<{ character: CharacterState }>;
}

export async function joinSession(sessionId: string, characterId: string) {
  return api(`/api/sessions/${sessionId}/join`, {
    method: 'POST',
    body: JSON.stringify({ character_id: characterId }),
  }) as Promise<{ session: GameSession }>;
}

export async function listCampaignSessions(campaignId: string) {
  return api(`/api/campaigns/${campaignId}/sessions`) as Promise<{
    sessions: { id: string; name: string; module_id: string; status: string; turn: number; phase: string; player_count: number }[];
  }>;
}

export async function getCampaignMembers(campaignId: string) {
  return api(`/api/campaigns/${campaignId}/members`) as Promise<{ members: CampaignMember[] }>;
}

export async function transferDm(campaignId: string, accountId: number) {
  return api(`/api/campaigns/${campaignId}/transfer_dm`, {
    method: 'POST',
    body: JSON.stringify({ account_id: accountId }),
  }) as Promise<{ campaign: Campaign }>;
}

export async function setMemberRole(campaignId: string, accountId: number, role: 'dm' | 'player' | 'none') {
  return api(`/api/campaigns/${campaignId}/members/${accountId}/role`, {
    method: 'POST',
    body: JSON.stringify({ role }),
  }) as Promise<{ account_id: number; role: string }>;
}

export async function getSessionPresence(sessionId: string) {
  return api(`/api/sessions/${sessionId}/presence`) as Promise<{ session_id: string; present: Presence[] }>;
}

export async function adminListCampaigns() {
  return api('/admin/campaigns') as Promise<{ campaigns: { id: string; name: string; ruleset_id: string; module_ids: string[]; dm_account_id: number; member_count: number; created_at: string | null }[] }>;
}

export async function adminDeleteCampaign(campaignId: string) {
  return api(`/admin/campaigns/${campaignId}`, { method: 'DELETE' }) as Promise<{ deleted: boolean }>;
}

export async function adminCreateCampaign(campaign: { name: string; password: string; module_ids: string[] }) {
  return api('/admin/campaigns', {
    method: 'POST',
    body: JSON.stringify(campaign),
  }) as Promise<{ campaign: Campaign }>;
}

export async function adminListSessions() {
  return api('/admin/sessions') as Promise<{ sessions: { id: string; name: string; module_id: string; campaign_id: string | null; status: string; turn: number; phase: string; player_count: number }[] }>;
}

export async function adminDeleteSession(sessionId: string) {
  return api(`/admin/sessions/${sessionId}`, { method: 'DELETE' }) as Promise<{ deleted: boolean }>;
}

export async function listBestiary() {
  return api('/api/bestiary') as Promise<{ monsters: string[] }>;
}

export async function dmSpawn(sessionId: string, payload: { name: string; x: number; y: number; token_id?: string }) {
  return api(`/api/sessions/${sessionId}/dm/spawn`, {
    method: 'POST',
    body: JSON.stringify(payload),
  }) as Promise<{ session: GameSession }>;
}

export async function dmMove(sessionId: string, payload: { token_id: string; x: number; y: number }) {
  return api(`/api/sessions/${sessionId}/dm/move`, {
    method: 'POST',
    body: JSON.stringify(payload),
  }) as Promise<{ session: GameSession }>;
}

export async function dmDamage(sessionId: string, payload: { token_id: string; amount: number }) {
  return api(`/api/sessions/${sessionId}/dm/damage`, {
    method: 'POST',
    body: JSON.stringify(payload),
  }) as Promise<{ session: GameSession }>;
}

export async function dmReveal(sessionId: string, payload: { x: number; y: number; radius?: number }) {
  return api(`/api/sessions/${sessionId}/dm/reveal`, {
    method: 'POST',
    body: JSON.stringify(payload),
  }) as Promise<{ session: GameSession }>;
}

export async function listFriends() {
  return api('/api/friends') as Promise<FriendListResponse>;
}

export async function addFriend(accountId: number) {
  return api('/api/friends', {
    method: 'POST',
    body: JSON.stringify({ account_id: accountId }),
  }) as Promise<{ status: string }>;
}

export async function acceptFriend(accountId: number) {
  return api(`/api/friends/${accountId}/accept`, { method: 'POST' }) as Promise<{ status: string }>;
}

export async function declineFriend(accountId: number) {
  return api(`/api/friends/${accountId}/decline`, { method: 'POST' }) as Promise<{ declined: boolean }>;
}

export async function removeFriend(accountId: number) {
  return api(`/api/friends/${accountId}`, { method: 'DELETE' }) as Promise<{ removed: boolean }>;
}

export async function inviteCampaign(campaignId: string, accountId: number) {
  return api(`/api/campaigns/${campaignId}/invite/${accountId}`, { method: 'POST' }) as Promise<{ invited: boolean }>;
}

export async function getAccountProgress() {
  return api('/api/account/progress') as Promise<AnalyticsSummary>;
}

export async function adminAnalytics() {
  return api('/api/admin/analytics') as Promise<AnalyticsSummary>;
}

export async function adminAnalyticsEvents(eventType?: string) {
  const query = eventType ? `?type=${encodeURIComponent(eventType)}` : '';
  return api(`/api/admin/analytics/events${query}`) as Promise<{ events: AnalyticsEvent[] }>;
}
