// cyclops-g2-hud — EvenRealities G2 plugin (even_hub_sdk).
//
// Receives Cyclops HUD frames over a WebSocket relay (the Cyclops companion
// app forwards DISPLAY_CMD/HUD_FRAME bytes), decodes them, and draws a
// glanceable 4x18 monochrome-green HUD on the G2 right lens.
//
// The wire format is identical to device/g2.py / device/g2_layout.py on the
// Cyclops side, so the wearable, the desktop simulator, and the G2 all agree.

const MAX_COLS = 18;
const MAX_LINES = 4;

// ---- shared layout (mirrors Python device/g2_layout.model_to_banner) ----
function modelToBanner(model) {
  const segs = [];
  if (model.kind && model.kind !== "HOME") segs.push(model.kind.slice(0, 5));
  if (model.hr != null) segs.push("H" + model.hr);
  if (model.spo2 != null) segs.push("S" + model.spo2);
  if (model.batt != null) segs.push("B" + model.batt);
  const out = [];
  const hdr = segs.join(" ").slice(0, MAX_COLS);
  if (hdr) out.push(hdr);
  (model.lines || []).slice(0, 3).forEach((l) => out.push(l.slice(0, MAX_COLS)));
  if (model.progress != null) out.push(("[" + model.progress + "%]").slice(0, MAX_COLS));
  return out.slice(0, MAX_LINES).join("\n");
}

function wrapLine(s) {
  const out = [];
  while (s.length > MAX_COLS) { out.push(s.slice(0, MAX_COLS)); s = s.slice(MAX_COLS); }
  out.push(s);
  return out;
}

// Produce the 4x18 grid the G2 draws. Each cell is a char (or space).
function layoutToGrid(model) {
  const banner = modelToBanner(model);
  const rows = banner.split("\n").flatMap(wrapLine).slice(0, MAX_LINES);
  while (rows.length < MAX_LINES) rows.push("");
  return rows.map((r) => r.padEnd(MAX_COLS, " ").slice(0, MAX_COLS).split(""));
}

// Decode a raw Cyclops frame (HUD_FRAME tagged "K/L/M" or DISPLAY_CMD JSON).
function decodeFrame(raw) {
  // HUD_FRAME tagged format
  if (raw.includes("K") && raw.includes("L")) {
    let kind = "HOME", lines = [], more = false;
    raw.split("\n").forEach((ln) => {
      if (!ln) return;
      const tag = ln[0], val = ln.slice(1);
      if (tag === "K") kind = val;
      else if (tag === "L") lines.push(val);
      else if (tag === "M") more = val === "1";
    });
    return { kind, lines, more };
  }
  // DISPLAY_CMD JSON
  try {
    const o = JSON.parse(raw);
    if (o.kind === "progress") return { kind: "HOME", progress: o.p };
    if (o.kind === "step") return { kind: "HOME", lines: ["> " + o.tool] };
    if (o.kind === "text") return { kind: "HOME", lines: [o.text || o.data || ""] };
  } catch (_) {}
  return { kind: "HOME", lines: [raw] };
}

// EvenRealities entry points (provided by even_hub_sdk at runtime).
function registerCyclopsG2(api) {
  const canvas = api.getDisplay(); // {width,height,drawGrid(grid)}
  function onFrame(raw) {
    const model = decodeFrame(raw);
    const grid = layoutToGrid(model);
    canvas.drawGrid(grid); // green monochrome 4x18
  }
  api.onFrame(onFrame);
  return { onFrame, layoutToGrid, decodeFrame, modelToBanner };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { registerCyclopsG2, layoutToGrid, decodeFrame, modelToBanner, wrapLine, MAX_COLS, MAX_LINES };
}
