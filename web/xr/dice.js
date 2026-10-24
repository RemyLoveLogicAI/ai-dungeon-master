// Pure d20 geometry and settle detection, shared by physics, rendering and tests.

const PHI = (1 + Math.sqrt(5)) / 2;

/** Icosahedron vertices (circumradius 1). */
export const D20_VERTICES = [
  [-1, PHI, 0], [1, PHI, 0], [-1, -PHI, 0], [1, -PHI, 0],
  [0, -1, PHI], [0, 1, PHI], [0, -1, -PHI], [0, 1, -PHI],
  [PHI, 0, -1], [PHI, 0, 1], [-PHI, 0, -1], [-PHI, 0, 1],
].map((v) => {
  const length = Math.hypot(...v);
  return v.map((c) => c / length);
});

/** Faces as counter-clockwise vertex index triples (outward normals). */
export const D20_FACES = [
  [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
  [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
  [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
  [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
];

function centroid(face) {
  return [0, 1, 2].map((axis) => face.reduce((sum, i) => sum + D20_VERTICES[i][axis], 0) / 3);
}

function normalize(v) {
  const length = Math.hypot(...v);
  return v.map((c) => c / length);
}

/** Outward unit normal of each face, in face order. */
export const D20_NORMALS = D20_FACES.map((face) => normalize(centroid(face)));

/** Face centroids (for placing number labels). */
export const D20_CENTROIDS = D20_FACES.map(centroid);

/** Value printed on each face; opposite faces sum to 21, like a real d20. */
export const D20_VALUES = (() => {
  const values = new Array(D20_FACES.length).fill(0);
  let next = 1;
  D20_NORMALS.forEach((normal, i) => {
    if (values[i]) return;
    const opposite = D20_NORMALS.findIndex(
      (other) => Math.abs(other[0] + normal[0]) + Math.abs(other[1] + normal[1]) + Math.abs(other[2] + normal[2]) < 1e-9,
    );
    values[i] = next;
    values[opposite] = 21 - next;
    next += 1;
  });
  return values;
})();

/** Rotate vector v by unit quaternion q = [x, y, z, w]. */
export function rotate([x, y, z, w], [vx, vy, vz]) {
  const tx = 2 * (y * vz - z * vy);
  const ty = 2 * (z * vx - x * vz);
  const tz = 2 * (x * vy - y * vx);
  return [
    vx + w * tx + (y * tz - z * ty),
    vy + w * ty + (z * tx - x * tz),
    vz + w * tz + (x * ty - y * tx),
  ];
}

// Resting flat, the top face points straight up (dot 1). Balanced on an edge the
// two top faces tilt ~20.9 deg (dot 0.934), so anything under this is cocked.
export const FLAT_DOT = 0.97;

/** Value of the face pointing up for orientation q, or null when the die is cocked. */
export function topFace(quaternion) {
  let best = -1;
  let bestDot = -Infinity;
  D20_NORMALS.forEach((normal, i) => {
    const dot = rotate(quaternion, normal)[1];
    if (dot > bestDot) {
      bestDot = dot;
      best = i;
    }
  });
  return bestDot >= FLAT_DOT ? D20_VALUES[best] : null;
}

/** Quaternion [x, y, z, w] that turns face `index` straight up. */
export function faceUpQuaternion(index) {
  const [nx, ny, nz] = D20_NORMALS[index];
  // Rotation taking n onto +Y: axis n x Y, angle acos(n . Y).
  const axis = [-nz, 0, nx];
  const axisLength = Math.hypot(...axis);
  if (axisLength < 1e-9) return ny > 0 ? [0, 0, 0, 1] : [1, 0, 0, 0];
  const angle = Math.acos(Math.max(-1, Math.min(1, ny)));
  const s = Math.sin(angle / 2) / axisLength;
  return [axis[0] * s, axis[1] * s, axis[2] * s, Math.cos(angle / 2)];
}

export const SETTLE_SPEED = 0.05;
export const SETTLE_FRAMES = 20;

/** True when the last `frames` speed samples are all below `threshold`. */
export function isSettled(speeds, threshold = SETTLE_SPEED, frames = SETTLE_FRAMES) {
  if (speeds.length < frames) return false;
  return speeds.slice(-frames).every((speed) => speed < threshold);
}
