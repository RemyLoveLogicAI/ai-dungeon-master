/* AI Dungeon Master — browser client for the agentsurface-blueprint/0.1 envelope.
 *
 * This file is a *renderer*, not a second rules engine. It walks the validated
 * blueprint produced by the Python producers and draws it. It never reimplements
 * combat, dice or scenario logic: the only thing it decides is how a component
 * looks and which intent a click dispatches.
 *
 * Security note the contract requires: text is written with `textContent` only.
 * Scenario and log strings are never interpolated into HTML, so a hostile string
 * cannot become markup.
 *
 * SUPPORTED_TYPES is the renderer's declared vocabulary. `test_web_demo.py`
 * parses this array and asserts it covers every component type the producers
 * actually emit, so a new Python component type cannot ship unrendered.
 */
(function () {
  "use strict";

  const SUPPORTED_TYPES = [
    "Stack", "Card", "Heading", "Text", "Stat", "Badge",
    "ProgressBar", "Table", "Select", "Button",
  ];

  const state = {
    data: null,
    sceneId: null,
    view: "onboarding",
    hero: {
      name: "Kaelen Ironheart",
      archetype: "Fighter",
      species: "Human",
      background: "Soldier",
      level: 1,
      hp: 12,
      maxHp: 12,
      ac: 16,
      edition: "D&D 5th Edition (Revised 2024)",
      confirmed: false,
    },
    journal: [],
  };

  function updateHeroBadge() {
    const node = document.getElementById("hero-badge");
    if (!node) return;
    if (state.hero.confirmed) {
      node.textContent = "⚔️ " + state.hero.name + " · " + state.hero.archetype + " (Lv " + state.hero.level + ") · HP " + state.hero.hp + "/" + state.hero.maxHp + " · AC " + state.hero.ac;
    } else {
      node.textContent = "Draft: " + state.hero.name + " (" + state.hero.archetype + ")";
    }
  }

  // ---------------------------------------------------------------- utilities

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    // textContent, never innerHTML: a scenario string stays a string.
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  // A tiny Web Audio cue generator. Optional and fully guarded: a browser
  // without AudioContext (or with autoplay blocked) simply gets no sound.
  let audioCtx = null;
  function cue(kind) {
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      audioCtx = audioCtx || new AC();
      const now = audioCtx.currentTime;
      const notes = { navigate: [440], choose: [523, 659], intent: [330, 247] }[kind] || [440];
      notes.forEach(function (freq, i) {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "triangle";
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, now + i * 0.09);
        gain.gain.exponentialRampToValueAtTime(0.12, now + i * 0.09 + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.09 + 0.18);
        osc.connect(gain).connect(audioCtx.destination);
        osc.start(now + i * 0.09);
        osc.stop(now + i * 0.09 + 0.2);
      });
    } catch (err) {
      /* audio is a nicety; never let it break the surface */
    }
  }

  function toast(message) {
    const box = document.getElementById("toast");
    box.textContent = message;
    box.classList.add("show");
    window.clearTimeout(toast._t);
    toast._t = window.setTimeout(function () { box.classList.remove("show"); }, 2200);
  }

  // ------------------------------------------------------------ component map

  function createComponent(component, ctx) {
    const type = component.type;
    const p = component.props || {};

    switch (type) {
      case "Stack": {
        const row = p.direction === "row";
        const node = el("div", row ? "row" : "stack col");
        if (p.gap) node.style.gap = /^\d+(\.\d+)?$/.test(p.gap) ? p.gap + "px" : p.gap;
        return node;
      }
      case "Card": {
        const node = el("section", "card");
        const body = el("div", "card-body");
        node.appendChild(body);
        node._body = body;
        return node;
      }
      case "Heading": {
        const level = Math.min(3, Math.max(1, Number(p.level) || 2));
        return el("h" + level, "heading", p.text);
      }
      case "Text":
        return el("p", "text", p.text);
      case "Stat": {
        const node = el("div", "metric");
        node.appendChild(el("span", "metric-label", p.label));
        node.appendChild(el("span", "metric-value", p.value));
        if (p.unit) node.appendChild(el("span", "metric-trend", p.unit));
        return node;
      }
      case "Badge": {
        const tone = p.tone === "warn" ? "warning" : (p.tone || "default");
        return el("span", "badge badge-" + tone, p.text);
      }
      case "ProgressBar": {
        const node = el("div", "bar-wrap");
        if (p.label) node.appendChild(el("span", "bar-label", p.label));
        const track = el("div", "bar-track");
        const fill = el("div", "bar-fill");
        const max = Number(p.max) || 0;
        const value = Number(p.value) || 0;
        const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
        fill.style.width = pct + "%";
        if (pct > 50) fill.classList.add("bar-good");
        else if (pct > 20) fill.classList.add("bar-warn");
        else fill.classList.add("bar-bad");
        track.appendChild(fill);
        node.appendChild(track);
        node.appendChild(el("span", "bar-value", value + " / " + max));
        return node;
      }
      case "Table": {
        const table = el("table", "surface-table");
        const head = el("thead");
        const headerRow = el("tr");
        (p.columns || []).forEach(function (column) {
          headerRow.appendChild(el("th", null, column.label));
        });
        head.appendChild(headerRow);
        table.appendChild(head);
        const body = el("tbody");
        (p.rows || []).forEach(function (row) {
          const tr = el("tr");
          (p.columns || []).forEach(function (column) {
            tr.appendChild(el("td", null, row[column.key]));
          });
          body.appendChild(tr);
        });
        table.appendChild(body);
        return table;
      }
      case "Select": {
        const node = el("label", "field");
        if (p.label) node.appendChild(el("span", "field-label", p.label));
        const select = el("select", "select");
        (p.options || []).forEach(function (option) {
          const opt = el("option", null, option);
          opt.value = String(option);
          select.appendChild(opt);
        });
        if (p.bind) {
          select.value = String(ctx.dataModel[p.bind]);
          select.addEventListener("change", function () {
            ctx.dataModel[p.bind] = select.value;
          });
        }
        node.appendChild(select);
        return node;
      }
      case "Button": {
        const action = p.action || {};
        const node = el("button", "btn", p.label);
        node.type = "button";
        node.addEventListener("click", function () {
          const payload = {};
          (action.payloadKeys || []).forEach(function (key) {
            payload[key] = ctx.dataModel[key];
          });
          ctx.onIntent(action.intent, payload);
        });
        return node;
      }
      default:
        return el("div", "unsupported", "[unsupported component: " + type + "]");
    }
  }

  function renderBlueprint(blueprint, onIntent) {
    const byId = new Map(blueprint.components.map(function (c) { return [c.id, c]; }));
    const ctx = { byId: byId, dataModel: Object.assign({}, blueprint.dataModel), onIntent: onIntent };
    const root = byId.get("root");
    if (!root) return el("div", "unsupported", "[blueprint has no root]");

    function build(component) {
      const node = createComponent(component, ctx);
      const mount = node._body || node;
      (component.children || []).forEach(function (childId) {
        const child = byId.get(childId);
        if (child) mount.appendChild(build(child));
      });
      return node;
    }
    return build(root);
  }

  // ------------------------------------------------------------------ routing

  function handleIntent(intent, payload) {
    const envelope = {
      surface: state.surfaceId,
      intent: intent,
      values: payload,
      ts: new Date().toISOString(),
    };
    const text = JSON.stringify(envelope, null, 2);
    const panel = el("section", "intent-result");
    panel.setAttribute("aria-live", "polite");
    panel.appendChild(el("h2", null, "Intent submitted"));
    panel.appendChild(el("pre", null, text));
    const copy = el("button", "btn", "Copy envelope");
    copy.type = "button";
    const status = el("p", "muted");
    copy.addEventListener("click", async function () {
      try {
        await navigator.clipboard.writeText(text);
        status.textContent = "Envelope copied.";
      } catch (_error) {
        status.textContent = "Clipboard unavailable. Select and copy the envelope above.";
      }
    });
    panel.appendChild(copy);
    panel.appendChild(status);
    document.getElementById("stage").appendChild(panel);
    cue("intent");
    copy.focus();

    if (intent === "CONFIRM_CHARACTER_DRAFT") {
      state.hero.confirmed = true;
      state.journal.push({
        action: "CONFIRM_CHARACTER_DRAFT",
        hero: Object.assign({}, state.hero),
        ts: new Date().toISOString(),
      });
      updateHeroBadge();
      toast("Character draft confirmed! Transitioning to adventure...");
      window.setTimeout(function () {
        setView("story");
      }, 1200);
    } else if (intent === "SWITCH_STARTER_ARCHETYPE") {
      const isFighter = state.hero.archetype === "Fighter";
      state.hero.archetype = isFighter ? "Wizard" : "Fighter";
      state.hero.name = isFighter ? "Eldrin Dawncaller" : "Kaelen Ironheart";
      state.hero.hp = isFighter ? 8 : 12;
      state.hero.maxHp = isFighter ? 8 : 12;
      state.hero.ac = isFighter ? 12 : 16;
      state.journal.push({
        action: "SWITCH_STARTER_ARCHETYPE",
        archetype: state.hero.archetype,
        ts: new Date().toISOString(),
      });
      updateHeroBadge();
      toast("Draft switched: " + state.hero.archetype + " (" + state.hero.name + ")");
    }
  }

  // Deep links: #onboarding, #scene=<id>, and #encounter. Sharing a link to a view is worth
  // more than a scroll position, and it makes each surface reachable directly.
  function syncHash(value) {
    if (window.location.hash !== value) {
      window.history.replaceState(null, "", value);
    }
  }

  function showOnboarding() {
    const host = document.getElementById("stage");
    const blueprint = state.data.onboarding.surface;
    state.surfaceId = blueprint.surface.id;
    host.replaceChildren(renderBlueprint(blueprint, handleIntent));
    document.getElementById("crumb").textContent = "onboarding (stage 1 & 2)";
    syncHash("#onboarding");
  }

  function showScene(sceneId) {
    state.sceneId = sceneId;
    const scene = state.data.scenario.scenes[sceneId];
    const host = document.getElementById("stage");
    state.surfaceId = scene.blueprint.surface.id;
    host.replaceChildren(renderBlueprint(scene.blueprint, handleIntent));
    document.getElementById("crumb").textContent = sceneId;
    syncHash("#scene=" + sceneId);
  }

  function showEncounter() {
    const host = document.getElementById("stage");
    const blueprint = state.data.encounter.surface;
    state.surfaceId = blueprint.surface.id;
    host.replaceChildren(renderBlueprint(blueprint, handleIntent));
    document.getElementById("crumb").textContent =
      "encounter (seeded " + state.data.encounter.seed + ")";
    syncHash("#encounter");
  }

  function setView(view) {
    state.view = view;
    document.querySelectorAll("[data-view]").forEach(function (tab) {
      tab.classList.toggle("active", tab.dataset.view === view);
    });
    cue("navigate");
    if (view === "onboarding") showOnboarding();
    else if (view === "story") showScene(state.sceneId);
    else showEncounter();
  }

  // -------------------------------------------------------------------- boot

  async function boot() {
    const response = await fetch("demo-data.json");
    if (!response.ok) throw new Error("could not load demo-data.json (" + response.status + ")");
    state.data = await response.json();
    state.sceneId = state.data.scenario.startScene;

    document.getElementById("title").textContent = state.data.scenario.title;
    document.getElementById("subtitle").textContent = state.data.scenario.description;
    document.getElementById("contract").textContent = state.data.contract;
    document.querySelectorAll("[data-view]").forEach(function (tab) {
      tab.addEventListener("click", function () { setView(tab.dataset.view); });
    });

    updateHeroBadge();
    const hash = window.location.hash || "";
    const sceneMatch = /^#scene=(.+)$/.exec(hash);
    if (hash === "#encounter") {
      setView("encounter");
    } else if (hash === "#story") {
      setView("story");
    } else if (sceneMatch && state.data.scenario.scenes[sceneMatch[1]]) {
      setView("story");
      showScene(sceneMatch[1]);
    } else {
      setView("onboarding");
    }
  }

  window.DungeonDemo = { SUPPORTED_TYPES: SUPPORTED_TYPES, renderBlueprint: renderBlueprint, handleIntent: handleIntent };

  boot().catch(function (err) {
    const host = document.getElementById("stage");
    host.replaceChildren(el("div", "unsupported", "Failed to start: " + err.message));
  });
})();
