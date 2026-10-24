import { test } from "node:test";
import assert from "node:assert/strict";
import {
  D20_FACES, D20_NORMALS, D20_VALUES, FLAT_DOT, faceUpQuaternion, isSettled, rotate, topFace,
} from "../dice.js";

test("twenty faces with outward unit normals and values 1..20", () => {
  assert.equal(D20_FACES.length, 20);
  assert.deepEqual([...D20_VALUES].sort((a, b) => a - b), Array.from({ length: 20 }, (_, i) => i + 1));
  for (const normal of D20_NORMALS) assert.ok(Math.abs(Math.hypot(...normal) - 1) < 1e-12);
});

test("opposite faces sum to 21", () => {
  D20_NORMALS.forEach((normal, i) => {
    const j = D20_NORMALS.findIndex((o) => o.every((c, k) => Math.abs(c + normal[k]) < 1e-9));
    assert.equal(D20_VALUES[i] + D20_VALUES[j], 21);
  });
});

test("each canonical face-up orientation reads that face", () => {
  D20_VALUES.forEach((value, index) => {
    const q = faceUpQuaternion(index);
    assert.ok(rotate(q, D20_NORMALS[index])[1] > 0.999999);
    assert.equal(topFace(q), value);
  });
});

test("die balanced on an edge is cocked (null)", () => {
  // Halfway between two adjacent face normals points up: the edge between them.
  const [a, b] = [0, 1];
  const mid = D20_NORMALS[a].map((c, k) => c + D20_NORMALS[b][k]);
  const length = Math.hypot(...mid);
  const up = mid.map((c) => c / length);
  const axis = [-up[2], 0, up[0]];
  const axisLength = Math.hypot(...axis);
  const angle = Math.acos(up[1]);
  const s = Math.sin(angle / 2) / axisLength;
  const q = [axis[0] * s, axis[1] * s, axis[2] * s, Math.cos(angle / 2)];
  assert.ok(rotate(q, D20_NORMALS[a])[1] < FLAT_DOT);
  assert.equal(topFace(q), null);
});

test("isSettled needs a full window of slow frames", () => {
  assert.equal(isSettled([0, 0, 0], 0.05, 5), false);
  assert.equal(isSettled([1, 0, 0, 0, 0, 0], 0.05, 5), true);
  assert.equal(isSettled([0, 0, 0, 0, 0.2, 0], 0.05, 5), false);
});

test("faces wind counter-clockwise outward (cannon ConvexPolyhedron, three front faces)", async () => {
  const { D20_VERTICES } = await import("../dice.js");
  for (const [a, b, c] of D20_FACES) {
    const [p, q, r] = [D20_VERTICES[a], D20_VERTICES[b], D20_VERTICES[c]];
    const u = q.map((v, k) => v - p[k]);
    const w = r.map((v, k) => v - p[k]);
    const cross = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    const outward = cross[0] * (p[0] + q[0] + r[0]) + cross[1] * (p[1] + q[1] + r[1]) + cross[2] * (p[2] + q[2] + r[2]);
    assert.ok(outward > 0, `face ${a},${b},${c} winds inward`);
  }
});
