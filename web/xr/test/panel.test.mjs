import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildPanel, hitTest, payloadFor } from "../panel.js";

const fixture = (name) =>
  JSON.parse(readFileSync(new URL(`../fixtures/${name}.json`, import.meta.url), "utf8"));

test("onboarding: confirm with stripped payload keys, switch, no unsupported intents", () => {
  const panel = buildPanel(fixture("onboarding"));
  assert.deepEqual(panel.actions.map((a) => a.intent), ["CONFIRM_CHARACTER_DRAFT", "SWITCH_STARTER_ARCHETYPE"]);
  const confirm = panel.actions[0];
  assert.deepEqual(Object.keys(confirm.payload).sort(), ["archetype", "characterName", "edition", "guidance"]);
  assert.equal(confirm.payload.characterName, "Kaelen Ironheart");
  assert.ok(!panel.actions.some((a) => a.intent === "ADJUST_GUIDANCE"));
  assert.equal(panel.prompt, null);
  assert.equal(panel.title, "Meet Your Dungeon Master");
});

test("story: one choose action per select option, carrying choice_id", () => {
  const panel = buildPanel(fixture("story"));
  const chooses = panel.actions.filter((a) => a.intent === "choose");
  assert.equal(chooses.length, 2);
  assert.deepEqual(chooses.map((a) => a.payload.choice_id).sort(), ["follow_the_bell", "help_the_courier"]);
  assert.ok(chooses.every((a) => !a.disabled));
  assert.ok(!panel.lines.some((l) => l.text.startsWith("follow_the_bell:")));
});

test("shrine_pending: roll prompt shown, choices disabled", () => {
  const panel = buildPanel(fixture("shrine_pending"));
  assert.equal(panel.prompt, "Roll d20 (Athletics DC 12)");
  const chooses = panel.actions.filter((a) => a.intent === "choose");
  assert.equal(chooses.length, 2);
  assert.ok(chooses.every((a) => a.disabled && a.label.endsWith("(roll first)")));
});

test("last roll renders a result line", () => {
  const body = { ...fixture("story"), lastRoll: { value: 9, modifier: 3, total: 12, dc: 12, success: true, isCritical: false } };
  const line = buildPanel(body).lines.at(-1);
  assert.equal(line.style, "roll");
  assert.equal(line.text, "d20 9 + 3 = 12 vs DC 12: Success!");
});

test("unknown component types are skipped", () => {
  const body = {
    supportedIntents: [],
    blueprint: {
      surface: { title: "t" },
      dataModel: {},
      components: [
        { id: "root", type: "Stack", children: ["x", "y"], props: {} },
        { id: "x", type: "Hologram", props: {} },
        { id: "y", type: "Text", props: { text: "kept" } },
      ],
    },
  };
  assert.deepEqual(buildPanel(body).lines, [{ text: "kept", style: "text" }]);
});

test("payloadFor keeps bare keys and strips the button prefix", () => {
  const button = { id: "b", props: { action: { payloadKeys: ["b.name", "choice_id"] } } };
  assert.deepEqual(payloadFor(button, { "b.name": "Ada", choice_id: "x" }), { name: "Ada", choice_id: "x" });
});

test("hitTest ignores disabled rects", () => {
  const rects = [
    { x: 0, y: 0, w: 10, h: 10, action: "a", disabled: true },
    { x: 0, y: 20, w: 10, h: 10, action: "b", disabled: false },
  ];
  assert.equal(hitTest(rects, 5, 5), null);
  assert.equal(hitTest(rects, 5, 25), "b");
  assert.equal(hitTest(rects, 50, 50), null);
});
