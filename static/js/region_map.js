/** Campaign region map: visual graph of modules and prerequisites. */

const REGION_MAP_WIDTH = 800;
const REGION_MAP_HEIGHT = 420;
const REGION_NODE_RADIUS = 26;

function openRegionMap() {
  const modal = document.getElementById("region-map-modal");
  if (!modal) return;
  renderRegionMap();
  modal.classList.remove("hidden");
}

function closeRegionMap() {
  const modal = document.getElementById("region-map-modal");
  if (!modal) return;
  modal.classList.add("hidden");
}

function getModuleState(id) {
  const mod = DUNGEON_MODULES[id];
  if (!mod) return "locked";
  if (campaign.completed_modules.includes(id)) return "completed";
  if (isModuleAvailable(id)) return "available";
  return "locked";
}

function modulePos(id, mod) {
  const pos = mod.map_pos || { x: 50, y: 50 };
  return {
    x: (pos.x / 100) * REGION_MAP_WIDTH,
    y: (pos.y / 100) * REGION_MAP_HEIGHT,
  };
}

function renderRegionMap() {
  const container = document.getElementById("region-map-svg");
  const title = document.getElementById("region-map-title");
  if (!container) return;

  const campaignData = CAMPAIGNS[campaign.campaign_id];
  if (title) title.textContent = campaignData ? `${campaignData.name} — Region Map` : "Region Map";

  const modules = Object.entries(DUNGEON_MODULES)
    .filter(([_, mod]) => mod.campaign_id === campaign.campaign_id)
    .sort((a, b) => (a[1].chapter || 0) - (b[1].chapter || 0));

  const positions = {};
  for (const [id, mod] of modules) {
    positions[id] = modulePos(id, mod);
  }

  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${REGION_MAP_WIDTH} ${REGION_MAP_HEIGHT}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.classList.add("region-map-svg");

  // Defs for glow filters.
  const defs = document.createElementNS(ns, "defs");
  const filter = document.createElementNS(ns, "filter");
  filter.setAttribute("id", "region-glow");
  filter.innerHTML = `
    <feGaussianBlur stdDeviation="2.5" result="coloredBlur"/>
    <feMerge>
      <feMergeNode in="coloredBlur"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  `;
  defs.appendChild(filter);
  svg.appendChild(defs);

  // Draw edges.
  const drawnEdges = new Set();
  function edgeKey(a, b) {
    return a < b ? `${a}|${b}` : `${b}|${a}`;
  }
  function drawEdge(fromId, toId, cls) {
    if (!positions[fromId] || !positions[toId]) return;
    const key = edgeKey(fromId, toId);
    if (drawnEdges.has(key)) return;
    drawnEdges.add(key);
    const a = positions[fromId];
    const b = positions[toId];
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", a.x);
    line.setAttribute("y1", a.y);
    line.setAttribute("x2", b.x);
    line.setAttribute("y2", b.y);
    line.classList.add("region-edge", cls);
    svg.appendChild(line);
  }

  for (const [id, mod] of modules) {
    const state = getModuleState(id);
    for (const reqId of mod.requires || []) {
      drawEdge(reqId, id, state === "locked" ? "locked" : "requires");
    }
    if (mod.unlocks) {
      drawEdge(id, mod.unlocks, state === "completed" ? "unlocked" : "future");
    }
  }

  // Draw nodes.
  for (const [id, mod] of modules) {
    const state = getModuleState(id);
    const pos = positions[id];
    const g = document.createElementNS(ns, "g");
    g.classList.add("region-node", state);
    g.setAttribute("data-id", id);
    g.style.cursor = state === "available" ? "pointer" : "default";

    const circle = document.createElementNS(ns, "circle");
    circle.setAttribute("cx", pos.x);
    circle.setAttribute("cy", pos.y);
    circle.setAttribute("r", REGION_NODE_RADIUS);
    g.appendChild(circle);

    // Icon.
    const icon = document.createElementNS(ns, "text");
    icon.setAttribute("x", pos.x);
    icon.setAttribute("y", pos.y - 2);
    icon.setAttribute("text-anchor", "middle");
    icon.setAttribute("dominant-baseline", "middle");
    icon.classList.add("region-node-icon");
    if (state === "completed") icon.textContent = "✓";
    else if (state === "locked") icon.textContent = "🔒";
    else icon.textContent = String(mod.chapter || "?");
    g.appendChild(icon);

    // Name label.
    const nameLabel = document.createElementNS(ns, "text");
    nameLabel.setAttribute("x", pos.x);
    nameLabel.setAttribute("y", pos.y + REGION_NODE_RADIUS + 16);
    nameLabel.setAttribute("text-anchor", "middle");
    nameLabel.classList.add("region-node-name");
    nameLabel.textContent = mod.name;
    g.appendChild(nameLabel);

    // Level label.
    const levelLabel = document.createElementNS(ns, "text");
    levelLabel.setAttribute("x", pos.x);
    levelLabel.setAttribute("y", pos.y + REGION_NODE_RADIUS + 32);
    levelLabel.setAttribute("text-anchor", "middle");
    levelLabel.classList.add("region-node-level");
    levelLabel.textContent = `Level ${mod.level || 1}`;
    g.appendChild(levelLabel);

    if (state === "available") {
      g.addEventListener("click", () => {
        campaign.selected_module = id;
        saveCampaign();
        closeRegionMap();
        openGuildBoard();
      });
    }

    svg.appendChild(g);
  }

  container.innerHTML = "";
  container.appendChild(svg);
}

function regionMapKeyHandler(e) {
  if (e.key === "Escape") {
    const modal = document.getElementById("region-map-modal");
    if (modal && !modal.classList.contains("hidden")) {
      closeRegionMap();
    }
  }
}

document.addEventListener("keydown", regionMapKeyHandler);
