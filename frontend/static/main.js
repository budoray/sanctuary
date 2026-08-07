var __defProp = Object.defineProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};

// src/net/api.ts
var API_BASE = "";
var SITE_URL = "https://tenshinarts.com";
function showAuthPrompt() {
  if (document.getElementById("tenshin-auth-prompt")) return;
  const overlay = document.createElement("div");
  overlay.id = "tenshin-auth-prompt";
  overlay.className = "auth-prompt-overlay";
  const box = document.createElement("div");
  box.className = "auth-prompt-box";
  box.innerHTML = `<h2>Sign in required</h2><p>Sanctuary uses your Tenshin Arts account. If you are already signed in on tenshinarts.com, third-party cookies may be blocked.</p>`;
  const signIn = document.createElement("button");
  signIn.className = "enter";
  signIn.textContent = "Sign in at Tenshin Arts";
  signIn.onclick = () => {
    const next = encodeURIComponent(window.location.href);
    window.location.href = `${SITE_URL}/?next=${next}`;
  };
  const retry = document.createElement("button");
  retry.textContent = "Retry";
  retry.onclick = () => {
    overlay.remove();
    window.location.reload();
  };
  box.appendChild(signIn);
  box.appendChild(retry);
  overlay.appendChild(box);
  document.body.appendChild(overlay);
}
async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    credentials: "include",
    ...options
  });
  if (res.status === 401) {
    if (sessionStorage.getItem("tenshin_auth_redirect")) {
      showAuthPrompt();
    } else {
      sessionStorage.setItem("tenshin_auth_redirect", "1");
      const next = encodeURIComponent(window.location.href);
      window.location.href = `${SITE_URL}/?next=${next}`;
    }
    const err = new Error("Not authenticated");
    err.status = 401;
    throw err;
  }
  sessionStorage.removeItem("tenshin_auth_redirect");
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    let detail = body;
    try {
      const parsed = JSON.parse(body);
      if (parsed.detail) detail = parsed.detail;
      else if (parsed.message) detail = parsed.message;
    } catch {
    }
    const err = new Error(detail || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
async function whoami() {
  return api("/api/whoami");
}
async function getAppConfig() {
  return api("/api/config");
}
async function getRulesetOptions() {
  return api("/api/ruleset/osric/options");
}
async function previewCharacter(character) {
  return api("/api/characters/preview", {
    method: "POST",
    body: JSON.stringify(character)
  });
}
async function createCharacter(character) {
  return api("/api/characters", {
    method: "POST",
    body: JSON.stringify(character)
  });
}
async function regeneratePortrait(characterId) {
  return api(`/api/characters/${characterId}/portrait`, {
    method: "POST"
  });
}
async function listCharacters() {
  return api("/api/characters");
}
async function deleteCharacter(characterId) {
  return api(`/api/characters/${characterId}`, { method: "DELETE" });
}
async function equipItem(characterId, instanceId) {
  return api(`/api/characters/${characterId}/equip`, {
    method: "POST",
    body: JSON.stringify({ instance_id: instanceId })
  });
}
async function useItem(characterId, instanceId) {
  return api(`/api/characters/${characterId}/use`, {
    method: "POST",
    body: JSON.stringify({ instance_id: instanceId })
  });
}
async function createCampaign(campaign) {
  return api("/api/campaigns", {
    method: "POST",
    body: JSON.stringify(campaign)
  });
}
async function listCampaigns() {
  return api("/api/campaigns");
}
async function getCampaign(campaignId) {
  return api(`/api/campaigns/${campaignId}`);
}
async function joinCampaign(campaignId, password) {
  return api(`/api/campaigns/${campaignId}/join`, {
    method: "POST",
    body: JSON.stringify({ password })
  });
}
async function createSession(characterId, moduleId = "sample_lair", campaignId, turnTimerSeconds = 0, options = {}) {
  return api("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      character_id: characterId,
      module_id: moduleId,
      campaign_id: campaignId,
      turn_timer_seconds: turnTimerSeconds,
      visibility: options.visibility || "solo",
      name: options.name || ""
    })
  });
}
async function listSessions() {
  return api("/api/sessions");
}
async function listJoinableSessions() {
  return api("/api/sessions/joinable");
}
async function joinSessionByCode(code, characterId) {
  return api("/api/sessions/join-by-code", {
    method: "POST",
    body: JSON.stringify({ code, character_id: characterId })
  });
}
async function deleteSession(sessionId) {
  return api(`/api/sessions/${sessionId}`, { method: "DELETE" });
}
async function deleteAllSessions() {
  return api("/api/sessions", { method: "DELETE" });
}
async function getSession(sessionId) {
  return api(`/api/sessions/${sessionId}`);
}
async function listModules() {
  return api("/api/modules");
}
async function getModule(moduleId) {
  return api(`/api/modules/${moduleId}`);
}
async function actInSession(sessionId, action, payload = {}) {
  return api(`/api/sessions/${sessionId}/act`, {
    method: "POST",
    body: JSON.stringify({ action, ...payload })
  });
}
async function advanceSession(sessionId) {
  return api(`/api/sessions/${sessionId}/advance`, {
    method: "POST"
  });
}
async function restInSession(sessionId) {
  return api(`/api/sessions/${sessionId}/rest`, {
    method: "POST"
  });
}
async function saveProgress(sessionId) {
  return api(`/api/sessions/${sessionId}/save`, {
    method: "POST"
  });
}
async function buyItem(characterId, itemId, cost = 15) {
  return api(`/api/characters/${characterId}/buy`, {
    method: "POST",
    body: JSON.stringify({ item_id: itemId, cost })
  });
}
async function joinSession(sessionId, characterId) {
  return api(`/api/sessions/${sessionId}/join`, {
    method: "POST",
    body: JSON.stringify({ character_id: characterId })
  });
}
async function listCampaignSessions(campaignId) {
  return api(`/api/campaigns/${campaignId}/sessions`);
}
async function getCampaignMembers(campaignId) {
  return api(`/api/campaigns/${campaignId}/members`);
}
async function transferDm(campaignId, accountId) {
  return api(`/api/campaigns/${campaignId}/transfer_dm`, {
    method: "POST",
    body: JSON.stringify({ account_id: accountId })
  });
}
async function setMemberRole(campaignId, accountId, role) {
  return api(`/api/campaigns/${campaignId}/members/${accountId}/role`, {
    method: "POST",
    body: JSON.stringify({ role })
  });
}
async function getSessionPresence(sessionId) {
  return api(`/api/sessions/${sessionId}/presence`);
}
async function adminListCampaigns() {
  return api("/admin/campaigns");
}
async function adminDeleteCampaign(campaignId) {
  return api(`/admin/campaigns/${campaignId}`, { method: "DELETE" });
}
async function adminCreateCampaign(campaign) {
  return api("/admin/campaigns", {
    method: "POST",
    body: JSON.stringify(campaign)
  });
}
async function adminListSessions() {
  return api("/admin/sessions");
}
async function adminDeleteSession(sessionId) {
  return api(`/admin/sessions/${sessionId}`, { method: "DELETE" });
}
async function dmSpawn(sessionId, payload) {
  return api(`/api/sessions/${sessionId}/dm/spawn`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
async function dmMove(sessionId, payload) {
  return api(`/api/sessions/${sessionId}/dm/move`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
async function dmReveal(sessionId, payload) {
  return api(`/api/sessions/${sessionId}/dm/reveal`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
async function getAccountProgress() {
  return api("/api/account/progress");
}
async function listItems() {
  return api("/api/items");
}
async function listBestiary() {
  return api("/api/bestiary");
}
async function listRooms() {
  return api("/api/rooms");
}
async function createRoom(room) {
  return api("/api/rooms", {
    method: "POST",
    body: JSON.stringify(room)
  });
}
async function getRoom(roomId) {
  return api(`/api/rooms/${roomId}`);
}
async function updateRoom(roomId, room) {
  return api(`/api/rooms/${roomId}`, {
    method: "PUT",
    body: JSON.stringify(room)
  });
}
async function deleteRoom(roomId) {
  return api(`/api/rooms/${roomId}`, { method: "DELETE" });
}
async function listDungeons() {
  return api("/api/dungeons");
}
async function createDungeon(dungeon) {
  return api("/api/dungeons", {
    method: "POST",
    body: JSON.stringify(dungeon)
  });
}
async function getDungeon(dungeonId) {
  return api(`/api/dungeons/${dungeonId}`);
}
async function updateDungeon(dungeonId, dungeon) {
  return api(`/api/dungeons/${dungeonId}`, {
    method: "PUT",
    body: JSON.stringify(dungeon)
  });
}
async function deleteDungeon(dungeonId) {
  return api(`/api/dungeons/${dungeonId}`, { method: "DELETE" });
}
async function playDungeon(dungeonId, characterId, campaignId, turnTimerSeconds = 0) {
  return api(`/api/dungeons/${dungeonId}/play`, {
    method: "POST",
    body: JSON.stringify({
      character_id: characterId,
      campaign_id: campaignId,
      turn_timer_seconds: turnTimerSeconds
    })
  });
}

// src/ui/utils.ts
function el(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (v === void 0 || v === null) return;
    if (k === "className") {
      element.className = String(v);
    } else if (k.startsWith("on") && k.length > 2 && typeof v === "function") {
      const event = k.slice(2).toLowerCase();
      element.addEventListener(event, v);
    } else {
      element.setAttribute(k, String(v));
    }
  });
  children.forEach((c) => {
    if (c === null || c === void 0) return;
    if (typeof c === "string" || typeof c === "number") {
      element.appendChild(document.createTextNode(String(c)));
    } else {
      element.appendChild(c);
    }
  });
  return element;
}
function clear(container) {
  while (container.firstChild) {
    container.removeChild(container.firstChild);
  }
}
function formatModifier(value2) {
  const sign = value2 >= 0 ? "+" : "";
  return `${sign}${value2}`;
}
function seededRandomSeed() {
  return Math.floor(Math.random() * 1e9);
}

// src/ui/admin-panel.ts
var ALL_MODULE_IDS = [
  { id: "sample_lair", name: "The Goblin Lair" },
  { id: "sunken_crypt", name: "The Sunken Crypt" },
  { id: "shadow_keep", name: "The Shadow Keep" },
  { id: "forsaken_library", name: "The Forsaken Library" },
  { id: "arena_pit", name: "The Arena Pit" }
];
var AdminPanel = class {
  root;
  onBack;
  campaignsEl;
  sessionsEl;
  editorEl;
  tabContent;
  selectedModules = [];
  constructor(container, onBack) {
    this.root = el("div", { className: "session-select" });
    this.onBack = onBack;
    const panel = el("div", { className: "session-panel" });
    panel.appendChild(el("h1", {}, "Admin Panel"));
    panel.appendChild(el("p", { className: "subtitle" }, "Manage campaigns and active sessions."));
    const tabs = el("div", { className: "admin-tabs" });
    tabs.appendChild(this.tabButton("Campaigns", "campaigns"));
    tabs.appendChild(this.tabButton("Active Sessions", "sessions"));
    tabs.appendChild(this.tabButton("Campaign Editor", "editor"));
    panel.appendChild(tabs);
    this.tabContent = el("div", { className: "admin-tab-content" });
    this.campaignsEl = el("div", {});
    this.sessionsEl = el("div", {});
    this.editorEl = el("div", {});
    this.tabContent.appendChild(this.campaignsEl);
    this.tabContent.appendChild(this.sessionsEl);
    this.tabContent.appendChild(this.editorEl);
    panel.appendChild(this.tabContent);
    const backBtn = el("button", { className: "enter", onclick: () => this.onBack() }, "Back");
    panel.appendChild(backBtn);
    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.buildEditor();
    this.switchTab("campaigns");
    this.load();
  }
  tabButton(label, tab) {
    const btn = el("button", {
      className: "admin-tab",
      "data-tab": tab,
      onclick: () => this.switchTab(tab)
    }, label);
    return btn;
  }
  switchTab(tab) {
    this.campaignsEl.style.display = tab === "campaigns" ? "block" : "none";
    this.sessionsEl.style.display = tab === "sessions" ? "block" : "none";
    this.editorEl.style.display = tab === "editor" ? "block" : "none";
    this.root.querySelectorAll(".admin-tab").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-tab") === tab);
    });
  }
  async load() {
    try {
      const [{ campaigns }, { sessions }] = await Promise.all([
        adminListCampaigns(),
        adminListSessions()
      ]);
      this.renderCampaigns(campaigns);
      this.renderSessions(sessions);
    } catch (err) {
      clear(this.campaignsEl);
      this.campaignsEl.appendChild(el("div", { className: "empty error" }, err.message || "Failed to load admin data."));
    }
  }
  buildEditor() {
    clear(this.editorEl);
    this.editorEl.appendChild(el("h2", {}, "Campaign Editor"));
    this.editorEl.appendChild(el("p", { className: "subtitle" }, "Create a campaign with a custom module order."));
    const form = el("div", { className: "admin-form" });
    const nameInput = el("input", { type: "text", placeholder: "Campaign name" });
    const passInput = el("input", { type: "text", placeholder: "Share password" });
    form.appendChild(el("label", {}, "Name"));
    form.appendChild(nameInput);
    form.appendChild(el("label", {}, "Password"));
    form.appendChild(passInput);
    form.appendChild(el("label", {}, "Modules (check in desired order)"));
    const checklist = el("div", { className: "module-checklist" });
    const orderDisplay = el("div", { className: "module-order" }, "Selected order: (none)");
    const updateOrder = () => {
      this.selectedModules = [];
      checklist.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
        const box = cb;
        if (box.checked) this.selectedModules.push(box.value);
      });
      orderDisplay.textContent = this.selectedModules.length > 0 ? `Selected order: ${this.selectedModules.map((id) => ALL_MODULE_IDS.find((m) => m.id === id)?.name || id).join(" \u2192 ")}` : "Selected order: (none)";
    };
    ALL_MODULE_IDS.forEach((mod) => {
      const row = el("label", { className: "module-check-row" });
      const cb = el("input", {
        type: "checkbox",
        value: mod.id,
        onchange: () => updateOrder()
      });
      row.appendChild(cb);
      row.appendChild(document.createTextNode(mod.name));
      checklist.appendChild(row);
    });
    form.appendChild(checklist);
    form.appendChild(orderDisplay);
    const statusEl = el("div", { className: "editor-status" });
    const createBtn = el("button", {
      className: "enter",
      onclick: async () => {
        const name = nameInput.value.trim();
        const password = passInput.value.trim();
        if (!name || !password) {
          statusEl.textContent = "Name and password are required.";
          return;
        }
        if (this.selectedModules.length === 0) {
          statusEl.textContent = "Select at least one module.";
          return;
        }
        try {
          createBtn.disabled = true;
          createBtn.textContent = "Creating...";
          await adminCreateCampaign({ name, password, module_ids: this.selectedModules });
          nameInput.value = "";
          passInput.value = "";
          checklist.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
            cb.checked = false;
          });
          this.selectedModules = [];
          updateOrder();
          statusEl.textContent = "Campaign created.";
          createBtn.textContent = "Create Campaign";
          createBtn.disabled = false;
          this.switchTab("campaigns");
          this.load();
        } catch (err) {
          statusEl.textContent = err.message || "Create failed";
          createBtn.textContent = "Create Campaign";
          createBtn.disabled = false;
        }
      }
    }, "Create Campaign");
    form.appendChild(createBtn);
    form.appendChild(statusEl);
    this.editorEl.appendChild(form);
  }
  renderCampaigns(campaigns) {
    clear(this.campaignsEl);
    this.campaignsEl.appendChild(el("h2", {}, "Campaigns"));
    if (campaigns.length === 0) {
      this.campaignsEl.appendChild(el("div", { className: "empty" }, "No campaigns."));
      return;
    }
    const list = el("ul", { className: "session-list" });
    campaigns.forEach((c) => {
      const info = el("div", { className: "session-info" });
      info.appendChild(el("strong", {}, c.name));
      const moduleNames = c.module_ids.map((id) => ALL_MODULE_IDS.find((m) => m.id === id)?.name || id).join(" \u2192 ");
      info.appendChild(el("span", {}, `${c.ruleset_id} \xB7 DM ${c.dm_account_id} \xB7 ${c.member_count} members`));
      info.appendChild(el("span", { className: "module-order" }, `Order: ${moduleNames}`));
      const delBtn = el("button", {
        className: "danger",
        onclick: async () => {
          if (!confirm(`Delete campaign "${c.name}"?`)) return;
          try {
            await adminDeleteCampaign(c.id);
            this.load();
          } catch (err) {
            alert(err.message || "Delete failed");
          }
        }
      }, "Delete");
      const row = el("li", {});
      row.appendChild(info);
      row.appendChild(delBtn);
      list.appendChild(row);
    });
    this.campaignsEl.appendChild(list);
  }
  renderSessions(sessions) {
    clear(this.sessionsEl);
    this.sessionsEl.appendChild(el("h2", {}, "Active Sessions"));
    if (sessions.length === 0) {
      this.sessionsEl.appendChild(el("div", { className: "empty" }, "No active sessions."));
      return;
    }
    const list = el("ul", { className: "session-list" });
    sessions.forEach((s) => {
      const info = el("div", { className: "session-info" });
      info.appendChild(el("strong", {}, s.name));
      info.appendChild(el("span", {}, `${s.module_id} \xB7 Turn ${s.turn} \xB7 ${s.phase} \xB7 ${s.player_count} players`));
      const delBtn = el("button", {
        className: "danger",
        onclick: async () => {
          if (!confirm(`Delete session "${s.name}"?`)) return;
          try {
            await adminDeleteSession(s.id);
            this.load();
          } catch (err) {
            alert(err.message || "Delete failed");
          }
        }
      }, "Delete");
      const row = el("li", {});
      row.appendChild(info);
      row.appendChild(delBtn);
      list.appendChild(row);
    });
    this.sessionsEl.appendChild(list);
  }
  destroy() {
    this.root.remove();
  }
};

// src/ui/dm-workshop.ts
function defaultTiles() {
  return Array.from({ length: 16 }, (_, y) => Array.from({ length: 16 }, (_, x) => y >= 6 && y <= 9 && x >= 6 && x <= 9 ? "0" : "1"));
}
var DmWorkshop = class {
  root;
  container;
  onPlayDungeon;
  onBack;
  tabContent;
  roomsTab;
  dungeonsTab;
  rooms = [];
  dungeons = [];
  characters = [];
  constructor(container, onPlayDungeon, onBack) {
    this.container = container;
    this.onPlayDungeon = onPlayDungeon;
    this.onBack = onBack;
    this.root = el("div", { className: "dm-workshop" });
    const panel = el("div", { className: "session-panel workshop-panel" });
    panel.appendChild(el("h1", {}, "DM Workshop"));
    panel.appendChild(el("p", { className: "subtitle" }, "Build rooms, link them into dungeons, and play-test them."));
    const tabs = el("div", { className: "admin-tabs workshop-tabs" });
    tabs.appendChild(this.tabButton("Rooms", "rooms"));
    tabs.appendChild(this.tabButton("Dungeons", "dungeons"));
    panel.appendChild(tabs);
    this.tabContent = el("div", { className: "workshop-tab-content" });
    this.roomsTab = el("div", { className: "workshop-tab" });
    this.dungeonsTab = el("div", { className: "workshop-tab" });
    this.tabContent.appendChild(this.roomsTab);
    this.tabContent.appendChild(this.dungeonsTab);
    panel.appendChild(this.tabContent);
    panel.appendChild(el("button", { className: "enter workshop-back", onclick: () => this.onBack() }, "\u2190 Back"));
    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.switchTab("rooms");
    this.load();
  }
  tabButton(label, tab) {
    return el("button", {
      className: "admin-tab workshop-tab-btn",
      "data-tab": tab,
      onclick: () => this.switchTab(tab)
    }, label);
  }
  switchTab(tab) {
    this.roomsTab.style.display = tab === "rooms" ? "block" : "none";
    this.dungeonsTab.style.display = tab === "dungeons" ? "block" : "none";
    this.root.querySelectorAll(".workshop-tab-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-tab") === tab);
    });
  }
  async load() {
    try {
      const [{ rooms }, { dungeons }, { characters }] = await Promise.all([
        listRooms(),
        listDungeons(),
        listCharacters()
      ]);
      this.rooms = rooms;
      this.dungeons = dungeons;
      this.characters = characters;
      this.renderRooms();
      this.renderDungeons();
    } catch (err) {
      clear(this.roomsTab);
      this.roomsTab.appendChild(el("div", { className: "empty error" }, err.message || "Failed to load workshop data."));
    }
  }
  renderRooms() {
    clear(this.roomsTab);
    const header = el("div", { className: "workshop-section-header" });
    header.appendChild(el("h2", {}, "Rooms"));
    header.appendChild(el("button", {
      className: "enter",
      onclick: () => this.newRoom()
    }, "+ New Room"));
    this.roomsTab.appendChild(header);
    if (this.rooms.length === 0) {
      this.roomsTab.appendChild(el("div", { className: "empty" }, "No rooms yet. Create one to get started."));
      return;
    }
    const list = el("ul", { className: "session-list workshop-list" });
    this.rooms.forEach((room) => {
      const info = el("div", { className: "session-info" });
      info.appendChild(el("strong", {}, room.name));
      info.appendChild(el("span", {}, `Theme: ${THEME_LABELS[room.theme] || room.theme || "dungeon"}`));
      const controls = el("div", { className: "workshop-item-controls" });
      controls.appendChild(el("button", {
        className: "solo-hub-btn",
        onclick: () => this.editRoom(room)
      }, "Edit"));
      controls.appendChild(el("button", {
        className: "danger",
        onclick: () => this.deleteRoom(room)
      }, "Delete"));
      const row = el("li", {});
      row.appendChild(info);
      row.appendChild(controls);
      list.appendChild(row);
    });
    this.roomsTab.appendChild(list);
  }
  async newRoom() {
    try {
      const { room } = await createRoom({
        name: "New Room",
        theme: "dungeon",
        tiles: defaultTiles(),
        entities: []
      });
      this.editRoom(room);
    } catch (err) {
      alert(err.message || "Failed to create room");
    }
  }
  editRoom(room) {
    this.destroy();
    const editor = new RoomEditor(this.container, room, () => {
      editor.destroy();
      this.root = el("div", { className: "dm-workshop" });
      this.container.appendChild(this.root);
      this.load();
    }, () => this.onBack());
  }
  async deleteRoom(room) {
    if (!confirm(`Delete room "${room.name}"?`)) return;
    try {
      await deleteRoom(room.id);
      this.load();
    } catch (err) {
      alert(err.message || "Delete failed");
    }
  }
  renderDungeons() {
    clear(this.dungeonsTab);
    const header = el("div", { className: "workshop-section-header" });
    header.appendChild(el("h2", {}, "Dungeons"));
    header.appendChild(el("button", {
      className: "enter",
      onclick: () => this.newDungeon()
    }, "+ New Dungeon"));
    this.dungeonsTab.appendChild(header);
    if (this.dungeons.length === 0) {
      this.dungeonsTab.appendChild(el("div", { className: "empty" }, "No dungeons yet. Create one to get started."));
      return;
    }
    const list = el("ul", { className: "session-list workshop-list" });
    this.dungeons.forEach((dungeon) => {
      const info = el("div", { className: "session-info" });
      info.appendChild(el("strong", {}, dungeon.name));
      info.appendChild(el("span", {}, `${dungeon.public ? "Public" : "Private"} \xB7 ${(dungeon.room_order || []).length} rooms`));
      const controls = el("div", { className: "workshop-item-controls" });
      controls.appendChild(el("button", {
        className: "solo-hub-btn",
        onclick: () => this.editDungeon(dungeon)
      }, "Edit"));
      controls.appendChild(el("button", {
        className: "danger",
        onclick: () => this.deleteDungeon(dungeon)
      }, "Delete"));
      controls.appendChild(el("button", {
        className: "enter",
        onclick: () => this.openCharacterPicker(dungeon)
      }, "Play Test"));
      const row = el("li", {});
      row.appendChild(info);
      row.appendChild(controls);
      list.appendChild(row);
    });
    this.dungeonsTab.appendChild(list);
  }
  async newDungeon() {
    try {
      const { dungeon } = await createDungeon({
        name: "New Dungeon",
        room_order: [],
        links: []
      });
      this.editDungeon(dungeon);
    } catch (err) {
      alert(err.message || "Failed to create dungeon");
    }
  }
  editDungeon(dungeon) {
    this.destroy();
    const editor = new DungeonEditor(this.container, dungeon, this.rooms, () => {
      editor.destroy();
      this.root = el("div", { className: "dm-workshop" });
      this.container.appendChild(this.root);
      this.load();
    }, () => this.onBack(), (dungeonId) => {
      editor.destroy();
      const d = this.dungeons.find((x) => x.id === dungeonId) || { id: dungeonId, name: "Dungeon" };
      this.openCharacterPicker(d);
    });
  }
  async deleteDungeon(dungeon) {
    if (!confirm(`Delete dungeon "${dungeon.name}"?`)) return;
    try {
      await deleteDungeon(dungeon.id);
      this.load();
    } catch (err) {
      alert(err.message || "Delete failed");
    }
  }
  openCharacterPicker(dungeon) {
    this.destroy();
    const picker = el("div", { className: "dm-workshop" });
    const panel = el("div", { className: "session-panel workshop-panel" });
    panel.appendChild(el("h1", {}, "Play Test"));
    panel.appendChild(el("p", { className: "subtitle" }, `Choose a hero to test "${dungeon.name}".`));
    const list = el("div", { className: "characters-grid" });
    if (this.characters.length === 0) {
      list.appendChild(el("div", { className: "empty" }, "No heroes available. Create one first."));
    } else {
      this.characters.forEach((c) => {
        const card = el("div", {
          className: "character-card",
          onclick: () => {
            picker.remove();
            this.onPlayDungeon(dungeon.id, c.id);
          }
        });
        const portraitUrl = c.portrait_url || `/portraits/${(c.classes?.[0] || "generic").toLowerCase().replace(/\s+/g, "-")}.png`;
        card.appendChild(el("img", { className: "character-portrait", src: portraitUrl, alt: c.name }));
        card.appendChild(el("h3", {}, c.name));
        card.appendChild(el("p", {}, (c.classes || []).join(" / ")));
        list.appendChild(card);
      });
    }
    panel.appendChild(list);
    panel.appendChild(el("button", {
      className: "enter workshop-back",
      onclick: () => {
        picker.remove();
        this.root = el("div", { className: "dm-workshop" });
        this.container.appendChild(this.root);
        this.load();
      }
    }, "\u2190 Back"));
    picker.appendChild(panel);
    this.container.appendChild(picker);
    this.root = picker;
  }
  destroy() {
    this.root.remove();
  }
};
var RoomEditor = class {
  root;
  container;
  room;
  onSave;
  onBack;
  nameInput;
  themeSelect;
  gridEl;
  entityMode = false;
  activeTile = "0";
  tiles = [];
  entities = [];
  entityForm;
  entityFormTitle;
  entityFormX = 0;
  entityFormY = 0;
  entityTypeSelect;
  entityKeyInput;
  entityCountInput;
  entityDamageInput;
  entityValueInput;
  entityItemSelect;
  entityMessageInput;
  entityNameInput;
  entityBestiarySelect;
  entityFieldsEl;
  modeToggleBtn;
  items = [];
  bestiary = [];
  constructor(container, room, onSave, onBack) {
    this.container = container;
    this.room = room;
    this.onSave = onSave;
    this.onBack = onBack;
    this.width = Math.max(4, Math.min(64, room.width || 16));
    this.height = Math.max(4, Math.min(64, room.height || 16));
    this.tiles = this.ensureTiles(room.tiles, this.width, this.height);
    this.entities = (room.entities || []).slice();
    this.root = el("div", { className: "room-editor" });
    const panel = el("div", { className: "session-panel editor-panel" });
    panel.appendChild(el("h1", {}, `Edit Room: ${room.name}`));
    panel.appendChild(this.buildForm());
    panel.appendChild(this.buildToolbar());
    panel.appendChild(this.buildGrid());
    this.entityForm = this.buildEntityForm();
    this.entityForm.style.display = "none";
    panel.appendChild(this.entityForm);
    panel.appendChild(this.buildFooter());
    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.loadRefs();
  }
  ensureTiles(tiles, width, height) {
    const w = Math.max(4, Math.min(64, width || 16));
    const h = Math.max(4, Math.min(64, height || 16));
    return Array.from({ length: h }, (_, y) =>
      Array.from({ length: w }, (_, x) => tiles?.[y]?.[x] != null ? String(tiles[y][x]) : "1")
    );
  }
  async loadRefs() {
    try {
      const [{ items }, { monsters }] = await Promise.all([
        listItems().catch(() => ({ items: [] })),
        listBestiary().catch(() => ({ monsters: [] }))
      ]);
      this.items = items || [];
      this.bestiary = monsters || [];
      clear(this.entityItemSelect);
      this.items.forEach((i) => {
        const opt = document.createElement("option");
        opt.value = i.id;
        opt.textContent = i.name || i.id;
        this.entityItemSelect.appendChild(opt);
      });
      clear(this.entityBestiarySelect);
      this.bestiary.forEach((b) => {
        const opt = document.createElement("option");
        opt.value = b;
        opt.textContent = b;
        this.entityBestiarySelect.appendChild(opt);
      });
    } catch (err) {
      this.items = [];
      this.bestiary = [];
    }
  }
  buildForm() {
    const form = el("div", { className: "editor-form" });
    this.nameInput = el("input", { type: "text", value: this.room.name || "New Room" });
    this.themeSelect = el("select", {});
    const themes = ["cave", "dungeon", "library", "ice", "lava", "forest", "tomb", "sewer"];
    themes.forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = THEME_LABELS[t] || t;
      if (t === (this.room.theme || "dungeon")) opt.selected = true;
      this.themeSelect.appendChild(opt);
    });
    form.appendChild(el("label", {}, "Name"));
    form.appendChild(this.nameInput);
    form.appendChild(el("label", {}, "Theme"));
    form.appendChild(this.themeSelect);
    this.widthInput = el("input", { type: "number", value: String(this.width), min: "4", max: "64" });
    this.heightInput = el("input", { type: "number", value: String(this.height), min: "4", max: "64" });
    form.appendChild(el("label", {}, "Width"));
    form.appendChild(this.widthInput);
    form.appendChild(el("label", {}, "Height"));
    form.appendChild(this.heightInput);
    form.appendChild(el("button", {
      className: "solo-hub-btn",
      onclick: () => this.resizeGrid()
    }, "Resize Grid"));
    return form;
  }
  buildToolbar() {
    const toolbar = el("div", { className: "editor-toolbar" });
    const palette = el("div", { className: "tile-palette" });
    const tiles = [
      { key: "0", label: "Floor" },
      { key: "1", label: "Wall" },
      { key: "2", label: "Difficult" },
      { key: "3", label: "Hazard 1" },
      { key: "4", label: "Hazard 2" },
      { key: "5", label: "Event" }
    ];
    tiles.forEach((t) => {
      const btn = el("button", {
        className: `palette-btn palette-${t.key}${t.key === this.activeTile ? " active" : ""}`,
        onclick: () => this.selectTile(t.key)
      }, t.label);
      palette.appendChild(btn);
    });
    toolbar.appendChild(palette);
    this.modeToggleBtn = el("button", {
      className: "entity-toggle",
      onclick: () => this.toggleEntityMode()
    }, "Entity Mode: Off");
    toolbar.appendChild(this.modeToggleBtn);
    return toolbar;
  }
  selectTile(key) {
    this.activeTile = key;
    this.entityMode = false;
    this.modeToggleBtn.textContent = "Entity Mode: Off";
    this.entityForm.style.display = "none";
    this.root.querySelectorAll(".palette-btn").forEach((b) => {
      b.classList.toggle("active", b.classList.contains(`palette-${this.activeTile}`));
    });
  }
  toggleEntityMode() {
    this.entityMode = !this.entityMode;
    this.modeToggleBtn.textContent = `Entity Mode: ${this.entityMode ? "On" : "Off"}`;
    this.entityForm.style.display = "none";
  }
  buildGrid() {
    this.gridEl = el("div", { className: "room-grid" });
    this.renderGrid();
    return this.gridEl;
  }
  resizeGrid() {
    const newW = Math.max(4, Math.min(64, parseInt(this.widthInput.value, 10) || 16));
    const newH = Math.max(4, Math.min(64, parseInt(this.heightInput.value, 10) || 16));
    const old = this.tiles;
    this.tiles = Array.from({ length: newH }, (_, y) =>
      Array.from({ length: newW }, (_, x) => old[y]?.[x] != null ? old[y][x] : "1")
    );
    this.width = newW;
    this.height = newH;
    this.widthInput.value = String(newW);
    this.heightInput.value = String(newH);
    this.renderGrid();
  }
  renderGrid() {
    clear(this.gridEl);
    this.gridEl.style.gridTemplateColumns = `repeat(${this.width}, 24px)`;
    for (let y = 0; y < this.height; y++) {
      for (let x = 0; x < this.width; x++) {
        const tile = this.tiles[y][x];
        const entity = this.entities.find((e) => e.x === x && e.y === y);
        const cell = el("div", {
          className: `room-grid-cell tile-${tile}${entity ? " has-entity" : ""}`,
          onclick: () => this.onCellClick(x, y)
        });
        if (entity) {
          cell.appendChild(el("span", { className: "entity-marker" }, entity.type[0].toUpperCase()));
          cell.title = `${entity.type}: ${entity.name || entity.key || entity.message || ""}`;
        }
        this.gridEl.appendChild(cell);
      }
    }
  }
  onCellClick(x, y) {
    if (this.entityMode) {
      this.entityFormX = x;
      this.entityFormY = y;
      this.showEntityForm(x, y);
      return;
    }
    this.tiles[y][x] = this.activeTile;
    this.renderGrid();
  }
  buildEntityForm() {
    const form = el("div", { className: "entity-form" });
    this.entityTypeSelect = el("select", {});
    ["monster", "trap", "treasure", "item", "event"].forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = t;
      this.entityTypeSelect.appendChild(opt);
    });
    this.entityKeyInput = el("input", { type: "text", placeholder: "key / label" });
    this.entityCountInput = el("input", { type: "number", placeholder: "count", value: "1" });
    this.entityDamageInput = el("input", { type: "text", placeholder: "damage e.g. 1d6" });
    this.entityValueInput = el("input", { type: "number", placeholder: "gold value", value: "0" });
    this.entityItemSelect = el("select", {});
    this.entityMessageInput = el("input", { type: "text", placeholder: "message" });
    this.entityNameInput = el("input", { type: "text", placeholder: "custom name" });
    this.entityBestiarySelect = el("select", {});
    this.entityFieldsEl = el("div", { className: "entity-fields" });
    this.entityTypeSelect.onchange = () => this.renderEntityFields();
    form.appendChild(el("label", {}, "Entity Type"));
    form.appendChild(this.entityTypeSelect);
    form.appendChild(this.entityFieldsEl);
    form.appendChild(el("button", {
      className: "enter",
      onclick: () => this.addEntity()
    }, "Add Entity"));
    form.appendChild(el("button", {
      className: "danger",
      onclick: () => this.removeEntity()
    }, "Remove Entity"));
    form.appendChild(el("button", {
      onclick: () => {
        this.entityForm.style.display = "none";
      }
    }, "Cancel"));
    this.renderEntityFields();
    return form;
  }
  renderEntityFields() {
    clear(this.entityFieldsEl);
    const type = this.entityTypeSelect.value;
    if (type === "monster") {
      this.entityFieldsEl.appendChild(el("label", {}, "Bestiary"));
      this.entityFieldsEl.appendChild(this.entityBestiarySelect);
      this.entityFieldsEl.appendChild(el("label", {}, "Count"));
      this.entityFieldsEl.appendChild(this.entityCountInput);
      this.entityFieldsEl.appendChild(el("label", {}, "Name (optional)"));
      this.entityFieldsEl.appendChild(this.entityNameInput);
    } else if (type === "trap") {
      this.entityFieldsEl.appendChild(el("label", {}, "Label"));
      this.entityFieldsEl.appendChild(this.entityKeyInput);
      this.entityFieldsEl.appendChild(el("label", {}, "Damage"));
      this.entityFieldsEl.appendChild(this.entityDamageInput);
    } else if (type === "treasure") {
      this.entityFieldsEl.appendChild(el("label", {}, "Gold"));
      this.entityFieldsEl.appendChild(this.entityValueInput);
      this.entityFieldsEl.appendChild(el("label", {}, "Item (optional)"));
      this.entityFieldsEl.appendChild(this.entityItemSelect);
    } else if (type === "item") {
      this.entityFieldsEl.appendChild(el("label", {}, "Item"));
      this.entityFieldsEl.appendChild(this.entityItemSelect);
    } else if (type === "event") {
      this.entityFieldsEl.appendChild(el("label", {}, "Message"));
      this.entityFieldsEl.appendChild(this.entityMessageInput);
    }
  }
  showEntityForm(x, y) {
    this.entityForm.style.display = "block";
    if (this.entityFormTitle) this.entityFormTitle.remove();
    this.entityFormTitle = el("h4", {}, `Entity at ${x}, ${y}`);
    this.entityForm.insertBefore(this.entityFormTitle, this.entityForm.firstChild);
    const existing = this.entities.find((e) => e.x === x && e.y === y);
    this.entityTypeSelect.value = existing?.type || "monster";
    this.renderEntityFields();
    if (existing) {
      if (existing.type === "monster") {
        this.entityBestiarySelect.value = existing.key || "";
        this.entityCountInput.value = String(existing.count || 1);
        this.entityNameInput.value = existing.name || "";
      } else if (existing.type === "trap") {
        this.entityKeyInput.value = existing.key || "";
        this.entityDamageInput.value = existing.damage || "";
      } else if (existing.type === "treasure") {
        this.entityValueInput.value = String(existing.value || 0);
        this.entityItemSelect.value = existing.item_id || "";
      } else if (existing.type === "item") {
        this.entityItemSelect.value = existing.item_id || "";
      } else if (existing.type === "event") {
        this.entityMessageInput.value = existing.message || "";
      }
    } else {
      this.entityKeyInput.value = "";
      this.entityCountInput.value = "1";
      this.entityDamageInput.value = "";
      this.entityValueInput.value = "0";
      this.entityMessageInput.value = "";
      this.entityNameInput.value = "";
      if (this.bestiary.length > 0) this.entityBestiarySelect.value = this.bestiary[0];
      if (this.items.length > 0) this.entityItemSelect.value = this.items[0]?.id || "";
    }
  }
  addEntity() {
    const type = this.entityTypeSelect.value;
    const base = { type, x: this.entityFormX, y: this.entityFormY };
    let entity;
    if (type === "monster") {
      entity = {
        ...base,
        key: this.entityBestiarySelect.value || this.entityKeyInput.value || "goblin",
        count: parseInt(this.entityCountInput.value, 10) || 1,
        name: this.entityNameInput.value || void 0
      };
    } else if (type === "trap") {
      entity = {
        ...base,
        key: this.entityKeyInput.value || "trap",
        damage: this.entityDamageInput.value || "1d6"
      };
    } else if (type === "treasure") {
      entity = {
        ...base,
        value: parseInt(this.entityValueInput.value, 10) || 0,
        item_id: this.entityItemSelect.value || void 0
      };
    } else if (type === "item") {
      entity = { ...base, item_id: this.entityItemSelect.value };
    } else if (type === "event") {
      entity = { ...base, message: this.entityMessageInput.value || "" };
    }
    this.entities = this.entities.filter((e) => !(e.x === this.entityFormX && e.y === this.entityFormY));
    this.entities.push(entity);
    this.entityForm.style.display = "none";
    this.renderGrid();
  }
  removeEntity() {
    this.entities = this.entities.filter((e) => !(e.x === this.entityFormX && e.y === this.entityFormY));
    this.entityForm.style.display = "none";
    this.renderGrid();
  }
  buildFooter() {
    const footer = el("div", { className: "editor-footer" });
    footer.appendChild(el("button", {
      className: "enter",
      onclick: () => this.save()
    }, "Save"));
    footer.appendChild(el("button", {
      className: "danger",
      onclick: () => this.onBack()
    }, "Back"));
    return footer;
  }
  async save() {
    try {
      await updateRoom(this.room.id, {
        name: this.nameInput.value.trim() || this.room.name,
        theme: this.themeSelect.value,
        width: this.width,
        height: this.height,
        tiles: this.tiles,
        entities: this.entities
      });
      this.onSave();
    } catch (err) {
      alert(err.message || "Save failed");
    }
  }
  destroy() {
    this.root.remove();
  }
};
var DungeonEditor = class {
  root;
  container;
  dungeon;
  rooms;
  onSave;
  onBack;
  onPlayTest;
  nameInput;
  publicCheckbox;
  roomOrderEl;
  linksEl;
  linkSourceSelect;
  linkTargetSelect;
  linkKindSelect;
  sourceGridEl;
  targetGridEl;
  startRoomSelect;
  startXInput;
  startYInput;
  sourceRoomId;
  targetRoomId;
  sourcePoint;
  targetPoint;
  constructor(container, dungeon, rooms, onSave, onBack, onPlayTest) {
    this.container = container;
    this.dungeon = dungeon;
    this.rooms = rooms;
    this.onSave = onSave;
    this.onBack = onBack;
    this.onPlayTest = onPlayTest;
    this.sourceRoomId = dungeon.start_room_id || dungeon.room_order?.[0] || null;
    this.targetRoomId = dungeon.room_order?.[0] || null;
    this.sourcePoint = null;
    this.targetPoint = null;
    this.root = el("div", { className: "dungeon-editor" });
    const panel = el("div", { className: "session-panel editor-panel" });
    panel.appendChild(el("h1", {}, `Edit Dungeon: ${dungeon.name}`));
    panel.appendChild(this.buildForm());
    panel.appendChild(this.buildRoomPool());
    panel.appendChild(this.buildRoomOrder());
    panel.appendChild(this.buildStartRoom());
    panel.appendChild(this.buildLinkEditor());
    panel.appendChild(this.buildFooter());
    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.renderRoomOrder();
    this.renderLinks();
    this.renderSourceGrid();
    this.renderTargetGrid();
  }
  buildForm() {
    const form = el("div", { className: "editor-form" });
    this.nameInput = el("input", { type: "text", value: this.dungeon.name || "New Dungeon" });
    this.publicCheckbox = el("input", { type: "checkbox", checked: !!this.dungeon.public });
    form.appendChild(el("label", {}, "Name"));
    form.appendChild(this.nameInput);
    const pubLabel = el("label", { className: "checkbox-label" });
    pubLabel.appendChild(this.publicCheckbox);
    pubLabel.appendChild(document.createTextNode(" Public"));
    form.appendChild(pubLabel);
    return form;
  }
  buildRoomPool() {
    const section = el("div", { className: "workshop-section" });
    section.appendChild(el("h2", {}, "Available Rooms"));
    if (this.rooms.length === 0) {
      section.appendChild(el("div", { className: "empty" }, "No rooms available. Create rooms first."));
      return section;
    }
    const grid = el("div", { className: "room-pool-grid" });
    this.rooms.forEach((room) => {
      const card = el("div", { className: "room-thumb" });
      card.appendChild(el("strong", {}, room.name));
      card.appendChild(el("span", {}, THEME_LABELS[room.theme] || room.theme || "dungeon"));
      card.appendChild(el("button", {
        className: "enter",
        onclick: () => this.addRoom(room.id)
      }, "Add"));
      grid.appendChild(card);
    });
    section.appendChild(grid);
    return section;
  }
  addRoom(roomId) {
    const order = this.dungeon.room_order || [];
    if (order.includes(roomId)) return;
    order.push(roomId);
    this.dungeon.room_order = order;
    if (!this.dungeon.start_room_id) {
      this.dungeon.start_room_id = roomId;
    }
    if (!this.sourceRoomId) this.sourceRoomId = roomId;
    if (!this.targetRoomId) this.targetRoomId = roomId;
    this.renderRoomOrder();
    this.renderStartRoom();
    this.updateLinkSelects();
    this.renderSourceGrid();
    this.renderTargetGrid();
  }
  buildRoomOrder() {
    const section = el("div", { className: "workshop-section" });
    section.appendChild(el("h2", {}, "Room Order"));
    this.roomOrderEl = el("ul", { className: "session-list order-list" });
    section.appendChild(this.roomOrderEl);
    return section;
  }
  renderRoomOrder() {
    clear(this.roomOrderEl);
    const order = this.dungeon.room_order || [];
    if (order.length === 0) {
      this.roomOrderEl.appendChild(el("li", { className: "empty" }, "No rooms added."));
      return;
    }
    order.forEach((roomId, index) => {
      const room = this.rooms.find((r) => r.id === roomId);
      const name = room ? room.name : roomId;
      const row = el("li", {});
      const info = el("div", { className: "session-info" });
      info.appendChild(el("strong", {}, `${index + 1}. ${name}`));
      row.appendChild(info);
      const controls = el("div", { className: "workshop-item-controls" });
      controls.appendChild(el("button", {
        disabled: index === 0,
        onclick: () => this.moveRoom(index, -1)
      }, "\u2191"));
      controls.appendChild(el("button", {
        disabled: index === order.length - 1,
        onclick: () => this.moveRoom(index, 1)
      }, "\u2193"));
      controls.appendChild(el("button", {
        className: "danger",
        onclick: () => this.removeRoom(index)
      }, "Remove"));
      row.appendChild(controls);
      this.roomOrderEl.appendChild(row);
    });
  }
  moveRoom(index, delta) {
    const order = this.dungeon.room_order || [];
    const newIndex = index + delta;
    if (newIndex < 0 || newIndex >= order.length) return;
    [order[index], order[newIndex]] = [order[newIndex], order[index]];
    this.renderRoomOrder();
  }
  removeRoom(index) {
    const order = this.dungeon.room_order || [];
    const removed = order.splice(index, 1)[0];
    if (this.dungeon.start_room_id === removed) {
      this.dungeon.start_room_id = order[0] || null;
    }
    if (this.sourceRoomId === removed) {
      this.sourceRoomId = order[0] || null;
      this.sourcePoint = null;
    }
    if (this.targetRoomId === removed) {
      this.targetRoomId = order[0] || null;
      this.targetPoint = null;
    }
    this.dungeon.links = (this.dungeon.links || []).filter(
      (l) => l.source_room_id !== removed && l.target_room_id !== removed
    );
    this.renderRoomOrder();
    this.renderStartRoom();
    this.updateLinkSelects();
    this.renderSourceGrid();
    this.renderTargetGrid();
  }
  buildStartRoom() {
    const section = el("div", { className: "workshop-section" });
    section.appendChild(el("h2", {}, "Start Position"));
    const form = el("div", { className: "editor-form inline" });
    this.startRoomSelect = el("select", {
      onchange: () => this.updateStartBounds()
    });
    this.startXInput = el("input", { type: "number", min: 1, max: 14, value: this.dungeon.start_x ?? 8 });
    this.startYInput = el("input", { type: "number", min: 1, max: 14, value: this.dungeon.start_y ?? 8 });
    this.updateStartRoomOptions();
    this.updateStartBounds();
    form.appendChild(el("label", {}, "Start Room"));
    form.appendChild(this.startRoomSelect);
    form.appendChild(el("label", {}, "X"));
    form.appendChild(this.startXInput);
    form.appendChild(el("label", {}, "Y"));
    form.appendChild(this.startYInput);
    section.appendChild(form);
    return section;
  }
  updateStartBounds() {
    const roomId = this.startRoomSelect.value;
    const room = this.rooms.find((r) => r.id === roomId);
    const w = Math.max(4, Math.min(64, room?.width || 16));
    const h = Math.max(4, Math.min(64, room?.height || 16));
    this.startXInput.max = String(Math.max(1, w - 2));
    this.startYInput.max = String(Math.max(1, h - 2));
    const x = Math.max(1, Math.min(parseInt(this.startXInput.value, 10) || 1, w - 2));
    const y = Math.max(1, Math.min(parseInt(this.startYInput.value, 10) || 1, h - 2));
    this.startXInput.value = String(x);
    this.startYInput.value = String(y);
  }
  updateStartRoomOptions() {
    clear(this.startRoomSelect);
    const order = this.dungeon.room_order || [];
    if (order.length === 0) {
      const opt = document.createElement("option");
      opt.textContent = "No rooms";
      this.startRoomSelect.appendChild(opt);
      return;
    }
    order.forEach((roomId) => {
      const room = this.rooms.find((r) => r.id === roomId);
      const opt = document.createElement("option");
      opt.value = roomId;
      opt.textContent = room ? room.name : roomId;
      if (roomId === this.dungeon.start_room_id) opt.selected = true;
      this.startRoomSelect.appendChild(opt);
    });
  }
  renderStartRoom() {
    this.updateStartRoomOptions();
    this.updateStartBounds();
  }
  buildLinkEditor() {
    const section = el("div", { className: "workshop-section link-editor" });
    section.appendChild(el("h2", {}, "Links"));
    const controls = el("div", { className: "link-controls" });
    this.linkSourceSelect = el("select", {
      onchange: () => {
        this.sourceRoomId = this.linkSourceSelect.value;
        this.sourcePoint = null;
        this.renderSourceGrid();
      }
    });
    this.linkTargetSelect = el("select", {
      onchange: () => {
        this.targetRoomId = this.linkTargetSelect.value;
        this.targetPoint = null;
        this.renderTargetGrid();
      }
    });
    this.linkKindSelect = el("select", {});
    ["passage", "stairs", "teleport"].forEach((k) => {
      const opt = document.createElement("option");
      opt.value = k;
      opt.textContent = k;
      this.linkKindSelect.appendChild(opt);
    });
    controls.appendChild(el("label", {}, "Source"));
    controls.appendChild(this.linkSourceSelect);
    controls.appendChild(el("label", {}, "Target"));
    controls.appendChild(this.linkTargetSelect);
    controls.appendChild(el("label", {}, "Kind"));
    controls.appendChild(this.linkKindSelect);
    controls.appendChild(el("button", {
      className: "enter",
      onclick: () => this.addLink()
    }, "Add Link"));
    section.appendChild(controls);
    const grids = el("div", { className: "link-grids" });
    this.sourceGridEl = el("div", { className: "link-grid-wrap" });
    this.targetGridEl = el("div", { className: "link-grid-wrap" });
    grids.appendChild(this.sourceGridEl);
    grids.appendChild(this.targetGridEl);
    section.appendChild(grids);
    this.linksEl = el("ul", { className: "session-list links-list" });
    section.appendChild(this.linksEl);
    this.updateLinkSelects();
    return section;
  }
  updateLinkSelects() {
    clear(this.linkSourceSelect);
    clear(this.linkTargetSelect);
    const order = this.dungeon.room_order || [];
    order.forEach((roomId) => {
      const room = this.rooms.find((r) => r.id === roomId);
      const name = room ? room.name : roomId;
      const srcOpt = document.createElement("option");
      srcOpt.value = roomId;
      srcOpt.textContent = name;
      if (roomId === this.sourceRoomId) srcOpt.selected = true;
      this.linkSourceSelect.appendChild(srcOpt);
      const tgtOpt = document.createElement("option");
      tgtOpt.value = roomId;
      tgtOpt.textContent = name;
      if (roomId === this.targetRoomId) tgtOpt.selected = true;
      this.linkTargetSelect.appendChild(tgtOpt);
    });
  }
  renderSourceGrid() {
    clear(this.sourceGridEl);
    const room = this.rooms.find((r) => r.id === this.sourceRoomId);
    this.sourceGridEl.appendChild(el("h3", {}, `Source: ${room ? room.name : "None"}`));
    if (!room) return;
    const grid = this.buildMiniGrid(room, this.sourcePoint, (x, y) => {
      this.sourcePoint = { x, y };
      this.renderSourceGrid();
    });
    this.sourceGridEl.appendChild(grid);
  }
  renderTargetGrid() {
    clear(this.targetGridEl);
    const room = this.rooms.find((r) => r.id === this.targetRoomId);
    this.targetGridEl.appendChild(el("h3", {}, `Target: ${room ? room.name : "None"}`));
    if (!room) return;
    const grid = this.buildMiniGrid(room, this.targetPoint, (x, y) => {
      this.targetPoint = { x, y };
      this.renderTargetGrid();
    });
    this.targetGridEl.appendChild(grid);
  }
  buildMiniGrid(room, selectedPoint, onClick) {
    const grid = el("div", { className: "room-grid link-grid" });
    const w = Math.max(4, Math.min(64, room.width || 16));
    const h = Math.max(4, Math.min(64, room.height || 16));
    grid.style.gridTemplateColumns = `repeat(${w}, 16px)`;
    const tiles = room.tiles || [];
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const tile = tiles[y]?.[x] ?? "1";
        const isSelected = selectedPoint && selectedPoint.x === x && selectedPoint.y === y;
        const cell = el("div", {
          className: `room-grid-cell tile-${tile}${isSelected ? " selected" : ""}`,
          onclick: () => onClick(x, y)
        });
        grid.appendChild(cell);
      }
    }
    return grid;
  }
  addLink() {
    if (!this.sourceRoomId || !this.targetRoomId || !this.sourcePoint || !this.targetPoint) {
      alert("Select source room, target room, and both link points.");
      return;
    }
    const link = {
      source_room_id: this.sourceRoomId,
      source_x: this.sourcePoint.x,
      source_y: this.sourcePoint.y,
      target_room_id: this.targetRoomId,
      target_x: this.targetPoint.x,
      target_y: this.targetPoint.y,
      kind: this.linkKindSelect.value
    };
    this.dungeon.links = this.dungeon.links || [];
    this.dungeon.links.push(link);
    this.sourcePoint = null;
    this.targetPoint = null;
    this.renderSourceGrid();
    this.renderTargetGrid();
    this.renderLinks();
  }
  deleteLink(index) {
    this.dungeon.links.splice(index, 1);
    this.renderLinks();
  }
  renderLinks() {
    clear(this.linksEl);
    const links = this.dungeon.links || [];
    if (links.length === 0) {
      this.linksEl.appendChild(el("li", { className: "empty" }, "No links yet."));
      return;
    }
    links.forEach((link, index) => {
      const src = this.rooms.find((r) => r.id === link.source_room_id);
      const tgt = this.rooms.find((r) => r.id === link.target_room_id);
      const text = `${src ? src.name : link.source_room_id} (${link.source_x},${link.source_y}) \u2192 ${tgt ? tgt.name : link.target_room_id} (${link.target_x},${link.target_y}) [${link.kind}]`;
      const row = el("li", {});
      row.appendChild(el("span", { className: "link-text" }, text));
      row.appendChild(el("button", {
        className: "danger",
        onclick: () => this.deleteLink(index)
      }, "Delete"));
      this.linksEl.appendChild(row);
    });
  }
  buildFooter() {
    const footer = el("div", { className: "editor-footer" });
    footer.appendChild(el("button", {
      className: "enter",
      onclick: () => this.save()
    }, "Save"));
    footer.appendChild(el("button", {
      className: "enter",
      onclick: () => this.onPlayTest(this.dungeon.id)
    }, "Play Test"));
    footer.appendChild(el("button", {
      className: "danger",
      onclick: () => this.onBack()
    }, "Back"));
    return footer;
  }
  async save() {
    const order = this.dungeon.room_order || [];
    const links = this.dungeon.links || [];
    if (order.length > 1 && links.length === 0) {
      if (!confirm("This dungeon has multiple rooms but no links. Players will be stuck in the first room. Save anyway?")) return;
    }
    try {
      await updateDungeon(this.dungeon.id, {
        name: this.nameInput.value.trim() || this.dungeon.name,
        public: this.publicCheckbox.checked,
        room_order: order,
        links: links,
        start_room_id: this.startRoomSelect.value || null,
        start_x: parseInt(this.startXInput.value, 10) || 1,
        start_y: parseInt(this.startYInput.value, 10) || 1
      });
      this.onSave();
    } catch (err) {
      alert(err.message || "Save failed");
    }
  }
  destroy() {
    this.root.remove();
  }
};

// src/ui/campaign-lobby.ts
var CampaignLobby = class _CampaignLobby {
  root;
  container;
  onSelect;
  onBack;
  listEl;
  user = null;
  adminBar = null;
  constructor(container, onSelect, onBack) {
    this.root = el("div", { className: "adventure-manager" });
    this.container = container;
    this.onSelect = onSelect;
    this.onBack = onBack;
    const background = el("div", { className: "adventure-manager-background" });
    const vignette = el("div", { className: "adventure-manager-vignette" });
    const shell = el("div", { className: "adventure-manager-shell" });
    shell.appendChild(this.buildHeader());
    shell.appendChild(this.buildForms());
    const listHeader = el("div", { className: "campaign-list-header" });
    listHeader.appendChild(el("h2", {}, "Your Campaigns"));
    this.adminBar = el("div", { className: "admin-bar" });
    this.adminBar.style.display = "none";
    listHeader.appendChild(this.adminBar);
    shell.appendChild(listHeader);
    this.listEl = el("div", { className: "campaigns-grid" });
    shell.appendChild(this.listEl);
    shell.appendChild(this.buildFooter());
    this.root.appendChild(background);
    this.root.appendChild(vignette);
    this.root.appendChild(shell);
    container.appendChild(this.root);
    this.load();
  }
  buildHeader() {
    const header = el("header", { className: "adventure-manager-header" });
    const title = el("div", { className: "adventure-manager-title" });
    title.appendChild(el("h1", {}, "Campaigns"));
    title.appendChild(el("p", {}, "Create a private campaign, join one by ID and password, or manage your existing campaigns."));
    header.appendChild(title);
    header.appendChild(el("button", { className: "adventure-manager-back", onclick: () => this.onBack() }, "\u2190 Back to Sanctuary"));
    return header;
  }
  buildForms() {
    const forms = el("div", { className: "campaign-forms" });
    const createCard = el("div", { className: "campaign-form-card" });
    createCard.appendChild(el("h3", {}, "Create Campaign"));
    createCard.appendChild(el("p", {}, "Start a new campaign for your friends. Set a password to keep it private."));
    const nameInput = el("input", { type: "text", placeholder: "Campaign name" });
    const passInput = el("input", { type: "text", placeholder: "Share password" });
    const createBtn = el("button", {
      className: "enter",
      onclick: async () => {
        const name = nameInput.value.trim();
        const password = passInput.value.trim();
        if (!name || !password) return;
        try {
          const { campaign } = await createCampaign({ name, password });
          this.onSelect(campaign);
        } catch (err) {
          alert(err.message || "Create failed");
        }
      }
    }, "Create Campaign");
    createCard.appendChild(nameInput);
    createCard.appendChild(passInput);
    createCard.appendChild(createBtn);
    forms.appendChild(createCard);
    const joinCard = el("div", { className: "campaign-form-card" });
    joinCard.appendChild(el("h3", {}, "Join Campaign"));
    joinCard.appendChild(el("p", {}, "Enter the campaign ID and password shared by the DM."));
    const idInput = el("input", { type: "text", placeholder: "Campaign ID" });
    const joinPassInput = el("input", { type: "text", placeholder: "Password" });
    const joinBtn = el("button", {
      className: "enter",
      onclick: async () => {
        const id = idInput.value.trim();
        const password = joinPassInput.value.trim();
        if (!id || !password) return;
        try {
          await joinCampaign(id, password);
          const { campaign } = await getCampaign(id);
          this.onSelect(campaign);
        } catch (err) {
          alert(err.message || "Join failed");
        }
      }
    }, "Join Campaign");
    joinCard.appendChild(idInput);
    joinCard.appendChild(joinPassInput);
    joinCard.appendChild(joinBtn);
    forms.appendChild(joinCard);
    return forms;
  }
  buildFooter() {
    const footer = el("footer", { className: "adventure-manager-footer" });
    footer.appendChild(el("button", { className: "adventure-manager-back", onclick: () => this.onBack() }, "\u2190 Back to Sanctuary"));
    return footer;
  }
  async load() {
    try {
      const [{ campaigns }, userData] = await Promise.all([
        listCampaigns(),
        whoami().catch(() => ({ user: { id: 0, name: "", is_admin: false } }))
      ]);
      this.user = userData.user;
      this.render(campaigns);
      this.renderAdminBar();
    } catch (err) {
      clear(this.listEl);
      this.listEl.appendChild(el("div", { className: "campaigns-empty error" }, err.message || "Failed to load campaigns."));
    }
  }
  renderAdminBar() {
    if (!this.adminBar || !this.user?.is_admin) return;
    clear(this.adminBar);
    this.adminBar.style.display = "flex";
    this.adminBar.appendChild(el("span", { className: "admin-badge" }, "Admin"));
    this.adminBar.appendChild(el("button", {
      onclick: () => this.showAdminPanel()
    }, "Open Admin Panel"));
  }
  showAdminPanel() {
    this.destroy();
    new AdminPanel(this.container, () => {
      new _CampaignLobby(this.container, this.onSelect, this.onBack);
    });
  }
  render(campaigns) {
    clear(this.listEl);
    if (campaigns.length === 0) {
      const empty2 = el("div", { className: "campaigns-empty" });
      empty2.appendChild(el("h3", {}, "No campaigns yet"));
      empty2.appendChild(el("p", {}, "Create a campaign above or join an existing one to get started."));
      this.listEl.appendChild(empty2);
      return;
    }
    campaigns.forEach((c) => {
      const total = c.module_ids.length;
      const cleared = (c.cleared_module_ids || []).length;
      const progressText = total > 0 ? `Progress ${cleared}/${total}` : "No modules";
      const card = el("div", { className: "campaign-card", onclick: () => this.onSelect(c) });
      const header = el("div", { className: "campaign-card-header" });
      header.appendChild(el("span", { className: "campaign-ruleset" }, c.ruleset_id));
      header.appendChild(el("span", { className: c.is_dm ? "campaign-role dm" : "campaign-role" }, c.is_dm ? "DM" : "Player"));
      card.appendChild(header);
      const body = el("div", { className: "campaign-card-body" });
      body.appendChild(el("h3", {}, c.name));
      body.appendChild(el("p", {}, progressText));
      if (c.completed) {
        body.appendChild(el("span", { className: "campaign-completed" }, "Completed"));
      }
      card.appendChild(body);
      const footer = el("div", { className: "campaign-card-footer" });
      footer.appendChild(el("span", { className: "campaign-id" }, c.id));
      footer.appendChild(el("span", {}, "Open \u2192"));
      card.appendChild(footer);
      this.listEl.appendChild(card);
    });
  }
  destroy() {
    this.root.remove();
  }
};

// src/ui/campaign-detail.ts
var CampaignDetail = class {
  root;
  campaign;
  onStartNew;
  onJoinSession;
  onBack;
  sessionsEl;
  membersEl;
  characters = [];
  members = [];
  constructor(container, campaign, onStartNew, onJoinSession, onBack) {
    this.root = el("div", { className: "adventure-manager" });
    this.campaign = campaign;
    this.onStartNew = onStartNew;
    this.onJoinSession = onJoinSession;
    this.onBack = onBack;
    const background = el("div", { className: "adventure-manager-background" });
    const vignette = el("div", { className: "adventure-manager-vignette" });
    const shell = el("div", { className: "adventure-manager-shell" });
    shell.appendChild(this.buildHeader());
    const main = el("main", { className: "campaign-detail-main" });
    const sessionsSection = el("section", { className: "campaign-detail-section" });
    const sessionsHeader = el("div", { className: "campaign-section-header" });
    sessionsHeader.appendChild(el("h2", {}, "Active Sessions"));
    if (campaign.is_dm) {
      sessionsHeader.appendChild(el("button", {
        className: "enter",
        onclick: () => this.onStartNew(campaign)
      }, "+ Start Session"));
    }
    sessionsSection.appendChild(sessionsHeader);
    this.sessionsEl = el("div", { className: "campaign-sessions-grid" });
    sessionsSection.appendChild(this.sessionsEl);
    main.appendChild(sessionsSection);
    const membersSection = el("section", { className: "campaign-detail-section" });
    membersSection.appendChild(el("h2", {}, "Members"));
    this.membersEl = el("div", { className: "members-list" });
    membersSection.appendChild(this.membersEl);
    main.appendChild(membersSection);
    shell.appendChild(main);
    shell.appendChild(this.buildFooter());
    this.root.appendChild(background);
    this.root.appendChild(vignette);
    this.root.appendChild(shell);
    container.appendChild(this.root);
    this.load();
  }
  buildHeader() {
    const header = el("header", { className: "adventure-manager-header" });
    const title = el("div", { className: "adventure-manager-title" });
    title.appendChild(el("h1", {}, this.campaign.name));
    const roleText = this.campaign.is_dm ? "You are the DM" : "Player";
    const total = this.campaign.module_ids.length;
    const cleared = (this.campaign.cleared_module_ids || []).length;
    const progress = total > 0 ? `${cleared}/${total} modules cleared` : "No modules assigned";
    title.appendChild(el("p", {}, `${this.campaign.ruleset_id} \xB7 ${roleText} \xB7 ${progress}`));
    header.appendChild(title);
    header.appendChild(el("button", { className: "adventure-manager-back", onclick: () => this.onBack() }, "\u2190 Back to Campaigns"));
    return header;
  }
  buildFooter() {
    const footer = el("footer", { className: "adventure-manager-footer" });
    footer.appendChild(el("button", { className: "adventure-manager-back", onclick: () => this.onBack() }, "\u2190 Back to Campaigns"));
    return footer;
  }
  async load() {
    try {
      const [{ sessions }, { characters }, { members }] = await Promise.all([
        listCampaignSessions(this.campaign.id),
        listCharacters(),
        getCampaignMembers(this.campaign.id)
      ]);
      this.characters = characters;
      this.members = members;
      this.render(sessions);
      this.renderMembers();
    } catch (err) {
      clear(this.sessionsEl);
      this.sessionsEl.appendChild(el("div", { className: "campaigns-empty error" }, err.message || "Failed to load sessions."));
    }
  }
  render(sessions) {
    clear(this.sessionsEl);
    if (sessions.length === 0) {
      const empty2 = el("div", { className: "campaigns-empty" });
      empty2.appendChild(el("p", {}, "No active sessions. Start one to bring the party together."));
      if (this.campaign.is_dm) {
        empty2.appendChild(el("button", {
          className: "enter",
          onclick: () => this.onStartNew(this.campaign)
        }, "Start New Session"));
      }
      this.sessionsEl.appendChild(empty2);
      return;
    }
    sessions.forEach((s) => {
      const phaseText = s.phase === "player" ? "Player Turn" : "DM's Turn";
      const card = el("div", { className: "session-card" });
      const header = el("div", { className: "session-card-header" });
      header.appendChild(el("span", { className: "session-status active" }, "Active"));
      header.appendChild(el("span", { className: "session-turn" }, `Turn ${s.turn}`));
      card.appendChild(header);
      const body = el("div", { className: "session-card-body" });
      body.appendChild(el("h3", {}, s.name));
      body.appendChild(el("p", {}, `${phaseText} \xB7 ${s.player_count} adventurer${s.player_count === 1 ? "" : "s"}`));
      card.appendChild(body);
      const actions = el("div", { className: "session-card-actions" });
      const select = el("select", {});
      if (this.characters.length === 0) {
        const opt = document.createElement("option");
        opt.textContent = "No characters";
        opt.value = "";
        select.appendChild(opt);
        select.disabled = true;
      } else {
        this.characters.forEach((c) => {
          const opt = document.createElement("option");
          opt.value = c.id ?? "";
          opt.textContent = c.name;
          select.appendChild(opt);
        });
      }
      actions.appendChild(select);
      actions.appendChild(el("button", {
        className: "enter",
        disabled: this.characters.length === 0,
        onclick: async () => {
          if (!select.value) return;
          try {
            await joinSession(s.id, select.value);
            this.onJoinSession(s);
          } catch (err) {
            alert(err.message || "Join failed");
          }
        }
      }, "Join"));
      card.appendChild(actions);
      this.sessionsEl.appendChild(card);
    });
  }
  renderMembers() {
    clear(this.membersEl);
    if (this.members.length === 0) {
      this.membersEl.appendChild(el("div", { className: "campaigns-empty" }, "No members."));
      return;
    }
    const isDm = this.campaign.is_dm;
    this.members.forEach((m) => {
      const row = el("div", { className: "member-row" });
      const info = el("div", { className: "member-info" });
      info.appendChild(el("strong", {}, `Account ${m.account_id}`));
      info.appendChild(el("span", { className: "member-role" }, m.role));
      row.appendChild(info);
      if (isDm) {
        const controls = el("div", { className: "member-controls" });
        if (m.role !== "dm") {
          controls.appendChild(el("button", {
            onclick: async () => {
              try {
                await transferDm(this.campaign.id, m.account_id);
                alert("DM role transferred.");
                this.campaign.dm_account_id = m.account_id;
                await this.load();
              } catch (err) {
                alert(err.message || "Transfer failed");
              }
            }
          }, "Make DM"));
        }
        if (m.role !== "dm") {
          controls.appendChild(el("button", {
            onclick: async () => {
              try {
                await setMemberRole(this.campaign.id, m.account_id, "dm");
                await this.load();
              } catch (err) {
                alert(err.message || "Promote failed");
              }
            }
          }, "Promote"));
        } else if (this.campaign.dm_account_id !== m.account_id) {
          controls.appendChild(el("button", {
            onclick: async () => {
              try {
                await setMemberRole(this.campaign.id, m.account_id, "player");
                await this.load();
              } catch (err) {
                alert(err.message || "Demote failed");
              }
            }
          }, "Demote"));
        }
        controls.appendChild(el("button", {
          className: "danger",
          onclick: async () => {
            if (!confirm(`Kick account ${m.account_id}?`)) return;
            try {
              await setMemberRole(this.campaign.id, m.account_id, "none");
              await this.load();
            } catch (err) {
              alert(err.message || "Kick failed");
            }
          }
        }, "Kick"));
        row.appendChild(controls);
      }
      this.membersEl.appendChild(row);
    });
  }
  destroy() {
    this.root.remove();
  }
};

// src/ui/dice-tray.ts
var COMMON_ROLLS = [
  { label: "d4", expr: "1d4" },
  { label: "d6", expr: "1d6" },
  { label: "d8", expr: "1d8" },
  { label: "d10", expr: "1d10" },
  { label: "d12", expr: "1d12" },
  { label: "d20", expr: "1d20" },
  { label: "d100", expr: "1d100" }
];
var DiceTray = class {
  root;
  history;
  controls;
  rolls = [];
  onRoll;
  collapsed = true;
  constructor(container, onRoll) {
    this.onRoll = onRoll;
    this.root = el("div", { className: "dice-tray collapsed" });
    const header = el("div", { className: "tray-header" });
    const title = el("span", {}, "Dice Tray");
    const toggle = el("button", {
      className: "tray-toggle",
      title: "Toggle dice tray",
      onclick: () => this.toggle()
    }, "\u25B2");
    header.appendChild(title);
    header.appendChild(toggle);
    this.controls = this.buildControls();
    this.history = el("div", { className: "tray-history" });
    this.root.appendChild(header);
    this.root.appendChild(this.controls);
    this.root.appendChild(this.history);
    container.appendChild(this.root);
    this.renderHistory();
  }
  toggle() {
    this.collapsed = !this.collapsed;
    this.root.classList.toggle("collapsed", this.collapsed);
    const btn = this.root.querySelector(".tray-toggle");
    if (btn) btn.textContent = this.collapsed ? "\u25B2" : "\u25BC";
  }
  buildControls() {
    const controls = el("div", { className: "tray-controls" });
    const quickButtons = el("div", { className: "tray-quick" });
    COMMON_ROLLS.forEach(({ label, expr }) => {
      const btn = el("button", { className: "tray-die", onclick: () => this.roll(expr) }, label);
      quickButtons.appendChild(btn);
    });
    const custom = el("div", { className: "tray-custom" });
    const input = el("input", {
      type: "text",
      placeholder: "e.g. 3d6, 2d8+3",
      onkeydown: (e) => {
        if (e.key === "Enter") {
          const value2 = input.value.trim();
          if (value2) {
            this.roll(value2);
            input.value = "";
          }
        }
      }
    });
    const rollBtn = el("button", { onclick: () => {
      const value2 = input.value.trim();
      if (value2) {
        this.roll(value2);
        input.value = "";
      }
    } }, "Roll");
    custom.appendChild(input);
    custom.appendChild(rollBtn);
    controls.appendChild(quickButtons);
    controls.appendChild(custom);
    return controls;
  }
  async roll(expr) {
    let total;
    try {
      if (this.onRoll) {
        total = await this.onRoll(expr);
      } else {
        total = this.evaluateLocal(expr);
      }
    } catch (err) {
      this.addHistory({ expr, total: NaN, timestamp: /* @__PURE__ */ new Date() });
      return;
    }
    this.addHistory({ expr, total, timestamp: /* @__PURE__ */ new Date() });
  }
  evaluateLocal(expr) {
    const normalized = expr.replace(/\s/g, "").toLowerCase();
    const parts2 = normalized.split(/(?=[+-])/);
    let total = 0;
    for (const part of parts2) {
      if (part.includes("d")) {
        const [countStr, facesStr] = part.split("d");
        const count = countStr === "" ? 1 : parseInt(countStr, 10);
        const faces = parseInt(facesStr, 10);
        if (Number.isNaN(count) || Number.isNaN(faces)) throw new Error("bad dice");
        for (let i = 0; i < count; i++) {
          total += Math.floor(Math.random() * faces) + 1;
        }
      } else {
        total += parseInt(part, 10) || 0;
      }
    }
    return total;
  }
  addHistory(roll) {
    this.rolls.unshift(roll);
    if (this.rolls.length > 50) this.rolls.pop();
    this.renderHistory();
  }
  renderHistory() {
    clear(this.history);
    if (this.rolls.length === 0) {
      this.history.appendChild(el("div", { className: "tray-empty" }, "Rolls appear here"));
      return;
    }
    this.rolls.forEach((r) => {
      const value2 = Number.isNaN(r.total) ? "?" : String(r.total);
      const item = el("div", { className: "tray-roll" });
      item.appendChild(el("span", { className: "tray-expr" }, r.expr));
      item.appendChild(el("span", { className: "tray-total" }, value2));
      this.history.appendChild(item);
    });
  }
  destroy() {
    this.root.remove();
  }
};

// src/ui/character-creator.ts
var CharacterCreator = class {
  root;
  onSaved;
  options = null;
  preview = null;
  arrangement;
  seed;
  nameInput;
  ancestrySelect;
  modeSelect;
  classContainer;
  previewPanel;
  messageEl;
  arrangeContainer;
  rollButton;
  saveButton;
  constructor(container, onSaved) {
    this.root = el("div", { className: "creator-shell" });
    this.onSaved = onSaved;
    const panel = el("div", { className: "creator-panel" });
    panel.appendChild(el("h1", {}, "Sanctuary"));
    panel.appendChild(el("p", { className: "subtitle" }, "Forge your adventurer"));
    this.messageEl = el("div", { className: "creator-message" });
    panel.appendChild(this.messageEl);
    this.nameInput = el("input", { type: "text", value: "Hero", maxlength: "24" });
    panel.appendChild(this.formGroup("Name", this.nameInput));
    this.ancestrySelect = el("select", { onchange: () => this.updateClassChoices() });
    panel.appendChild(this.formGroup("Ancestry", this.ancestrySelect));
    this.modeSelect = el("select", {});
    panel.appendChild(this.formGroup("Generation", this.modeSelect));
    this.classContainer = el("div", { className: "creator-classes" });
    panel.appendChild(this.formGroup("Class", this.classContainer));
    this.rollButton = el("button", { className: "reroll", onclick: () => this.rollPreview() }, "Roll Abilities");
    panel.appendChild(this.rollButton);
    this.arrangeContainer = el("div", { className: "arrange-container" });
    panel.appendChild(this.arrangeContainer);
    this.previewPanel = el("div", { className: "preview-panel" });
    panel.appendChild(this.previewPanel);
    this.saveButton = el("button", { className: "enter", onclick: () => this.save() }, "Enter Sanctuary");
    this.saveButton.disabled = true;
    panel.appendChild(this.saveButton);
    this.root.appendChild(panel);
    const trayAnchor = el("div", { className: "tray-anchor" });
    this.root.appendChild(trayAnchor);
    new DiceTray(trayAnchor);
    container.appendChild(this.root);
    this.loadOptions();
  }
  formGroup(label, control) {
    const group = el("div", { className: "form-group" });
    group.appendChild(el("label", {}, label));
    group.appendChild(control);
    return group;
  }
  async loadOptions() {
    try {
      this.options = await getRulesetOptions();
      this.populateControls();
    } catch (err) {
      this.showMessage("Could not load ruleset options.", true);
    }
  }
  populateControls() {
    if (!this.options) return;
    clear(this.ancestrySelect);
    this.options.ancestries.forEach((a) => {
      this.ancestrySelect.appendChild(el("option", { value: a }, this.titleCase(a)));
    });
    clear(this.modeSelect);
    this.options.modes.forEach((m) => {
      const label = `${this.titleCase(m.id)} \xB7 ${m.roll}${m.arrange ? " \xB7 arrange" : ""}`;
      this.modeSelect.appendChild(el("option", { value: m.id }, label));
    });
    this.updateClassChoices();
  }
  updateClassChoices() {
    if (!this.options) return;
    clear(this.classContainer);
    this.options.classes.forEach((c) => {
      const label = el("label", { className: "class-chip" });
      const checkbox = el("input", { type: "checkbox", value: c, onchange: () => this.validateClassSelection() });
      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(this.titleCase(c)));
      this.classContainer.appendChild(label);
    });
    this.validateClassSelection();
  }
  validateClassSelection() {
    const selected = Array.from(this.classContainer.querySelectorAll("input:checked")).map(
      (i) => i.value
    );
    if (selected.length === 0) {
      this.showMessage("Choose at least one class.", true);
      this.saveButton.disabled = true;
      return;
    }
    this.clearMessage();
  }
  selectedClasses() {
    return Array.from(this.classContainer.querySelectorAll("input:checked")).map(
      (i) => i.value
    );
  }
  async rollPreview() {
    this.rollButton.disabled = true;
    this.saveButton.disabled = true;
    this.clearMessage();
    this.arrangement = void 0;
    try {
      const req = this.buildRequest();
      const { character } = await previewCharacter(req);
      this.preview = character;
      this.seed = character.seed;
      this.renderPreview();
      this.saveButton.disabled = false;
      if (this.currentMode()?.arrange) {
        this.renderArrange();
      }
    } catch (err) {
      this.showMessage(this.formatError(err) || "Roll failed.", true);
    } finally {
      this.rollButton.disabled = false;
    }
  }
  currentMode() {
    return this.options?.modes.find((m) => m.id === this.modeSelect.value);
  }
  buildRequest() {
    return {
      mode: this.modeSelect.value,
      ancestry: this.ancestrySelect.value,
      classes: this.selectedClasses(),
      name: this.nameInput.value.trim() || "Hero",
      seed: this.seed ?? seededRandomSeed(),
      arrangement: this.arrangement
    };
  }
  renderPreview() {
    clear(this.previewPanel);
    if (!this.preview) return;
    const char = this.preview;
    const portraitUrl = char.portrait_url || this.fallbackPortraitUrl(char.classes[0]);
    const portrait = el("img", {
      className: "creator-portrait",
      src: portraitUrl,
      alt: char.name,
      onerror: () => {
        portrait.src = this.fallbackPortraitUrl();
      }
    });
    this.previewPanel.appendChild(portrait);
    const grid = el("div", { className: "abilities-grid" });
    this.options?.abilities.forEach((ability) => {
      const score = char.scores[ability];
      const mod = char.modifiers[ability];
      const cell = el("div");
      cell.appendChild(el("span", {}, this.abbreviate(ability)));
      cell.appendChild(el("strong", {}, String(score)));
      if (mod !== void 0) {
        cell.appendChild(el("small", {}, formatModifier(mod)));
      }
      grid.appendChild(cell);
    });
    const derived = el("div", { className: "derived" });
    derived.appendChild(el("span", {}, `HP ${char.hit_points}`));
    derived.appendChild(el("span", {}, `AC ${char.armour_class}`));
    this.previewPanel.appendChild(grid);
    this.previewPanel.appendChild(derived);
  }
  fallbackPortraitUrl(className) {
    const key = (className || "generic").toLowerCase().replace(/\s+/g, "-");
    return `/portraits/${key}.png`;
  }
  renderArrange() {
    clear(this.arrangeContainer);
    if (!this.preview || !this.options) return;
    const values = Object.values(this.preview.scores);
    const slots = {};
    const wrapper = el("div", { className: "arrange-panel" });
    wrapper.appendChild(el("p", {}, "Drag values to assign abilities"));
    const pool = el("div", { className: "arrange-pool" });
    values.forEach((v) => {
      const chip = el("div", { className: "arrange-chip", draggable: "true" }, String(v));
      chip.dataset.value = String(v);
      chip.addEventListener("dragstart", (e) => {
        e.dataTransfer?.setData("text/plain", String(v));
      });
      pool.appendChild(chip);
    });
    const abilitySlots = el("div", { className: "arrange-slots" });
    this.options.abilities.forEach((ability) => {
      const slot = el("div", { className: "arrange-slot" });
      slot.dataset.ability = ability;
      slot.appendChild(el("span", {}, this.abbreviate(ability)));
      const valueEl = el("strong", {}, "-");
      slot.appendChild(valueEl);
      slots[ability] = valueEl;
      slot.addEventListener("dragover", (e) => e.preventDefault());
      slot.addEventListener("drop", (e) => {
        e.preventDefault();
        const value2 = parseInt(e.dataTransfer?.getData("text/plain") || "0", 10);
        if (!value2) return;
        slots[ability].textContent = String(value2);
        this.updateArrangement();
      });
      abilitySlots.appendChild(slot);
    });
    wrapper.appendChild(pool);
    wrapper.appendChild(abilitySlots);
    this.arrangeContainer.appendChild(wrapper);
  }
  updateArrangement() {
    const slots = this.arrangeContainer.querySelectorAll(".arrange-slot");
    const arrangement = {};
    let complete = true;
    slots.forEach((s) => {
      const ability = s.dataset.ability;
      const text = s.querySelector("strong")?.textContent || "";
      const value2 = parseInt(text, 10);
      if (Number.isNaN(value2)) {
        complete = false;
      } else {
        arrangement[ability] = value2;
      }
    });
    this.arrangement = complete ? arrangement : void 0;
    if (complete) {
      this.rollPreview();
    }
  }
  async save() {
    if (!this.preview) return;
    this.saveButton.disabled = true;
    this.clearMessage();
    try {
      const req = this.buildRequest();
      const { character } = await createCharacter(req);
      this.onSaved(character);
    } catch (err) {
      this.showMessage(this.formatError(err) || "Save failed.", true);
      this.saveButton.disabled = false;
    }
  }
  formatError(err) {
    const raw = err?.message || String(err);
    const detailMatch = raw.match(/\{[^}]*"detail"\s*:\s*"([^"]+)"/);
    const detail = detailMatch ? detailMatch[1] : raw;
    const minimumsMatch = detail.match(/does not meet ([^']+)'s ability minimums/);
    if (minimumsMatch) {
      const className = this.titleCase(minimumsMatch[1].replace(/-/g, " "));
      return `${className} requires higher ability scores than your current rolls provide. Try a different class or rearrange your scores.`;
    }
    if (detail.toLowerCase().includes("may not be")) {
      return "That ancestry cannot take that combination of classes.";
    }
    if (detail.toLowerCase().includes("ability scores do not meet")) {
      return "Your rolled scores do not meet the minimum requirements for that ancestry.";
    }
    return detail;
  }
  showMessage(text, error = false) {
    this.messageEl.textContent = text;
    this.messageEl.className = `creator-message ${error ? "error" : ""}`;
  }
  clearMessage() {
    this.messageEl.textContent = "";
    this.messageEl.className = "creator-message";
  }
  titleCase(str) {
    return str.replace(/\b\w/g, (c) => c.toUpperCase());
  }
  abbreviate(ability) {
    return ability.slice(0, 3).toUpperCase();
  }
  destroy() {
    this.root.remove();
  }
};

// src/ui/character-sheet.ts
var CharacterSheet = class {
  root;
  character;
  onClose;
  overlay;
  constructor(container, character, onClose) {
    this.root = container;
    this.character = character;
    this.onClose = onClose;
    this.overlay = el("div", { className: "character-sheet-overlay" });
    const panel = el("div", { className: "character-sheet-panel" });
    panel.appendChild(this.buildHeader());
    panel.appendChild(this.buildStats());
    panel.appendChild(this.buildEquipment());
    panel.appendChild(this.buildInventory());
    panel.appendChild(this.buildShop());
    const closeBtn = el("button", { className: "enter", onclick: () => this.close() }, "Close");
    panel.appendChild(closeBtn);
    this.overlay.appendChild(panel);
    this.overlay.addEventListener("click", (e) => {
      if (e.target === this.overlay) this.close();
    });
    this.root.appendChild(this.overlay);
    this.addRegenerateButtonIfAvailable();
  }
  async addRegenerateButtonIfAvailable() {
    try {
      const config = await getAppConfig();
      if (!config.pixellab_host) return;
      const header = this.overlay.querySelector(".sheet-header");
      if (!header) return;
      const existing = header.querySelector(".regenerate-portrait");
      if (existing) return;
      header.appendChild(
        el(
          "button",
          {
            className: "reroll regenerate-portrait",
            onclick: () => this.doRegeneratePortrait()
          },
          "Regenerate Portrait"
        )
      );
    } catch {
    }
  }
  async doRegeneratePortrait() {
    if (!this.character.id) return;
    try {
      const { portrait_url } = await regeneratePortrait(this.character.id);
      this.character.portrait_url = portrait_url;
      this.refresh();
    } catch (err) {
      alert(err.message || "Portrait generation failed");
    }
  }
  buildHeader() {
    const c = this.character;
    const header = el("div", { className: "sheet-header" });
    const portraitUrl = c.portrait_url || this.fallbackPortraitUrl(c.classes[0]);
    const portrait = el("img", {
      className: "sheet-portrait",
      src: portraitUrl,
      alt: c.name,
      onerror: () => {
        portrait.src = this.fallbackPortraitUrl();
      }
    });
    header.appendChild(portrait);
    header.appendChild(el("h1", {}, c.name));
    header.appendChild(
      el("p", { className: "subtitle" }, `${this.titleCase(c.ancestry)} ${c.classes.map((x) => this.titleCase(x)).join("/")}`)
    );
    return header;
  }
  fallbackPortraitUrl(className) {
    const key = (className || "generic").toLowerCase().replace(/\s+/g, "-");
    return `/portraits/${key}.png`;
  }
  buildStats() {
    const c = this.character;
    const grid = el("div", { className: "sheet-stats" });
    grid.appendChild(this.statBox("Level", String(c.level ?? 1)));
    grid.appendChild(this.statBox("XP", String(c.xp ?? 0)));
    grid.appendChild(this.statBox("Gold", String(c.gold ?? 0)));
    grid.appendChild(this.statBox("HP", `${c.hit_points}/${c.max_hp}`));
    grid.appendChild(this.statBox("AC", String(c.armour_class)));
    return grid;
  }
  statBox(label, value2) {
    const box = el("div", { className: "sheet-stat-box" });
    box.appendChild(el("span", {}, label));
    box.appendChild(el("strong", {}, value2));
    return box;
  }
  buildEquipment() {
    const equipment = this.character.equipment || {};
    const section = el("div", { className: "sheet-section" });
    section.appendChild(el("h2", {}, "Equipped"));
    const list = el("ul", { className: "sheet-list" });
    const slots = Object.keys(equipment);
    if (slots.length === 0) {
      list.appendChild(el("li", { className: "empty" }, "Nothing equipped."));
    } else {
      slots.forEach((slot) => {
        const item = equipment[slot];
        list.appendChild(el("li", {}, `${this.titleCase(slot)}: ${item.name}`));
      });
    }
    section.appendChild(list);
    return section;
  }
  buildInventory() {
    const inventory = this.character.inventory || [];
    const section = el("div", { className: "sheet-section" });
    section.appendChild(el("h2", {}, "Inventory"));
    const list = el("ul", { className: "sheet-list" });
    if (inventory.length === 0) {
      list.appendChild(el("li", { className: "empty" }, "No items."));
    } else {
      inventory.forEach((item) => {
        const li = el("li", { className: "sheet-item" });
        li.appendChild(el("span", {}, item.name));
        const actions = el("div", { className: "sheet-item-actions" });
        if (item.slot && item.slot !== "consumable") {
          actions.appendChild(
            el("button", { onclick: () => this.doEquip(item) }, "Equip")
          );
        }
        if (item.slot === "consumable") {
          actions.appendChild(
            el("button", { onclick: () => this.doUse(item) }, "Use")
          );
        }
        li.appendChild(actions);
        list.appendChild(li);
      });
    }
    section.appendChild(list);
    return section;
  }
  async doEquip(item) {
    if (!this.character.id) return;
    try {
      const { character } = await equipItem(this.character.id, item.instance_id);
      this.character = character;
      this.refresh();
    } catch (err) {
      alert(err.message || "Equip failed");
    }
  }
  async doUse(item) {
    if (!this.character.id) return;
    try {
      const { character, restored } = await useItem(this.character.id, item.instance_id);
      this.character = character;
      this.refresh();
      if (restored) {
        alert(`Restored ${restored} HP.`);
      }
    } catch (err) {
      alert(err.message || "Use failed");
    }
  }
  buildShop() {
    const section = el("div", { className: "sheet-section" });
    section.appendChild(el("h2", {}, "Shop"));
    const row = el("div", { className: "sheet-shop-row" });
    const gold = this.character.gold ?? 0;
    const canAfford = gold >= 15;
    const buyBtn = el(
      "button",
      {
        disabled: !canAfford,
        onclick: () => this.doBuy()
      },
      "Buy Potion (15g)"
    );
    row.appendChild(buyBtn);
    row.appendChild(el("span", { className: "sheet-shop-gold" }, `${gold}g`));
    section.appendChild(row);
    return section;
  }
  async doBuy() {
    if (!this.character.id) return;
    try {
      const { character } = await buyItem(this.character.id, "healing_potion", 15);
      this.character = character;
      this.refresh();
    } catch (err) {
      alert(err.message || "Buy failed");
    }
  }
  refresh() {
    clear(this.overlay);
    const panel = el("div", { className: "character-sheet-panel" });
    panel.appendChild(this.buildHeader());
    panel.appendChild(this.buildStats());
    panel.appendChild(this.buildEquipment());
    panel.appendChild(this.buildInventory());
    panel.appendChild(this.buildShop());
    const closeBtn = el("button", { className: "enter", onclick: () => this.close() }, "Close");
    panel.appendChild(closeBtn);
    this.overlay.appendChild(panel);
    this.addRegenerateButtonIfAvailable();
  }
  close() {
    this.overlay.remove();
    this.onClose();
  }
  titleCase(str) {
    return str.replace(/\b\w/g, (c) => c.toUpperCase());
  }
};

// src/ui/character-select.ts
var THEME_LABELS = {
  dungeon: "Dungeon",
  cave: "Cave",
  library: "Library",
  ice: "Frozen",
  lava: "Volcanic",
  forest: "Forest",
  tomb: "Tomb",
  sewer: "Sewer"
};
var CharacterSelect = class {
  root;
  onPlay;
  onCreate;
  onCampaigns;
  onSessions;
  onBack;
  charactersEl;
  timerInput;
  moduleCardsEl;
  moduleErrorEl;
  progressEl;
  mainEl;
  detailEl;
  modules = [];
  selectedModuleId = "sample_lair";
  characters = [];
  constructor(container, onPlay, onCreate, onCampaigns, onSessions, onBack, onDmWorkshop) {
    this.root = el("div", { className: "solo-hub" });
    this.onPlay = onPlay;
    this.onCreate = onCreate;
    this.onCampaigns = onCampaigns;
    this.onSessions = onSessions;
    this.onBack = onBack;
    this.onDmWorkshop = onDmWorkshop;
    const background = el("div", { className: "solo-hub-background" });
    const vignette = el("div", { className: "solo-hub-vignette" });
    const shell = el("div", { className: "solo-hub-shell" });
    shell.appendChild(this.buildHeader());
    shell.appendChild(this.buildMain());
    shell.appendChild(this.buildFooter());
    this.root.appendChild(background);
    this.root.appendChild(vignette);
    this.root.appendChild(shell);
    container.appendChild(this.root);
    this.load();
  }
  buildHeader() {
    const header = el("header", { className: "solo-hub-header" });
    const titleBlock = el("div", { className: "solo-hub-title" });
    titleBlock.appendChild(el("h1", {}, "Solo Adventure"));
    titleBlock.appendChild(el("p", {}, "Choose a hero and a room to begin your delve."));
    header.appendChild(titleBlock);
    this.progressEl = el("div", { className: "account-progress" });
    header.appendChild(this.progressEl);
    const controls = el("div", { className: "solo-hub-controls" });
    const timerWrap = el("div", { className: "timer-config" });
    timerWrap.appendChild(el("label", { htmlFor: "turn-timer" }, "Turn timer"));
    this.timerInput = el("select", { id: "turn-timer" });
    [
      { value: "0", label: "Off" },
      { value: "15", label: "15 seconds" },
      { value: "30", label: "30 seconds" },
      { value: "60", label: "1 minute" }
    ].forEach((opt) => {
      const option = document.createElement("option");
      option.value = opt.value;
      option.textContent = opt.label;
      this.timerInput.appendChild(option);
    });
    timerWrap.appendChild(this.timerInput);
    controls.appendChild(timerWrap);
    const actionGroup = el("div", { className: "solo-hub-actions" });
    actionGroup.appendChild(el("button", { className: "solo-hub-btn", onclick: () => this.onCreate() }, "+ New Hero"));
    actionGroup.appendChild(el("button", { className: "solo-hub-btn", onclick: () => this.onCampaigns() }, "Campaigns"));
    actionGroup.appendChild(el("button", { className: "solo-hub-btn", onclick: () => this.onDmWorkshop() }, "DM Workshop"));
    if (this.onSessions) {
      actionGroup.appendChild(el("button", { className: "solo-hub-btn", onclick: () => this.onSessions() }, "Saved"));
    }
    controls.appendChild(actionGroup);
    header.appendChild(controls);
    return header;
  }
  buildMain() {
    this.mainEl = el("main", { className: "solo-hub-main" });
    const charactersSection = el("section", { className: "solo-hub-section characters-section" });
    charactersSection.appendChild(el("h2", {}, "Your Heroes"));
    this.charactersEl = el("div", { className: "characters-grid" });
    charactersSection.appendChild(this.charactersEl);
    this.mainEl.appendChild(charactersSection);
    const roomsSection = el("section", { className: "solo-hub-section rooms-section" });
    const roomsHeader = el("div", { className: "rooms-header" });
    roomsHeader.appendChild(el("h2", {}, "Rooms"));
    this.moduleErrorEl = el("div", { className: "module-select-error" });
    roomsHeader.appendChild(this.moduleErrorEl);
    roomsSection.appendChild(roomsHeader);
    this.moduleCardsEl = el("div", { className: "module-cards" });
    roomsSection.appendChild(this.moduleCardsEl);
    this.mainEl.appendChild(roomsSection);
    this.detailEl = el("section", { className: "solo-hub-section room-detail" });
    this.mainEl.appendChild(this.detailEl);
    return this.mainEl;
  }
  buildFooter() {
    const footer = el("footer", { className: "solo-hub-footer" });
    if (this.onBack) {
      footer.appendChild(el("button", { className: "solo-hub-back", onclick: () => this.onBack() }, "\u2190 Back to Sanctuary"));
    }
    footer.appendChild(el("span", { className: "solo-hub-hint" }, "Tip: click a room to select it, then Play a hero."));
    return footer;
  }
  async load() {
    try {
      const [{ characters }, { modules }, progress] = await Promise.all([
        listCharacters(),
        listModules(),
        getAccountProgress().catch(() => null)
      ]);
      this.modules = modules;
      this.characters = characters;
      this.renderProgress(progress);
      this.renderModules();
      this.renderCharacters(characters);
      this.renderDetail();
    } catch (err) {
      this.charactersEl.appendChild(el("div", { className: "characters-empty" }, err.message || "Failed to load heroes."));
      this.moduleErrorEl.textContent = err.message || "Failed to load rooms.";
    }
  }
  renderProgress(progress) {
    clear(this.progressEl);
    if (!progress) {
      this.progressEl.style.display = "none";
      return;
    }
    this.progressEl.style.display = "flex";
    const stats = [
      ["Wins", progress.wins ?? 0],
      ["Losses", progress.losses ?? 0],
      ["Boss Kills", progress.boss_kills ?? 0],
      ["Cleared", progress.modules_cleared ?? 0],
      ["Deaths", progress.deaths ?? 0],
      ["Level Ups", progress.level_ups ?? 0]
    ];
    stats.forEach(([label, value2]) => {
      this.progressEl.appendChild(el("span", {}, `${label} ${value2}`));
    });
  }
  renderModules() {
    clear(this.moduleCardsEl);
    clear(this.moduleErrorEl);
    if (this.modules.length === 0) {
      this.moduleErrorEl.textContent = "No rooms available.";
      return;
    }
    this.modules.forEach((m) => {
      const card = el("div", {
        className: `module-card${m.id === this.selectedModuleId ? " selected" : ""}`,
        onclick: () => this.selectModule(m.id)
      });
      const preview = this.buildMiniMap(m);
      if (preview) card.appendChild(preview);
      const body = el("div", { className: "module-card-body" });
      const header = el("div", { className: "module-card-header" });
      const theme = THEME_LABELS[m.theme || "dungeon"] || m.theme || "Dungeon";
      header.appendChild(el("span", { className: `module-theme theme-${m.theme || "dungeon"}` }, theme));
      header.appendChild(el("span", { className: "module-size" }, `${m.width}\xD7${m.height}`));
      body.appendChild(header);
      body.appendChild(el("h3", {}, m.name));
      body.appendChild(el("p", { className: "module-desc" }, m.description || ""));
      card.appendChild(body);
      this.moduleCardsEl.appendChild(card);
    });
  }
  buildMiniMap(m) {
    if (!m.tiles || m.tiles.length === 0) return null;
    const wrap = el("div", { className: "module-mini-map" });
    const maxRows = Math.min(m.height, 20);
    const maxCols = Math.min(m.width, 28);
    wrap.style.gridTemplateRows = `repeat(${maxRows}, 1fr)`;
    wrap.style.gridTemplateColumns = `repeat(${maxCols}, 1fr)`;
    for (let y = 0; y < maxRows; y++) {
      const row = m.tiles[y] || "";
      for (let x = 0; x < maxCols; x++) {
        const tile = row[x] || "0";
        const cell = el("span", { className: `mini-tile mini-tile-${tile === "1" ? "wall" : tile === "2" ? "trap" : "floor"}` });
        wrap.appendChild(cell);
      }
    }
    return wrap;
  }
  selectModule(id) {
    this.selectedModuleId = id;
    this.renderModules();
    this.renderCharacters(this.characters);
    this.renderDetail();
  }
  renderDetail() {
    clear(this.detailEl);
    const selected = this.modules.find((m) => m.id === this.selectedModuleId);
    if (!selected) {
      this.detailEl.style.display = "none";
      return;
    }
    this.detailEl.style.display = "block";
    const theme = selected.theme || "dungeon";
    const themeLabel = THEME_LABELS[theme] || theme;
    const header = el("div", { className: "room-detail-header" });
    header.appendChild(el("span", { className: `module-theme theme-${theme}` }, themeLabel));
    header.appendChild(el("h2", {}, selected.name));
    header.appendChild(el("span", { className: "module-size" }, `${selected.width}\xD7${selected.height}`));
    this.detailEl.appendChild(header);
    const body = el("div", { className: "room-detail-body" });
    const desc = el("p", {}, selected.description || "No description available.");
    body.appendChild(desc);
    const actions = el("div", { className: "room-detail-actions" });
    if (this.characters.length === 0) {
      actions.appendChild(el("button", { className: "enter", onclick: () => this.onCreate() }, "Create a Hero to Play"));
    } else {
      const first = this.characters[0];
      actions.appendChild(el("button", {
        className: "enter",
        onclick: () => this.onPlay(first, parseInt(this.timerInput.value, 10) || 0, selected.id)
      }, `Play ${first.name}`));
      if (this.characters.length > 1) {
        const select = el("select", {});
        this.characters.forEach((c) => {
          const opt = document.createElement("option");
          opt.value = c.id ?? "";
          opt.textContent = c.name;
          select.appendChild(opt);
        });
        actions.appendChild(select);
        actions.appendChild(el("button", {
          className: "enter",
          onclick: () => {
            const c = this.characters.find((x) => x.id === select.value);
            if (c) this.onPlay(c, parseInt(this.timerInput.value, 10) || 0, selected.id);
          }
        }, "Play Selected"));
      }
    }
    body.appendChild(actions);
    this.detailEl.appendChild(body);
  }
  renderCharacters(characters) {
    clear(this.charactersEl);
    this.mainEl.classList.toggle("solo-hub-main--no-heroes", characters.length === 0);
    if (characters.length === 0) {
      const empty2 = el("div", { className: "characters-empty" });
      empty2.appendChild(el("div", { className: "characters-empty-icon" }));
      empty2.appendChild(el("h3", {}, "No heroes yet"));
      empty2.appendChild(el("p", {}, "Create your first adventurer to enter the rooms."));
      empty2.appendChild(el("button", { className: "enter", onclick: () => this.onCreate() }, "Create Your First Hero"));
      this.charactersEl.appendChild(empty2);
      return;
    }
    characters.forEach((c) => {
      const card = el("div", { className: "character-card" });
      const portraitUrl = c.portrait_url || this.fallbackPortraitUrl(c.classes[0]);
      const portrait = el("img", {
        className: "character-portrait",
        src: portraitUrl,
        alt: c.name,
        onerror: () => {
          portrait.src = this.fallbackPortraitUrl();
        }
      });
      const info = el("div", { className: "character-info" });
      info.appendChild(el("strong", {}, c.name));
      info.appendChild(el("span", { className: "character-meta" }, `${this.titleCase(c.ancestry)} \xB7 ${c.classes.map((x) => this.titleCase(x)).join("/")}`));
      const hpPercent = Math.max(0, Math.min(100, Math.round(c.hit_points / Math.max(1, c.max_hp) * 100)));
      const hpBar = el("div", { className: "character-hp-bar" });
      hpBar.appendChild(el("span", { style: `width:${hpPercent}%` }));
      info.appendChild(hpBar);
      const stats = el("div", { className: "character-stats" });
      stats.appendChild(el("span", {}, `HP ${c.hit_points}/${c.max_hp}`));
      stats.appendChild(el("span", {}, `AC ${c.armour_class}`));
      stats.appendChild(el("span", {}, `LVL ${c.level ?? 1}`));
      info.appendChild(stats);
      const abilities = el("div", { className: "character-abilities" });
      const abilityEntries = [
        ["STR", c.scores?.strength],
        ["DEX", c.scores?.dexterity],
        ["CON", c.scores?.constitution],
        ["INT", c.scores?.intelligence],
        ["WIS", c.scores?.wisdom],
        ["CHA", c.scores?.charisma]
      ];
      abilityEntries.forEach(([label, value2]) => {
        abilities.appendChild(el("span", {}, `${label} ${value2 ?? "-"}`));
      });
      info.appendChild(abilities);
      const actions = el("div", { className: "character-actions" });
      actions.appendChild(el("button", { className: "play-btn", onclick: () => this.onPlay(c, parseInt(this.timerInput.value, 10) || 0, this.selectedModuleId) }, "Play"));
      actions.appendChild(el("button", { onclick: () => this.openSheet(c) }, "Sheet"));
      actions.appendChild(el("button", {
        className: "danger",
        onclick: async () => {
          if (!c.id) return;
          if (!confirm(`Delete ${c.name}?`)) return;
          await deleteCharacter(c.id);
          this.load();
        }
      }, "Delete"));
      card.appendChild(portrait);
      card.appendChild(info);
      card.appendChild(actions);
      this.charactersEl.appendChild(card);
    });
  }
  fallbackPortraitUrl(className) {
    const key = (className || "generic").toLowerCase().replace(/\s+/g, "-");
    return `/portraits/${key}.png`;
  }
  openSheet(character) {
    new CharacterSheet(this.root, character, () => this.load());
  }
  titleCase(str) {
    return str.replace(/\b\w/g, (c) => c.toUpperCase());
  }
  destroy() {
    this.root.remove();
  }
};

// src/ui/adventure-create.ts
var AdventureCreate = class {
  root;
  onCreate;
  onBack;
  characters = [];
  modules = [];
  dungeons = [];
  selectedCharacterId = "";
  selectedModuleId = "sample_lair";
  selectedDungeonId = "";
  source = "module";
  constructor(container, onCreate, onBack) {
    this.onCreate = onCreate;
    this.onBack = onBack;
    this.root = el("div", { className: "adventure-create" });
    const panel = el("div", { className: "session-panel adventure-create-panel" });
    panel.appendChild(el("h1", {}, "Create Adventure"));
    panel.appendChild(el("p", { className: "subtitle" }, "Choose a hero, a room, and who can join."));
    this.formEl = el("div", { className: "adventure-create-form" });
    panel.appendChild(this.formEl);
    panel.appendChild(this.buildFooter());
    this.root.appendChild(panel);
    container.appendChild(this.root);
    this.load();
  }
  async load() {
    try {
      const [{ characters }, { modules }, { dungeons }] = await Promise.all([
        listCharacters(),
        listModules(),
        listDungeons().catch(() => ({ dungeons: [] }))
      ]);
      this.characters = characters;
      this.modules = modules;
      this.dungeons = dungeons;
      if (characters.length > 0) this.selectedCharacterId = characters[0].id;
      if (modules.length > 0) this.selectedModuleId = modules[0].id;
      if (dungeons.length > 0) this.selectedDungeonId = dungeons[0].id;
      this.render();
    } catch (err) {
      clear(this.formEl);
      this.formEl.appendChild(el("div", { className: "empty error" }, err.message || "Failed to load data."));
    }
  }
  render() {
    clear(this.formEl);
    this.formEl.appendChild(el("label", {}, "Adventure Name"));
    this.nameInput = el("input", { type: "text", placeholder: "e.g. Goblin Lair Run" });
    this.formEl.appendChild(this.nameInput);

    this.formEl.appendChild(el("label", {}, "Visibility"));
    const visibilityWrap = el("div", { className: "visibility-options" });
    const visibilities = [
      { key: "solo", label: "Solo", desc: "Only you" },
      { key: "friends", label: "Friends", desc: "Friends can join" },
      { key: "public", label: "Public", desc: "Anyone can join" },
      { key: "invite", label: "Invite Only", desc: "Code required" }
    ];
    this.visibilitySelect = el("select", {});
    visibilities.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v.key;
      opt.textContent = `${v.label} — ${v.desc}`;
      if (v.key === "friends") opt.selected = true;
      this.visibilitySelect.appendChild(opt);
    });
    this.formEl.appendChild(this.visibilitySelect);

    this.formEl.appendChild(el("label", {}, "Source"));
    const sourceSelect = el("select", {});
    const sources = [
      { key: "module", label: "Built-in Room" },
      { key: "dungeon", label: "Custom Dungeon" }
    ];
    sources.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.key;
      opt.textContent = s.label;
      if (s.key === this.source) opt.selected = true;
      sourceSelect.appendChild(opt);
    });
    sourceSelect.onchange = () => {
      this.source = sourceSelect.value;
      this.render();
    };
    this.formEl.appendChild(sourceSelect);

    if (this.source === "dungeon") {
      this.formEl.appendChild(el("label", {}, "Dungeon"));
      if (this.dungeons.length === 0) {
        this.formEl.appendChild(el("div", { className: "empty" }, "No dungeons. Build one in the DM Workshop first."));
      } else {
        const dungeonSelect = el("select", {});
        this.dungeons.forEach((d) => {
          const opt = document.createElement("option");
          opt.value = d.id;
          opt.textContent = d.name;
          if (d.id === this.selectedDungeonId) opt.selected = true;
          dungeonSelect.appendChild(opt);
        });
        dungeonSelect.onchange = () => this.selectedDungeonId = dungeonSelect.value;
        this.formEl.appendChild(dungeonSelect);
      }
    } else {
      this.formEl.appendChild(el("label", {}, "Room"));
      const moduleSelect = el("select", {});
      this.modules.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = m.name;
        if (m.id === this.selectedModuleId) opt.selected = true;
        moduleSelect.appendChild(opt);
      });
      moduleSelect.onchange = () => this.selectedModuleId = moduleSelect.value;
      this.formEl.appendChild(moduleSelect);
    }

    this.formEl.appendChild(el("label", {}, "Hero"));
    if (this.characters.length === 0) {
      this.formEl.appendChild(el("div", { className: "empty" }, "No heroes. Create one first."));
    } else {
      const charSelect = el("select", {});
      this.characters.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.name;
        if (c.id === this.selectedCharacterId) opt.selected = true;
        charSelect.appendChild(opt);
      });
      charSelect.onchange = () => this.selectedCharacterId = charSelect.value;
      this.formEl.appendChild(charSelect);
    }
  }
  buildFooter() {
    const footer = el("div", { className: "editor-footer" });
    footer.appendChild(el("button", {
      className: "enter",
      onclick: () => this.doCreate()
    }, "Create Adventure"));
    footer.appendChild(el("button", {
      onclick: () => this.onBack()
    }, "\u2190 Back"));
    return footer;
  }
  async doCreate() {
    if (!this.selectedCharacterId) {
      alert("Select a hero first.");
      return;
    }
    if (this.source === "dungeon" && this.dungeons.length === 0) {
      alert("No dungeons available. Build one in the DM Workshop first.");
      return;
    }
    try {
      let session;
      if (this.source === "dungeon") {
        ({ session } = await playDungeon(this.selectedDungeonId, this.selectedCharacterId, void 0, 0));
      } else {
        ({ session } = await createSession(this.selectedCharacterId, this.selectedModuleId, void 0, 0, {
          visibility: this.visibilitySelect.value,
          name: this.nameInput.value.trim()
        }));
      }
      this.onCreate(session);
    } catch (err) {
      alert(err.message || "Failed to create adventure");
    }
  }
  destroy() {
    this.root.remove();
  }
};

// node_modules/engine.io-parser/build/esm/commons.js
var PACKET_TYPES = /* @__PURE__ */ Object.create(null);
PACKET_TYPES["open"] = "0";
PACKET_TYPES["close"] = "1";
PACKET_TYPES["ping"] = "2";
PACKET_TYPES["pong"] = "3";
PACKET_TYPES["message"] = "4";
PACKET_TYPES["upgrade"] = "5";
PACKET_TYPES["noop"] = "6";
var PACKET_TYPES_REVERSE = /* @__PURE__ */ Object.create(null);
Object.keys(PACKET_TYPES).forEach((key) => {
  PACKET_TYPES_REVERSE[PACKET_TYPES[key]] = key;
});
var ERROR_PACKET = { type: "error", data: "parser error" };

// node_modules/engine.io-parser/build/esm/encodePacket.browser.js
var withNativeBlob = typeof Blob === "function" || typeof Blob !== "undefined" && Object.prototype.toString.call(Blob) === "[object BlobConstructor]";
var withNativeArrayBuffer = typeof ArrayBuffer === "function";
var isView = (obj) => {
  return typeof ArrayBuffer.isView === "function" ? ArrayBuffer.isView(obj) : obj && obj.buffer instanceof ArrayBuffer;
};
var encodePacket = ({ type, data }, supportsBinary, callback) => {
  if (withNativeBlob && data instanceof Blob) {
    if (supportsBinary) {
      return callback(data);
    } else {
      return encodeBlobAsBase64(data, callback);
    }
  } else if (withNativeArrayBuffer && (data instanceof ArrayBuffer || isView(data))) {
    if (supportsBinary) {
      return callback(data);
    } else {
      return encodeBlobAsBase64(new Blob([data]), callback);
    }
  }
  return callback(PACKET_TYPES[type] + (data || ""));
};
var encodeBlobAsBase64 = (data, callback) => {
  const fileReader = new FileReader();
  fileReader.onload = function() {
    const content = fileReader.result.split(",")[1];
    callback("b" + (content || ""));
  };
  return fileReader.readAsDataURL(data);
};
function toArray(data) {
  if (data instanceof Uint8Array) {
    return data;
  } else if (data instanceof ArrayBuffer) {
    return new Uint8Array(data);
  } else {
    return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
  }
}
var TEXT_ENCODER;
function encodePacketToBinary(packet, callback) {
  if (withNativeBlob && packet.data instanceof Blob) {
    return packet.data.arrayBuffer().then(toArray).then(callback);
  } else if (withNativeArrayBuffer && (packet.data instanceof ArrayBuffer || isView(packet.data))) {
    return callback(toArray(packet.data));
  }
  encodePacket(packet, false, (encoded) => {
    if (!TEXT_ENCODER) {
      TEXT_ENCODER = new TextEncoder();
    }
    callback(TEXT_ENCODER.encode(encoded));
  });
}

// node_modules/engine.io-parser/build/esm/contrib/base64-arraybuffer.js
var chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
var lookup = typeof Uint8Array === "undefined" ? [] : new Uint8Array(256);
for (let i = 0; i < chars.length; i++) {
  lookup[chars.charCodeAt(i)] = i;
}
var decode = (base64) => {
  let bufferLength = base64.length * 0.75, len = base64.length, i, p = 0, encoded1, encoded2, encoded3, encoded4;
  if (base64[base64.length - 1] === "=") {
    bufferLength--;
    if (base64[base64.length - 2] === "=") {
      bufferLength--;
    }
  }
  const arraybuffer = new ArrayBuffer(bufferLength), bytes = new Uint8Array(arraybuffer);
  for (i = 0; i < len; i += 4) {
    encoded1 = lookup[base64.charCodeAt(i)];
    encoded2 = lookup[base64.charCodeAt(i + 1)];
    encoded3 = lookup[base64.charCodeAt(i + 2)];
    encoded4 = lookup[base64.charCodeAt(i + 3)];
    bytes[p++] = encoded1 << 2 | encoded2 >> 4;
    bytes[p++] = (encoded2 & 15) << 4 | encoded3 >> 2;
    bytes[p++] = (encoded3 & 3) << 6 | encoded4 & 63;
  }
  return arraybuffer;
};

// node_modules/engine.io-parser/build/esm/decodePacket.browser.js
var withNativeArrayBuffer2 = typeof ArrayBuffer === "function";
var decodePacket = (encodedPacket, binaryType) => {
  if (typeof encodedPacket !== "string") {
    return {
      type: "message",
      data: mapBinary(encodedPacket, binaryType)
    };
  }
  const type = encodedPacket.charAt(0);
  if (type === "b") {
    return {
      type: "message",
      data: decodeBase64Packet(encodedPacket.substring(1), binaryType)
    };
  }
  const packetType = PACKET_TYPES_REVERSE[type];
  if (!packetType) {
    return ERROR_PACKET;
  }
  return encodedPacket.length > 1 ? {
    type: PACKET_TYPES_REVERSE[type],
    data: encodedPacket.substring(1)
  } : {
    type: PACKET_TYPES_REVERSE[type]
  };
};
var decodeBase64Packet = (data, binaryType) => {
  if (withNativeArrayBuffer2) {
    const decoded = decode(data);
    return mapBinary(decoded, binaryType);
  } else {
    return { base64: true, data };
  }
};
var mapBinary = (data, binaryType) => {
  switch (binaryType) {
    case "blob":
      if (data instanceof Blob) {
        return data;
      } else {
        return new Blob([data]);
      }
    case "arraybuffer":
    default:
      if (data instanceof ArrayBuffer) {
        return data;
      } else {
        return data.buffer;
      }
  }
};

// node_modules/engine.io-parser/build/esm/index.js
var SEPARATOR = String.fromCharCode(30);
var encodePayload = (packets, callback) => {
  const length = packets.length;
  const encodedPackets = new Array(length);
  let count = 0;
  packets.forEach((packet, i) => {
    encodePacket(packet, false, (encodedPacket) => {
      encodedPackets[i] = encodedPacket;
      if (++count === length) {
        callback(encodedPackets.join(SEPARATOR));
      }
    });
  });
};
var decodePayload = (encodedPayload, binaryType) => {
  const encodedPackets = encodedPayload.split(SEPARATOR);
  const packets = [];
  for (let i = 0; i < encodedPackets.length; i++) {
    const decodedPacket = decodePacket(encodedPackets[i], binaryType);
    packets.push(decodedPacket);
    if (decodedPacket.type === "error") {
      break;
    }
  }
  return packets;
};
function createPacketEncoderStream() {
  return new TransformStream({
    transform(packet, controller) {
      encodePacketToBinary(packet, (encodedPacket) => {
        const payloadLength = encodedPacket.length;
        let header;
        if (payloadLength < 126) {
          header = new Uint8Array(1);
          new DataView(header.buffer).setUint8(0, payloadLength);
        } else if (payloadLength < 65536) {
          header = new Uint8Array(3);
          const view = new DataView(header.buffer);
          view.setUint8(0, 126);
          view.setUint16(1, payloadLength);
        } else {
          header = new Uint8Array(9);
          const view = new DataView(header.buffer);
          view.setUint8(0, 127);
          view.setBigUint64(1, BigInt(payloadLength));
        }
        if (packet.data && typeof packet.data !== "string") {
          header[0] |= 128;
        }
        controller.enqueue(header);
        controller.enqueue(encodedPacket);
      });
    }
  });
}
var TEXT_DECODER;
function totalLength(chunks) {
  return chunks.reduce((acc, chunk) => acc + chunk.length, 0);
}
function concatChunks(chunks, size) {
  if (chunks[0].length === size) {
    return chunks.shift();
  }
  const buffer = new Uint8Array(size);
  let j = 0;
  for (let i = 0; i < size; i++) {
    buffer[i] = chunks[0][j++];
    if (j === chunks[0].length) {
      chunks.shift();
      j = 0;
    }
  }
  if (chunks.length && j < chunks[0].length) {
    chunks[0] = chunks[0].slice(j);
  }
  return buffer;
}
function createPacketDecoderStream(maxPayload, binaryType) {
  if (!TEXT_DECODER) {
    TEXT_DECODER = new TextDecoder();
  }
  const chunks = [];
  let state = 0;
  let expectedLength = -1;
  let isBinary2 = false;
  return new TransformStream({
    transform(chunk, controller) {
      chunks.push(chunk);
      while (true) {
        if (state === 0) {
          if (totalLength(chunks) < 1) {
            break;
          }
          const header = concatChunks(chunks, 1);
          isBinary2 = (header[0] & 128) === 128;
          expectedLength = header[0] & 127;
          if (expectedLength < 126) {
            state = 3;
          } else if (expectedLength === 126) {
            state = 1;
          } else {
            state = 2;
          }
        } else if (state === 1) {
          if (totalLength(chunks) < 2) {
            break;
          }
          const headerArray = concatChunks(chunks, 2);
          expectedLength = new DataView(headerArray.buffer, headerArray.byteOffset, headerArray.length).getUint16(0);
          state = 3;
        } else if (state === 2) {
          if (totalLength(chunks) < 8) {
            break;
          }
          const headerArray = concatChunks(chunks, 8);
          const view = new DataView(headerArray.buffer, headerArray.byteOffset, headerArray.length);
          const n = view.getUint32(0);
          if (n > Math.pow(2, 53 - 32) - 1) {
            controller.enqueue(ERROR_PACKET);
            break;
          }
          expectedLength = n * Math.pow(2, 32) + view.getUint32(4);
          state = 3;
        } else {
          if (totalLength(chunks) < expectedLength) {
            break;
          }
          const data = concatChunks(chunks, expectedLength);
          controller.enqueue(decodePacket(isBinary2 ? data : TEXT_DECODER.decode(data), binaryType));
          state = 0;
        }
        if (expectedLength === 0 || expectedLength > maxPayload) {
          controller.enqueue(ERROR_PACKET);
          break;
        }
      }
    }
  });
}
var protocol = 4;

// node_modules/@socket.io/component-emitter/lib/esm/index.js
function Emitter(obj) {
  if (obj) return mixin(obj);
}
function mixin(obj) {
  for (var key in Emitter.prototype) {
    obj[key] = Emitter.prototype[key];
  }
  return obj;
}
Emitter.prototype.on = Emitter.prototype.addEventListener = function(event, fn) {
  this._callbacks = this._callbacks || {};
  (this._callbacks["$" + event] = this._callbacks["$" + event] || []).push(fn);
  return this;
};
Emitter.prototype.once = function(event, fn) {
  function on2() {
    this.off(event, on2);
    fn.apply(this, arguments);
  }
  on2.fn = fn;
  this.on(event, on2);
  return this;
};
Emitter.prototype.off = Emitter.prototype.removeListener = Emitter.prototype.removeAllListeners = Emitter.prototype.removeEventListener = function(event, fn) {
  this._callbacks = this._callbacks || {};
  if (0 == arguments.length) {
    this._callbacks = {};
    return this;
  }
  var callbacks = this._callbacks["$" + event];
  if (!callbacks) return this;
  if (1 == arguments.length) {
    delete this._callbacks["$" + event];
    return this;
  }
  var cb;
  for (var i = 0; i < callbacks.length; i++) {
    cb = callbacks[i];
    if (cb === fn || cb.fn === fn) {
      callbacks.splice(i, 1);
      break;
    }
  }
  if (callbacks.length === 0) {
    delete this._callbacks["$" + event];
  }
  return this;
};
Emitter.prototype.emit = function(event) {
  this._callbacks = this._callbacks || {};
  var args = new Array(arguments.length - 1), callbacks = this._callbacks["$" + event];
  for (var i = 1; i < arguments.length; i++) {
    args[i - 1] = arguments[i];
  }
  if (callbacks) {
    callbacks = callbacks.slice(0);
    for (var i = 0, len = callbacks.length; i < len; ++i) {
      callbacks[i].apply(this, args);
    }
  }
  return this;
};
Emitter.prototype.emitReserved = Emitter.prototype.emit;
Emitter.prototype.listeners = function(event) {
  this._callbacks = this._callbacks || {};
  return this._callbacks["$" + event] || [];
};
Emitter.prototype.hasListeners = function(event) {
  return !!this.listeners(event).length;
};

// node_modules/engine.io-client/build/esm/globals.js
var nextTick = (() => {
  const isPromiseAvailable = typeof Promise === "function" && typeof Promise.resolve === "function";
  if (isPromiseAvailable) {
    return (cb) => Promise.resolve().then(cb);
  } else {
    return (cb, setTimeoutFn) => setTimeoutFn(cb, 0);
  }
})();
var globalThisShim = (() => {
  if (typeof self !== "undefined") {
    return self;
  } else if (typeof window !== "undefined") {
    return window;
  } else {
    return Function("return this")();
  }
})();
var defaultBinaryType = "arraybuffer";
function createCookieJar() {
}

// node_modules/engine.io-client/build/esm/util.js
function pick(obj, ...attr) {
  return attr.reduce((acc, k) => {
    if (obj.hasOwnProperty(k)) {
      acc[k] = obj[k];
    }
    return acc;
  }, {});
}
var NATIVE_SET_TIMEOUT = globalThisShim.setTimeout;
var NATIVE_CLEAR_TIMEOUT = globalThisShim.clearTimeout;
function installTimerFunctions(obj, opts) {
  if (opts.useNativeTimers) {
    obj.setTimeoutFn = NATIVE_SET_TIMEOUT.bind(globalThisShim);
    obj.clearTimeoutFn = NATIVE_CLEAR_TIMEOUT.bind(globalThisShim);
  } else {
    obj.setTimeoutFn = globalThisShim.setTimeout.bind(globalThisShim);
    obj.clearTimeoutFn = globalThisShim.clearTimeout.bind(globalThisShim);
  }
}
var BASE64_OVERHEAD = 1.33;
function byteLength(obj) {
  if (typeof obj === "string") {
    return utf8Length(obj);
  }
  return Math.ceil((obj.byteLength || obj.size) * BASE64_OVERHEAD);
}
function utf8Length(str) {
  let c = 0, length = 0;
  for (let i = 0, l = str.length; i < l; i++) {
    c = str.charCodeAt(i);
    if (c < 128) {
      length += 1;
    } else if (c < 2048) {
      length += 2;
    } else if (c < 55296 || c >= 57344) {
      length += 3;
    } else {
      i++;
      length += 4;
    }
  }
  return length;
}
function randomString() {
  return Date.now().toString(36).substring(3) + Math.random().toString(36).substring(2, 5);
}

// node_modules/engine.io-client/build/esm/contrib/parseqs.js
function encode(obj) {
  let str = "";
  for (let i in obj) {
    if (obj.hasOwnProperty(i)) {
      if (str.length)
        str += "&";
      str += encodeURIComponent(i) + "=" + encodeURIComponent(obj[i]);
    }
  }
  return str;
}
function decode2(qs) {
  let qry = {};
  let pairs = qs.split("&");
  for (let i = 0, l = pairs.length; i < l; i++) {
    let pair = pairs[i].split("=");
    qry[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1]);
  }
  return qry;
}

// node_modules/engine.io-client/build/esm/transport.js
var TransportError = class extends Error {
  constructor(reason, description, context) {
    super(reason);
    this.description = description;
    this.context = context;
    this.type = "TransportError";
  }
};
var Transport = class extends Emitter {
  /**
   * Transport abstract constructor.
   *
   * @param {Object} opts - options
   * @protected
   */
  constructor(opts) {
    super();
    this.writable = false;
    installTimerFunctions(this, opts);
    this.opts = opts;
    this.query = opts.query;
    this.socket = opts.socket;
    this.supportsBinary = !opts.forceBase64;
  }
  /**
   * Emits an error.
   *
   * @param {String} reason
   * @param description
   * @param context - the error context
   * @return {Transport} for chaining
   * @protected
   */
  onError(reason, description, context) {
    super.emitReserved("error", new TransportError(reason, description, context));
    return this;
  }
  /**
   * Opens the transport.
   */
  open() {
    this.readyState = "opening";
    this.doOpen();
    return this;
  }
  /**
   * Closes the transport.
   */
  close() {
    if (this.readyState === "opening" || this.readyState === "open") {
      this.doClose();
      this.onClose();
    }
    return this;
  }
  /**
   * Sends multiple packets.
   *
   * @param {Array} packets
   */
  send(packets) {
    if (this.readyState === "open") {
      this.write(packets);
    } else {
    }
  }
  /**
   * Called upon open
   *
   * @protected
   */
  onOpen() {
    this.readyState = "open";
    this.writable = true;
    super.emitReserved("open");
  }
  /**
   * Called with data.
   *
   * @param {String} data
   * @protected
   */
  onData(data) {
    const packet = decodePacket(data, this.socket.binaryType);
    this.onPacket(packet);
  }
  /**
   * Called with a decoded packet.
   *
   * @protected
   */
  onPacket(packet) {
    super.emitReserved("packet", packet);
  }
  /**
   * Called upon close.
   *
   * @protected
   */
  onClose(details) {
    this.readyState = "closed";
    super.emitReserved("close", details);
  }
  /**
   * Pauses the transport, in order not to lose packets during an upgrade.
   *
   * @param onPause
   */
  pause(onPause) {
  }
  createUri(schema, query = {}) {
    return schema + "://" + this._hostname() + this._port() + this.opts.path + this._query(query);
  }
  _hostname() {
    const hostname = this.opts.hostname;
    return hostname.indexOf(":") === -1 ? hostname : "[" + hostname + "]";
  }
  _port() {
    if (this.opts.port && (this.opts.secure && Number(this.opts.port) !== 443 || !this.opts.secure && Number(this.opts.port) !== 80)) {
      return ":" + this.opts.port;
    } else {
      return "";
    }
  }
  _query(query) {
    const encodedQuery = encode(query);
    return encodedQuery.length ? "?" + encodedQuery : "";
  }
};

// node_modules/engine.io-client/build/esm/transports/polling.js
var Polling = class extends Transport {
  constructor() {
    super(...arguments);
    this._polling = false;
  }
  get name() {
    return "polling";
  }
  /**
   * Opens the socket (triggers polling). We write a PING message to determine
   * when the transport is open.
   *
   * @protected
   */
  doOpen() {
    this._poll();
  }
  /**
   * Pauses polling.
   *
   * @param {Function} onPause - callback upon buffers are flushed and transport is paused
   * @package
   */
  pause(onPause) {
    this.readyState = "pausing";
    const pause = () => {
      this.readyState = "paused";
      onPause();
    };
    if (this._polling || !this.writable) {
      let total = 0;
      if (this._polling) {
        total++;
        this.once("pollComplete", function() {
          --total || pause();
        });
      }
      if (!this.writable) {
        total++;
        this.once("drain", function() {
          --total || pause();
        });
      }
    } else {
      pause();
    }
  }
  /**
   * Starts polling cycle.
   *
   * @private
   */
  _poll() {
    this._polling = true;
    this.doPoll();
    this.emitReserved("poll");
  }
  /**
   * Overloads onData to detect payloads.
   *
   * @protected
   */
  onData(data) {
    const callback = (packet) => {
      if ("opening" === this.readyState && packet.type === "open") {
        this.onOpen();
      }
      if ("close" === packet.type) {
        this.onClose({ description: "transport closed by the server" });
        return false;
      }
      this.onPacket(packet);
    };
    decodePayload(data, this.socket.binaryType).forEach(callback);
    if ("closed" !== this.readyState) {
      this._polling = false;
      this.emitReserved("pollComplete");
      if ("open" === this.readyState) {
        this._poll();
      } else {
      }
    }
  }
  /**
   * For polling, send a close packet.
   *
   * @protected
   */
  doClose() {
    const close = () => {
      this.write([{ type: "close" }]);
    };
    if ("open" === this.readyState) {
      close();
    } else {
      this.once("open", close);
    }
  }
  /**
   * Writes a packets payload.
   *
   * @param {Array} packets - data packets
   * @protected
   */
  write(packets) {
    this.writable = false;
    encodePayload(packets, (data) => {
      this.doWrite(data, () => {
        this.writable = true;
        this.emitReserved("drain");
      });
    });
  }
  /**
   * Generates uri for connection.
   *
   * @private
   */
  uri() {
    const schema = this.opts.secure ? "https" : "http";
    const query = this.query || {};
    if (false !== this.opts.timestampRequests) {
      query[this.opts.timestampParam] = randomString();
    }
    if (!this.supportsBinary && !query.sid) {
      query.b64 = 1;
    }
    return this.createUri(schema, query);
  }
};

// node_modules/engine.io-client/build/esm/contrib/has-cors.js
var value = false;
try {
  value = typeof XMLHttpRequest !== "undefined" && "withCredentials" in new XMLHttpRequest();
} catch (err) {
}
var hasCORS = value;

// node_modules/engine.io-client/build/esm/transports/polling-xhr.js
function empty() {
}
var BaseXHR = class extends Polling {
  /**
   * XHR Polling constructor.
   *
   * @param {Object} opts
   * @package
   */
  constructor(opts) {
    super(opts);
    if (typeof location !== "undefined") {
      const isSSL = "https:" === location.protocol;
      let port = location.port;
      if (!port) {
        port = isSSL ? "443" : "80";
      }
      this.xd = typeof location !== "undefined" && opts.hostname !== location.hostname || port !== opts.port;
    }
  }
  /**
   * Sends data.
   *
   * @param {String} data - data to send.
   * @param {Function} fn - called upon flush.
   * @private
   */
  doWrite(data, fn) {
    const req = this.request({
      method: "POST",
      data
    });
    req.on("success", fn);
    req.on("error", (xhrStatus, context) => {
      this.onError("xhr post error", xhrStatus, context);
    });
  }
  /**
   * Starts a poll cycle.
   *
   * @private
   */
  doPoll() {
    const req = this.request();
    req.on("data", this.onData.bind(this));
    req.on("error", (xhrStatus, context) => {
      this.onError("xhr poll error", xhrStatus, context);
    });
    this.pollXhr = req;
  }
};
var Request = class _Request extends Emitter {
  /**
   * Request constructor
   *
   * @param {Object} options
   * @package
   */
  constructor(createRequest, uri, opts) {
    super();
    this.createRequest = createRequest;
    installTimerFunctions(this, opts);
    this._opts = opts;
    this._method = opts.method || "GET";
    this._uri = uri;
    this._data = void 0 !== opts.data ? opts.data : null;
    this._create();
  }
  /**
   * Creates the XHR object and sends the request.
   *
   * @private
   */
  _create() {
    var _a;
    const opts = pick(this._opts, "agent", "pfx", "key", "passphrase", "cert", "ca", "ciphers", "rejectUnauthorized", "autoUnref");
    opts.xdomain = !!this._opts.xd;
    const xhr = this._xhr = this.createRequest(opts);
    try {
      xhr.open(this._method, this._uri, true);
      try {
        if (this._opts.extraHeaders) {
          xhr.setDisableHeaderCheck && xhr.setDisableHeaderCheck(true);
          for (let i in this._opts.extraHeaders) {
            if (this._opts.extraHeaders.hasOwnProperty(i)) {
              xhr.setRequestHeader(i, this._opts.extraHeaders[i]);
            }
          }
        }
      } catch (e) {
      }
      if ("POST" === this._method) {
        try {
          xhr.setRequestHeader("Content-type", "text/plain;charset=UTF-8");
        } catch (e) {
        }
      }
      try {
        xhr.setRequestHeader("Accept", "*/*");
      } catch (e) {
      }
      (_a = this._opts.cookieJar) === null || _a === void 0 ? void 0 : _a.addCookies(xhr);
      if ("withCredentials" in xhr) {
        xhr.withCredentials = this._opts.withCredentials;
      }
      if (this._opts.requestTimeout) {
        xhr.timeout = this._opts.requestTimeout;
      }
      xhr.onreadystatechange = () => {
        var _a2;
        if (xhr.readyState === 3) {
          (_a2 = this._opts.cookieJar) === null || _a2 === void 0 ? void 0 : _a2.parseCookies(
            // @ts-ignore
            xhr.getResponseHeader("set-cookie")
          );
        }
        if (4 !== xhr.readyState)
          return;
        if (200 === xhr.status || 1223 === xhr.status) {
          this._onLoad();
        } else {
          this.setTimeoutFn(() => {
            this._onError(typeof xhr.status === "number" ? xhr.status : 0);
          }, 0);
        }
      };
      xhr.send(this._data);
    } catch (e) {
      this.setTimeoutFn(() => {
        this._onError(e);
      }, 0);
      return;
    }
    if (typeof document !== "undefined") {
      this._index = _Request.requestsCount++;
      _Request.requests[this._index] = this;
    }
  }
  /**
   * Called upon error.
   *
   * @private
   */
  _onError(err) {
    this.emitReserved("error", err, this._xhr);
    this._cleanup(true);
  }
  /**
   * Cleans up house.
   *
   * @private
   */
  _cleanup(fromError) {
    if ("undefined" === typeof this._xhr || null === this._xhr) {
      return;
    }
    this._xhr.onreadystatechange = empty;
    if (fromError) {
      try {
        this._xhr.abort();
      } catch (e) {
      }
    }
    if (typeof document !== "undefined") {
      delete _Request.requests[this._index];
    }
    this._xhr = null;
  }
  /**
   * Called upon load.
   *
   * @private
   */
  _onLoad() {
    const data = this._xhr.responseText;
    if (data !== null) {
      this.emitReserved("data", data);
      this.emitReserved("success");
      this._cleanup();
    }
  }
  /**
   * Aborts the request.
   *
   * @package
   */
  abort() {
    this._cleanup();
  }
};
Request.requestsCount = 0;
Request.requests = {};
if (typeof document !== "undefined") {
  if (typeof attachEvent === "function") {
    attachEvent("onunload", unloadHandler);
  } else if (typeof addEventListener === "function") {
    const terminationEvent = "onpagehide" in globalThisShim ? "pagehide" : "unload";
    addEventListener(terminationEvent, unloadHandler, false);
  }
}
function unloadHandler() {
  for (let i in Request.requests) {
    if (Request.requests.hasOwnProperty(i)) {
      Request.requests[i].abort();
    }
  }
}
var hasXHR2 = function() {
  const xhr = newRequest({
    xdomain: false
  });
  return xhr && xhr.responseType !== null;
}();
var XHR = class extends BaseXHR {
  constructor(opts) {
    super(opts);
    const forceBase64 = opts && opts.forceBase64;
    this.supportsBinary = hasXHR2 && !forceBase64;
  }
  request(opts = {}) {
    Object.assign(opts, { xd: this.xd }, this.opts);
    return new Request(newRequest, this.uri(), opts);
  }
};
function newRequest(opts) {
  const xdomain = opts.xdomain;
  try {
    if ("undefined" !== typeof XMLHttpRequest && (!xdomain || hasCORS)) {
      return new XMLHttpRequest();
    }
  } catch (e) {
  }
  if (!xdomain) {
    try {
      return new globalThisShim[["Active"].concat("Object").join("X")]("Microsoft.XMLHTTP");
    } catch (e) {
    }
  }
}

// node_modules/engine.io-client/build/esm/transports/websocket.js
var isReactNative = typeof navigator !== "undefined" && typeof navigator.product === "string" && navigator.product.toLowerCase() === "reactnative";
var BaseWS = class extends Transport {
  get name() {
    return "websocket";
  }
  doOpen() {
    const uri = this.uri();
    const protocols = this.opts.protocols;
    const opts = isReactNative ? {} : pick(this.opts, "agent", "perMessageDeflate", "pfx", "key", "passphrase", "cert", "ca", "ciphers", "rejectUnauthorized", "localAddress", "protocolVersion", "origin", "maxPayload", "family", "checkServerIdentity");
    if (this.opts.extraHeaders) {
      opts.headers = this.opts.extraHeaders;
    }
    try {
      this.ws = this.createSocket(uri, protocols, opts);
    } catch (err) {
      return this.emitReserved("error", err);
    }
    this.ws.binaryType = this.socket.binaryType;
    this.addEventListeners();
  }
  /**
   * Adds event listeners to the socket
   *
   * @private
   */
  addEventListeners() {
    this.ws.onopen = () => {
      if (this.opts.autoUnref) {
        this.ws._socket.unref();
      }
      this.onOpen();
    };
    this.ws.onclose = (closeEvent) => this.onClose({
      description: "websocket connection closed",
      context: closeEvent
    });
    this.ws.onmessage = (ev) => this.onData(ev.data);
    this.ws.onerror = (e) => this.onError("websocket error", e);
  }
  write(packets) {
    this.writable = false;
    for (let i = 0; i < packets.length; i++) {
      const packet = packets[i];
      const lastPacket = i === packets.length - 1;
      encodePacket(packet, this.supportsBinary, (data) => {
        try {
          this.doWrite(packet, data);
        } catch (e) {
        }
        if (lastPacket) {
          nextTick(() => {
            this.writable = true;
            this.emitReserved("drain");
          }, this.setTimeoutFn);
        }
      });
    }
  }
  doClose() {
    if (typeof this.ws !== "undefined") {
      this.ws.onerror = () => {
      };
      this.ws.close();
      this.ws = null;
    }
  }
  /**
   * Generates uri for connection.
   *
   * @private
   */
  uri() {
    const schema = this.opts.secure ? "wss" : "ws";
    const query = this.query || {};
    if (this.opts.timestampRequests) {
      query[this.opts.timestampParam] = randomString();
    }
    if (!this.supportsBinary) {
      query.b64 = 1;
    }
    return this.createUri(schema, query);
  }
};
var WebSocketCtor = globalThisShim.WebSocket || globalThisShim.MozWebSocket;
var WS = class extends BaseWS {
  createSocket(uri, protocols, opts) {
    return !isReactNative ? protocols ? new WebSocketCtor(uri, protocols) : new WebSocketCtor(uri) : new WebSocketCtor(uri, protocols, opts);
  }
  doWrite(_packet, data) {
    this.ws.send(data);
  }
};

// node_modules/engine.io-client/build/esm/transports/webtransport.js
var WT = class extends Transport {
  get name() {
    return "webtransport";
  }
  doOpen() {
    try {
      this._transport = new WebTransport(this.createUri("https"), this.opts.transportOptions[this.name]);
    } catch (err) {
      return this.emitReserved("error", err);
    }
    this._transport.closed.then(() => {
      this.onClose();
    }).catch((err) => {
      this.onError("webtransport error", err);
    });
    this._transport.ready.then(() => {
      this._transport.createBidirectionalStream().then((stream) => {
        const decoderStream = createPacketDecoderStream(Number.MAX_SAFE_INTEGER, this.socket.binaryType);
        const reader = stream.readable.pipeThrough(decoderStream).getReader();
        const encoderStream = createPacketEncoderStream();
        encoderStream.readable.pipeTo(stream.writable);
        this._writer = encoderStream.writable.getWriter();
        const read = () => {
          reader.read().then(({ done, value: value2 }) => {
            if (done) {
              return;
            }
            this.onPacket(value2);
            read();
          }).catch((err) => {
          });
        };
        read();
        const packet = { type: "open" };
        if (this.query.sid) {
          packet.data = `{"sid":"${this.query.sid}"}`;
        }
        this._writer.write(packet).then(() => this.onOpen());
      });
    });
  }
  write(packets) {
    this.writable = false;
    for (let i = 0; i < packets.length; i++) {
      const packet = packets[i];
      const lastPacket = i === packets.length - 1;
      this._writer.write(packet).then(() => {
        if (lastPacket) {
          nextTick(() => {
            this.writable = true;
            this.emitReserved("drain");
          }, this.setTimeoutFn);
        }
      });
    }
  }
  doClose() {
    var _a;
    (_a = this._transport) === null || _a === void 0 ? void 0 : _a.close();
  }
};

// node_modules/engine.io-client/build/esm/transports/index.js
var transports = {
  websocket: WS,
  webtransport: WT,
  polling: XHR
};

// node_modules/engine.io-client/build/esm/contrib/parseuri.js
var re = /^(?:(?![^:@\/?#]+:[^:@\/]*@)(http|https|ws|wss):\/\/)?((?:(([^:@\/?#]*)(?::([^:@\/?#]*))?)?@)?((?:[a-f0-9]{0,4}:){2,7}[a-f0-9]{0,4}|[^:\/?#]*)(?::(\d*))?)(((\/(?:[^?#](?![^?#\/]*\.[^?#\/.]+(?:[?#]|$)))*\/?)?([^?#\/]*))(?:\?([^#]*))?(?:#(.*))?)/;
var parts = [
  "source",
  "protocol",
  "authority",
  "userInfo",
  "user",
  "password",
  "host",
  "port",
  "relative",
  "path",
  "directory",
  "file",
  "query",
  "anchor"
];
function parse(str) {
  if (str.length > 8e3) {
    throw "URI too long";
  }
  const src = str, b = str.indexOf("["), e = str.indexOf("]");
  if (b != -1 && e != -1) {
    str = str.substring(0, b) + str.substring(b, e).replace(/:/g, ";") + str.substring(e, str.length);
  }
  let m = re.exec(str || ""), uri = {}, i = 14;
  while (i--) {
    uri[parts[i]] = m[i] || "";
  }
  if (b != -1 && e != -1) {
    uri.source = src;
    uri.host = uri.host.substring(1, uri.host.length - 1).replace(/;/g, ":");
    uri.authority = uri.authority.replace("[", "").replace("]", "").replace(/;/g, ":");
    uri.ipv6uri = true;
  }
  uri.pathNames = pathNames(uri, uri["path"]);
  uri.queryKey = queryKey(uri, uri["query"]);
  return uri;
}
function pathNames(obj, path) {
  const regx = /\/{2,9}/g, names = path.replace(regx, "/").split("/");
  if (path.slice(0, 1) == "/" || path.length === 0) {
    names.splice(0, 1);
  }
  if (path.slice(-1) == "/") {
    names.splice(names.length - 1, 1);
  }
  return names;
}
function queryKey(uri, query) {
  const data = {};
  query.replace(/(?:^|&)([^&=]*)=?([^&]*)/g, function($0, $1, $2) {
    if ($1) {
      data[$1] = $2;
    }
  });
  return data;
}

// node_modules/engine.io-client/build/esm/socket.js
var withEventListeners = typeof addEventListener === "function" && typeof removeEventListener === "function";
var OFFLINE_EVENT_LISTENERS = [];
if (withEventListeners) {
  addEventListener("offline", () => {
    OFFLINE_EVENT_LISTENERS.forEach((listener) => listener());
  }, false);
}
var SocketWithoutUpgrade = class _SocketWithoutUpgrade extends Emitter {
  /**
   * Socket constructor.
   *
   * @param {String|Object} uri - uri or options
   * @param {Object} opts - options
   */
  constructor(uri, opts) {
    super();
    this.binaryType = defaultBinaryType;
    this.writeBuffer = [];
    this._prevBufferLen = 0;
    this._pingInterval = -1;
    this._pingTimeout = -1;
    this._maxPayload = -1;
    this._pingTimeoutTime = Infinity;
    if (uri && "object" === typeof uri) {
      opts = uri;
      uri = null;
    }
    if (uri) {
      const parsedUri = parse(uri);
      opts.hostname = parsedUri.host;
      opts.secure = parsedUri.protocol === "https" || parsedUri.protocol === "wss";
      opts.port = parsedUri.port;
      if (parsedUri.query)
        opts.query = parsedUri.query;
    } else if (opts.host) {
      opts.hostname = parse(opts.host).host;
    }
    installTimerFunctions(this, opts);
    this.secure = null != opts.secure ? opts.secure : typeof location !== "undefined" && "https:" === location.protocol;
    if (opts.hostname && !opts.port) {
      opts.port = this.secure ? "443" : "80";
    }
    this.hostname = opts.hostname || (typeof location !== "undefined" ? location.hostname : "localhost");
    this.port = opts.port || (typeof location !== "undefined" && location.port ? location.port : this.secure ? "443" : "80");
    this.transports = [];
    this._transportsByName = {};
    opts.transports.forEach((t) => {
      const transportName = t.prototype.name;
      this.transports.push(transportName);
      this._transportsByName[transportName] = t;
    });
    this.opts = Object.assign({
      path: "/engine.io",
      agent: false,
      withCredentials: false,
      upgrade: true,
      timestampParam: "t",
      rememberUpgrade: false,
      addTrailingSlash: true,
      rejectUnauthorized: true,
      perMessageDeflate: {
        threshold: 1024
      },
      transportOptions: {},
      closeOnBeforeunload: false
    }, opts);
    this.opts.path = this.opts.path.replace(/\/$/, "") + (this.opts.addTrailingSlash ? "/" : "");
    if (typeof this.opts.query === "string") {
      this.opts.query = decode2(this.opts.query);
    }
    if (withEventListeners) {
      if (this.opts.closeOnBeforeunload) {
        this._beforeunloadEventListener = () => {
          if (this.transport) {
            this.transport.removeAllListeners();
            this.transport.close();
          }
        };
        addEventListener("beforeunload", this._beforeunloadEventListener, false);
      }
      if (this.hostname !== "localhost") {
        this._offlineEventListener = () => {
          this._onClose("transport close", {
            description: "network connection lost"
          });
        };
        OFFLINE_EVENT_LISTENERS.push(this._offlineEventListener);
      }
    }
    if (this.opts.withCredentials) {
      this._cookieJar = createCookieJar();
    }
    this._open();
  }
  /**
   * Creates transport of the given type.
   *
   * @param {String} name - transport name
   * @return {Transport}
   * @private
   */
  createTransport(name) {
    const query = Object.assign({}, this.opts.query);
    query.EIO = protocol;
    query.transport = name;
    if (this.id)
      query.sid = this.id;
    const opts = Object.assign({}, this.opts, {
      query,
      socket: this,
      hostname: this.hostname,
      secure: this.secure,
      port: this.port
    }, this.opts.transportOptions[name]);
    return new this._transportsByName[name](opts);
  }
  /**
   * Initializes transport to use and starts probe.
   *
   * @private
   */
  _open() {
    if (this.transports.length === 0) {
      this.setTimeoutFn(() => {
        this.emitReserved("error", "No transports available");
      }, 0);
      return;
    }
    const transportName = this.opts.rememberUpgrade && _SocketWithoutUpgrade.priorWebsocketSuccess && this.transports.indexOf("websocket") !== -1 ? "websocket" : this.transports[0];
    this.readyState = "opening";
    const transport = this.createTransport(transportName);
    transport.open();
    this.setTransport(transport);
  }
  /**
   * Sets the current transport. Disables the existing one (if any).
   *
   * @private
   */
  setTransport(transport) {
    if (this.transport) {
      this.transport.removeAllListeners();
    }
    this.transport = transport;
    transport.on("drain", this._onDrain.bind(this)).on("packet", this._onPacket.bind(this)).on("error", this._onError.bind(this)).on("close", (reason) => this._onClose("transport close", reason));
  }
  /**
   * Called when connection is deemed open.
   *
   * @private
   */
  onOpen() {
    this.readyState = "open";
    _SocketWithoutUpgrade.priorWebsocketSuccess = "websocket" === this.transport.name;
    this.emitReserved("open");
    this.flush();
  }
  /**
   * Handles a packet.
   *
   * @private
   */
  _onPacket(packet) {
    if ("opening" === this.readyState || "open" === this.readyState || "closing" === this.readyState) {
      this.emitReserved("packet", packet);
      this.emitReserved("heartbeat");
      switch (packet.type) {
        case "open":
          this.onHandshake(JSON.parse(packet.data));
          break;
        case "ping":
          this._sendPacket("pong");
          this.emitReserved("ping");
          this.emitReserved("pong");
          this._resetPingTimeout();
          break;
        case "error":
          const err = new Error("server error");
          err.code = packet.data;
          this._onError(err);
          break;
        case "message":
          this.emitReserved("data", packet.data);
          this.emitReserved("message", packet.data);
          break;
      }
    } else {
    }
  }
  /**
   * Called upon handshake completion.
   *
   * @param {Object} data - handshake obj
   * @private
   */
  onHandshake(data) {
    this.emitReserved("handshake", data);
    this.id = data.sid;
    this.transport.query.sid = data.sid;
    this._pingInterval = data.pingInterval;
    this._pingTimeout = data.pingTimeout;
    this._maxPayload = data.maxPayload;
    this.onOpen();
    if ("closed" === this.readyState)
      return;
    this._resetPingTimeout();
  }
  /**
   * Sets and resets ping timeout timer based on server pings.
   *
   * @private
   */
  _resetPingTimeout() {
    this.clearTimeoutFn(this._pingTimeoutTimer);
    const delay = this._pingInterval + this._pingTimeout;
    this._pingTimeoutTime = Date.now() + delay;
    this._pingTimeoutTimer = this.setTimeoutFn(() => {
      this._onClose("ping timeout");
    }, delay);
    if (this.opts.autoUnref) {
      this._pingTimeoutTimer.unref();
    }
  }
  /**
   * Called on `drain` event
   *
   * @private
   */
  _onDrain() {
    this.writeBuffer.splice(0, this._prevBufferLen);
    this._prevBufferLen = 0;
    if (0 === this.writeBuffer.length) {
      this.emitReserved("drain");
    } else {
      this.flush();
    }
  }
  /**
   * Flush write buffers.
   *
   * @private
   */
  flush() {
    if ("closed" !== this.readyState && this.transport.writable && !this.upgrading && this.writeBuffer.length) {
      const packets = this._getWritablePackets();
      this.transport.send(packets);
      this._prevBufferLen = packets.length;
      this.emitReserved("flush");
    }
  }
  /**
   * Ensure the encoded size of the writeBuffer is below the maxPayload value sent by the server (only for HTTP
   * long-polling)
   *
   * @private
   */
  _getWritablePackets() {
    const shouldCheckPayloadSize = this._maxPayload && this.transport.name === "polling" && this.writeBuffer.length > 1;
    if (!shouldCheckPayloadSize) {
      return this.writeBuffer;
    }
    let payloadSize = 1;
    for (let i = 0; i < this.writeBuffer.length; i++) {
      const data = this.writeBuffer[i].data;
      if (data) {
        payloadSize += byteLength(data);
      }
      if (i > 0 && payloadSize > this._maxPayload) {
        return this.writeBuffer.slice(0, i);
      }
      payloadSize += 2;
    }
    return this.writeBuffer;
  }
  /**
   * Checks whether the heartbeat timer has expired but the socket has not yet been notified.
   *
   * Note: this method is private for now because it does not really fit the WebSocket API, but if we put it in the
   * `write()` method then the message would not be buffered by the Socket.IO client.
   *
   * @return {boolean}
   * @private
   */
  /* private */
  _hasPingExpired() {
    if (!this._pingTimeoutTime)
      return true;
    const hasExpired = Date.now() > this._pingTimeoutTime;
    if (hasExpired) {
      this._pingTimeoutTime = 0;
      nextTick(() => {
        this._onClose("ping timeout");
      }, this.setTimeoutFn);
    }
    return hasExpired;
  }
  /**
   * Sends a message.
   *
   * @param {String} msg - message.
   * @param {Object} options.
   * @param {Function} fn - callback function.
   * @return {Socket} for chaining.
   */
  write(msg, options, fn) {
    this._sendPacket("message", msg, options, fn);
    return this;
  }
  /**
   * Sends a message. Alias of {@link Socket#write}.
   *
   * @param {String} msg - message.
   * @param {Object} options.
   * @param {Function} fn - callback function.
   * @return {Socket} for chaining.
   */
  send(msg, options, fn) {
    this._sendPacket("message", msg, options, fn);
    return this;
  }
  /**
   * Sends a packet.
   *
   * @param {String} type - packet type.
   * @param {String} data.
   * @param {Object} options.
   * @param {Function} fn - callback function.
   * @private
   */
  _sendPacket(type, data, options, fn) {
    if ("function" === typeof data) {
      fn = data;
      data = void 0;
    }
    if ("function" === typeof options) {
      fn = options;
      options = null;
    }
    if ("closing" === this.readyState || "closed" === this.readyState) {
      return;
    }
    options = options || {};
    options.compress = false !== options.compress;
    const packet = {
      type,
      data,
      options
    };
    this.emitReserved("packetCreate", packet);
    this.writeBuffer.push(packet);
    if (fn)
      this.once("flush", fn);
    this.flush();
  }
  /**
   * Closes the connection.
   */
  close() {
    const close = () => {
      this._onClose("forced close");
      this.transport.close();
    };
    const cleanupAndClose = () => {
      this.off("upgrade", cleanupAndClose);
      this.off("upgradeError", cleanupAndClose);
      close();
    };
    const waitForUpgrade = () => {
      this.once("upgrade", cleanupAndClose);
      this.once("upgradeError", cleanupAndClose);
    };
    if ("opening" === this.readyState || "open" === this.readyState) {
      this.readyState = "closing";
      if (this.writeBuffer.length) {
        this.once("drain", () => {
          if (this.upgrading) {
            waitForUpgrade();
          } else {
            close();
          }
        });
      } else if (this.upgrading) {
        waitForUpgrade();
      } else {
        close();
      }
    }
    return this;
  }
  /**
   * Called upon transport error
   *
   * @private
   */
  _onError(err) {
    _SocketWithoutUpgrade.priorWebsocketSuccess = false;
    if (this.opts.tryAllTransports && this.transports.length > 1 && this.readyState === "opening") {
      this.transports.shift();
      return this._open();
    }
    this.emitReserved("error", err);
    this._onClose("transport error", err);
  }
  /**
   * Called upon transport close.
   *
   * @private
   */
  _onClose(reason, description) {
    if ("opening" === this.readyState || "open" === this.readyState || "closing" === this.readyState) {
      this.clearTimeoutFn(this._pingTimeoutTimer);
      this.transport.removeAllListeners("close");
      this.transport.close();
      this.transport.removeAllListeners();
      if (withEventListeners) {
        if (this._beforeunloadEventListener) {
          removeEventListener("beforeunload", this._beforeunloadEventListener, false);
        }
        if (this._offlineEventListener) {
          const i = OFFLINE_EVENT_LISTENERS.indexOf(this._offlineEventListener);
          if (i !== -1) {
            OFFLINE_EVENT_LISTENERS.splice(i, 1);
          }
        }
      }
      this.readyState = "closed";
      this.id = null;
      this.emitReserved("close", reason, description);
      this.writeBuffer = [];
      this._prevBufferLen = 0;
    }
  }
};
SocketWithoutUpgrade.protocol = protocol;
var SocketWithUpgrade = class extends SocketWithoutUpgrade {
  constructor() {
    super(...arguments);
    this._upgrades = [];
  }
  onOpen() {
    super.onOpen();
    if ("open" === this.readyState && this.opts.upgrade) {
      for (let i = 0; i < this._upgrades.length; i++) {
        this._probe(this._upgrades[i]);
      }
    }
  }
  /**
   * Probes a transport.
   *
   * @param {String} name - transport name
   * @private
   */
  _probe(name) {
    let transport = this.createTransport(name);
    let failed = false;
    SocketWithoutUpgrade.priorWebsocketSuccess = false;
    const onTransportOpen = () => {
      if (failed)
        return;
      transport.send([{ type: "ping", data: "probe" }]);
      transport.once("packet", (msg) => {
        if (failed)
          return;
        if ("pong" === msg.type && "probe" === msg.data) {
          this.upgrading = true;
          this.emitReserved("upgrading", transport);
          if (!transport)
            return;
          SocketWithoutUpgrade.priorWebsocketSuccess = "websocket" === transport.name;
          this.transport.pause(() => {
            if (failed)
              return;
            if ("closed" === this.readyState)
              return;
            cleanup();
            this.setTransport(transport);
            transport.send([{ type: "upgrade" }]);
            this.emitReserved("upgrade", transport);
            transport = null;
            this.upgrading = false;
            this.flush();
          });
        } else {
          const err = new Error("probe error");
          err.transport = transport.name;
          this.emitReserved("upgradeError", err);
        }
      });
    };
    function freezeTransport() {
      if (failed)
        return;
      failed = true;
      cleanup();
      transport.close();
      transport = null;
    }
    const onerror = (err) => {
      const error = new Error("probe error: " + err);
      error.transport = transport.name;
      freezeTransport();
      this.emitReserved("upgradeError", error);
    };
    function onTransportClose() {
      onerror("transport closed");
    }
    function onclose() {
      onerror("socket closed");
    }
    function onupgrade(to) {
      if (transport && to.name !== transport.name) {
        freezeTransport();
      }
    }
    const cleanup = () => {
      transport.removeListener("open", onTransportOpen);
      transport.removeListener("error", onerror);
      transport.removeListener("close", onTransportClose);
      this.off("close", onclose);
      this.off("upgrading", onupgrade);
    };
    transport.once("open", onTransportOpen);
    transport.once("error", onerror);
    transport.once("close", onTransportClose);
    this.once("close", onclose);
    this.once("upgrading", onupgrade);
    if (this._upgrades.indexOf("webtransport") !== -1 && name !== "webtransport") {
      this.setTimeoutFn(() => {
        if (!failed) {
          transport.open();
        }
      }, 200);
    } else {
      transport.open();
    }
  }
  onHandshake(data) {
    this._upgrades = this._filterUpgrades(data.upgrades);
    super.onHandshake(data);
  }
  /**
   * Filters upgrades, returning only those matching client transports.
   *
   * @param {Array} upgrades - server upgrades
   * @private
   */
  _filterUpgrades(upgrades) {
    const filteredUpgrades = [];
    for (let i = 0; i < upgrades.length; i++) {
      if (~this.transports.indexOf(upgrades[i]))
        filteredUpgrades.push(upgrades[i]);
    }
    return filteredUpgrades;
  }
};
var Socket = class extends SocketWithUpgrade {
  constructor(uri, opts = {}) {
    const isOptionsOnly = typeof uri === "object";
    const o = isOptionsOnly ? { ...uri } : { ...opts };
    if (!o.transports || o.transports && typeof o.transports[0] === "string") {
      o.transports = (o.transports || ["polling", "websocket", "webtransport"]).map((transportName) => transports[transportName]).filter((t) => !!t);
    }
    super(isOptionsOnly ? o : uri, o);
  }
};

// node_modules/engine.io-client/build/esm/index.js
var protocol2 = Socket.protocol;

// node_modules/socket.io-client/build/esm/url.js
function url(uri, path = "", loc) {
  let obj = uri;
  loc = loc || typeof location !== "undefined" && location;
  if (null == uri)
    uri = loc.protocol + "//" + loc.host;
  if (typeof uri === "string") {
    if ("/" === uri.charAt(0)) {
      if ("/" === uri.charAt(1)) {
        uri = loc.protocol + uri;
      } else {
        uri = loc.host + uri;
      }
    }
    if (!/^(https?|wss?):\/\//.test(uri)) {
      if ("undefined" !== typeof loc) {
        uri = loc.protocol + "//" + uri;
      } else {
        uri = "https://" + uri;
      }
    }
    obj = parse(uri);
  }
  if (!obj.port) {
    if (/^(http|ws)$/.test(obj.protocol)) {
      obj.port = "80";
    } else if (/^(http|ws)s$/.test(obj.protocol)) {
      obj.port = "443";
    }
  }
  obj.path = obj.path || "/";
  const ipv6 = obj.host.indexOf(":") !== -1;
  const host = ipv6 ? "[" + obj.host + "]" : obj.host;
  obj.id = obj.protocol + "://" + host + ":" + obj.port + path;
  obj.href = obj.protocol + "://" + host + (loc && loc.port === obj.port ? "" : ":" + obj.port);
  return obj;
}

// node_modules/socket.io-parser/build/esm/index.js
var esm_exports = {};
__export(esm_exports, {
  Decoder: () => Decoder,
  Encoder: () => Encoder,
  PacketType: () => PacketType,
  isPacketValid: () => isPacketValid,
  protocol: () => protocol3
});

// node_modules/socket.io-parser/build/esm/is-binary.js
var withNativeArrayBuffer3 = typeof ArrayBuffer === "function";
var isView2 = (obj) => {
  return typeof ArrayBuffer.isView === "function" ? ArrayBuffer.isView(obj) : obj.buffer instanceof ArrayBuffer;
};
var toString = Object.prototype.toString;
var withNativeBlob2 = typeof Blob === "function" || typeof Blob !== "undefined" && toString.call(Blob) === "[object BlobConstructor]";
var withNativeFile = typeof File === "function" || typeof File !== "undefined" && toString.call(File) === "[object FileConstructor]";
function isBinary(obj) {
  return withNativeArrayBuffer3 && (obj instanceof ArrayBuffer || isView2(obj)) || withNativeBlob2 && obj instanceof Blob || withNativeFile && obj instanceof File;
}
function hasBinary(obj, toJSON) {
  if (!obj || typeof obj !== "object") {
    return false;
  }
  if (Array.isArray(obj)) {
    for (let i = 0, l = obj.length; i < l; i++) {
      if (hasBinary(obj[i])) {
        return true;
      }
    }
    return false;
  }
  if (isBinary(obj)) {
    return true;
  }
  if (obj.toJSON && typeof obj.toJSON === "function" && arguments.length === 1) {
    return hasBinary(obj.toJSON(), true);
  }
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key) && hasBinary(obj[key])) {
      return true;
    }
  }
  return false;
}

// node_modules/socket.io-parser/build/esm/binary.js
function deconstructPacket(packet) {
  const buffers = [];
  const packetData = packet.data;
  const pack = packet;
  pack.data = _deconstructPacket(packetData, buffers);
  pack.attachments = buffers.length;
  return { packet: pack, buffers };
}
function _deconstructPacket(data, buffers, toJSON) {
  if (!data)
    return data;
  if (isBinary(data)) {
    const placeholder = { _placeholder: true, num: buffers.length };
    buffers.push(data);
    return placeholder;
  } else if (Array.isArray(data)) {
    const newData = new Array(data.length);
    for (let i = 0; i < data.length; i++) {
      newData[i] = _deconstructPacket(data[i], buffers);
    }
    return newData;
  } else if (typeof data === "object" && !(data instanceof Date)) {
    if (data.toJSON && typeof data.toJSON === "function" && !toJSON) {
      return _deconstructPacket(data.toJSON(), buffers, true);
    }
    const newData = {};
    for (const key in data) {
      if (Object.prototype.hasOwnProperty.call(data, key)) {
        newData[key] = _deconstructPacket(data[key], buffers);
      }
    }
    return newData;
  }
  return data;
}
function reconstructPacket(packet, buffers) {
  packet.data = _reconstructPacket(packet.data, buffers);
  delete packet.attachments;
  return packet;
}
function _reconstructPacket(data, buffers) {
  if (!data)
    return data;
  if (data && data._placeholder === true) {
    const isIndexValid = typeof data.num === "number" && data.num >= 0 && data.num < buffers.length;
    if (isIndexValid) {
      return buffers[data.num];
    } else {
      throw new Error("illegal attachments");
    }
  } else if (Array.isArray(data)) {
    for (let i = 0; i < data.length; i++) {
      data[i] = _reconstructPacket(data[i], buffers);
    }
  } else if (typeof data === "object") {
    for (const key in data) {
      if (Object.prototype.hasOwnProperty.call(data, key)) {
        data[key] = _reconstructPacket(data[key], buffers);
      }
    }
  }
  return data;
}

// node_modules/socket.io-parser/build/esm/index.js
var RESERVED_EVENTS = [
  "connect",
  // used on the client side
  "connect_error",
  // used on the client side
  "disconnect",
  // used on both sides
  "disconnecting",
  // used on the server side
  "newListener",
  // used by the Node.js EventEmitter
  "removeListener"
  // used by the Node.js EventEmitter
];
var protocol3 = 5;
var PacketType;
(function(PacketType2) {
  PacketType2[PacketType2["CONNECT"] = 0] = "CONNECT";
  PacketType2[PacketType2["DISCONNECT"] = 1] = "DISCONNECT";
  PacketType2[PacketType2["EVENT"] = 2] = "EVENT";
  PacketType2[PacketType2["ACK"] = 3] = "ACK";
  PacketType2[PacketType2["CONNECT_ERROR"] = 4] = "CONNECT_ERROR";
  PacketType2[PacketType2["BINARY_EVENT"] = 5] = "BINARY_EVENT";
  PacketType2[PacketType2["BINARY_ACK"] = 6] = "BINARY_ACK";
})(PacketType || (PacketType = {}));
var Encoder = class {
  /**
   * Encoder constructor
   *
   * @param {function} replacer - custom replacer to pass down to JSON.parse
   */
  constructor(replacer) {
    this.replacer = replacer;
  }
  /**
   * Encode a packet as a single string if non-binary, or as a
   * buffer sequence, depending on packet type.
   *
   * @param {Object} obj - packet object
   */
  encode(obj) {
    if (obj.type === PacketType.EVENT || obj.type === PacketType.ACK) {
      if (hasBinary(obj)) {
        return this.encodeAsBinary({
          type: obj.type === PacketType.EVENT ? PacketType.BINARY_EVENT : PacketType.BINARY_ACK,
          nsp: obj.nsp,
          data: obj.data,
          id: obj.id
        });
      }
    }
    return [this.encodeAsString(obj)];
  }
  /**
   * Encode packet as string.
   */
  encodeAsString(obj) {
    let str = "" + obj.type;
    if (obj.type === PacketType.BINARY_EVENT || obj.type === PacketType.BINARY_ACK) {
      str += obj.attachments + "-";
    }
    if (obj.nsp && "/" !== obj.nsp) {
      str += obj.nsp + ",";
    }
    if (null != obj.id) {
      str += obj.id;
    }
    if (null != obj.data) {
      str += JSON.stringify(obj.data, this.replacer);
    }
    return str;
  }
  /**
   * Encode packet as 'buffer sequence' by removing blobs, and
   * deconstructing packet into object with placeholders and
   * a list of buffers.
   */
  encodeAsBinary(obj) {
    const deconstruction = deconstructPacket(obj);
    const pack = this.encodeAsString(deconstruction.packet);
    const buffers = deconstruction.buffers;
    buffers.unshift(pack);
    return buffers;
  }
};
var Decoder = class _Decoder extends Emitter {
  /**
   * Decoder constructor
   */
  constructor(opts) {
    super();
    this.opts = Object.assign({
      reviver: void 0,
      maxAttachments: 10
    }, typeof opts === "function" ? { reviver: opts } : opts);
  }
  /**
   * Decodes an encoded packet string into packet JSON.
   *
   * @param {String} obj - encoded packet
   */
  add(obj) {
    let packet;
    if (typeof obj === "string") {
      if (this.reconstructor) {
        throw new Error("got plaintext data when reconstructing a packet");
      }
      packet = this.decodeString(obj);
      const isBinaryEvent = packet.type === PacketType.BINARY_EVENT;
      if (isBinaryEvent || packet.type === PacketType.BINARY_ACK) {
        packet.type = isBinaryEvent ? PacketType.EVENT : PacketType.ACK;
        this.reconstructor = new BinaryReconstructor(packet);
      } else {
        super.emitReserved("decoded", packet);
      }
    } else if (isBinary(obj) || obj.base64) {
      if (!this.reconstructor) {
        throw new Error("got binary data when not reconstructing a packet");
      } else {
        packet = this.reconstructor.takeBinaryData(obj);
        if (packet) {
          this.reconstructor = null;
          super.emitReserved("decoded", packet);
        }
      }
    } else {
      throw new Error("Unknown type: " + obj);
    }
  }
  /**
   * Decode a packet String (JSON data)
   *
   * @param {String} str
   * @return {Object} packet
   */
  decodeString(str) {
    let i = 0;
    const p = {
      type: Number(str.charAt(0))
    };
    if (PacketType[p.type] === void 0) {
      throw new Error("unknown packet type " + p.type);
    }
    if (p.type === PacketType.BINARY_EVENT || p.type === PacketType.BINARY_ACK) {
      const start = i + 1;
      while (str.charAt(++i) !== "-" && i != str.length) {
      }
      const buf = str.substring(start, i);
      if (buf != Number(buf) || str.charAt(i) !== "-") {
        throw new Error("Illegal attachments");
      }
      const n = Number(buf);
      if (!isInteger(n) || n < 1) {
        throw new Error("Illegal attachments");
      } else if (n > this.opts.maxAttachments) {
        throw new Error("too many attachments");
      }
      p.attachments = n;
    }
    if ("/" === str.charAt(i + 1)) {
      const start = i + 1;
      while (++i) {
        const c = str.charAt(i);
        if ("," === c)
          break;
        if (i === str.length)
          break;
      }
      p.nsp = str.substring(start, i);
    } else {
      p.nsp = "/";
    }
    const next = str.charAt(i + 1);
    if ("" !== next && Number(next) == next) {
      const start = i + 1;
      while (++i) {
        const c = str.charAt(i);
        if (null == c || Number(c) != c) {
          --i;
          break;
        }
        if (i === str.length)
          break;
      }
      p.id = Number(str.substring(start, i + 1));
    }
    if (str.charAt(++i)) {
      const payload = this.tryParse(str.substr(i));
      if (_Decoder.isPayloadValid(p.type, payload)) {
        p.data = payload;
      } else {
        throw new Error("invalid payload");
      }
    }
    return p;
  }
  tryParse(str) {
    try {
      return JSON.parse(str, this.opts.reviver);
    } catch (e) {
      return false;
    }
  }
  static isPayloadValid(type, payload) {
    switch (type) {
      case PacketType.CONNECT:
        return isObject(payload);
      case PacketType.DISCONNECT:
        return payload === void 0;
      case PacketType.CONNECT_ERROR:
        return typeof payload === "string" || isObject(payload);
      case PacketType.EVENT:
      case PacketType.BINARY_EVENT:
        return Array.isArray(payload) && (typeof payload[0] === "number" || typeof payload[0] === "string" && RESERVED_EVENTS.indexOf(payload[0]) === -1);
      case PacketType.ACK:
      case PacketType.BINARY_ACK:
        return Array.isArray(payload);
    }
  }
  /**
   * Deallocates a parser's resources
   */
  destroy() {
    if (this.reconstructor) {
      this.reconstructor.finishedReconstruction();
      this.reconstructor = null;
    }
  }
};
var BinaryReconstructor = class {
  constructor(packet) {
    this.packet = packet;
    this.buffers = [];
    this.reconPack = packet;
  }
  /**
   * Method to be called when binary data received from connection
   * after a BINARY_EVENT packet.
   *
   * @param {Buffer | ArrayBuffer} binData - the raw binary data received
   * @return {null | Object} returns null if more binary data is expected or
   *   a reconstructed packet object if all buffers have been received.
   */
  takeBinaryData(binData) {
    this.buffers.push(binData);
    if (this.buffers.length === this.reconPack.attachments) {
      const packet = reconstructPacket(this.reconPack, this.buffers);
      this.finishedReconstruction();
      return packet;
    }
    return null;
  }
  /**
   * Cleans up binary packet reconstruction variables.
   */
  finishedReconstruction() {
    this.reconPack = null;
    this.buffers = [];
  }
};
function isNamespaceValid(nsp) {
  return typeof nsp === "string";
}
var isInteger = Number.isInteger || function(value2) {
  return typeof value2 === "number" && isFinite(value2) && Math.floor(value2) === value2;
};
function isAckIdValid(id) {
  return id === void 0 || isInteger(id);
}
function isObject(value2) {
  return Object.prototype.toString.call(value2) === "[object Object]";
}
function isDataValid(type, payload) {
  switch (type) {
    case PacketType.CONNECT:
      return payload === void 0 || isObject(payload);
    case PacketType.DISCONNECT:
      return payload === void 0;
    case PacketType.EVENT:
      return Array.isArray(payload) && (typeof payload[0] === "number" || typeof payload[0] === "string" && RESERVED_EVENTS.indexOf(payload[0]) === -1);
    case PacketType.ACK:
      return Array.isArray(payload);
    case PacketType.CONNECT_ERROR:
      return typeof payload === "string" || isObject(payload);
    default:
      return false;
  }
}
function isPacketValid(packet) {
  return isNamespaceValid(packet.nsp) && isAckIdValid(packet.id) && isDataValid(packet.type, packet.data);
}

// node_modules/socket.io-client/build/esm/on.js
function on(obj, ev, fn) {
  obj.on(ev, fn);
  return function subDestroy() {
    obj.off(ev, fn);
  };
}

// node_modules/socket.io-client/build/esm/socket.js
var RESERVED_EVENTS2 = Object.freeze({
  connect: 1,
  connect_error: 1,
  disconnect: 1,
  disconnecting: 1,
  // EventEmitter reserved events: https://nodejs.org/api/events.html#events_event_newlistener
  newListener: 1,
  removeListener: 1
});
var Socket2 = class extends Emitter {
  /**
   * `Socket` constructor.
   */
  constructor(io, nsp, opts) {
    super();
    this.connected = false;
    this.recovered = false;
    this.receiveBuffer = [];
    this.sendBuffer = [];
    this._queue = [];
    this._queueSeq = 0;
    this.ids = 0;
    this.acks = {};
    this.flags = {};
    this.io = io;
    this.nsp = nsp;
    if (opts && opts.auth) {
      this.auth = opts.auth;
    }
    this._opts = Object.assign({}, opts);
    if (this.io._autoConnect)
      this.open();
  }
  /**
   * Whether the socket is currently disconnected
   *
   * @example
   * const socket = io();
   *
   * socket.on("connect", () => {
   *   console.log(socket.disconnected); // false
   * });
   *
   * socket.on("disconnect", () => {
   *   console.log(socket.disconnected); // true
   * });
   */
  get disconnected() {
    return !this.connected;
  }
  /**
   * Subscribe to open, close and packet events
   *
   * @private
   */
  subEvents() {
    if (this.subs)
      return;
    const io = this.io;
    this.subs = [
      on(io, "open", this.onopen.bind(this)),
      on(io, "packet", this.onpacket.bind(this)),
      on(io, "error", this.onerror.bind(this)),
      on(io, "close", this.onclose.bind(this))
    ];
  }
  /**
   * Whether the Socket will try to reconnect when its Manager connects or reconnects.
   *
   * @example
   * const socket = io();
   *
   * console.log(socket.active); // true
   *
   * socket.on("disconnect", (reason) => {
   *   if (reason === "io server disconnect") {
   *     // the disconnection was initiated by the server, you need to manually reconnect
   *     console.log(socket.active); // false
   *   }
   *   // else the socket will automatically try to reconnect
   *   console.log(socket.active); // true
   * });
   */
  get active() {
    return !!this.subs;
  }
  /**
   * "Opens" the socket.
   *
   * @example
   * const socket = io({
   *   autoConnect: false
   * });
   *
   * socket.connect();
   */
  connect() {
    if (this.connected)
      return this;
    this.subEvents();
    if (!this.io["_reconnecting"])
      this.io.open();
    if ("open" === this.io._readyState)
      this.onopen();
    return this;
  }
  /**
   * Alias for {@link connect()}.
   */
  open() {
    return this.connect();
  }
  /**
   * Sends a `message` event.
   *
   * This method mimics the WebSocket.send() method.
   *
   * @see https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/send
   *
   * @example
   * socket.send("hello");
   *
   * // this is equivalent to
   * socket.emit("message", "hello");
   *
   * @return self
   */
  send(...args) {
    args.unshift("message");
    this.emit.apply(this, args);
    return this;
  }
  /**
   * Override `emit`.
   * If the event is in `events`, it's emitted normally.
   *
   * @example
   * socket.emit("hello", "world");
   *
   * // all serializable datastructures are supported (no need to call JSON.stringify)
   * socket.emit("hello", 1, "2", { 3: ["4"], 5: Uint8Array.from([6]) });
   *
   * // with an acknowledgement from the server
   * socket.emit("hello", "world", (val) => {
   *   // ...
   * });
   *
   * @return self
   */
  emit(ev, ...args) {
    var _a, _b, _c;
    if (RESERVED_EVENTS2.hasOwnProperty(ev)) {
      throw new Error('"' + ev.toString() + '" is a reserved event name');
    }
    args.unshift(ev);
    if (this._opts.retries && !this.flags.fromQueue && !this.flags.volatile) {
      this._addToQueue(args);
      return this;
    }
    const packet = {
      type: PacketType.EVENT,
      data: args
    };
    packet.options = {};
    packet.options.compress = this.flags.compress !== false;
    if ("function" === typeof args[args.length - 1]) {
      const id = this.ids++;
      const ack = args.pop();
      this._registerAckCallback(id, ack);
      packet.id = id;
    }
    const isTransportWritable = (_b = (_a = this.io.engine) === null || _a === void 0 ? void 0 : _a.transport) === null || _b === void 0 ? void 0 : _b.writable;
    const isConnected = this.connected && !((_c = this.io.engine) === null || _c === void 0 ? void 0 : _c._hasPingExpired());
    const discardPacket = this.flags.volatile && !isTransportWritable;
    if (discardPacket) {
    } else if (isConnected) {
      this.notifyOutgoingListeners(packet);
      this.packet(packet);
    } else {
      this.sendBuffer.push(packet);
    }
    this.flags = {};
    return this;
  }
  /**
   * @private
   */
  _registerAckCallback(id, ack) {
    var _a;
    const timeout = (_a = this.flags.timeout) !== null && _a !== void 0 ? _a : this._opts.ackTimeout;
    if (timeout === void 0) {
      this.acks[id] = ack;
      return;
    }
    const timer = this.io.setTimeoutFn(() => {
      delete this.acks[id];
      for (let i = 0; i < this.sendBuffer.length; i++) {
        if (this.sendBuffer[i].id === id) {
          this.sendBuffer.splice(i, 1);
        }
      }
      ack.call(this, new Error("operation has timed out"));
    }, timeout);
    const fn = (...args) => {
      this.io.clearTimeoutFn(timer);
      ack.apply(this, args);
    };
    fn.withError = true;
    this.acks[id] = fn;
  }
  /**
   * Emits an event and waits for an acknowledgement
   *
   * @example
   * // without timeout
   * const response = await socket.emitWithAck("hello", "world");
   *
   * // with a specific timeout
   * try {
   *   const response = await socket.timeout(1000).emitWithAck("hello", "world");
   * } catch (err) {
   *   // the server did not acknowledge the event in the given delay
   * }
   *
   * @return a Promise that will be fulfilled when the server acknowledges the event
   */
  emitWithAck(ev, ...args) {
    return new Promise((resolve, reject) => {
      const fn = (arg1, arg2) => {
        return arg1 ? reject(arg1) : resolve(arg2);
      };
      fn.withError = true;
      args.push(fn);
      this.emit(ev, ...args);
    });
  }
  /**
   * Add the packet to the queue.
   * @param args
   * @private
   */
  _addToQueue(args) {
    let ack;
    if (typeof args[args.length - 1] === "function") {
      ack = args.pop();
    }
    const packet = {
      id: this._queueSeq++,
      tryCount: 0,
      pending: false,
      args,
      flags: Object.assign({ fromQueue: true }, this.flags)
    };
    args.push((err, ...responseArgs) => {
      if (packet !== this._queue[0]) {
      }
      const hasError = err !== null;
      if (hasError) {
        if (packet.tryCount > this._opts.retries) {
          this._queue.shift();
          if (ack) {
            ack(err);
          }
        }
      } else {
        this._queue.shift();
        if (ack) {
          ack(null, ...responseArgs);
        }
      }
      packet.pending = false;
      return this._drainQueue();
    });
    this._queue.push(packet);
    this._drainQueue();
  }
  /**
   * Send the first packet of the queue, and wait for an acknowledgement from the server.
   * @param force - whether to resend a packet that has not been acknowledged yet
   *
   * @private
   */
  _drainQueue(force = false) {
    if (!this.connected || this._queue.length === 0) {
      return;
    }
    const packet = this._queue[0];
    if (packet.pending && !force) {
      return;
    }
    packet.pending = true;
    packet.tryCount++;
    this.flags = packet.flags;
    this.emit.apply(this, packet.args);
  }
  /**
   * Sends a packet.
   *
   * @param packet
   * @private
   */
  packet(packet) {
    packet.nsp = this.nsp;
    this.io._packet(packet);
  }
  /**
   * Called upon engine `open`.
   *
   * @private
   */
  onopen() {
    if (typeof this.auth == "function") {
      this.auth((data) => {
        this._sendConnectPacket(data);
      });
    } else {
      this._sendConnectPacket(this.auth);
    }
  }
  /**
   * Sends a CONNECT packet to initiate the Socket.IO session.
   *
   * @param data
   * @private
   */
  _sendConnectPacket(data) {
    this.packet({
      type: PacketType.CONNECT,
      data: this._pid ? Object.assign({ pid: this._pid, offset: this._lastOffset }, data) : data
    });
  }
  /**
   * Called upon engine or manager `error`.
   *
   * @param err
   * @private
   */
  onerror(err) {
    if (!this.connected) {
      this.emitReserved("connect_error", err);
    }
  }
  /**
   * Called upon engine `close`.
   *
   * @param reason
   * @param description
   * @private
   */
  onclose(reason, description) {
    this.connected = false;
    delete this.id;
    this.emitReserved("disconnect", reason, description);
    this._clearAcks();
  }
  /**
   * Clears the acknowledgement handlers upon disconnection, since the client will never receive an acknowledgement from
   * the server.
   *
   * @private
   */
  _clearAcks() {
    Object.keys(this.acks).forEach((id) => {
      const isBuffered = this.sendBuffer.some((packet) => String(packet.id) === id);
      if (!isBuffered) {
        const ack = this.acks[id];
        delete this.acks[id];
        if (ack.withError) {
          ack.call(this, new Error("socket has been disconnected"));
        }
      }
    });
  }
  /**
   * Called with socket packet.
   *
   * @param packet
   * @private
   */
  onpacket(packet) {
    const sameNamespace = packet.nsp === this.nsp;
    if (!sameNamespace)
      return;
    switch (packet.type) {
      case PacketType.CONNECT:
        if (packet.data && packet.data.sid) {
          this.onconnect(packet.data.sid, packet.data.pid);
        } else {
          this.emitReserved("connect_error", new Error("It seems you are trying to reach a Socket.IO server in v2.x with a v3.x client, but they are not compatible (more information here: https://socket.io/docs/v3/migrating-from-2-x-to-3-0/)"));
        }
        break;
      case PacketType.EVENT:
      case PacketType.BINARY_EVENT:
        this.onevent(packet);
        break;
      case PacketType.ACK:
      case PacketType.BINARY_ACK:
        this.onack(packet);
        break;
      case PacketType.DISCONNECT:
        this.ondisconnect();
        break;
      case PacketType.CONNECT_ERROR:
        this.destroy();
        const err = new Error(packet.data.message);
        err.data = packet.data.data;
        this.emitReserved("connect_error", err);
        break;
    }
  }
  /**
   * Called upon a server event.
   *
   * @param packet
   * @private
   */
  onevent(packet) {
    const args = packet.data || [];
    if (null != packet.id) {
      args.push(this.ack(packet.id));
    }
    if (this.connected) {
      this.emitEvent(args);
    } else {
      this.receiveBuffer.push(Object.freeze(args));
    }
  }
  emitEvent(args) {
    if (this._anyListeners && this._anyListeners.length) {
      const listeners = this._anyListeners.slice();
      for (const listener of listeners) {
        listener.apply(this, args);
      }
    }
    super.emit.apply(this, args);
    if (this._pid && args.length && typeof args[args.length - 1] === "string") {
      this._lastOffset = args[args.length - 1];
    }
  }
  /**
   * Produces an ack callback to emit with an event.
   *
   * @private
   */
  ack(id) {
    const self2 = this;
    let sent = false;
    return function(...args) {
      if (sent)
        return;
      sent = true;
      self2.packet({
        type: PacketType.ACK,
        id,
        data: args
      });
    };
  }
  /**
   * Called upon a server acknowledgement.
   *
   * @param packet
   * @private
   */
  onack(packet) {
    const ack = this.acks[packet.id];
    if (typeof ack !== "function") {
      return;
    }
    delete this.acks[packet.id];
    if (ack.withError) {
      packet.data.unshift(null);
    }
    ack.apply(this, packet.data);
  }
  /**
   * Called upon server connect.
   *
   * @private
   */
  onconnect(id, pid) {
    this.id = id;
    this.recovered = pid && this._pid === pid;
    this._pid = pid;
    this.connected = true;
    this.emitBuffered();
    this._drainQueue(true);
    this.emitReserved("connect");
  }
  /**
   * Emit buffered events (received and emitted).
   *
   * @private
   */
  emitBuffered() {
    this.receiveBuffer.forEach((args) => this.emitEvent(args));
    this.receiveBuffer = [];
    this.sendBuffer.forEach((packet) => {
      this.notifyOutgoingListeners(packet);
      this.packet(packet);
    });
    this.sendBuffer = [];
  }
  /**
   * Called upon server disconnect.
   *
   * @private
   */
  ondisconnect() {
    this.destroy();
    this.onclose("io server disconnect");
  }
  /**
   * Called upon forced client/server side disconnections,
   * this method ensures the manager stops tracking us and
   * that reconnections don't get triggered for this.
   *
   * @private
   */
  destroy() {
    if (this.subs) {
      this.subs.forEach((subDestroy) => subDestroy());
      this.subs = void 0;
    }
    this.io["_destroy"](this);
  }
  /**
   * Disconnects the socket manually. In that case, the socket will not try to reconnect.
   *
   * If this is the last active Socket instance of the {@link Manager}, the low-level connection will be closed.
   *
   * @example
   * const socket = io();
   *
   * socket.on("disconnect", (reason) => {
   *   // console.log(reason); prints "io client disconnect"
   * });
   *
   * socket.disconnect();
   *
   * @return self
   */
  disconnect() {
    if (this.connected) {
      this.packet({ type: PacketType.DISCONNECT });
    }
    this.destroy();
    if (this.connected) {
      this.onclose("io client disconnect");
    }
    return this;
  }
  /**
   * Alias for {@link disconnect()}.
   *
   * @return self
   */
  close() {
    return this.disconnect();
  }
  /**
   * Sets the compress flag.
   *
   * @example
   * socket.compress(false).emit("hello");
   *
   * @param compress - if `true`, compresses the sending data
   * @return self
   */
  compress(compress) {
    this.flags.compress = compress;
    return this;
  }
  /**
   * Sets a modifier for a subsequent event emission that the event message will be dropped when this socket is not
   * ready to send messages.
   *
   * @example
   * socket.volatile.emit("hello"); // the server may or may not receive it
   *
   * @returns self
   */
  get volatile() {
    this.flags.volatile = true;
    return this;
  }
  /**
   * Sets a modifier for a subsequent event emission that the callback will be called with an error when the
   * given number of milliseconds have elapsed without an acknowledgement from the server:
   *
   * @example
   * socket.timeout(5000).emit("my-event", (err) => {
   *   if (err) {
   *     // the server did not acknowledge the event in the given delay
   *   }
   * });
   *
   * @returns self
   */
  timeout(timeout) {
    this.flags.timeout = timeout;
    return this;
  }
  /**
   * Adds a listener that will be fired when any event is emitted. The event name is passed as the first argument to the
   * callback.
   *
   * @example
   * socket.onAny((event, ...args) => {
   *   console.log(`got ${event}`);
   * });
   *
   * @param listener
   */
  onAny(listener) {
    this._anyListeners = this._anyListeners || [];
    this._anyListeners.push(listener);
    return this;
  }
  /**
   * Adds a listener that will be fired when any event is emitted. The event name is passed as the first argument to the
   * callback. The listener is added to the beginning of the listeners array.
   *
   * @example
   * socket.prependAny((event, ...args) => {
   *   console.log(`got event ${event}`);
   * });
   *
   * @param listener
   */
  prependAny(listener) {
    this._anyListeners = this._anyListeners || [];
    this._anyListeners.unshift(listener);
    return this;
  }
  /**
   * Removes the listener that will be fired when any event is emitted.
   *
   * @example
   * const catchAllListener = (event, ...args) => {
   *   console.log(`got event ${event}`);
   * }
   *
   * socket.onAny(catchAllListener);
   *
   * // remove a specific listener
   * socket.offAny(catchAllListener);
   *
   * // or remove all listeners
   * socket.offAny();
   *
   * @param listener
   */
  offAny(listener) {
    if (!this._anyListeners) {
      return this;
    }
    if (listener) {
      const listeners = this._anyListeners;
      for (let i = 0; i < listeners.length; i++) {
        if (listener === listeners[i]) {
          listeners.splice(i, 1);
          return this;
        }
      }
    } else {
      this._anyListeners = [];
    }
    return this;
  }
  /**
   * Returns an array of listeners that are listening for any event that is specified. This array can be manipulated,
   * e.g. to remove listeners.
   */
  listenersAny() {
    return this._anyListeners || [];
  }
  /**
   * Adds a listener that will be fired when any event is emitted. The event name is passed as the first argument to the
   * callback.
   *
   * Note: acknowledgements sent to the server are not included.
   *
   * @example
   * socket.onAnyOutgoing((event, ...args) => {
   *   console.log(`sent event ${event}`);
   * });
   *
   * @param listener
   */
  onAnyOutgoing(listener) {
    this._anyOutgoingListeners = this._anyOutgoingListeners || [];
    this._anyOutgoingListeners.push(listener);
    return this;
  }
  /**
   * Adds a listener that will be fired when any event is emitted. The event name is passed as the first argument to the
   * callback. The listener is added to the beginning of the listeners array.
   *
   * Note: acknowledgements sent to the server are not included.
   *
   * @example
   * socket.prependAnyOutgoing((event, ...args) => {
   *   console.log(`sent event ${event}`);
   * });
   *
   * @param listener
   */
  prependAnyOutgoing(listener) {
    this._anyOutgoingListeners = this._anyOutgoingListeners || [];
    this._anyOutgoingListeners.unshift(listener);
    return this;
  }
  /**
   * Removes the listener that will be fired when any event is emitted.
   *
   * @example
   * const catchAllListener = (event, ...args) => {
   *   console.log(`sent event ${event}`);
   * }
   *
   * socket.onAnyOutgoing(catchAllListener);
   *
   * // remove a specific listener
   * socket.offAnyOutgoing(catchAllListener);
   *
   * // or remove all listeners
   * socket.offAnyOutgoing();
   *
   * @param [listener] - the catch-all listener (optional)
   */
  offAnyOutgoing(listener) {
    if (!this._anyOutgoingListeners) {
      return this;
    }
    if (listener) {
      const listeners = this._anyOutgoingListeners;
      for (let i = 0; i < listeners.length; i++) {
        if (listener === listeners[i]) {
          listeners.splice(i, 1);
          return this;
        }
      }
    } else {
      this._anyOutgoingListeners = [];
    }
    return this;
  }
  /**
   * Returns an array of listeners that are listening for any event that is specified. This array can be manipulated,
   * e.g. to remove listeners.
   */
  listenersAnyOutgoing() {
    return this._anyOutgoingListeners || [];
  }
  /**
   * Notify the listeners for each packet sent
   *
   * @param packet
   *
   * @private
   */
  notifyOutgoingListeners(packet) {
    if (this._anyOutgoingListeners && this._anyOutgoingListeners.length) {
      const listeners = this._anyOutgoingListeners.slice();
      for (const listener of listeners) {
        listener.apply(this, packet.data);
      }
    }
  }
};

// node_modules/socket.io-client/build/esm/contrib/backo2.js
function Backoff(opts) {
  opts = opts || {};
  this.ms = opts.min || 100;
  this.max = opts.max || 1e4;
  this.factor = opts.factor || 2;
  this.jitter = opts.jitter > 0 && opts.jitter <= 1 ? opts.jitter : 0;
  this.attempts = 0;
}
Backoff.prototype.duration = function() {
  var ms = this.ms * Math.pow(this.factor, this.attempts++);
  if (this.jitter) {
    var rand = Math.random();
    var deviation = Math.floor(rand * this.jitter * ms);
    ms = (Math.floor(rand * 10) & 1) == 0 ? ms - deviation : ms + deviation;
  }
  return Math.min(ms, this.max) | 0;
};
Backoff.prototype.reset = function() {
  this.attempts = 0;
};
Backoff.prototype.setMin = function(min) {
  this.ms = min;
};
Backoff.prototype.setMax = function(max) {
  this.max = max;
};
Backoff.prototype.setJitter = function(jitter) {
  this.jitter = jitter;
};

// node_modules/socket.io-client/build/esm/manager.js
var Manager = class extends Emitter {
  constructor(uri, opts) {
    var _a;
    super();
    this.nsps = {};
    this.subs = [];
    if (uri && "object" === typeof uri) {
      opts = uri;
      uri = void 0;
    }
    opts = opts || {};
    opts.path = opts.path || "/socket.io";
    this.opts = opts;
    installTimerFunctions(this, opts);
    this.reconnection(opts.reconnection !== false);
    this.reconnectionAttempts(opts.reconnectionAttempts || Infinity);
    this.reconnectionDelay(opts.reconnectionDelay || 1e3);
    this.reconnectionDelayMax(opts.reconnectionDelayMax || 5e3);
    this.randomizationFactor((_a = opts.randomizationFactor) !== null && _a !== void 0 ? _a : 0.5);
    this.backoff = new Backoff({
      min: this.reconnectionDelay(),
      max: this.reconnectionDelayMax(),
      jitter: this.randomizationFactor()
    });
    this.timeout(null == opts.timeout ? 2e4 : opts.timeout);
    this._readyState = "closed";
    this.uri = uri;
    const _parser = opts.parser || esm_exports;
    this.encoder = new _parser.Encoder();
    this.decoder = new _parser.Decoder();
    this._autoConnect = opts.autoConnect !== false;
    if (this._autoConnect)
      this.open();
  }
  reconnection(v) {
    if (!arguments.length)
      return this._reconnection;
    this._reconnection = !!v;
    if (!v) {
      this.skipReconnect = true;
    }
    return this;
  }
  reconnectionAttempts(v) {
    if (v === void 0)
      return this._reconnectionAttempts;
    this._reconnectionAttempts = v;
    return this;
  }
  reconnectionDelay(v) {
    var _a;
    if (v === void 0)
      return this._reconnectionDelay;
    this._reconnectionDelay = v;
    (_a = this.backoff) === null || _a === void 0 ? void 0 : _a.setMin(v);
    return this;
  }
  randomizationFactor(v) {
    var _a;
    if (v === void 0)
      return this._randomizationFactor;
    this._randomizationFactor = v;
    (_a = this.backoff) === null || _a === void 0 ? void 0 : _a.setJitter(v);
    return this;
  }
  reconnectionDelayMax(v) {
    var _a;
    if (v === void 0)
      return this._reconnectionDelayMax;
    this._reconnectionDelayMax = v;
    (_a = this.backoff) === null || _a === void 0 ? void 0 : _a.setMax(v);
    return this;
  }
  timeout(v) {
    if (!arguments.length)
      return this._timeout;
    this._timeout = v;
    return this;
  }
  /**
   * Starts trying to reconnect if reconnection is enabled and we have not
   * started reconnecting yet
   *
   * @private
   */
  maybeReconnectOnOpen() {
    if (!this._reconnecting && this._reconnection && this.backoff.attempts === 0) {
      this.reconnect();
    }
  }
  /**
   * Sets the current transport `socket`.
   *
   * @param {Function} fn - optional, callback
   * @return self
   * @public
   */
  open(fn) {
    if (~this._readyState.indexOf("open"))
      return this;
    this.engine = new Socket(this.uri, this.opts);
    const socket = this.engine;
    const self2 = this;
    this._readyState = "opening";
    this.skipReconnect = false;
    const openSubDestroy = on(socket, "open", function() {
      self2.onopen();
      fn && fn();
    });
    const onError = (err) => {
      this.cleanup();
      this._readyState = "closed";
      this.emitReserved("error", err);
      if (fn) {
        fn(err);
      } else {
        this.maybeReconnectOnOpen();
      }
    };
    const errorSub = on(socket, "error", onError);
    if (false !== this._timeout) {
      const timeout = this._timeout;
      const timer = this.setTimeoutFn(() => {
        openSubDestroy();
        onError(new Error("timeout"));
        socket.close();
      }, timeout);
      if (this.opts.autoUnref) {
        timer.unref();
      }
      this.subs.push(() => {
        this.clearTimeoutFn(timer);
      });
    }
    this.subs.push(openSubDestroy);
    this.subs.push(errorSub);
    return this;
  }
  /**
   * Alias for open()
   *
   * @return self
   * @public
   */
  connect(fn) {
    return this.open(fn);
  }
  /**
   * Called upon transport open.
   *
   * @private
   */
  onopen() {
    this.cleanup();
    this._readyState = "open";
    this.emitReserved("open");
    const socket = this.engine;
    this.subs.push(
      on(socket, "ping", this.onping.bind(this)),
      on(socket, "data", this.ondata.bind(this)),
      on(socket, "error", this.onerror.bind(this)),
      on(socket, "close", this.onclose.bind(this)),
      // @ts-ignore
      on(this.decoder, "decoded", this.ondecoded.bind(this))
    );
  }
  /**
   * Called upon a ping.
   *
   * @private
   */
  onping() {
    this.emitReserved("ping");
  }
  /**
   * Called with data.
   *
   * @private
   */
  ondata(data) {
    try {
      this.decoder.add(data);
    } catch (e) {
      this.onclose("parse error", e);
    }
  }
  /**
   * Called when parser fully decodes a packet.
   *
   * @private
   */
  ondecoded(packet) {
    nextTick(() => {
      this.emitReserved("packet", packet);
    }, this.setTimeoutFn);
  }
  /**
   * Called upon socket error.
   *
   * @private
   */
  onerror(err) {
    this.emitReserved("error", err);
  }
  /**
   * Creates a new socket for the given `nsp`.
   *
   * @return {Socket}
   * @public
   */
  socket(nsp, opts) {
    let socket = this.nsps[nsp];
    if (!socket) {
      socket = new Socket2(this, nsp, opts);
      this.nsps[nsp] = socket;
    } else if (this._autoConnect && !socket.active) {
      socket.connect();
    }
    return socket;
  }
  /**
   * Called upon a socket close.
   *
   * @param socket
   * @private
   */
  _destroy(socket) {
    const nsps = Object.keys(this.nsps);
    for (const nsp of nsps) {
      const socket2 = this.nsps[nsp];
      if (socket2.active) {
        return;
      }
    }
    this._close();
  }
  /**
   * Writes a packet.
   *
   * @param packet
   * @private
   */
  _packet(packet) {
    const encodedPackets = this.encoder.encode(packet);
    for (let i = 0; i < encodedPackets.length; i++) {
      this.engine.write(encodedPackets[i], packet.options);
    }
  }
  /**
   * Clean up transport subscriptions and packet buffer.
   *
   * @private
   */
  cleanup() {
    this.subs.forEach((subDestroy) => subDestroy());
    this.subs.length = 0;
    this.decoder.destroy();
  }
  /**
   * Close the current socket.
   *
   * @private
   */
  _close() {
    this.skipReconnect = true;
    this._reconnecting = false;
    this.onclose("forced close");
  }
  /**
   * Alias for close()
   *
   * @private
   */
  disconnect() {
    return this._close();
  }
  /**
   * Called when:
   *
   * - the low-level engine is closed
   * - the parser encountered a badly formatted packet
   * - all sockets are disconnected
   *
   * @private
   */
  onclose(reason, description) {
    var _a;
    this.cleanup();
    (_a = this.engine) === null || _a === void 0 ? void 0 : _a.close();
    this.backoff.reset();
    this._readyState = "closed";
    this.emitReserved("close", reason, description);
    if (this._reconnection && !this.skipReconnect) {
      this.reconnect();
    }
  }
  /**
   * Attempt a reconnection.
   *
   * @private
   */
  reconnect() {
    if (this._reconnecting || this.skipReconnect)
      return this;
    const self2 = this;
    if (this.backoff.attempts >= this._reconnectionAttempts) {
      this.backoff.reset();
      this.emitReserved("reconnect_failed");
      this._reconnecting = false;
    } else {
      const delay = this.backoff.duration();
      this._reconnecting = true;
      const timer = this.setTimeoutFn(() => {
        if (self2.skipReconnect)
          return;
        this.emitReserved("reconnect_attempt", self2.backoff.attempts);
        if (self2.skipReconnect)
          return;
        self2.open((err) => {
          if (err) {
            self2._reconnecting = false;
            self2.reconnect();
            this.emitReserved("reconnect_error", err);
          } else {
            self2.onreconnect();
          }
        });
      }, delay);
      if (this.opts.autoUnref) {
        timer.unref();
      }
      this.subs.push(() => {
        this.clearTimeoutFn(timer);
      });
    }
  }
  /**
   * Called upon successful reconnect.
   *
   * @private
   */
  onreconnect() {
    const attempt = this.backoff.attempts;
    this._reconnecting = false;
    this.backoff.reset();
    this.emitReserved("reconnect", attempt);
  }
};

// node_modules/socket.io-client/build/esm/index.js
var cache = {};
function lookup2(uri, opts) {
  if (typeof uri === "object") {
    opts = uri;
    uri = void 0;
  }
  opts = opts || {};
  const parsed = url(uri, opts.path || "/socket.io");
  const source = parsed.source;
  const id = parsed.id;
  const path = parsed.path;
  const sameNamespace = cache[id] && path in cache[id]["nsps"];
  const newConnection = opts.forceNew || opts["force new connection"] || false === opts.multiplex || sameNamespace;
  let io;
  if (newConnection) {
    io = new Manager(source, opts);
  } else {
    if (!cache[id]) {
      cache[id] = new Manager(source, opts);
    }
    io = cache[id];
  }
  if (parsed.query && !opts.query) {
    opts.query = parsed.queryKey;
  }
  return io.socket(parsed.path, opts);
}
Object.assign(lookup2, {
  Manager,
  Socket: Socket2,
  io: lookup2,
  connect: lookup2
});

// src/net/socket.ts
var WS_PATH = "/ws/socket.io/";
function connectSocket() {
  const socket = lookup2({
    path: WS_PATH,
    transports: ["websocket", "polling"]
  });
  socket.on("connect", () => {
    console.log("Socket connected:", socket.id);
  });
  socket.on("disconnect", () => {
    console.log("Socket disconnected");
  });
  return socket;
}

// src/ui/audio.ts
var MusicLibrary = class {
  basePath;
  tracks = /* @__PURE__ */ new Map();
  current = null;
  currentName = null;
  volume = 0.35;
  muted = false;
  fallback = null;
  constructor(basePath = "/music/") {
    this.basePath = basePath;
  }
  setFallback(fn) {
    this.fallback = fn;
  }
  audioUrl(name) {
    return `${this.basePath}${name}.mp3`;
  }
  getTrack(name) {
    return this.tracks.get(name);
  }
  loadTrack(name) {
    const existing = this.getTrack(name);
    if (existing) return Promise.resolve(existing);
    return new Promise((resolve, reject) => {
      const audio = new Audio(this.audioUrl(name));
      audio.preload = "auto";
      audio.addEventListener("canplaythrough", () => {
        this.tracks.set(name, audio);
        resolve(audio);
      }, { once: true });
      audio.addEventListener("error", () => {
        reject(new Error(`Unable to load track ${name}`));
      }, { once: true });
      audio.load();
    });
  }
  async playTrack(name, loop = false) {
    if (this.muted) {
      this.currentName = name;
      return true;
    }
    try {
      const audio = await this.loadTrack(name);
      if (this.current && this.current !== audio) {
        this.stopTrack();
      }
      audio.loop = loop;
      audio.volume = this.volume;
      this.current = audio;
      this.currentName = name;
      await audio.play();
      return true;
    } catch {
      this.currentName = name;
      if (this.fallback) {
        this.fallback(name, loop);
      }
      return false;
    }
  }
  stopTrack() {
    if (this.current) {
      this.current.pause();
      this.current.currentTime = 0;
      this.current = null;
    }
  }
  setVolume(volume) {
    this.volume = Math.max(0, Math.min(1, volume));
    if (this.current) {
      this.current.volume = this.volume;
    }
  }
  getVolume() {
    return this.volume;
  }
  setMuted(muted) {
    this.muted = muted;
    if (this.current) {
      this.current.muted = muted;
      if (muted) {
        this.current.pause();
      } else if (this.currentName) {
        this.current.play().catch(() => {
        });
      }
    }
  }
  isMuted() {
    return this.muted;
  }
};
var AudioController = class {
  ctx = null;
  muted = false;
  musicVolume = 0.35;
  ambientActive = false;
  ambientType = null;
  ambientNodes = null;
  userGestureStarted = false;
  music;
  constructor() {
    this.music = new MusicLibrary();
    this.music.setFallback((name, loop) => this._fallbackMusic(name, loop));
  }
  ensureContext() {
    if (this.muted) return null;
    if (typeof window === "undefined") return null;
    if (!this.ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return null;
      try {
        this.ctx = new Ctx();
      } catch {
        return null;
      }
    }
    if (this.ctx?.state === "suspended") {
      this.ctx.resume().catch(() => {
      });
    }
    return this.ctx;
  }
  async ensureStartedFromGesture() {
    if (this.userGestureStarted) return;
    this.userGestureStarted = true;
    const ctx = this.ensureContext();
    if (!ctx) return;
    if (ctx.state === "suspended") {
      await ctx.resume().catch(() => {
      });
    }
  }
  toggleMute() {
    this.muted = !this.muted;
    this.music.setMuted(this.muted);
    if (this.muted && this.ctx) {
      this.ctx.suspend().catch(() => {
      });
    } else if (!this.muted && this.ctx) {
      this.ctx.resume().catch(() => {
      });
      if (this.ambientActive && this.ambientType) {
        this.playAmbient(this.ambientType);
      }
    }
    return this.muted;
  }
  setMusicVolume(volume) {
    this.musicVolume = Math.max(0, Math.min(1, volume));
    this.music.setVolume(this.musicVolume);
    if (this.ambientNodes) {
      this.ambientNodes.gain.gain.setTargetAtTime(this.musicVolume, this.ctx?.currentTime || 0, 0.1);
    }
  }
  getMusicVolume() {
    return this.musicVolume;
  }
  // MusicLibrary façade.
  playTrack(name, loop = false) {
    return this.music.playTrack(name, loop);
  }
  stopTrack() {
    this.music.stopTrack();
  }
  // Asset-aware music triggers with generative fallback.
  exploration() {
    this.playTrack("exploration", true);
  }
  combatSting() {
    this.playTrack("combat", true);
  }
  victory() {
    this.playTrack("victory", false);
  }
  defeat() {
    this.playTrack("defeat", false);
  }
  _fallbackMusic(name, _loop = false) {
    switch (name) {
      case "exploration":
        this._generativeExploration();
        break;
      case "combat":
        this._generativeCombatSting();
        break;
      case "victory":
        this._generativeVictory();
        break;
      case "defeat":
        this._generativeDefeat();
        break;
      case "ambient":
        if (this.ambientType) {
          this._generativeAmbient(this.ambientType);
        }
        break;
    }
  }
  _generativeVictory() {
    this.tone(523.25, 0.25, "sine", 0.18);
    this.tone(659.25, 0.25, "sine", 0.18);
    this.tone(783.99, 0.4, "sine", 0.18);
  }
  _generativeDefeat() {
    this.tone(392, 0.35, "sine", 0.18, 196);
    this.tone(196, 0.5, "sine", 0.18);
  }
  _generativeExploration() {
    const base = 261.63;
    const notes = [base, base * 1.125, base * 1.25, base * 1.5];
    notes.forEach((freq, i) => {
      if (typeof window !== "undefined") {
        window.setTimeout(() => this.tone(freq, 0.35, "triangle", 0.08), i * 180);
      }
    });
  }
  _generativeCombatSting() {
    this.tone(196, 0.18, "sawtooth", 0.12);
    this.tone(146.83, 0.28, "sawtooth", 0.12);
    if (typeof window !== "undefined") {
      window.setTimeout(() => this.tone(110, 0.45, "sawtooth", 0.14), 220);
    }
  }
  noiseBuffer(duration) {
    const ctx = this.ensureContext();
    if (!ctx) return null;
    const samples = Math.max(1, Math.ceil(ctx.sampleRate * duration));
    const buffer = ctx.createBuffer(1, samples, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i++) {
      data[i] = Math.random() * 2 - 1;
    }
    return buffer;
  }
  playNoise(duration, filterFreq, gain) {
    const ctx = this.ensureContext();
    if (!ctx) return;
    const buffer = this.noiseBuffer(duration);
    if (!buffer) return;
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = filterFreq;
    filter.Q.value = 1;
    const env = ctx.createGain();
    env.gain.setValueAtTime(gain, ctx.currentTime);
    env.gain.exponentialRampToValueAtTime(1e-3, ctx.currentTime + duration);
    src.connect(filter);
    filter.connect(env);
    env.connect(ctx.destination);
    src.start();
    src.stop(ctx.currentTime + duration);
  }
  tone(frequency, duration, type = "sine", gain = 0.15, sweepTo) {
    const ctx = this.ensureContext();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    osc.type = type;
    osc.frequency.setValueAtTime(frequency, ctx.currentTime);
    if (sweepTo !== void 0) {
      osc.frequency.exponentialRampToValueAtTime(Math.max(20, sweepTo), ctx.currentTime + duration);
    }
    const env = ctx.createGain();
    env.gain.setValueAtTime(1e-4, ctx.currentTime);
    env.gain.linearRampToValueAtTime(gain, ctx.currentTime + Math.min(0.02, duration * 0.2));
    env.gain.exponentialRampToValueAtTime(1e-3, ctx.currentTime + duration);
    osc.connect(env);
    env.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration);
  }
  swordHit() {
    this.playNoise(0.18, 800, 0.25);
    this.tone(120, 0.12, "sawtooth", 0.08);
  }
  rangedShot() {
    this.tone(1200, 0.22, "square", 0.12, 400);
  }
  footstep() {
    this.playNoise(0.06, 250, 0.08);
  }
  trapTrigger() {
    this.playNoise(0.25, 600, 0.25);
    this.tone(150, 0.2, "sawtooth", 0.12);
  }
  playAmbient(type) {
    this.ambientType = type;
    this.ambientActive = true;
    this.playTrack("ambient", true).then((played) => {
      if (!played) {
        this._generativeAmbient(type);
      }
    });
  }
  _generativeAmbient(type) {
    if (this.muted) return;
    const ctx = this.ensureContext();
    if (!ctx) return;
    this.stopAmbient();
    const duration = 4;
    const samples = Math.ceil(ctx.sampleRate * duration);
    const buffer = ctx.createBuffer(1, samples, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    let last = 0;
    for (let i = 0; i < data.length; i++) {
      const white = Math.random() * 2 - 1;
      last = (last + white * 0.05) / 1.05;
      data[i] = last;
    }
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.loop = true;
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = type === "cave" ? 180 : 260;
    filter.Q.value = 0.7;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(this.musicVolume, ctx.currentTime + 1.5);
    const lfo = ctx.createOscillator();
    lfo.type = "sine";
    lfo.frequency.value = type === "cave" ? 0.12 : 0.2;
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = type === "cave" ? 30 : 45;
    lfo.connect(lfoGain);
    lfoGain.connect(filter.frequency);
    lfo.start();
    src.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);
    src.start();
    this.ambientNodes = { source: src, gain, filter };
  }
  stopAmbient() {
    this.ambientActive = false;
    this.music.stopTrack();
    if (!this.ambientNodes) return;
    const ctx = this.ctx;
    if (ctx) {
      const { source, gain } = this.ambientNodes;
      try {
        gain.gain.cancelScheduledValues(ctx.currentTime);
        gain.gain.setValueAtTime(gain.gain.value, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.5);
        source.stop(ctx.currentTime + 0.6);
      } catch {
        source.stop();
      }
    }
    this.ambientNodes = null;
  }
  isAmbientActive() {
    return this.ambientActive;
  }
};

// src/lib/tile-atlas.ts
var THEMES = {
  dungeon: {
    name: "Dungeon",
    floor: [20, 0],
    wall: [21, 1],
    trap: [8, 6],
    images: { floor: "/assets/tiles/dungeon_floor.png", wall: "/assets/tiles/dungeon_wall.png", trap: "/assets/tiles/dungeon_trap.png" }
  },
  cave: {
    name: "Cave",
    floor: [6, 0],
    wall: [6, 5],
    trap: [8, 6],
    images: { floor: "/assets/tiles/cave_floor.png", wall: "/assets/tiles/cave_wall.png", trap: "/assets/tiles/cave_trap.png" }
  },
  library: {
    name: "Library",
    floor: [15, 0],
    wall: [10, 2],
    trap: [8, 6],
    images: { floor: "/assets/tiles/library_floor.png", wall: "/assets/tiles/library_wall.png", trap: "/assets/tiles/library_trap.png" }
  },
  ice: {
    name: "Frozen",
    floor: [17, 13],
    wall: [19, 12],
    trap: [8, 6],
    water: [17, 12],
    images: { floor: "/assets/tiles/ice_floor.png", wall: "/assets/tiles/ice_wall.png", trap: "/assets/tiles/ice_trap.png" }
  },
  lava: {
    name: "Volcanic",
    floor: [28, 14],
    wall: [29, 12],
    trap: [8, 6],
    lava: [29, 14],
    images: { floor: "/assets/tiles/lava_floor.png", wall: "/assets/tiles/lava_wall.png", trap: "/assets/tiles/lava_trap.png" }
  },
  forest: {
    name: "Forest",
    floor: [0, 0],
    wall: [3, 6],
    trap: [8, 6],
    water: [1, 0],
    images: { floor: "/assets/tiles/forest_floor.png", wall: "/assets/tiles/forest_wall.png", trap: "/assets/tiles/forest_trap.png" }
  },
  tomb: {
    name: "Tomb",
    floor: [20, 13],
    wall: [21, 13],
    trap: [8, 6],
    images: { floor: "/assets/tiles/tomb_floor.png", wall: "/assets/tiles/tomb_wall.png", trap: "/assets/tiles/tomb_trap.png" }
  },
  sewer: {
    name: "Sewer",
    floor: [10, 13],
    wall: [12, 13],
    trap: [8, 6],
    water: [1, 0],
    images: { floor: "/assets/tiles/sewer_floor.png", wall: "/assets/tiles/sewer_wall.png", trap: "/assets/tiles/sewer_trap.png" }
  }
};
var TOKEN_IMAGES = {
  hero: "/assets/tokens/hero.png",
  fighter: "/assets/tokens/hero.png",
  cleric: "/assets/tokens/hero.png",
  magicuser: "/assets/tokens/hero.png",
  illusionist: "/assets/tokens/hero.png",
  thief: "/assets/tokens/hero.png",
  ranger: "/assets/tokens/hero.png",
  paladin: "/assets/tokens/hero.png",
  druid: "/assets/tokens/hero.png",
  assassin: "/assets/tokens/hero.png",
  monk: "/assets/tokens/hero.png",
  goblin: "/assets/tokens/goblin.png",
  orc: "/assets/tokens/orc.png",
  skeleton: "/assets/tokens/skeleton.png",
  zombie: "/assets/tokens/zombie.png",
  ghoul: "/assets/tokens/ghoul.png",
  shadow_imp: "/assets/tokens/shadow_imp.png",
  librarian: "/assets/tokens/librarian.png",
  animated_book: "/assets/tokens/animated_book.png",
  shadow_warden: "/assets/tokens/shadow_warden.png",
  wolf: "/assets/tokens/wolf.png",
  bear: "/assets/tokens/bear.png",
  spider: "/assets/tokens/spider.png",
  snake: "/assets/tokens/snake.png",
  bat: "/assets/tokens/bat.png",
  rat: "/assets/tokens/rat.png",
  slime: "/assets/tokens/slime.png",
  demon: "/assets/tokens/demon.png",
  dragon: "/assets/tokens/dragon.png"
};
function getTheme(id) {
  if (!id) return null;
  return THEMES[id] ?? null;
}
function preloadImage(src) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve();
    img.onerror = () => resolve();
    img.src = src;
  });
}
async function loadAtlas() {
  const urls = /* @__PURE__ */ new Set();
  for (const theme of Object.values(THEMES)) {
    if (theme.images?.floor) urls.add(theme.images.floor);
    if (theme.images?.wall) urls.add(theme.images.wall);
    if (theme.images?.trap) urls.add(theme.images.trap);
  }
  for (const path of Object.values(TOKEN_IMAGES)) {
    urls.add(path);
  }
  await Promise.all([...urls].map(preloadImage));
}
function tileFrame(_themeId, theme, tile) {
  switch (tile) {
    case "0":
    case "3":
    case "4":
    case "5":
      return theme.images?.floor ?? null;
    case "1":
      return theme.images?.wall ?? null;
    case "2":
      return theme.images?.trap ?? null;
    default:
      return theme.images?.floor ?? null;
  }
}
function tokenFrame(key) {
  if (!key) return null;
  const normalized = key.toLowerCase().replace(/[-\s]/g, "");
  return TOKEN_IMAGES[normalized] ?? null;
}

// src/ui/auto-player.ts
var RANGED_RANGE = 4;
var AutoPlayer = class {
  game;
  running = false;
  pending = false;
  constructor(game) {
    this.game = game;
  }
  start() {
    this.running = true;
    this.tick();
  }
  stop() {
    this.running = false;
  }
  isRunning() {
    return this.running;
  }
  onUpdate() {
    if (!this.running) return;
    window.setTimeout(() => this.tick(), 600);
  }
  async tick() {
    if (!this.running || this.pending) return;
    const session = this.game.getSession();
    const mod = this.game.getModule();
    if (!session || !mod || session.status !== "active") {
      this.stop();
      return;
    }
    if (session.phase === "dm" && !session.campaign_id) {
      this.pending = true;
      try {
        await this.game.runDmTurn();
      } finally {
        this.pending = false;
      }
      return;
    }
    if (session.phase !== "player") return;
    const player = session.player;
    if (!player || player.down || player.alive === false) {
      this.stop();
      return;
    }
    const aliveMonsters = session.monsters.filter((m) => m.alive !== false);
    if (aliveMonsters.length === 0) {
      this.stop();
      return;
    }
    this.pending = true;
    try {
      await this.takeTurn(session, mod, player, aliveMonsters);
    } finally {
      this.pending = false;
    }
  }
  async takeTurn(session, mod, player, monsters) {
    const occupied = /* @__PURE__ */ new Set();
    for (const t of [...session.players, ...session.monsters]) {
      if (t.alive !== false && t.id !== player.id) {
        occupied.add(`${t.x},${t.y}`);
      }
    }
    const isWalkable = (x, y) => {
      if (x < 0 || y < 0 || x >= mod.width || y >= mod.height) return false;
      const row = mod.tiles[y] || "";
      return row[x] !== "1" && !occupied.has(`${x},${y}`);
    };
    const adjacentMonster = this.findNearestAdjacent(player, monsters);
    if (adjacentMonster) {
      const { session: next2 } = await actInSession(session.id, "attack", { target_id: adjacentMonster.id });
      this.game.update(next2);
      return;
    }
    const rangedTarget = this.findRangedTarget(player, monsters, mod);
    if (rangedTarget) {
      const { session: next2 } = await actInSession(session.id, "ranged", { target_id: rangedTarget.id });
      this.game.update(next2);
      return;
    }
    const step = this.findStepTowards(player, monsters, isWalkable);
    if (step) {
      const { session: next2 } = await actInSession(session.id, "move", { x: step.x, y: step.y });
      this.game.update(next2);
      return;
    }
    const { session: next } = await actInSession(session.id, "end_turn");
    this.game.update(next);
  }
  findNearestAdjacent(player, monsters) {
    let best = null;
    let bestDist = Infinity;
    for (const m of monsters) {
      const dist = Math.abs(player.x - m.x) + Math.abs(player.y - m.y);
      if (dist === 1 && dist < bestDist) {
        best = m;
        bestDist = dist;
      }
    }
    return best;
  }
  findRangedTarget(player, monsters, mod) {
    let best = null;
    let bestDist = Infinity;
    for (const m of monsters) {
      const dist = Math.abs(player.x - m.x) + Math.abs(player.y - m.y);
      if (dist > 1 && dist <= RANGED_RANGE && dist < bestDist && this.hasLineOfSight(player, m, mod)) {
        best = m;
        bestDist = dist;
      }
    }
    return best;
  }
  findStepTowards(player, monsters, isWalkable) {
    const start = `${player.x},${player.y}`;
    const visited = /* @__PURE__ */ new Set([start]);
    const parent = /* @__PURE__ */ new Map();
    parent.set(start, null);
    const queue = [{ x: player.x, y: player.y }];
    let bestTarget = null;
    let bestScore = Infinity;
    while (queue.length > 0) {
      const cur2 = queue.shift();
      for (const m of monsters) {
        const d = Math.abs(cur2.x - m.x) + Math.abs(cur2.y - m.y);
        if (d < bestScore) {
          bestScore = d;
          bestTarget = cur2;
        }
      }
      for (const [dx, dy] of [[0, -1], [0, 1], [-1, 0], [1, 0]]) {
        const nx = cur2.x + dx;
        const ny = cur2.y + dy;
        const key = `${nx},${ny}`;
        if (visited.has(key) || !isWalkable(nx, ny)) continue;
        visited.add(key);
        parent.set(key, `${cur2.x},${cur2.y}`);
        queue.push({ x: nx, y: ny });
      }
    }
    if (!bestTarget) return null;
    let cur = `${bestTarget.x},${bestTarget.y}`;
    while (parent.get(cur)) {
      const prev = parent.get(cur);
      if (prev === start) {
        const [x, y] = cur.split(",").map(Number);
        return { x, y };
      }
      cur = prev;
    }
    return null;
  }
  hasLineOfSight(a, b, mod) {
    let dx = Math.abs(b.x - a.x);
    let dy = Math.abs(b.y - a.y);
    const sx = a.x < b.x ? 1 : -1;
    const sy = a.y < b.y ? 1 : -1;
    let err = dx - dy;
    let x = a.x;
    let y = a.y;
    while (x !== b.x || y !== b.y) {
      const e2 = 2 * err;
      if (e2 > -dy) {
        err -= dy;
        x += sx;
      }
      if (e2 < dx) {
        err += dx;
        y += sy;
      }
      if ((x !== a.x || y !== a.y) && mod.tiles[y]?.[x] === "1") {
        return false;
      }
    }
    return true;
  }
};

// src/ui/game.ts
var TILE_SIZE = 64;
function withTimeout(promise, ms, reason = "Operation timed out") {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(reason)), ms);
    promise.then((value2) => {
      window.clearTimeout(timer);
      resolve(value2);
    }).catch((err) => {
      window.clearTimeout(timer);
      reject(err);
    });
  });
}
var VISION_RADIUS = 6;
var RANGED_RANGE2 = 4;
var Game = class {
  root;
  sessionId;
  module;
  mapContainer;
  tokenContainer;
  fxContainer;
  ui;
  logEl = document.createElement("div");
  statusEl = document.createElement("div");
  timerEl = document.createElement("div");
  statEl = document.createElement("div");
  partyEl = document.createElement("div");
  rosterEl = document.createElement("div");
  dmOverlay = document.createElement("div");
  damageFlash = document.createElement("div");
  action = null;
  session = null;
  userId = null;
  onExit;
  onReplay;
  canvasContainer;
  timerInterval = null;
  timeoutFired = false;
  tileSprites = [];
  lastTokenHp = /* @__PURE__ */ new Map();
  shakeFrames = 0;
  lastLogLength = 0;
  lastBannerTurn = 0;
  cameraX = 0;
  cameraY = 0;
  tooltip;
  moveBtn;
  attackBtn;
  rangedBtn;
  potionBtn;
  abilityBtn;
  stabilizeBtn;
  restBtn;
  endBtn;
  saveBtn;
  dmTurnBtn;
  autoplayBtn;
  autoPlayer;
  dmToolsEl = document.createElement("div");
  dmMonsterSelect = document.createElement("select");
  dmTokenSelect = document.createElement("select");
  dmAction = null;
  socket = null;
  visited = /* @__PURE__ */ new Set();
  audio = new AudioController();
  chatPanel = null;
  chatMessages = document.createElement("div");
  chatInput = document.createElement("input");
  chatCollapsed = false;
  presencePanel = null;
  presenceList = document.createElement("div");
  journalPanel = null;
  journalOpen = false;
  heartbeatInterval = null;
  moduleId;
  loadingOverlay;
  constructor(container, sessionId, module, initialSession, onExit, onReplay, userId) {
    this.root = container;
    this.sessionId = sessionId;
    this.module = module;
    this.moduleId = initialSession.module_id;
    this.userId = userId ?? null;
    this.onExit = onExit;
    this.onReplay = onReplay;
    this.root.className = "game-shell";
    this.canvasContainer = el("div", { className: "game-canvas-container" });
    this.mapContainer = el("div", { className: "game-map" });
    this.tokenContainer = el("div", { className: "game-tokens" });
    this.fxContainer = el("div", { className: "game-effects" });
    this.canvasContainer.appendChild(this.mapContainer);
    this.canvasContainer.appendChild(this.tokenContainer);
    this.canvasContainer.appendChild(this.fxContainer);
    this.ui = this.buildUI();
    this.chatPanel = this.buildChatPanel();
    this.presencePanel = this.buildPresencePanel();
    this.root.appendChild(this.canvasContainer);
    this.root.appendChild(this.ui);
    if (this.presencePanel) this.root.appendChild(this.presencePanel);
    if (this.chatPanel) this.root.appendChild(this.chatPanel);
    this.tooltip = el("div", { className: "token-tooltip" });
    this.tooltip.style.display = "none";
    this.root.appendChild(this.tooltip);
    this.dmOverlay = el("div", { className: "dm-overlay" });
    this.dmOverlay.innerHTML = '<div class="dm-spinner"></div><span>The DM ponders...</span>';
    this.dmOverlay.style.display = "none";
    this.root.appendChild(this.dmOverlay);
    this.damageFlash = el("div", { className: "damage-flash" });
    this.root.appendChild(this.damageFlash);
    const scanlines = el("div", { className: "scanlines" });
    this.root.appendChild(scanlines);
    const trayAnchor = el("div", { className: "tray-anchor" });
    this.root.appendChild(trayAnchor);
    new DiceTray(trayAnchor);
    this.loadingOverlay = el("div", { className: "game-loading" });
    this.loadingOverlay.innerHTML = '<div class="game-loading-spinner"></div><span>Entering the room...</span>';
    this.root.appendChild(this.loadingOverlay);
    this.autoPlayer = new AutoPlayer(this);
    this.update(initialSession);
    window.addEventListener("resize", () => this.centerMap());
    this.keydownHandler = (e) => this.onKeyDown(e);
    window.addEventListener("keydown", this.keydownHandler);
    this.beforeUnloadHandler = () => {
      if (this.session && this.session.status !== "won") {
        this.saveProgression().catch(() => {
        });
      }
    };
    window.addEventListener("beforeunload", this.beforeUnloadHandler);
  }
  keydownHandler = null;
  beforeUnloadHandler = null;
  isCampaignSession() {
    return !!this.session?.campaign_id;
  }
  getSession() {
    return this.session;
  }
  getModule() {
    return this.module;
  }
  toggleAutoplay() {
    if (this.autoPlayer.isRunning()) {
      this.autoPlayer.stop();
      this.autoplayBtn.textContent = "\u25B6 Observer";
      this.autoplayBtn.classList.remove("active");
    } else {
      this.autoPlayer.start();
      this.autoplayBtn.textContent = "\u23F8 Observer";
      this.autoplayBtn.classList.add("active");
    }
  }
  isDm() {
    return this.isCampaignSession() && this.session?.dm_account_id === this.userId;
  }
  isPlayer() {
    if (!this.session) return false;
    const active = this.session.player;
    if (active?.down) return false;
    if (active && "account_id" in active && active.account_id != null) {
      return active.account_id === this.userId;
    }
    return !this.session.campaign_id || this.session.account_id === this.userId;
  }
  setLoadingStatus(text) {
    const span = this.loadingOverlay.querySelector("span");
    if (span) {
      span.textContent = text;
      span.getBoundingClientRect();
    }
  }
  async init() {
    const safetyTimeout = window.setTimeout(() => {
      console.error("Game init safety timeout fired.");
      this.showInitFailure("The room is taking too long to answer.");
    }, 12e3);
    const releaseSafety = () => window.clearTimeout(safetyTimeout);
    try {
      this.setLoadingStatus("Loading room tiles...");
      try {
        await withTimeout(loadAtlas(), 5e3, "Tile atlas load timed out");
      } catch (err) {
        console.warn("Proceeding without tile atlas:", err);
      }
      this.setLoadingStatus("Carving the dungeon...");
      this.renderMap();
      this.renderTokens(true);
      this.centerMap();
      this.setLoadingStatus("Joining the session...");
      this.socket = connectSocket();
      this.socket.emit("join_session", { session_id: this.sessionId });
      this.socket.on("session_update", (payload) => {
        if (payload.session && payload.session.id === this.sessionId) {
          this.update(payload.session);
        }
      });
      this.socket.on("chat_broadcast", (payload) => {
        this.appendChatMessage(payload);
      });
      this.socket.on("presence_update", (payload) => {
        if (payload.session_id === this.sessionId && payload.present) {
          this.updatePresence(payload.present);
        }
      });
      try {
        const { present } = await withTimeout(getSessionPresence(this.sessionId), 5e3, "Presence fetch timed out");
        this.updatePresence(present);
      } catch {
      }
      this.heartbeatInterval = window.setInterval(() => {
        this.socket?.emit("heartbeat", { session_id: this.sessionId });
      }, 3e4);
    } catch (err) {
      releaseSafety();
      console.error("Failed to initialize game:", err);
      this.showInitFailure(err?.message || "Failed to enter the room.");
      throw err;
    }
    releaseSafety();
    this.loadingOverlay.remove();
  }
  showInitFailure(message) {
    this.loadingOverlay.innerHTML = `<span>${message}</span><button>Return</button>`;
    const btn = this.loadingOverlay.querySelector("button");
    if (btn) btn.onclick = () => this.onExit();
  }
  buildUI() {
    const hud = el("div", { className: "game-hud" });
    hud.appendChild(el("h1", {}, "Sanctuary"));
    this.statusEl = el("div", { className: "game-status" }, "Turn 1 \xB7 Your Move");
    hud.appendChild(this.statusEl);
    this.timerEl = el("div", { className: "game-timer" });
    hud.appendChild(this.timerEl);
    const actions = el("div", { className: "game-actions" });
    this.moveBtn = el("button", { onclick: () => {
      this.ensureAudioStarted();
      this.setAction("move");
    } }, "Move [M]");
    this.attackBtn = el("button", { onclick: () => {
      this.ensureAudioStarted();
      this.setAction("attack");
    } }, "Attack [F]");
    this.rangedBtn = el("button", { onclick: () => {
      this.ensureAudioStarted();
      this.setAction("ranged");
    } }, "Ranged [R]");
    this.potionBtn = el("button", { onclick: () => {
      this.ensureAudioStarted();
      this.usePotion();
    } }, "Potion [P]");
    this.abilityBtn = el("button", { onclick: () => {
      this.ensureAudioStarted();
      this.setAction("ability");
    } }, "Ability [Q]");
    this.stabilizeBtn = el("button", { onclick: () => {
      this.ensureAudioStarted();
      this.stabilize();
    } }, "Stabilize [S]");
    this.restBtn = el("button", { onclick: () => {
      this.ensureAudioStarted();
      this.rest();
    } }, "Rest");
    this.endBtn = el("button", { onclick: () => {
      this.ensureAudioStarted();
      this.endTurn();
    } }, "End [E]");
    actions.appendChild(this.moveBtn);
    actions.appendChild(this.attackBtn);
    actions.appendChild(this.rangedBtn);
    actions.appendChild(this.potionBtn);
    actions.appendChild(this.abilityBtn);
    actions.appendChild(this.stabilizeBtn);
    actions.appendChild(this.restBtn);
    actions.appendChild(this.endBtn);
    hud.appendChild(actions);
    this.dmTurnBtn = el("button", {
      className: "dm-turn-btn",
      onclick: () => this.runDmTurn()
    }, "Run DM Turn");
    this.dmTurnBtn.style.display = "none";
    hud.appendChild(this.dmTurnBtn);
    this.autoplayBtn = el("button", {
      className: "autoplay-btn small",
      onclick: () => this.toggleAutoplay()
    }, "\u25B6 Observer");
    this.autoplayBtn.style.display = "none";
    hud.appendChild(this.autoplayBtn);
    this.statEl = el("div", { className: "player-stats" });
    hud.appendChild(this.statEl);
    const unitsPanel = el("div", { className: "units-panel" });
    const unitsHeader = el("div", { className: "units-tabs" });
    const partyTab = el("button", {
      className: "units-tab active",
      onclick: () => this.setUnitsTab("party", partyTab, foesTab)
    }, "Party");
    const foesTab = el("button", {
      className: "units-tab",
      onclick: () => this.setUnitsTab("foes", partyTab, foesTab)
    }, "Foes");
    unitsHeader.appendChild(partyTab);
    unitsHeader.appendChild(foesTab);
    unitsPanel.appendChild(unitsHeader);
    this.partyEl = el("div", { className: "party-roster" });
    this.rosterEl = el("div", { className: "monster-roster", style: "display:none" });
    unitsPanel.appendChild(this.partyEl);
    unitsPanel.appendChild(this.rosterEl);
    hud.appendChild(unitsPanel);
    this.logEl = el("div", { className: "game-log" });
    hud.appendChild(el("h2", {}, "Chronicle"));
    hud.appendChild(this.logEl);
    this.dmToolsEl = this.buildDmTools();
    this.dmToolsEl.style.display = "none";
    hud.appendChild(this.dmToolsEl);
    const footer = el("div", { className: "hud-footer" });
    const audioGroup = el("div", { className: "hud-footer-group" });
    const muteBtn = el("button", {
      className: "mute-btn icon-btn",
      title: "Toggle mute",
      onclick: () => {
        this.ensureAudioStarted();
        const muted = this.audio.toggleMute();
        muteBtn.textContent = muted ? "\u{1F507}" : "\u{1F50A}";
        muteBtn.classList.toggle("muted", muted);
      }
    }, "\u{1F50A}");
    audioGroup.appendChild(muteBtn);
    const ambientBtn = el("button", {
      className: "ambient-btn icon-btn",
      title: "Toggle ambient sound",
      onclick: () => {
        this.ensureAudioStarted();
        if (this.audio.isAmbientActive()) {
          this.audio.stopAmbient();
          ambientBtn.classList.remove("active");
        } else {
          this.audio.playAmbient(this.moduleId === "sunken_crypt" ? "cave" : "dungeon");
          ambientBtn.classList.add("active");
        }
      }
    }, "\u266B");
    audioGroup.appendChild(ambientBtn);
    const volumeSlider = el("input", {
      className: "hud-volume",
      type: "range",
      min: "0",
      max: "1",
      step: "0.05",
      value: String(this.audio.getMusicVolume()),
      title: "Music volume",
      oninput: (e) => {
        const val = parseFloat(e.target.value);
        this.audio.setMusicVolume(val);
      }
    });
    audioGroup.appendChild(volumeSlider);
    footer.appendChild(audioGroup);
    const actionGroup = el("div", { className: "hud-footer-group" });
    const saveBtn = el("button", {
      className: "save-btn small",
      title: "Save progress",
      onclick: () => this.saveProgression()
    }, "\u{1F4BE}");
    this.saveBtn = saveBtn;
    actionGroup.appendChild(saveBtn);
    const journalBtn = el("button", {
      className: "journal-btn small",
      title: "Journal",
      onclick: () => this.toggleJournal()
    }, "\u{1F4DC}");
    actionGroup.appendChild(journalBtn);
    const exitBtn = el("button", { className: "danger small", title: "Leave session", onclick: () => this.leaveSession() }, "\u2715");
    actionGroup.appendChild(exitBtn);
    footer.appendChild(actionGroup);
    hud.appendChild(footer);
    return hud;
  }
  ensureAudioStarted() {
    this.audio.ensureStartedFromGesture().catch(() => {
    });
  }
  buildChatPanel() {
    const panel = el("div", { className: "chat-panel" });
    const header = el("div", {
      className: "chat-header",
      onclick: () => this.toggleChat()
    }, "Party Chat");
    panel.appendChild(header);
    this.chatMessages = el("div", { className: "chat-messages" });
    panel.appendChild(this.chatMessages);
    const controls = el("div", { className: "chat-controls" });
    this.chatInput = el("input", {
      type: "text",
      placeholder: "Say something...",
      maxlength: 500,
      onkeydown: (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          this.sendChat();
        }
      }
    });
    const sendBtn = el("button", {
      onclick: () => this.sendChat()
    }, "Send");
    controls.appendChild(this.chatInput);
    controls.appendChild(sendBtn);
    panel.appendChild(controls);
    panel.style.display = "none";
    return panel;
  }
  buildPresencePanel() {
    const panel = el("div", { className: "presence-panel" });
    panel.appendChild(el("h3", {}, "Online"));
    this.presenceList = el("div", { className: "presence-list" });
    panel.appendChild(this.presenceList);
    panel.style.display = "none";
    return panel;
  }
  buildJournalPanel() {
    const panel = el("div", { className: "journal-overlay" });
    const card = el("div", { className: "journal-card" });
    const header = el("div", { className: "journal-header" });
    header.appendChild(el("h2", {}, "Adventure Journal"));
    const close = el("button", { className: "journal-close", onclick: () => this.toggleJournal() }, "\xD7");
    header.appendChild(close);
    card.appendChild(header);
    const body = el("div", { className: "journal-body" });
    const moduleName = el("h3", { className: "journal-module" }, this.moduleId);
    body.appendChild(moduleName);
    const bestiary = el("div", { className: "journal-bestiary" });
    bestiary.appendChild(el("h4", {}, "Bestiary"));
    const bestiaryList = el("div", { className: "journal-bestiary-list" });
    bestiary.appendChild(bestiaryList);
    body.appendChild(bestiary);
    const chronicle = el("div", { className: "journal-chronicle" });
    chronicle.appendChild(el("h4", {}, "Chronicle"));
    const chronicleList = el("div", { className: "journal-chronicle-list" });
    chronicle.appendChild(chronicleList);
    body.appendChild(chronicle);
    card.appendChild(body);
    panel.appendChild(card);
    panel.style.display = "none";
    return panel;
  }
  toggleJournal() {
    if (!this.journalPanel) {
      this.journalPanel = this.buildJournalPanel();
      this.root.appendChild(this.journalPanel);
    }
    this.journalOpen = !this.journalOpen;
    this.journalPanel.style.display = this.journalOpen ? "flex" : "none";
    if (this.journalOpen) this.updateJournal();
  }
  updateJournal() {
    if (!this.journalPanel || !this.session) return;
    const moduleName = this.journalPanel.querySelector(".journal-module");
    if (moduleName) moduleName.textContent = this.moduleId;
    const bestiaryList = this.journalPanel.querySelector(".journal-bestiary-list");
    if (bestiaryList) {
      clear(bestiaryList);
      const seen = /* @__PURE__ */ new Set();
      [...this.session.monsters, ...this.session.players || []].forEach((t) => {
        const key = t.type === "monster" ? t.monster || t.name : t.name;
        if (!key || seen.has(key)) return;
        seen.add(key);
        const row = el("div", { className: "journal-bestiary-row" });
        row.appendChild(el("span", { className: "journal-bestiary-name" }, key));
        row.appendChild(el("span", { className: "journal-bestiary-hp" }, `HP ${t.hp}/${t.max_hp}`));
        row.appendChild(el("span", { className: "journal-bestiary-ac" }, `AC ${t.ac}`));
        bestiaryList.appendChild(row);
      });
      if (bestiaryList.childElementCount === 0) {
        bestiaryList.appendChild(el("div", { className: "journal-empty" }, "No creatures encountered yet."));
      }
    }
    const chronicleList = this.journalPanel.querySelector(".journal-chronicle-list");
    if (chronicleList) {
      clear(chronicleList);
      const log = this.session.log.slice(-30);
      if (log.length === 0) {
        chronicleList.appendChild(el("div", { className: "journal-empty" }, "No events recorded yet."));
      } else {
        log.forEach((entry) => {
          const row = el("div", { className: "journal-chronicle-row" }, entry);
          chronicleList.appendChild(row);
        });
      }
    }
  }
  updatePresence(present) {
    if (!this.presencePanel) return;
    clear(this.presenceList);
    if (present.length === 0) {
      this.presencePanel.style.display = "none";
      return;
    }
    this.presencePanel.style.display = "block";
    present.forEach((p) => {
      const name = p.name || `Account ${p.account_id ?? "?"}`;
      this.presenceList.appendChild(el("div", { className: "presence-row" }, name));
    });
  }
  toggleChat() {
    this.chatCollapsed = !this.chatCollapsed;
    this.chatPanel?.classList.toggle("collapsed", this.chatCollapsed);
  }
  sendChat() {
    if (!this.socket) return;
    const text = this.chatInput.value.trim();
    if (!text) return;
    this.socket.emit("chat_message", {
      session_id: this.sessionId,
      text,
      name: document.body.dataset.user || "Player"
    });
    this.chatInput.value = "";
  }
  appendChatMessage(payload) {
    if (!payload.text) return;
    const name = payload.name || "Player";
    const time = payload.timestamp ? new Date(payload.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
    const row = el("div", { className: "chat-message" });
    const timeSpan = el("span", { className: "chat-time" }, time);
    const nameSpan = el("span", { className: "chat-name" }, name);
    const textSpan = el("span", { className: "chat-text" }, payload.text);
    row.appendChild(timeSpan);
    row.appendChild(nameSpan);
    row.appendChild(textSpan);
    this.chatMessages.appendChild(row);
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
  }
  showTooltip(token, clientX, clientY) {
    const subtitle = token.type === "player" ? (token.classes || ["Adventurer"]).join(" / ") : token.name;
    const statusText = (token.statuses || []).map((s) => `${s.type}${s.duration ? ` (${s.duration})` : ""}`).join(", ");
    const downText = token.down ? '<div class="token-tooltip-down">DOWNED</div>' : "";
    this.tooltip.innerHTML = `
      <strong>${token.name}</strong>
      <div class="token-tooltip-sub">${subtitle}</div>
      <div>HP ${token.hp}/${token.max_hp}</div>
      <div>AC ${token.ac}</div>
      ${downText}
      ${statusText ? `<div>Status: ${statusText}</div>` : ""}
    `;
    this.tooltip.style.display = "block";
    this.positionTooltip(clientX, clientY);
  }
  moveTooltip(clientX, clientY) {
    if (this.tooltip.style.display === "none") return;
    this.positionTooltip(clientX, clientY);
  }
  positionTooltip(clientX, clientY) {
    const rect = this.root.getBoundingClientRect();
    const x = clientX - rect.left + 14;
    const y = clientY - rect.top + 14;
    const maxX = rect.width - 180;
    const maxY = rect.height - 90;
    this.tooltip.style.left = `${Math.min(x, maxX)}px`;
    this.tooltip.style.top = `${Math.min(y, maxY)}px`;
  }
  hideTooltip() {
    this.tooltip.style.display = "none";
  }
  showGameOver() {
    if (!this.session || this.session.status === "active") return;
    const existing = this.root.querySelector(".game-over-overlay");
    if (existing) return;
    const overlay = el("div", { className: "game-over-overlay" });
    const panel = el("div", { className: "game-over-panel" });
    const won = this.session.status === "won";
    panel.appendChild(el("h1", {}, won ? "Victory" : "Defeat"));
    if (won) {
      const living = this.session.players.filter((p) => p.alive !== false);
      const totalXp = living.reduce((sum, p) => sum + (p.xp ?? 0), 0);
      const totalGold = living.reduce((sum, p) => sum + (p.gold ?? 0), 0);
      panel.appendChild(el("p", { className: "message" }, `The lair is quiet. Party gains ${totalXp} XP and ${totalGold} gold.`));
    } else {
      panel.appendChild(el("p", { className: "message" }, "Your light fades in the dark. The dungeon claims another."));
    }
    const isCampaign = this.isCampaignSession();
    if (isCampaign && won) {
      const journey = el("button", { className: "enter", onclick: () => this.journeyOn() }, "Journey On");
      panel.appendChild(journey);
    } else if (this.onReplay && this.session.character_id) {
      const replay = el("button", { className: "enter", onclick: () => this.onReplay(this.session.character_id) }, "Play Again");
      panel.appendChild(replay);
    }
    const leave = el("button", { onclick: () => this.onExit() }, "Return to Sanctuary");
    panel.appendChild(leave);
    overlay.appendChild(panel);
    this.root.appendChild(overlay);
  }
  setAction(action) {
    this.action = this.action === action ? null : action;
    this.updateStatus();
    this.highlightActionTiles();
  }
  setDmAction(action) {
    this.dmAction = this.dmAction === action ? null : action;
    this.updateStatus();
  }
  buildDmTools() {
    const panel = el("div", { className: "dm-tools" });
    panel.appendChild(el("h3", {}, "DM Tools"));
    const spawnWrap = el("div", { className: "dm-tool-row" });
    this.dmMonsterSelect = el("select", {});
    ["goblin", "orc", "skeleton", "zombie", "ghoul", "shadow_imp", "librarian", "animated_book"].forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      this.dmMonsterSelect.appendChild(opt);
    });
    spawnWrap.appendChild(this.dmMonsterSelect);
    spawnWrap.appendChild(el("button", { onclick: () => this.setDmAction("spawn") }, "Spawn"));
    panel.appendChild(spawnWrap);
    const moveWrap = el("div", { className: "dm-tool-row" });
    this.dmTokenSelect = el("select", {});
    moveWrap.appendChild(this.dmTokenSelect);
    moveWrap.appendChild(el("button", { onclick: () => this.setDmAction("move") }, "Move"));
    panel.appendChild(moveWrap);
    panel.appendChild(
      el("button", { onclick: () => this.setDmAction("reveal") }, "Reveal Fog")
    );
    return panel;
  }
  updateDmTools() {
    const isDm = this.isDm();
    this.dmToolsEl.style.display = isDm && this.session?.status === "active" ? "block" : "none";
    if (!isDm || !this.session) return;
    const currentToken = this.dmTokenSelect.value;
    clear(this.dmTokenSelect);
    this.session.monsters.filter((m) => m.alive !== false).forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = `${m.name} (${m.id})`;
      this.dmTokenSelect.appendChild(opt);
    });
    if (currentToken) this.dmTokenSelect.value = currentToken;
  }
  onKeyDown(e) {
    this.ensureAudioStarted();
    if (!this.session || this.session.status !== "active" || this.session.phase !== "player") return;
    switch (e.key.toLowerCase()) {
      case "escape":
        if (this.action) {
          this.action = null;
          this.updateStatus();
          this.highlightActionTiles();
        }
        break;
      case "m":
        this.setAction("move");
        break;
      case "f":
        this.setAction("attack");
        break;
      case "r":
        this.setAction("ranged");
        break;
      case "p":
        e.preventDefault();
        this.usePotion();
        break;
      case "q":
        this.setAction("ability");
        break;
      case "s":
        e.preventDefault();
        this.stabilize();
        break;
      case "e":
      case " ":
        e.preventDefault();
        this.endTurn();
        break;
      case "arrowup":
        e.preventDefault();
        this.tryMove(0, -1);
        break;
      case "arrowdown":
        e.preventDefault();
        this.tryMove(0, 1);
        break;
      case "arrowleft":
        e.preventDefault();
        this.tryMove(-1, 0);
        break;
      case "arrowright":
        e.preventDefault();
        this.tryMove(1, 0);
        break;
    }
  }
  async tryMove(dx, dy) {
    if (!this.session || this.session.phase !== "player" || this.session.status !== "active") return;
    if (this.action && this.action !== "move") return;
    const player = this.session.player;
    const x = player.x + dx;
    const y = player.y + dy;
    try {
      const { session } = await actInSession(this.sessionId, "move", { x, y });
      this.action = null;
      this.update(session);
    } catch (err) {
      this.log(err.message || "Move failed.");
    }
  }
  async endTurn() {
    if (!this.session || this.session.phase !== "player") return;
    try {
      const { session } = await actInSession(this.sessionId, "end_turn");
      this.action = null;
      this.update(session);
      if (session.phase === "dm" && !this.isCampaignSession()) {
        setTimeout(() => this.runDmTurn(), 600);
      }
    } catch (err) {
      this.log(err.message || "End turn failed.");
    }
  }
  async usePotion() {
    if (!this.session || this.session.phase !== "player" || !this.isPlayer()) return;
    try {
      const { session } = await actInSession(this.sessionId, "use_potion");
      this.update(session);
      if (session.phase === "dm" && !this.isCampaignSession()) {
        setTimeout(() => this.runDmTurn(), 600);
      }
    } catch (err) {
      this.log(err.message || "Potion failed.");
    }
  }
  async stabilize() {
    if (!this.session || this.session.phase !== "player" || !this.isPlayer()) return;
    const target = this.findAdjacentDownedAlly();
    if (!target) return;
    try {
      const { session } = await actInSession(this.sessionId, "stabilize", { target_id: target.id });
      this.update(session);
      if (session.phase === "dm" && !this.isCampaignSession()) {
        setTimeout(() => this.runDmTurn(), 600);
      }
    } catch (err) {
      this.log(err.message || "Stabilize failed.");
    }
  }
  async rest() {
    if (!this.session || this.session.status !== "active") return;
    try {
      const { session } = await restInSession(this.sessionId);
      this.update(session);
    } catch (err) {
      this.log(err.message || "Rest failed.");
    }
  }
  async saveProgression() {
    if (!this.session) return;
    try {
      this.saveBtn.disabled = true;
      this.saveBtn.textContent = "Saving...";
      await saveProgress(this.sessionId);
      this.saveBtn.textContent = "Saved";
      window.setTimeout(() => {
        this.saveBtn.textContent = "Save Progress";
        this.saveBtn.disabled = false;
      }, 1500);
    } catch (err) {
      this.saveBtn.textContent = "Save Failed";
      this.log(err.message || "Save progress failed.");
      window.setTimeout(() => {
        this.saveBtn.textContent = "Save Progress";
        this.saveBtn.disabled = false;
      }, 1500);
    }
  }
  async leaveSession() {
    if (this.session && this.session.status !== "won") {
      await this.saveProgression();
    }
    this.onExit();
  }
  async journeyOn() {
    if (!this.session || this.session.status !== "won" || !this.isCampaignSession()) return;
    try {
      const { session } = await advanceSession(this.sessionId);
      const { module } = await getModule(session.module_id);
      this.module = module.map;
      this.visited.clear();
      this.renderMap();
      this.update(session);
      const overlay = this.root.querySelector(".game-over-overlay");
      overlay?.remove();
    } catch (err) {
      this.log(err.message || "Journey on failed.");
    }
  }
  findAdjacentDownedAlly() {
    if (!this.session) return null;
    const player = this.session.player;
    for (const p of this.session.players) {
      if (p.id === player.id || !p.down) continue;
      const dist = Math.abs(player.x - p.x) + Math.abs(player.y - p.y);
      if (dist === 1) return p;
    }
    return null;
  }
  async runDmTurn() {
    try {
      const { session } = await actInSession(this.sessionId, "dm_turn");
      this.update(session);
    } catch (err) {
      this.log(err.message || "DM turn failed.");
    }
  }
  renderMap() {
    clear(this.mapContainer);
    this.tileSprites = [];
    const themeId = this.module.theme ?? "";
    const theme = getTheme(themeId);
    const mapW = this.module.width * TILE_SIZE;
    const mapH = this.module.height * TILE_SIZE;
    this.mapContainer.style.width = `${mapW}px`;
    this.mapContainer.style.height = `${mapH}px`;
    this.mapContainer.style.gridTemplateColumns = `repeat(${this.module.width}, ${TILE_SIZE}px)`;
    this.mapContainer.style.gridTemplateRows = `repeat(${this.module.height}, ${TILE_SIZE}px)`;
    this.tokenContainer.style.width = `${mapW}px`;
    this.tokenContainer.style.height = `${mapH}px`;
    this.fxContainer.style.width = `${mapW}px`;
    this.fxContainer.style.height = `${mapH}px`;
    for (let y = 0; y < this.module.height; y++) {
      const row = this.module.tiles[y] || "";
      const tileRow = [];
      for (let x = 0; x < this.module.width; x++) {
        const tile = row[x] || "0";
        const url2 = theme ? tileFrame(themeId, theme, tile) : null;
        const kind = tile === "1" ? "wall" : tile === "2" ? "trap" : "floor";
        const tileEl = el("div", {
          className: `game-tile tile-${kind}`,
          style: url2 ? `background-image:url('${url2}')` : void 0,
          onclick: () => this.onTileClick(x, y)
        });
        this.mapContainer.appendChild(tileEl);
        tileRow.push(tileEl);
      }
      this.tileSprites.push(tileRow);
    }
    this.centerMap();
  }
  hasLineOfSight(x0, y0, x1, y1) {
    let dx = Math.abs(x1 - x0);
    let dy = Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1;
    const sy = y0 < y1 ? 1 : -1;
    let err = dx - dy;
    let x = x0;
    let y = y0;
    while (x !== x1 || y !== y1) {
      const e2 = 2 * err;
      if (e2 > -dy) {
        err -= dy;
        x += sx;
      }
      if (e2 < dx) {
        err += dx;
        y += sy;
      }
      if (x !== x0 || y !== y0) {
        const row = this.module.tiles[y] || "";
        if (row[x] === "1") return false;
      }
    }
    return true;
  }
  highlightActionTiles() {
    if (!this.session) return;
    const player = this.session.player;
    for (let y = 0; y < this.module.height; y++) {
      const row = this.module.tiles[y] || "";
      for (let x = 0; x < this.module.width; x++) {
        const g = this.tileSprites[y]?.[x];
        if (!g) continue;
        const tile = row[x] || "0";
        g.classList.remove("tile-highlight-move", "tile-highlight-range");
        if (this.action === "move" && tile !== "1") {
          const dist = Math.abs(x - player.x) + Math.abs(y - player.y);
          if (dist === 1) g.classList.add("tile-highlight-move");
        }
        if (this.action === "ranged" && tile !== "1") {
          const dist = Math.abs(x - player.x) + Math.abs(y - player.y);
          if (dist > 0 && dist <= RANGED_RANGE2 && this.hasLineOfSight(player.x, player.y, x, y)) {
            g.classList.add("tile-highlight-range");
          }
        }
        if (this.action === "ability" && tile !== "1") {
          const dist = Math.abs(x - player.x) + Math.abs(y - player.y);
          const cls = (player.classes?.[0] ?? "").toLowerCase();
          const abilityRange = cls === "magic-user" || cls === "illusionist" ? 6 : cls === "cleric" ? 4 : 1;
          if (dist > 0 && dist <= abilityRange && this.hasLineOfSight(player.x, player.y, x, y)) {
            g.classList.add("tile-highlight-range");
          }
        }
      }
    }
  }
  updateLighting() {
    if (!this.session || this.tileSprites.length === 0) return;
    const px = this.session.player.x;
    const py = this.session.player.y;
    for (let y = 0; y < this.module.height; y++) {
      const row = this.module.tiles[y] || "";
      for (let x = 0; x < this.module.width; x++) {
        const tile = row[x] || "0";
        const dist = Math.sqrt((x - px) ** 2 + (y - py) ** 2);
        const inRadius = dist <= VISION_RADIUS + 1;
        const hasLos = inRadius && this.hasLineOfSight(px, py, x, y);
        const key = `${x},${y}`;
        let alpha;
        if (hasLos) {
          this.visited.add(key);
          if (dist <= VISION_RADIUS - 1) {
            alpha = 1;
          } else {
            const t = (dist - (VISION_RADIUS - 1)) / 2;
            const isWall = tile === "1";
            alpha = 1 - t * (1 - (isWall ? 0.22 : 0.1));
          }
        } else if (this.visited.has(key)) {
          alpha = 0.35;
        } else {
          alpha = 0;
        }
        const el2 = this.tileSprites[y][x];
        el2.style.opacity = String(alpha);
        el2.classList.toggle("tile-hidden", alpha === 0);
      }
    }
  }
  centerMap() {
    const target = this.playerPixelCenter();
    const mw = this.module.width * TILE_SIZE;
    const mh = this.module.height * TILE_SIZE;
    const cw = this.canvasContainer.clientWidth;
    const ch = this.canvasContainer.clientHeight;
    let baseX;
    let baseY;
    if (mw <= cw && mh <= ch) {
      baseX = (cw - mw) / 2;
      baseY = (ch - mh) / 2;
    } else {
      const px = target ? target.x : mw / 2;
      const py = target ? target.y : mh / 2;
      baseX = cw / 2 - px;
      baseY = ch / 2 - py;
      baseX = Math.min(0, Math.max(cw - mw, baseX));
      baseY = Math.min(0, Math.max(ch - mh, baseY));
    }
    this.cameraX = baseX;
    this.cameraY = baseY;
    this.applyMapPosition();
  }
  playerPixelCenter() {
    if (!this.session) return null;
    return {
      x: this.session.player.x * TILE_SIZE + TILE_SIZE / 2,
      y: this.session.player.y * TILE_SIZE + TILE_SIZE / 2
    };
  }
  applyMapPosition() {
    let ox = 0;
    let oy = 0;
    if (this.shakeFrames > 0) {
      const intensity = Math.min(this.shakeFrames, 8);
      ox = (Math.random() - 0.5) * intensity;
      oy = (Math.random() - 0.5) * intensity;
    }
    const transform = `translate(${this.cameraX + ox}px, ${this.cameraY + oy}px)`;
    this.mapContainer.style.transform = transform;
    this.tokenContainer.style.transform = transform;
    this.fxContainer.style.transform = transform;
  }
  shake(frames) {
    this.shakeFrames = frames;
    const step = () => {
      if (this.shakeFrames <= 0) {
        this.shakeFrames = 0;
        this.applyMapPosition();
        return;
      }
      this.applyMapPosition();
      this.shakeFrames -= 1;
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  renderTokens(_snap = false) {
    if (!this.session) return;
    const session = this.session;
    const tokens = [...session.players, ...session.monsters];
    const activeId = session.phase === "player" ? session.player?.id : null;
    clear(this.tokenContainer);
    tokens.forEach((t) => {
      if (t.alive === false) return;
      const isPlayer = t.type === "player";
      const isVisible = isPlayer || this.isDm() || this.visited.has(`${t.x},${t.y}`);
      if (!isVisible) return;
      const isActive = t.id === activeId;
      const x = t.x * TILE_SIZE;
      const y = t.y * TILE_SIZE;
      const tokenEl = el("div", {
        className: `game-token ${isPlayer ? "player" : "monster"}${isActive ? " active" : ""}${t.down ? " down" : ""}`,
        style: `left:${x}px;top:${y}px;`,
        onclick: () => this.onTokenClick(t),
        onmouseenter: (e) => this.showTooltip(t, e.clientX, e.clientY),
        onmousemove: (e) => this.moveTooltip(e.clientX, e.clientY),
        onmouseleave: () => this.hideTooltip()
      });
      const backing = el("div", { className: "token-backing" });
      tokenEl.appendChild(backing);
      const tokenKey = isPlayer ? t.classes?.[0] ?? "hero" : t.monster ?? "";
      const tokenUrl = tokenFrame(tokenKey);
      if (tokenUrl) {
        const img = el("img", {
          className: "token-image",
          src: tokenUrl,
          alt: t.name,
          onerror: () => {
            img.style.display = "none";
          }
        });
        tokenEl.appendChild(img);
      } else {
        const initial = (t.name || "?").charAt(0).toUpperCase();
        tokenEl.appendChild(el("div", { className: "token-initial" }, initial));
      }
      const hpRatio = Math.max(0, Math.min(1, t.hp / t.max_hp));
      const bar = el("div", { className: "token-hp-bar" });
      const fill = el("div", { className: "token-hp-fill" });
      fill.style.width = `${Math.round(hpRatio * 100)}%`;
      fill.classList.add(hpRatio > 0.5 ? "high" : hpRatio > 0.25 ? "medium" : "low");
      bar.appendChild(fill);
      tokenEl.appendChild(bar);
      this.tokenContainer.appendChild(tokenEl);
    });
    this.lastTokenHp.clear();
    for (const t of tokens) {
      if (t.alive !== false) this.lastTokenHp.set(t.id, t.hp);
    }
  }
  spawnSlashEffect(fromX, fromY, toX, toY) {
    const cx = (fromX + toX) / 2 * TILE_SIZE + TILE_SIZE / 2;
    const cy = (fromY + toY) / 2 * TILE_SIZE + TILE_SIZE / 2;
    const slash = el("div", { className: "slash-effect" });
    slash.style.left = `${cx - TILE_SIZE / 2}px`;
    slash.style.top = `${cy - TILE_SIZE / 2}px`;
    this.fxContainer.appendChild(slash);
    window.setTimeout(() => slash.remove(), 350);
  }
  async onTileClick(x, y) {
    if (!this.session || this.session.status !== "active") return;
    if (this.dmAction && this.isDm()) {
      try {
        let response;
        if (this.dmAction === "spawn") {
          const name = this.dmMonsterSelect.value || "goblin";
          response = await dmSpawn(this.sessionId, { name, x, y });
        } else if (this.dmAction === "move") {
          const tokenId = this.dmTokenSelect.value;
          if (!tokenId) return;
          response = await dmMove(this.sessionId, { token_id: tokenId, x, y });
        } else if (this.dmAction === "reveal") {
          response = await dmReveal(this.sessionId, { x, y, radius: 4 });
        }
        if (response) {
          this.dmAction = null;
          this.update(response.session);
        }
      } catch (err) {
        this.log(err.message || "DM action failed.");
      }
      return;
    }
    if (this.session.phase !== "player") return;
    if (this.action && this.action !== "move") return;
    const player = this.session.player;
    const dist = Math.abs(x - player.x) + Math.abs(y - player.y);
    if (dist !== 1) return;
    try {
      const { session } = await actInSession(this.sessionId, "move", { x, y });
      this.action = null;
      this.update(session);
    } catch (err) {
      this.log(err.message || "Move failed.");
    }
  }
  async onTokenClick(token) {
    if (!this.session || this.session.phase !== "player") return;
    if (token.type !== "monster") return;
    const player = this.session.player;
    const dist = Math.abs(player.x - token.x) + Math.abs(player.y - token.y);
    if (!this.action) {
      if (dist === 1) {
        this.action = "attack";
      } else if (dist <= RANGED_RANGE2 && this.hasLineOfSight(player.x, player.y, token.x, token.y)) {
        this.action = "ranged";
      }
    }
    if (this.action === "attack") {
      if (token.type !== "monster") return;
      const player2 = this.session.player;
      const isAdjacent = Math.abs(player2.x - token.x) + Math.abs(player2.y - token.y) === 1;
      this.audio.swordHit();
      this.audio.combatSting();
      try {
        const { session } = await actInSession(this.sessionId, "attack", { target_id: token.id });
        this.action = null;
        if (isAdjacent) {
          this.spawnSlashEffect(player2.x, player2.y, token.x, token.y);
        }
        this.update(session);
        if (session.phase === "dm") {
          setTimeout(() => this.runDmTurn(), 600);
        }
      } catch (err) {
        this.log(err.message || "Attack failed.");
      }
    } else if (this.action === "ranged") {
      if (token.type !== "monster") return;
      const player2 = this.session.player;
      this.audio.rangedShot();
      this.audio.combatSting();
      try {
        const { session } = await actInSession(this.sessionId, "ranged", { target_id: token.id });
        this.action = null;
        this.spawnSlashEffect(player2.x, player2.y, token.x, token.y);
        this.update(session);
        if (session.phase === "dm") {
          setTimeout(() => this.runDmTurn(), 600);
        }
      } catch (err) {
        this.log(err.message || "Ranged attack failed.");
      }
    } else if (this.action === "ability") {
      if (token.type !== "monster") return;
      const player2 = this.session.player;
      const cls = (player2.classes?.[0] ?? "").toLowerCase();
      const rangedAbility = cls === "magic-user" || cls === "illusionist" || cls === "cleric";
      if (rangedAbility) {
        this.audio.rangedShot();
      } else {
        this.audio.swordHit();
      }
      this.audio.combatSting();
      try {
        const { session } = await actInSession(this.sessionId, "ability", { target_id: token.id });
        this.action = null;
        this.spawnSlashEffect(player2.x, player2.y, token.x, token.y);
        this.update(session);
        if (session.phase === "dm") {
          setTimeout(() => this.runDmTurn(), 600);
        }
      } catch (err) {
        this.log(err.message || "Ability failed.");
      }
    }
  }
  update(session) {
    const prevSession = this.session;
    const wasDm = prevSession?.phase === "dm";
    const playerHurt = prevSession ? session.player.hp < prevSession.player.hp : false;
    const prevStatus = prevSession?.status;
    const prevPlayerPos = prevSession ? `${prevSession.player.x},${prevSession.player.y}` : "";
    this.session = session;
    const canAutoplay = !this.isCampaignSession() && session.status === "active";
    this.autoplayBtn.style.display = canAutoplay ? "inline-block" : "none";
    this.autoPlayer.onUpdate();
    session.dm_revealed?.forEach((key) => this.visited.add(key));
    if (!prevSession) {
      if (session.mode === "arena") {
        this.audio.combatSting();
      } else {
        this.audio.exploration();
      }
    }
    if (this.chatPanel) {
      this.chatPanel.style.display = this.isCampaignSession() ? "flex" : "none";
    }
    this.updateDmTools();
    this.updateJournal();
    this.renderTokens();
    this.updateLighting();
    this.highlightActionTiles();
    this.centerMap();
    this.updateStatus();
    this.updateActions();
    this.updateStats();
    this.updatePartyRoster();
    this.updateRoster();
    this.updateTimer();
    this.renderLog();
    if (prevStatus === "active" && session.status === "won") {
      this.audio.victory();
    } else if (prevStatus === "active" && session.status === "lost") {
      this.audio.defeat();
    }
    if (prevPlayerPos && prevPlayerPos !== `${session.player.x},${session.player.y}`) {
      this.audio.footstep();
    }
    if (session.status === "active" && session.phase === "player" && session.turn !== this.lastBannerTurn) {
      this.showTurnBanner(session.turn);
      this.lastBannerTurn = session.turn;
    }
    if (wasDm && session.phase === "player" && playerHurt) {
      this.spawnMonsterAttackSlash();
      this.triggerDamageFlash();
    }
  }
  triggerDamageFlash() {
    this.damageFlash.classList.remove("active");
    void this.damageFlash.offsetWidth;
    this.damageFlash.classList.add("active");
    window.setTimeout(() => this.damageFlash.classList.remove("active"), 350);
  }
  showTurnBanner(turn) {
    const existing = this.root.querySelector(".turn-banner");
    if (existing) existing.remove();
    const banner = el("div", { className: "turn-banner" });
    banner.innerHTML = `<span>Turn ${turn}</span>`;
    this.root.appendChild(banner);
    window.setTimeout(() => banner.classList.add("visible"), 10);
    window.setTimeout(() => {
      banner.classList.remove("visible");
      window.setTimeout(() => banner.remove(), 600);
    }, 1400);
  }
  updateStats() {
    if (!this.session) return;
    const p = this.session.player;
    const ratio = Math.max(0, Math.min(1, p.hp / p.max_hp));
    const hpColor = ratio > 0.5 ? "#2ecc71" : ratio > 0.25 ? "#f1c40f" : "#c0392b";
    this.statEl.innerHTML = `
      <div class="player-name">${p.name}</div>
      <div class="player-class">${(p.classes || ["Adventurer"]).join(" / ")}</div>
      <div class="hp-bar"><span style="width:${Math.round(ratio * 100)}%; background:${hpColor};"></span></div>
      <div class="hp-text">HP ${p.hp}/${p.max_hp}</div>
      <div class="ac-text">AC ${p.ac}</div>
      <div class="progression-text">Level ${p.level ?? 1} \xB7 XP ${p.xp ?? 0} \xB7 Gold ${p.gold ?? 0}</div>
    `;
    this.root.classList.toggle("low-hp", ratio <= 0.25 && p.hp > 0);
  }
  setUnitsTab(tab, partyBtn, foesBtn) {
    partyBtn.classList.toggle("active", tab === "party");
    foesBtn.classList.toggle("active", tab === "foes");
    this.partyEl.style.display = tab === "party" ? "block" : "none";
    this.rosterEl.style.display = tab === "foes" ? "block" : "none";
  }
  updatePartyRoster() {
    if (!this.session) return;
    clear(this.partyEl);
    const activeId = this.session.phase === "player" ? this.session.player?.id : null;
    this.session.players.forEach((p) => {
      const isActive = p.id === activeId;
      const ratio = Math.max(0, Math.min(1, p.hp / p.max_hp));
      const hpColor = ratio > 0.5 ? "#2ecc71" : ratio > 0.25 ? "#f1c40f" : "#c0392b";
      const row = el("div", { className: `party-row${isActive ? " active" : ""}` });
      const portraitUrl = this.fallbackPortraitUrl(p.classes?.[0] ?? "");
      const portrait = el("img", {
        className: "party-portrait",
        src: portraitUrl,
        alt: p.name,
        onerror: () => {
          portrait.src = this.fallbackPortraitUrl();
        }
      });
      row.appendChild(portrait);
      row.appendChild(el("span", { className: "party-name" }, p.name));
      const barWrap = el("div", { className: "party-hp-bar" });
      barWrap.innerHTML = `<span style="width:${Math.round(ratio * 100)}%; background:${hpColor};"></span>`;
      row.appendChild(barWrap);
      row.appendChild(el("span", { className: "party-hp-text" }, `${p.hp}/${p.max_hp}`));
      const statusText = (p.statuses || []).map((s) => `${s.type}${s.duration ? ` ${s.duration}t` : ""}`).join(", ");
      if (statusText || p.down) {
        const statusEl = el("span", { className: "party-status" });
        statusEl.textContent = [p.down ? "DOWN" : "", statusText].filter(Boolean).join(" \xB7 ");
        row.appendChild(statusEl);
      }
      row.appendChild(el("span", { className: "party-progression" }, `Lv${p.level ?? 1} \xB7 XP ${p.xp ?? 0} \xB7 G ${p.gold ?? 0}`));
      this.partyEl.appendChild(row);
    });
  }
  fallbackPortraitUrl(className) {
    const key = (className || "generic").toLowerCase().replace(/\s+/g, "-");
    return `/portraits/${key}.png`;
  }
  updateRoster() {
    if (!this.session) return;
    clear(this.rosterEl);
    const alive = this.session.monsters.filter((m) => m.alive !== false);
    if (alive.length === 0) {
      this.rosterEl.appendChild(el("div", { className: "empty-roster" }, "None remain."));
      return;
    }
    alive.forEach((m) => {
      const ratio = Math.max(0, Math.min(1, m.hp / m.max_hp));
      const hpColor = ratio > 0.5 ? "#2ecc71" : ratio > 0.25 ? "#f1c40f" : "#c0392b";
      const row = el("div", { className: "monster-row" });
      row.appendChild(el("span", { className: "monster-name" }, m.name));
      const barWrap = el("div", { className: "monster-hp-bar" });
      barWrap.innerHTML = `<span style="width:${Math.round(ratio * 100)}%; background:${hpColor};"></span>`;
      row.appendChild(barWrap);
      this.rosterEl.appendChild(row);
    });
  }
  spawnMonsterAttackSlash() {
    if (!this.session) return;
    const player = this.session.player;
    let attacker = null;
    let bestDist = Infinity;
    for (const m of this.session.monsters) {
      if (m.alive === false) continue;
      const dist = Math.abs(m.x - player.x) + Math.abs(m.y - player.y);
      if (dist <= 1 && dist < bestDist) {
        attacker = m;
        bestDist = dist;
      }
    }
    if (attacker) {
      this.spawnSlashEffect(attacker.x, attacker.y, player.x, player.y);
      this.shake(12);
    }
  }
  updateActions() {
    const player = this.session?.player;
    const isActiveUser = !!this.session && this.session.status === "active" && this.session.phase === "player" && (player && "account_id" in player && player.account_id != null && player.account_id === this.userId || (!this.session.campaign_id || this.session.account_id === this.userId));
    const canAct = isActiveUser && !player?.down;
    const hasPotion = !!player && (player.inventory || []).some((i) => i.slot === "consumable" || i.type === "potion");
    const isSessionPlayer = !!this.session && this.session.status === "active" && (this.session.players.some((p) => p.account_id === this.userId) || !this.session.campaign_id && this.session.account_id === this.userId);
    this.moveBtn.disabled = !canAct;
    this.attackBtn.disabled = !canAct;
    this.rangedBtn.disabled = !canAct;
    this.potionBtn.disabled = !canAct || !hasPotion;
    this.abilityBtn.disabled = !canAct;
    this.endBtn.disabled = !isActiveUser;
    const canStabilize = canAct && !!this.findAdjacentDownedAlly();
    this.stabilizeBtn.style.display = canStabilize ? "inline-block" : "none";
    this.restBtn.disabled = !isSessionPlayer;
  }
  updateStatus() {
    if (!this.session) return;
    const isDmPhase = this.session.phase === "dm";
    const isCampaign = this.isCampaignSession();
    let phaseText = this.session.phase === "player" ? "Your Move" : "DM's Move";
    if (isCampaign && isDmPhase && this.isDm()) {
      phaseText = "DM's Move \xB7 Run Turn";
    } else if (isCampaign && isDmPhase) {
      phaseText = "Waiting for DM";
    }
    const actionText = this.action ? ` \xB7 ${this.action} mode` : "";
    const dmActionText = this.dmAction ? ` \xB7 DM: ${this.dmAction}` : "";
    this.statusEl.textContent = `Turn ${this.session.turn} \xB7 ${phaseText}${actionText}${dmActionText}`;
    const showDmBtn = this.session.status === "active" && isDmPhase && isCampaign && this.isDm();
    this.dmTurnBtn.style.display = showDmBtn ? "block" : "none";
    this.dmOverlay.style.display = this.session.status === "active" && isDmPhase ? "flex" : "none";
    if (this.session.status !== "active") {
      this.statusEl.textContent = `Game ${this.session.status.toUpperCase()}`;
      this.dmOverlay.style.display = "none";
      this.dmTurnBtn.style.display = "none";
      this.showGameOver();
    }
  }
  updateTimer() {
    if (this.timerInterval) {
      window.clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
    if (!this.session || this.session.status !== "active" || this.session.phase !== "player" || this.session.turn_timer_seconds <= 0 || !this.session.turn_deadline) {
      this.timerEl.textContent = "";
      return;
    }
    const tick = () => {
      const deadline = new Date(this.session.turn_deadline).getTime();
      const remaining = Math.ceil((deadline - Date.now()) / 1e3);
      if (remaining <= 0) {
        this.timerEl.textContent = "Time up!";
        if (!this.timeoutFired) {
          this.timeoutFired = true;
          this.endTurn();
        }
      } else {
        this.timeoutFired = false;
        const mins = Math.floor(remaining / 60);
        const secs = remaining % 60;
        this.timerEl.textContent = `${mins}:${secs.toString().padStart(2, "0")} remaining`;
      }
    };
    tick();
    this.timerInterval = window.setInterval(tick, 250);
  }
  renderLog() {
    if (!this.session) return;
    const log = this.session.log;
    if (log.length > this.lastLogLength) {
      const newCount = log.length - this.lastLogLength;
      for (let i = log.length - newCount; i < log.length; i++) {
        const entry = log[i];
        const isTurn = entry.startsWith("\u2014 Turn");
        const className = isTurn ? "log-entry turn-marker" : "log-entry fresh";
        const row = el("div", { className }, entry);
        this.logEl.appendChild(row);
        if (!isTurn) {
          window.setTimeout(() => row.classList.remove("fresh"), 600);
        }
      }
      while (this.logEl.childElementCount > 20) {
        this.logEl.firstElementChild?.remove();
      }
      const newEntries = log.slice(this.lastLogLength);
      const combatKeywords = ["strike", "blow", "hit", "miss", "pain", "weapon", "crumple", "fall", "dies", "bites", "stinging"];
      if (newEntries.some((e) => combatKeywords.some((k) => e.toLowerCase().includes(k)))) {
        this.shake(12);
      }
      if (newEntries.some((e) => e.toLowerCase().includes("trap") || e.toLowerCase().includes("spike"))) {
        this.audio.trapTrigger();
        this.shake(20);
        this.triggerDamageFlash();
      }
      this.lastLogLength = log.length;
    } else if (this.logEl.childElementCount === 0) {
      log.slice(-20).forEach((entry) => {
        const isTurn = entry.startsWith("\u2014 Turn");
        const className = isTurn ? "log-entry turn-marker" : "log-entry";
        this.logEl.appendChild(el("div", { className }, entry));
      });
      this.lastLogLength = log.length;
    }
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }
  log(message) {
    this.logEl.appendChild(el("div", { className: "log-entry error" }, message));
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }
  destroy() {
    if (this.timerInterval) {
      window.clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
    if (this.heartbeatInterval) {
      window.clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    if (this.keydownHandler) {
      window.removeEventListener("keydown", this.keydownHandler);
      this.keydownHandler = null;
    }
    if (this.beforeUnloadHandler) {
      window.removeEventListener("beforeunload", this.beforeUnloadHandler);
      this.beforeUnloadHandler = null;
    }
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
    clear(this.root);
  }
};

// src/ui/hub.ts
var THEME_LABELS2 = {
  dungeon: "Dungeon",
  cave: "Cave",
  library: "Library",
  ice: "Frozen",
  lava: "Volcanic",
  forest: "Forest",
  tomb: "Tomb",
  sewer: "Sewer"
};
var Hub = class {
  root;
  onSolo;
  onJoin;
  onCampaigns;
  onResume;
  container;
  modules = [];
  progressEl;
  constructor(container, onSolo, onJoin, onCampaigns, onResume, onCreateAdventure, onDmWorkshop) {
    this.root = el("div", { className: "sanctuary-hub" });
    this.onSolo = onSolo;
    this.onJoin = onJoin;
    this.onCampaigns = onCampaigns;
    this.onResume = onResume;
    this.onCreateAdventure = onCreateAdventure;
    this.onDmWorkshop = onDmWorkshop;
    const background = el("div", { className: "hub-background" });
    const vignette = el("div", { className: "hub-vignette" });
    const particles = el("div", { className: "hub-particles" });
    for (let i = 0; i < 32; i++) {
      const p = el("span", { className: "hub-particle" });
      p.style.left = `${Math.random() * 100}%`;
      p.style.top = `${Math.random() * 100}%`;
      p.style.animationDelay = `${Math.random() * 6}s`;
      p.style.animationDuration = `${4 + Math.random() * 4}s`;
      particles.appendChild(p);
    }
    this.container = el("div", { className: "hub-container" });
    this.progressEl = el("div", { className: "hub-progress" });
    this.container.appendChild(this.progressEl);
    this.renderHeader();
    this.renderActions();
    this.renderRoom();
    this.root.appendChild(background);
    this.root.appendChild(vignette);
    this.root.appendChild(particles);
    this.root.appendChild(this.container);
    container.appendChild(this.root);
    this.loadData();
  }
  renderHeader() {
    const header = el("header", { className: "hub-header" });
    const badge = el("span", { className: "hub-badge" }, "Tenshin Arts");
    const title = el("h1", {}, "Sanctuary");
    const subtitle = el("p", {}, "Choose your path into the dark.");
    header.appendChild(badge);
    header.appendChild(title);
    header.appendChild(subtitle);
    this.container.appendChild(header);
  }
  renderActions() {
    const grid = el("div", { className: "hub-actions" });
    const solo = this.buildCard(
      "solo",
      "Solo Adventure",
      "Forge a hero and delve into any room alone. Your torch, your choices, your fate.",
      "Begin Solo",
      () => this.onSolo()
    );
    const create = this.buildCard(
      "create",
      "Create Adventure",
      "Start a solo or co-op room with your hero, then invite friends or keep it private.",
      "Create Adventure",
      () => this.onCreateAdventure()
    );
    const join = this.buildCard(
      "join",
      "Join Adventure",
      "Resume a saved session or join an active adventure already in progress with friends.",
      "Join / Resume",
      () => this.onJoin()
    );
    const group = this.buildCard(
      "group",
      "Create Group Adventure",
      "Start a campaign, invite friends, and lead or follow as DM with AI assistance.",
      "Create Campaign",
      () => this.onCampaigns()
    );
    const dm = this.buildCard(
      "dm",
      "DM Workshop",
      "Build rooms, link them into adventures, place monsters and treasure, then play-test or publish.",
      "Open Workshop",
      () => this.onDmWorkshop()
    );
    grid.appendChild(solo);
    grid.appendChild(create);
    grid.appendChild(join);
    grid.appendChild(group);
    grid.appendChild(dm);
    this.container.appendChild(grid);
    this.loadResumeHint();
  }
  buildCard(kind, title, desc, action, onClick) {
    const card = el("div", { className: `hub-card hub-card-${kind}` });
    const icon = el("div", { className: "hub-card-icon" });
    const body = el("div", { className: "hub-card-body" });
    const h2 = el("h2", {}, title);
    const p = el("p", {}, desc);
    const btn = el("button", { onclick: onClick }, action);
    body.appendChild(h2);
    body.appendChild(p);
    body.appendChild(btn);
    card.appendChild(icon);
    card.appendChild(body);
    return card;
  }
  async loadResumeHint() {
    try {
      const [{ sessions }, { campaigns }] = await Promise.all([listSessions(), listCampaigns()]);
      const activeSessions = sessions.filter((s) => s.status === "active");
      if (activeSessions.length === 0 && campaigns.length === 0) return;
      const hint = el("div", { className: "hub-resume-hint" });
      const parts2 = [];
      if (activeSessions.length > 0) parts2.push(`${activeSessions.length} active adventure${activeSessions.length > 1 ? "s" : ""}`);
      if (campaigns.length > 0) parts2.push(`${campaigns.length} campaign${campaigns.length > 1 ? "s" : ""}`);
      hint.textContent = `You have ${parts2.join(" and ")} waiting. `;
      const link = el("button", { className: "hub-resume-link", onclick: () => this.onResume() }, "Resume now");
      hint.appendChild(link);
      this.container.appendChild(hint);
    } catch {
    }
  }
  async loadData() {
    try {
      const [{ modules }, progress] = await Promise.all([
        listModules(),
        getAccountProgress().catch(() => null)
      ]);
      this.modules = modules;
      this.renderProgress(progress);
      this.renderRoom();
    } catch {
    }
  }
  renderProgress(progress) {
    clear(this.progressEl);
    if (!progress) {
      this.progressEl.style.display = "none";
      return;
    }
    this.progressEl.style.display = "flex";
    const stats = [
      ["Wins", progress.wins ?? 0],
      ["Losses", progress.losses ?? 0],
      ["Boss Kills", progress.boss_kills ?? 0],
      ["Cleared", progress.modules_cleared ?? 0],
      ["Deaths", progress.deaths ?? 0],
      ["Level Ups", progress.level_ups ?? 0]
    ];
    stats.forEach(([label, value2]) => {
      this.progressEl.appendChild(el("span", {}, `${label} ${value2}`));
    });
  }
  renderRoom() {
    const existing = this.container.querySelector(".hub-room");
    if (existing) existing.remove();
    const room = el("div", { className: "hub-room" });
    const header = el("div", { className: "hub-room-header" });
    header.appendChild(el("h3", {}, "Rooms"));
    header.appendChild(el("span", { className: "hub-room-count" }, `${this.modules.length} available`));
    room.appendChild(header);
    if (this.modules.length === 0) {
      room.appendChild(el("p", { className: "hub-room-empty" }, "Loading rooms..."));
    } else {
      const scroll = el("div", { className: "hub-room-scroll" });
      this.modules.forEach((m) => {
        const chip = el("div", { className: "hub-room-chip" });
        const preview = this.buildMiniMap(m);
        if (preview) chip.appendChild(preview);
        const meta = el("div", { className: "hub-room-meta" });
        const theme = m.theme || "dungeon";
        meta.appendChild(el("span", { className: `hub-room-theme theme-${theme}` }, THEME_LABELS2[theme] || theme));
        meta.appendChild(el("strong", {}, m.name));
        meta.appendChild(el("span", { className: "hub-room-size" }, `${m.width}\xD7${m.height}`));
        chip.appendChild(meta);
        scroll.appendChild(chip);
      });
      room.appendChild(scroll);
    }
    this.container.appendChild(room);
  }
  buildMiniMap(m) {
    if (!m.tiles || m.tiles.length === 0) return null;
    const wrap = el("div", { className: "hub-room-map" });
    const maxRows = Math.min(m.height, 12);
    const maxCols = Math.min(m.width, 18);
    wrap.style.gridTemplateRows = `repeat(${maxRows}, 1fr)`;
    wrap.style.gridTemplateColumns = `repeat(${maxCols}, 1fr)`;
    for (let y = 0; y < maxRows; y++) {
      const row = m.tiles[y] || "";
      for (let x = 0; x < maxCols; x++) {
        const tile = row[x] || "0";
        const cell = el("span", { className: `mini-tile mini-tile-${tile === "1" ? "wall" : tile === "2" ? "trap" : "floor"}` });
        wrap.appendChild(cell);
      }
    }
    return wrap;
  }
  destroy() {
    this.root.remove();
  }
};

// src/ui/session-select.ts
var SessionSelect = class {
  root;
  onResume;
  onJoin;
  onNew;
  onBack;
  gridEl;
  tabContent;
  activeTab = "yours";
  characters = [];
  constructor(container, onResume, onJoin, onNew, onBack) {
    this.root = el("div", { className: "adventure-manager" });
    this.onResume = onResume;
    this.onJoin = onJoin;
    this.onNew = onNew;
    this.onBack = onBack;
    const background = el("div", { className: "adventure-manager-background" });
    const vignette = el("div", { className: "adventure-manager-vignette" });
    const shell = el("div", { className: "adventure-manager-shell" });
    shell.appendChild(this.buildHeader());
    shell.appendChild(this.buildTabs());
    this.gridEl = el("div", { className: "sessions-grid" });
    shell.appendChild(this.gridEl);
    shell.appendChild(this.buildFooter());
    this.root.appendChild(background);
    this.root.appendChild(vignette);
    this.root.appendChild(shell);
    container.appendChild(this.root);
    this.loadCharacters();
    this.loadTab();
  }
  buildHeader() {
    const header = el("header", { className: "adventure-manager-header" });
    const title = el("div", { className: "adventure-manager-title" });
    title.appendChild(el("h1", {}, "Join Adventure"));
    title.appendChild(el("p", {}, "Resume yours, join a friend's, or enter an invite code."));
    header.appendChild(title);
    const actions = el("div", { className: "adventure-manager-actions" });
    actions.appendChild(el("button", { className: "adventure-manager-btn", onclick: () => this.onNew() }, "+ New Hero"));
    actions.appendChild(el("button", { className: "danger", onclick: () => this.onDeleteAll() }, "Delete All"));
    if (this.onBack) {
      actions.appendChild(el("button", { onclick: () => this.onBack() }, "\u2190 Back"));
    }
    header.appendChild(actions);
    return header;
  }
  async onDeleteAll() {
    if (!confirm("Delete ALL your saved adventures? This cannot be undone.")) return;
    try {
      await deleteAllSessions();
      this.loadTab();
    } catch (err) {
      clear(this.gridEl);
      this.gridEl.appendChild(el("div", { className: "sessions-empty error" }, err.message || "Failed to delete sessions."));
    }
  }
  buildTabs() {
    const tabs = el("div", { className: "session-tabs" });
    const items = [
      { key: "yours", label: "Your Adventures" },
      { key: "joinable", label: "Joinable" },
      { key: "code", label: "Join by Code" }
    ];
    items.forEach((item) => {
      const btn = el("button", {
        className: `session-tab${item.key === this.activeTab ? " active" : ""}`,
        onclick: () => this.switchTab(item.key)
      }, item.label);
      tabs.appendChild(btn);
    });
    return tabs;
  }
  switchTab(tab) {
    this.activeTab = tab;
    this.root.querySelectorAll(".session-tab").forEach((b) => {
      b.classList.toggle("active", b.textContent === (tab === "yours" ? "Your Adventures" : tab === "joinable" ? "Joinable" : "Join by Code"));
    });
    this.loadTab();
  }
  async loadCharacters() {
    try {
      const { characters } = await listCharacters();
      this.characters = characters;
    } catch {
      this.characters = [];
    }
  }
  async loadTab() {
    clear(this.gridEl);
    if (this.activeTab === "yours") {
      try {
        const { sessions } = await listSessions();
        this.renderYours(sessions);
      } catch (err) {
        this.gridEl.appendChild(el("div", { className: "sessions-empty error" }, err.message || "Failed to load sessions."));
      }
    } else if (this.activeTab === "joinable") {
      try {
        const { sessions } = await listJoinableSessions();
        this.renderJoinable(sessions);
      } catch (err) {
        this.gridEl.appendChild(el("div", { className: "sessions-empty error" }, err.message || "Failed to load adventures."));
      }
    } else if (this.activeTab === "code") {
      this.renderCodeForm();
    }
  }
  renderYours(sessions) {
    if (sessions.length === 0) {
      const empty2 = el("div", { className: "sessions-empty" });
      empty2.appendChild(el("h2", {}, "No saved adventures"));
      empty2.appendChild(el("p", {}, "Create a solo or co-op adventure from the Sanctuary hub."));
      this.gridEl.appendChild(empty2);
      return;
    }
    sessions.forEach((s) => this.renderSessionCard(s, true));
  }
  renderJoinable(sessions) {
    if (sessions.length === 0) {
      const empty2 = el("div", { className: "sessions-empty" });
      empty2.appendChild(el("h2", {}, "No adventures to join"));
      empty2.appendChild(el("p", {}, "No public or friend adventures are active right now."));
      this.gridEl.appendChild(empty2);
      return;
    }
    sessions.forEach((s) => this.renderSessionCard(s, false));
  }
  renderCodeForm() {
    const form = el("div", { className: "sessions-empty" });
    form.appendChild(el("h2", {}, "Join by Invite Code"));
    form.appendChild(el("p", {}, "Enter the code shared by the host."));
    const codeInput = el("input", { type: "text", placeholder: "ABC123", style: "text-transform: uppercase;" });
    const charSelect = el("select", {});
    if (this.characters.length === 0) {
      charSelect.appendChild(el("option", {}, "No heroes"));
      charSelect.disabled = true;
    } else {
      this.characters.forEach((c) => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.name;
        charSelect.appendChild(opt);
      });
    }
    const joinBtn = el("button", {
      className: "enter",
      disabled: this.characters.length === 0,
      onclick: async () => {
        const code = codeInput.value.trim().toUpperCase();
        if (!code) return;
        joinBtn.disabled = true;
        try {
          const { session } = await joinSessionByCode(code, charSelect.value);
          this.onJoin(session);
        } catch (err) {
          alert(err.message || "Failed to join adventure");
          joinBtn.disabled = false;
        }
      }
    }, "Join");
    form.appendChild(codeInput);
    form.appendChild(el("label", {}, "Hero"));
    form.appendChild(charSelect);
    form.appendChild(joinBtn);
    this.gridEl.appendChild(form);
  }
  renderSessionCard(s, isOwner) {
    const phaseText = s.phase === "player" ? "Your Move" : "DM's Move";
    const statusLabel = s.status === "active" ? "Active" : "Complete";
    const statusClass = s.status === "active" ? "active" : "complete";
    const card = el("div", { className: "session-card" });
    const header = el("div", { className: "session-card-header" });
    header.appendChild(el("span", { className: `session-status ${statusClass}` }, statusLabel));
    header.appendChild(el("span", { className: "session-turn" }, `Turn ${s.turn}`));
    card.appendChild(header);
    const body = el("div", { className: "session-card-body" });
    body.appendChild(el("h3", {}, s.name));
    body.appendChild(el("p", {}, `${phaseText} \xB7 ${s.module_id}${s.visibility ? ` \xB7 ${s.visibility}` : ""}`));
    if (s.invite_code) {
      body.appendChild(el("p", { className: "invite-code" }, `Code: ${s.invite_code}`));
    }
    card.appendChild(body);
    const actions = el("div", { className: "session-card-actions" });
    if (isOwner) {
      actions.appendChild(el("button", {
        className: "enter",
        onclick: () => this.resume(s.id)
      }, s.status === "active" ? "Resume" : "View"));
      actions.appendChild(el("button", {
        className: "danger",
        onclick: () => this.onDelete(s.id)
      }, "Delete"));
    } else {
      actions.appendChild(el("button", {
        className: "enter",
        onclick: () => this.joinById(s.id)
      }, "Join"));
    }
    card.appendChild(actions);
    this.gridEl.appendChild(card);
  }
  async onDelete(sessionId) {
    if (!confirm("Delete this adventure? This cannot be undone.")) return;
    try {
      await deleteSession(sessionId);
      this.loadTab();
    } catch (err) {
      clear(this.gridEl);
      this.gridEl.appendChild(el("div", { className: "sessions-empty error" }, err.message || "Failed to delete session."));
    }
  }
  async resume(sessionId) {
    try {
      const { session } = await getSession(sessionId);
      this.onResume(session);
    } catch (err) {
      clear(this.gridEl);
      this.gridEl.appendChild(el("div", { className: "sessions-empty error" }, err.message || "Failed to resume session."));
    }
  }
  async joinById(sessionId) {
    if (this.characters.length === 0) {
      alert("Create a hero first.");
      return;
    }
    const charSelect = el("select", {});
    this.characters.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = c.name;
      charSelect.appendChild(opt);
    });
    const charId = prompt("Join with which hero? (enter hero name)");
    if (!charId) return;
    const character = this.characters.find((c) => c.name.toLowerCase() === charId.toLowerCase());
    if (!character) {
      alert("Hero not found.");
      return;
    }
    try {
      const { session } = await api(`/api/sessions/${sessionId}/join`, {
        method: "POST",
        body: JSON.stringify({ character_id: character.id })
      });
      this.onJoin(session);
    } catch (err) {
      alert(err.message || "Failed to join adventure");
    }
  }
  buildFooter() {
    const footer = el("footer", { className: "adventure-manager-footer" });
    if (this.onBack) {
      footer.appendChild(el("button", { className: "adventure-manager-back", onclick: () => this.onBack() }, "\u2190 Back to Sanctuary"));
    }
    return footer;
  }
  destroy() {
    this.root.remove();
  }
};

// src/ui/app.ts
var SanctuaryApp = class {
  app;
  userId = null;
  current = null;
  constructor(app2) {
    this.app = app2;
  }
  async start() {
    try {
      const user = await whoami();
      this.userId = user.user.id ?? null;
      document.body.dataset.user = user.user.name || "player";
    } catch {
      return;
    }
    this.showHub();
  }
  setScreen(name) {
    document.body.dataset.screen = name;
  }
  showHub() {
    this.setScreen("hub");
    clear(this.app);
    this.current?.destroy();
    this.current = new Hub(
      this.app,
      () => this.showSelect(),
      () => this.showSessions(),
      () => this.showCampaigns(),
      () => this.showSessions(),
      () => this.showAdventureCreate(),
      () => this.showDmWorkshop()
    );
  }
  showAdventureCreate() {
    this.setScreen("adventure-create");
    clear(this.app);
    this.current?.destroy();
    this.current = new AdventureCreate(
      this.app,
      (session) => this.resumeGame(session),
      () => this.showHub()
    );
  }
  showSelect() {
    this.setScreen("select");
    clear(this.app);
    this.current?.destroy();
    this.current = new CharacterSelect(
      this.app,
      (character, timerSeconds, moduleId) => this.enterGame(character, void 0, timerSeconds, moduleId),
      () => this.showCreate(),
      () => this.showCampaigns(),
      () => this.showSessions(),
      () => this.showHub(),
      () => this.showDmWorkshop()
    );
  }
  showCreate() {
    this.setScreen("create");
    clear(this.app);
    this.current?.destroy();
    this.current = new CharacterCreator(this.app, (character) => {
      this.enterGame(character);
    });
  }
  showCampaigns() {
    this.setScreen("campaigns");
    clear(this.app);
    this.current?.destroy();
    this.current = new CampaignLobby(
      this.app,
      (campaign) => {
        this.showCampaignDetail(campaign);
      },
      () => this.showSelect()
    );
  }
  showCampaignDetail(campaign) {
    this.setScreen("campaigns");
    clear(this.app);
    this.current?.destroy();
    this.current = new CampaignDetail(
      this.app,
      campaign,
      (c) => this.showSelectForCampaign(c),
      async (s) => {
        try {
          const { session } = await getSession(s.id);
          this.resumeGame(session);
        } catch (err) {
          console.error("Failed to load joined session:", err);
          this.showCampaigns();
        }
      },
      () => this.showCampaigns()
    );
  }
  showSelectForCampaign(campaign) {
    this.setScreen("select");
    clear(this.app);
    this.current?.destroy();
    this.current = new CharacterSelect(
      this.app,
      (character, timerSeconds, _moduleId) => this.enterGame(character, campaign.id, timerSeconds),
      () => this.showCreate(),
      () => this.showCampaigns(),
      () => this.showSessions(),
      () => this.showHub(),
      () => this.showDmWorkshop()
    );
  }
  showSessions() {
    this.setScreen("sessions");
    clear(this.app);
    this.current?.destroy();
    this.current = new SessionSelect(
      this.app,
      (session) => this.resumeGame(session),
      (session) => this.resumeGame(session),
      () => this.showSelect(),
      () => this.showHub()
    );
  }
  showDmWorkshop() {
    this.setScreen("dm-workshop");
    clear(this.app);
    this.current?.destroy();
    this.current = new DmWorkshop(
      this.app,
      (dungeonId, characterId) => this.enterDungeon(dungeonId, characterId),
      () => this.showHub()
    );
  }
  async enterDungeon(dungeonId, characterId, campaignId) {
    this.setScreen("loading");
    clear(this.app);
    this.current?.destroy();
    try {
      const { session } = await playDungeon(dungeonId, characterId, campaignId, 0);
      const { module } = await getModule(session.module_id);
      this.setScreen("game");
      const game = new Game(
        this.app,
        session.id,
        module.map,
        session,
        () => this.showSessions(),
        (cid) => this.replayGame(cid),
        this.userId ?? void 0
      );
      this.current = game;
      await game.init();
    } catch (err) {
      this.setScreen("dm-workshop");
      this.showDmWorkshop();
      console.error("Failed to enter dungeon:", err);
    }
  }
  async resumeGame(session) {
    this.setScreen("loading");
    clear(this.app);
    this.current?.destroy();
    try {
      const { module } = await getModule(session.module_id);
      this.setScreen("game");
      const game = new Game(
        this.app,
        session.id,
        module.map,
        session,
        () => this.showSessions(),
        (characterId) => this.replayGame(characterId),
        this.userId ?? void 0
      );
      this.current = game;
      await game.init();
    } catch (err) {
      this.setScreen("select");
      this.showSelect();
      console.error("Failed to resume game:", err);
    }
  }
  async replayGame(characterId) {
    this.setScreen("loading");
    clear(this.app);
    this.current?.destroy();
    try {
      const { session } = await createSession(characterId, "sample_lair");
      const { module } = await getModule(session.module_id);
      this.setScreen("game");
      const game = new Game(
        this.app,
        session.id,
        module.map,
        session,
        () => this.showSessions(),
        (cid) => this.replayGame(cid),
        this.userId ?? void 0
      );
      this.current = game;
      await game.init();
    } catch (err) {
      this.setScreen("select");
      this.showSelect();
      console.error("Failed to replay game:", err);
    }
  }
  async enterGame(character, campaignId, turnTimerSeconds = 0, moduleId = "sample_lair") {
    if (!character.id) return;
    this.setScreen("loading");
    clear(this.app);
    this.current?.destroy();
    try {
      const { session } = await createSession(character.id, moduleId, campaignId, turnTimerSeconds);
      const { module } = await getModule(session.module_id);
      this.setScreen("game");
      const game = new Game(
        this.app,
        session.id,
        module.map,
        session,
        () => this.showSessions(),
        (characterId) => this.replayGame(characterId),
        this.userId ?? void 0
      );
      this.current = game;
      await game.init();
    } catch (err) {
      this.setScreen("select");
      this.showSelect();
      console.error("Failed to enter game:", err);
    }
  }
};

// src/main.ts
var app = document.getElementById("app");
if (!app) {
  throw new Error("Missing #app container");
}
function hideSplash() {
  const splash = document.getElementById("splash");
  if (!splash) return;
  splash.classList.add("hidden");
  setTimeout(() => splash.remove(), 600);
}
async function boot() {
  const sanctuary = new SanctuaryApp(app);
  try {
    await sanctuary.start();
  } finally {
    hideSplash();
  }
}
boot();
