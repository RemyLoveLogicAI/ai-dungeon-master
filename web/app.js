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
    // narrative vocabulary (game_foundation adapter)
    "Surface", "Stack", "Heading", "Text", "Select", "Button",
    // tactical vocabulary (genui exporter)
    "Card", "Row", "Column", "Metric", "Badge", "ProgressBar",
    "TacticalGrid", "DiceTray",
  ];

  const state = { data: null, sceneId: null, view: "story" };

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
      case "Surface": {
        const node = el("div", "surface");
        if (p.maxWidth) node.style.maxWidth = p.maxWidth;
        if (p.padding) node.style.padding = p.padding;
        return node;
      }
      case "Stack":
      case "Column": {
        const node = el("div", "stack col");
        if (p.gap) node.style.gap = p.gap;
        return node;
      }
      case "Row": {
        const node = el("div", "row");
        if (p.gap) node.style.gap = p.gap;
        if (p.marginTop) node.style.marginTop = p.marginTop;
        if (p.flex) node.style.flex = String(p.flex);
        return node;
      }
      case "Card": {
        const node = el("section", "card");
        if (p.title) {
          const head = el("div", "card-head");
          head.appendChild(el("h3", null, p.title));
          if (p.badge) head.appendChild(el("span", "chip", p.badge));
          node.appendChild(head);
        }
        const body = el("div", "card-body");
        node.appendChild(body);
        node._body = body; // children are appended here, not after the header
        return node;
      }
      case "Heading": {
        const level = Math.min(3, Math.max(1, Number(p.level) || 2));
        return el("h" + level, "heading", p.text);
      }
      case "Text": {
        const variant = p.variant === "caption" ? "muted" : "";
        return el("p", "text " + variant, p.text !== undefined ? p.text : p.content);
      }
      case "Metric": {
        const node = el("div", "metric metric-" + (p.variant || "neutral"));
        node.appendChild(el("span", "metric-label", p.label));
        node.appendChild(el("span", "metric-value", p.value));
        if (p.trend) node.appendChild(el("span", "metric-trend", p.trend));
        return node;
      }
      case "Badge": {
        return el("span", "badge badge-" + (p.variant || "neutral"), p.label);
      }
      case "ProgressBar": {
        const node = el("div", "bar-wrap");
        if (p.label) node.appendChild(el("span", "bar-label", p.label));
        const track = el("div", "bar-track");
        const fill = el("div", "bar-fill");
        const max = Number(p.max) || 0;
        const current = Number(p.current) || 0;
        const pct = max > 0 ? Math.max(0, Math.min(100, (current / max) * 100)) : 0;
        fill.style.width = pct + "%";
        if (pct > 50) fill.classList.add("bar-good");
        else if (pct > 20) fill.classList.add("bar-warn");
        else fill.classList.add("bar-bad");
        track.appendChild(fill);
        node.appendChild(track);
        node.appendChild(el("span", "bar-value", current + " / " + max + " " + (p.unit || "")));
        return node;
      }
      case "TacticalGrid": {
        const node = el("div", "grid-wrap");
        if (p.lighting) node.appendChild(el("div", "grid-caption", p.lighting));
        const table = el("div", "grid");
        const w = Number(p.gridWidth) || 10;
        const h = Number(p.gridHeight) || 6;
        table.style.gridTemplateColumns = "repeat(" + w + ", 1fr)";
        const covers = new Set((p.covers || []).map(function (c) { return c[0] + "," + c[1]; }));
        const hero = (p.heroPos || []).join(",");
        const enemy = (p.enemyPos || []).join(",");
        for (let y = 0; y < h; y++) {
          for (let x = 0; x < w; x++) {
            const key = x + "," + y;
            const cell = el("div", "cell");
            if (key === hero) { cell.classList.add("cell-hero"); cell.textContent = "@"; }
            else if (key === enemy) { cell.classList.add("cell-enemy"); cell.textContent = "G"; }
            else if (covers.has(key)) { cell.classList.add("cell-cover"); cell.textContent = "#"; }
            table.appendChild(cell);
          }
        }
        node.appendChild(table);
        node.appendChild(el("div", "grid-legend", "@ Hero   G Gargoyle   # Half-cover"));
        return node;
      }
      case "DiceTray": {
        return el("div", "dice-tray", p.label || "Dice");
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
        if (p.enabled === false) node.disabled = true;
        node.addEventListener("click", function () {
          const payload = {};
          (action.payloadKeys || []).forEach(function (key) {
            payload[key] = ctx.dataModel[key];
          });
          ctx.onIntent(action.intent, payload);
        });
        return node;
      }
      default: {
        // Unreachable for generated data (the test asserts coverage), but a
        // renderer should degrade visibly rather than render nothing at all.
        return el("div", "unsupported", "[unsupported component: " + type + "]");
      }
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
    if (intent === "choose") {
      const scene = state.data.scenario.scenes[state.sceneId];
      const target = scene.targets[payload.choice_id];
      if (target) {
        cue("choose");
        showScene(target);
        return;
      }
      toast("No scene is mapped to choice " + payload.choice_id);
      return;
    }
    // Every other intent is a host-routed action. This demo has no host, and it
    // says so rather than pretending the click did something.
    cue("intent");
    toast("Intent " + (intent || "(none)") + " fired — a real host would route this.");
  }

  // Deep links: #scene=<id> and #encounter. Sharing a link to a view is worth
  // more than a scroll position, and it makes each surface reachable directly.
  function syncHash(value) {
    if (window.location.hash !== value) {
      window.history.replaceState(null, "", value);
    }
  }

  function showScene(sceneId) {
    state.sceneId = sceneId;
    const scene = state.data.scenario.scenes[sceneId];
    const host = document.getElementById("stage");
    host.replaceChildren(renderBlueprint(scene.blueprint, handleIntent));
    document.getElementById("crumb").textContent = sceneId;
    syncHash("#scene=" + sceneId);
  }

  function showEncounter() {
    const host = document.getElementById("stage");
    host.replaceChildren(renderBlueprint(state.data.encounter.surface, handleIntent));
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
    if (view === "story") showScene(state.sceneId);
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

    const hash = window.location.hash || "";
    const sceneMatch = /^#scene=(.+)$/.exec(hash);
    if (hash === "#encounter") {
      setView("encounter");
    } else if (sceneMatch && state.data.scenario.scenes[sceneMatch[1]]) {
      showScene(sceneMatch[1]);
    } else {
      showScene(state.sceneId);
    }
  }

  window.DungeonDemo = { SUPPORTED_TYPES: SUPPORTED_TYPES, renderBlueprint: renderBlueprint, handleIntent: handleIntent };

  boot().catch(function (err) {
    const host = document.getElementById("stage");
    host.replaceChildren(el("div", "unsupported", "Failed to start: " + err.message));
  });
})();
