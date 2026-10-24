// WebXR client: a tabletop room, a DM panel rendered from server blueprints,
// and a physical d20. Rules live on the server; this file only renders and
// reports what the player did.
import * as THREE from "three";
import * as CANNON from "cannon-es";
import { VRButton } from "three/addons/webxr/VRButton.js";
import { ARButton } from "three/addons/webxr/ARButton.js";
import { XRControllerModelFactory } from "three/addons/webxr/XRControllerModelFactory.js";
import { buildPanel, hitTest } from "./panel.js";
import { D20_CENTROIDS, D20_FACES, D20_NORMALS, D20_VALUES, D20_VERTICES, isSettled, topFace } from "./dice.js";

// Calibration knobs: tune on device.
const THROW_GAIN = 1.4;
const MAX_THROW_SPEED = 6;
const GRAB_RADIUS = 0.18;
const DIE_RADIUS = 0.045;
const TABLE_TOP = 0.75;
const REQUEST_TIMEOUT_MS = 3000;

// ---------- renderer / scene ----------
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.xr.enabled = true;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const roomBackground = new THREE.Color(0x0d0b10);
scene.background = roomBackground;
const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.02, 50);
camera.position.set(0, 1.45, 0.35);

scene.add(new THREE.HemisphereLight(0xffe7c2, 0x1a1420, 0.9));
const lantern = new THREE.PointLight(0xffb15c, 6, 4, 1.6);
lantern.position.set(0.25, 1.35, -0.55);
scene.add(lantern);

const mat = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.85, ...extra });

// Room (hidden in passthrough).
const room = new THREE.Group();
const floor = new THREE.Mesh(new THREE.PlaneGeometry(8, 8), mat(0x2a2028));
floor.rotation.x = -Math.PI / 2;
room.add(floor);
for (const [x, z, ry] of [[0, -3, 0], [-3, 0, Math.PI / 2], [3, 0, -Math.PI / 2], [0, 3, Math.PI]]) {
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(8, 3.2), mat(0x1c1620));
  wall.position.set(x, 1.6, z);
  wall.rotation.y = ry;
  room.add(wall);
}
scene.add(room);

// Table + tray.
const table = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.06, 0.9), mat(0x5a3b24));
table.position.set(0, TABLE_TOP - 0.03, -0.6);
scene.add(table);
const TRAY = { x: 0.42, z: -0.42, w: 0.36, d: 0.3, wall: 0.06 };
const trayFelt = new THREE.Mesh(new THREE.BoxGeometry(TRAY.w, 0.005, TRAY.d), mat(0x1f4a35));
trayFelt.position.set(TRAY.x, TABLE_TOP + 0.0025, TRAY.z);
scene.add(trayFelt);

// Diorama: causeway over water leading to a sunken shrine, plus the hero mini.
const diorama = new THREE.Group();
diorama.position.set(-0.15, TABLE_TOP, -0.65);
const water = new THREE.Mesh(new THREE.BoxGeometry(0.75, 0.02, 0.55), mat(0x1d4f6e, { roughness: 0.2, metalness: 0.3 }));
water.position.y = 0.01;
diorama.add(water);
const causeway = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.03, 0.5), mat(0x8a8072));
causeway.position.set(0.1, 0.035, 0);
diorama.add(causeway);
const shrineBase = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.03, 0.14), mat(0x6d6a63));
shrineBase.position.set(-0.17, 0.035, -0.12);
diorama.add(shrineBase);
for (const [px, pz] of [[-0.24, -0.17], [-0.1, -0.17], [-0.24, -0.07], [-0.1, -0.07]]) {
  const pillar = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.09), mat(0xb8b0a0));
  pillar.position.set(px, 0.095, pz);
  diorama.add(pillar);
}
const shrineLamp = new THREE.Mesh(new THREE.SphereGeometry(0.014), mat(0xffd27a, { emissive: 0xffa53a, emissiveIntensity: 2 }));
shrineLamp.position.set(-0.17, 0.08, -0.12);
diorama.add(shrineLamp);
const hero = new THREE.Group();
const heroBody = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.016, 0.05), mat(0x9b2d2d));
heroBody.position.y = 0.025;
const heroHead = new THREE.Mesh(new THREE.SphereGeometry(0.011), mat(0xe0c09a));
heroHead.position.y = 0.06;
hero.add(heroBody, heroHead);
hero.position.set(0.1, 0.05, 0.2);
diorama.add(hero);
scene.add(diorama);

// ---------- DM panel ----------
const PANEL_PX = 1024;
const panelCanvas = document.createElement("canvas");
panelCanvas.width = panelCanvas.height = PANEL_PX;
const ctx = panelCanvas.getContext("2d");
const panelTexture = new THREE.CanvasTexture(panelCanvas);
panelTexture.colorSpace = THREE.SRGBColorSpace;
const panel = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.9), new THREE.MeshBasicMaterial({ map: panelTexture, transparent: true }));
panel.position.set(-0.05, 1.45, -1.15);
scene.add(panel);
let actionRects = [];

function wrap(text, maxWidth) {
  const words = String(text).split(" ");
  const out = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (ctx.measureText(candidate).width > maxWidth && line) {
      out.push(line);
      line = word;
    } else line = candidate;
  }
  if (line) out.push(line);
  return out;
}

function drawPanel(model, status) {
  ctx.clearRect(0, 0, PANEL_PX, PANEL_PX);
  ctx.fillStyle = "rgba(20, 15, 24, 0.92)";
  ctx.beginPath();
  ctx.roundRect(8, 8, PANEL_PX - 16, PANEL_PX - 16, 28);
  ctx.fill();
  ctx.strokeStyle = "#a07a3c";
  ctx.lineWidth = 4;
  ctx.stroke();

  const pad = 48;
  const width = PANEL_PX - pad * 2;
  let y = 84;
  ctx.fillStyle = "#f3c97a";
  ctx.font = "bold 46px Georgia, serif";
  for (const line of wrap(model.title, width)) {
    ctx.fillText(line, pad, y);
    y += 54;
  }
  y += 6;
  const fonts = { heading: "bold 34px Georgia, serif", badge: "26px system-ui", text: "28px system-ui", roll: "bold 32px system-ui" };
  const colors = { heading: "#f3c97a", badge: "#c9b38a", text: "#e8dcc4", roll: "#8fe3a8" };
  const actionsHeight = model.actions.length * 82 + (model.prompt ? 70 : 0) + (status ? 60 : 0);
  for (const line of model.lines) {
    ctx.font = fonts[line.style] ?? fonts.text;
    ctx.fillStyle = colors[line.style] ?? colors.text;
    for (const wrapped of wrap(line.text, width)) {
      if (y > PANEL_PX - actionsHeight - 40) break;
      ctx.fillText(wrapped, pad, y);
      y += line.style === "heading" ? 42 : 36;
    }
    y += 8;
  }

  let by = PANEL_PX - actionsHeight - 24;
  if (model.prompt) {
    ctx.font = "bold 34px system-ui";
    ctx.fillStyle = "#ffcf5a";
    ctx.fillText(`🎲 ${model.prompt}: grab and throw the die`, pad, by + 40);
    by += 70;
  }
  if (status) {
    ctx.font = "bold 28px system-ui";
    ctx.fillStyle = "#ff8a7a";
    ctx.fillText(status, pad, by + 36);
    by += 60;
  }
  actionRects = [];
  for (const action of model.actions) {
    const rect = { x: pad, y: by, w: width, h: 68, action, disabled: action.disabled };
    ctx.fillStyle = action.disabled ? "#3a3340" : "#6b3f1d";
    ctx.beginPath();
    ctx.roundRect(rect.x, rect.y, rect.w, rect.h, 14);
    ctx.fill();
    ctx.font = "28px system-ui";
    ctx.fillStyle = action.disabled ? "#8d8494" : "#fff1d6";
    ctx.fillText(wrap(action.label, width - 40)[0], rect.x + 20, rect.y + 44);
    actionRects.push(rect);
    by += 82;
  }
  panelTexture.needsUpdate = true;
}

// ---------- server ----------
let lastResponse = null;
let lastModel = { title: "Connecting to the Dungeon Master…", lines: [], actions: [], prompt: null };
const RETRY = { label: "↻ Retry", intent: "__retry", payload: {}, disabled: false };

async function request(path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(path, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const json = await response.json();
    if (!response.ok) throw Object.assign(new Error(json.error ?? `HTTP ${response.status}`), { rejected: true });
    return json;
  } finally {
    clearTimeout(timer);
  }
}

function render(response, status = null) {
  if (response) {
    lastResponse = response;
    lastModel = buildPanel(response);
  }
  const model = status && !status.startsWith("DM:") ? { ...lastModel, actions: [...lastModel.actions, RETRY] } : lastModel;
  drawPanel(model, status);
}

async function call(path, body) {
  try {
    const response = await request(path, body);
    render(response);
    return response;
  } catch (error) {
    // A 4xx is the DM refusing the move; anything else means the server is unreachable.
    render(null, error.rejected ? `DM: ${error.message}` : "Lost the Dungeon Master: tap Retry");
    return null;
  }
}

const refresh = () => call("/api/surface");
const sendIntent = (intent, values = {}) => call("/api/intent", { intent, values });

async function activate(action) {
  if (!action) return;
  if (action.intent === "__retry") await refresh();
  else await sendIntent(action.intent, action.payload);
}

// ---------- audio ----------
const sfx = { roll: new Audio("/sfx/dice_roll.wav"), crit: new Audio("/sfx/crit_fanfare.wav") };
function play(name) {
  const clip = sfx[name];
  clip.currentTime = 0;
  clip.play().catch(() => {});
}

// ---------- physics ----------
const world = new CANNON.World({ gravity: new CANNON.Vec3(0, -9.82, 0) });
world.allowSleep = false;
const tableBody = new CANNON.Body({ mass: 0, shape: new CANNON.Box(new CANNON.Vec3(0.7, 0.03, 0.45)) });
tableBody.position.set(0, TABLE_TOP - 0.03, -0.6);
world.addBody(tableBody);
const floorBody = new CANNON.Body({ mass: 0, shape: new CANNON.Plane() });
floorBody.quaternion.setFromEuler(-Math.PI / 2, 0, 0);
world.addBody(floorBody);
// Tray walls keep a hard throw on the table.
for (const [dx, dz, hx, hz] of [
  [0, -TRAY.d / 2, TRAY.w / 2, 0.005], [0, TRAY.d / 2, TRAY.w / 2, 0.005],
  [-TRAY.w / 2, 0, 0.005, TRAY.d / 2], [TRAY.w / 2, 0, 0.005, TRAY.d / 2],
]) {
  const wallBody = new CANNON.Body({ mass: 0, shape: new CANNON.Box(new CANNON.Vec3(hx, TRAY.wall / 2, hz)) });
  wallBody.position.set(TRAY.x + dx, TABLE_TOP + TRAY.wall / 2, TRAY.z + dz);
  world.addBody(wallBody);
  const wallMesh = new THREE.Mesh(new THREE.BoxGeometry(hx * 2, TRAY.wall, hz * 2), mat(0x3b2616));
  wallMesh.position.copy(wallBody.position);
  scene.add(wallMesh);
}

const dieShape = new CANNON.ConvexPolyhedron({
  vertices: D20_VERTICES.map(([x, y, z]) => new CANNON.Vec3(x * DIE_RADIUS, y * DIE_RADIUS, z * DIE_RADIUS)),
  faces: D20_FACES,
});
const dieBody = new CANNON.Body({ mass: 0.02, shape: dieShape, linearDamping: 0.1, angularDamping: 0.1 });
const DIE_HOME = new CANNON.Vec3(TRAY.x, TABLE_TOP + 0.08, TRAY.z);
dieBody.position.copy(DIE_HOME);
world.addBody(dieBody);

const dieGeometry = new THREE.BufferGeometry();
dieGeometry.setAttribute("position", new THREE.Float32BufferAttribute(D20_FACES.flat().flatMap((i) => D20_VERTICES[i].map((c) => c * DIE_RADIUS)), 3));
dieGeometry.computeVertexNormals();
const die = new THREE.Mesh(dieGeometry, new THREE.MeshStandardMaterial({ color: 0x7b1f2e, roughness: 0.35, metalness: 0.1, flatShading: true }));
D20_FACES.forEach((_, i) => {
  const label = document.createElement("canvas");
  label.width = label.height = 64;
  const lctx = label.getContext("2d");
  lctx.fillStyle = "#f5e6c8";
  lctx.font = "bold 40px Georgia, serif";
  lctx.textAlign = "center";
  lctx.textBaseline = "middle";
  lctx.fillText(String(D20_VALUES[i]) + (D20_VALUES[i] === 6 || D20_VALUES[i] === 9 ? "." : ""), 32, 34);
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(DIE_RADIUS * 0.55, DIE_RADIUS * 0.55), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(label), transparent: true }));
  const centroid = new THREE.Vector3(...D20_CENTROIDS[i]).multiplyScalar(DIE_RADIUS * 1.01);
  plane.position.copy(centroid);
  plane.lookAt(centroid.clone().add(new THREE.Vector3(...D20_NORMALS[i])));
  die.add(plane);
});
scene.add(die);

// ---------- throw state ----------
const speeds = [];
let rolling = false;
let heldBy = null;
const history = [];
const tmpVec = new THREE.Vector3();
const tmpQuat = new THREE.Quaternion();

function releaseDie(velocity) {
  dieBody.type = CANNON.Body.DYNAMIC;
  dieBody.mass = 0.02;
  dieBody.updateMassProperties();
  const scaled = velocity.multiplyScalar(THROW_GAIN);
  if (scaled.length() > MAX_THROW_SPEED) scaled.setLength(MAX_THROW_SPEED);
  dieBody.velocity.set(scaled.x, scaled.y, scaled.z);
  dieBody.angularVelocity.set((Math.random() - 0.5) * 30, (Math.random() - 0.5) * 30, (Math.random() - 0.5) * 30);
  speeds.length = 0;
  rolling = true;
  play("roll");
}

function desktopThrow() {
  // Drop from above the tray with a little spin; tumbles but stays inside the walls.
  dieBody.position.set(TRAY.x, TABLE_TOP + 0.22, TRAY.z + 0.04);
  dieBody.quaternion.setFromEuler(Math.random() * 6, Math.random() * 6, Math.random() * 6);
  releaseDie(new THREE.Vector3((Math.random() - 0.5) * 0.4, 0.3, -0.15 - Math.random() * 0.2));
}

async function onDieSettled() {
  rolling = false;
  const q = dieBody.quaternion;
  const value = topFace([q.x, q.y, q.z, q.w]);
  if (value === null) {
    render(null, "DM: The die is cocked. Roll again!");
    return;
  }
  if (!lastResponse?.pendingCheck) {
    render(null, `DM: You rolled ${value}, but no check is pending.`);
    return;
  }
  const response = await sendIntent("PHYSICAL_DICE_ROLL", { roll: value });
  if (response?.lastRoll?.isCritical) play("crit");
}

// ---------- input: controllers ----------
const raycaster = new THREE.Raycaster();
const controllerFactory = new XRControllerModelFactory();
const controllers = [0, 1].map((index) => {
  const controller = renderer.xr.getController(index);
  const ray = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 0, -3)]), new THREE.LineBasicMaterial({ color: 0xffd27a }));
  controller.add(ray);
  scene.add(controller);
  const grip = renderer.xr.getControllerGrip(index);
  grip.add(controllerFactory.createControllerModel(grip));
  scene.add(grip);

  controller.addEventListener("select", () => {
    tmpQuat.setFromRotationMatrix(controller.matrixWorld);
    raycaster.set(controller.getWorldPosition(tmpVec), new THREE.Vector3(0, 0, -1).applyQuaternion(tmpQuat));
    clickPanel(raycaster);
  });
  grip.addEventListener("squeezestart", () => {
    if (heldBy || grip.getWorldPosition(tmpVec).distanceTo(die.position) > GRAB_RADIUS) return;
    heldBy = grip;
    history.length = 0;
    dieBody.type = CANNON.Body.KINEMATIC;
    dieBody.velocity.setZero();
    dieBody.angularVelocity.setZero();
  });
  grip.addEventListener("squeezeend", () => {
    if (heldBy !== grip) return;
    heldBy = null;
    const velocity = new THREE.Vector3();
    if (history.length >= 2) {
      const first = history[0];
      const last = history[history.length - 1];
      velocity.subVectors(last.p, first.p).divideScalar(Math.max(last.t - first.t, 1e-3));
    }
    releaseDie(velocity);
  });
  return controller;
});

function clickPanel(ray) {
  const hit = ray.intersectObject(panel)[0];
  if (!hit?.uv) return;
  activate(hitTest(actionRects, hit.uv.x * PANEL_PX, (1 - hit.uv.y) * PANEL_PX));
}

// ---------- input: desktop ----------
let yaw = 0;
let pitch = -0.25;
let dragging = null;
renderer.domElement.addEventListener("pointerdown", (event) => {
  dragging = { x: event.clientX, y: event.clientY, moved: false };
});
renderer.domElement.addEventListener("pointermove", (event) => {
  if (!dragging) return;
  const dx = event.clientX - dragging.x;
  const dy = event.clientY - dragging.y;
  if (Math.abs(dx) + Math.abs(dy) > 3) dragging.moved = true;
  yaw -= dx * 0.004;
  pitch = Math.max(-1.2, Math.min(1.2, pitch - dy * 0.004));
  dragging.x = event.clientX;
  dragging.y = event.clientY;
});
renderer.domElement.addEventListener("pointerup", (event) => {
  const wasClick = dragging && !dragging.moved;
  dragging = null;
  if (!wasClick) return;
  const pointer = new THREE.Vector2((event.clientX / window.innerWidth) * 2 - 1, -(event.clientY / window.innerHeight) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  clickPanel(raycaster);
});
window.addEventListener("keydown", (event) => {
  if (event.code === "Space") {
    event.preventDefault();
    desktopThrow();
  }
});
window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ---------- frame-time HUD ----------
const hudCanvas = document.createElement("canvas");
hudCanvas.width = 256;
hudCanvas.height = 48;
const hctx = hudCanvas.getContext("2d");
const hudTexture = new THREE.CanvasTexture(hudCanvas);
const hud = new THREE.Mesh(new THREE.PlaneGeometry(0.24, 0.045), new THREE.MeshBasicMaterial({ map: hudTexture, transparent: true }));
hud.position.set(-0.05, 0.96, -1.15);
scene.add(hud);
const FRAME_WINDOW = 600;
const frameTimes = new Float32Array(FRAME_WINDOW);
let frameCount = 0;
function updateHud() {
  const n = Math.min(frameCount, FRAME_WINDOW);
  const sorted = Array.from(frameTimes.subarray(0, n)).sort((a, b) => a - b);
  const p95 = sorted[Math.floor(n * 0.95)] ?? 0;
  window.__xrStats = { p95, frames: frameCount };
  hctx.clearRect(0, 0, 256, 48);
  hctx.fillStyle = p95 < 13.9 ? "#8fe3a8" : "#ff8a7a";
  hctx.font = "bold 26px monospace";
  hctx.fillText(`p95 ${p95.toFixed(1)} ms`, 8, 34);
  hudTexture.needsUpdate = true;
}

// ---------- loop ----------
const clock = new THREE.Clock();
renderer.setAnimationLoop(() => {
  const dt = Math.min(clock.getDelta(), 0.1);
  frameTimes[frameCount % FRAME_WINDOW] = dt * 1000;
  frameCount += 1;
  if (frameCount % 60 === 0) updateHud();

  if (!renderer.xr.isPresenting) {
    camera.rotation.set(pitch, yaw, 0, "YXZ");
  }
  if (heldBy) {
    heldBy.getWorldPosition(tmpVec);
    dieBody.position.set(tmpVec.x, tmpVec.y, tmpVec.z);
    heldBy.getWorldQuaternion(tmpQuat);
    dieBody.quaternion.set(tmpQuat.x, tmpQuat.y, tmpQuat.z, tmpQuat.w);
    history.push({ p: tmpVec.clone(), t: performance.now() / 1000 });
    if (history.length > 5) history.shift();
  }
  world.step(1 / 120, dt, 8);
  if (dieBody.position.y < 0.1) {
    // Fell off the table: put it back in the tray.
    dieBody.position.copy(DIE_HOME);
    dieBody.velocity.setZero();
    dieBody.angularVelocity.setZero();
  }
  die.position.copy(dieBody.position);
  die.quaternion.copy(dieBody.quaternion);
  if (rolling) {
    speeds.push(dieBody.velocity.length() + dieBody.angularVelocity.length() * DIE_RADIUS);
    if (speeds.length > 120) speeds.shift();
    if (isSettled(speeds)) onDieSettled();
  }
  renderer.render(scene, camera);
});

// ---------- XR entry ----------
document.body.appendChild(VRButton.createButton(renderer));
if (navigator.xr?.isSessionSupported) {
  navigator.xr.isSessionSupported("immersive-ar").then((supported) => {
    if (!supported) return;
    const arButton = ARButton.createButton(renderer);
    arButton.style.bottom = "70px";
    document.body.appendChild(arButton);
  });
}
renderer.xr.addEventListener("sessionstart", () => {
  const passthrough = renderer.xr.getSession()?.environmentBlendMode !== "opaque";
  room.visible = !passthrough;
  scene.background = passthrough ? null : roomBackground;
});
renderer.xr.addEventListener("sessionend", () => {
  room.visible = true;
  scene.background = roomBackground;
});

window.__xr = { die, dieBody, topFace, activate, desktopThrow, sendIntent, refresh, get model() { return lastModel; }, get actionRects() { return actionRects; } };
drawPanel(lastModel, null);
refresh();
