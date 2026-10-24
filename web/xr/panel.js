// Pure blueprint -> panel model. No three.js import, so node --test can load it.
// The server is authoritative: this only decides what to show and what each
// action posts back.

const TEXT_TYPES = new Set(["Heading", "Text", "Badge", "Stat", "ProgressBar"]);
const CONTAINER_TYPES = new Set(["Stack", "Card"]);
const warnedTypes = new Set();

function warnOnce(type) {
  if (warnedTypes.has(type)) return;
  warnedTypes.add(type);
  console.warn(`panel: skipping unsupported component type ${type}`);
}

// genui namespaces payload keys as "<btnId>.<key>"; handle_intent reads bare keys.
export function payloadFor(button, dataModel) {
  const payload = {};
  for (const key of button.props.action.payloadKeys ?? []) {
    const bare = key.startsWith(`${button.id}.`) ? key.slice(button.id.length + 1) : key;
    payload[bare] = dataModel[key];
  }
  return payload;
}

function textLine(component) {
  const { type, props } = component;
  if (type === "Heading") return { text: props.text, style: "heading" };
  if (type === "Badge") return { text: props.text, style: "badge" };
  if (type === "Stat") return { text: `${props.label}: ${props.value}`, style: "text" };
  if (type === "ProgressBar") return { text: `${props.label}`, style: "text" };
  return { text: props.text, style: "text" };
}

function rollLine(lastRoll) {
  const sign = lastRoll.modifier < 0 ? "-" : "+";
  const verdict = lastRoll.success ? "Success!" : "Failure.";
  const crit = lastRoll.isCritical ? " Natural 20!" : "";
  return `d20 ${lastRoll.value} ${sign} ${Math.abs(lastRoll.modifier)} = ${lastRoll.total} vs DC ${lastRoll.dc}: ${verdict}${crit}`;
}

/**
 * @param {object} response  server body: {blueprint, supportedIntents, pendingCheck, lastRoll}
 * @returns {{title: string, lines: {text: string, style: string}[], actions: object[], prompt: string|null}}
 */
export function buildPanel(response) {
  const { blueprint, supportedIntents = [], pendingCheck = null, lastRoll = null } = response;
  const supported = new Set(supportedIntents);
  const byId = new Map(blueprint.components.map((c) => [c.id, c]));
  const dataModel = blueprint.dataModel ?? {};
  const buttons = blueprint.components.filter((c) => c.type === "Button");
  const selects = blueprint.components.filter((c) => c.type === "Select");
  const optionLabels = new Map();
  for (const select of selects) {
    for (const option of select.props.options) optionLabels.set(`${option}:`, option);
  }

  const lines = [];
  const actions = [];
  const consumedButtons = new Set();

  const addAction = (label, intent, payload) => {
    if (!supported.has(intent)) return;
    const blocked = pendingCheck !== null && intent === "choose";
    actions.push({ label: blocked ? `${label} (roll first)` : label, intent, payload, disabled: blocked });
  };

  const visit = (id) => {
    const component = byId.get(id);
    if (!component) return;
    const { type, props } = component;
    if (CONTAINER_TYPES.has(type)) {
      for (const child of component.children ?? []) visit(child);
    } else if (TEXT_TYPES.has(type)) {
      // "<option>: description" lines become the option buttons' labels instead.
      const prefix = (props.text ?? "").split(" ")[0];
      if (!optionLabels.has(prefix)) lines.push(textLine(component));
    } else if (type === "Select") {
      const target = buttons.find((b) => (b.props.action.payloadKeys ?? []).includes(props.bind));
      if (!target) return;
      consumedButtons.add(target.id);
      for (const option of props.options) {
        const described = blueprint.components.find(
          (c) => c.type === "Text" && (c.props.text ?? "").startsWith(`${option}: `),
        );
        const label = described ? described.props.text.slice(option.length + 2) : option;
        addAction(label, target.props.action.intent, {
          ...payloadFor(target, dataModel),
          [props.bind]: option,
        });
      }
    } else if (type === "Button") {
      if (!consumedButtons.has(component.id)) {
        addAction(props.label, props.action.intent, payloadFor(component, dataModel));
      }
    } else {
      warnOnce(type);
    }
  };
  visit("root");

  let prompt = null;
  if (pendingCheck) prompt = `Roll d20 (${pendingCheck.skill} DC ${pendingCheck.dc})`;
  if (lastRoll) lines.push({ text: rollLine(lastRoll), style: "roll" });
  return { title: blueprint.surface?.title ?? "", lines, actions, prompt };
}

/** Return the action whose rect contains canvas point (x, y), or null. */
export function hitTest(rects, x, y) {
  for (const rect of rects) {
    if (x >= rect.x && x <= rect.x + rect.w && y >= rect.y && y <= rect.y + rect.h) {
      return rect.disabled ? null : rect.action;
    }
  }
  return null;
}
