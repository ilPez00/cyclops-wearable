// Node smoke test for the G2 plugin layout logic (no G2 hardware / SDK needed).
// Parity with Python device/g2_layout.py: same model -> same 4x18 grid shape
// and same banner text.
const assert = require("assert");
const { layoutToGrid, decodeFrame, modelToBanner, MAX_COLS, MAX_LINES } =
  require("../main.js");

let n = 0;
function ok(name, cond) { assert.ok(cond, name); console.log("OK " + name); n++; }

// 1) agent frame decoded
const agent = decodeFrame("Kagent\nLMeet Bob at 3pm\nLbring the cable\nM0");
ok("decode HUD_FRAME agent", agent.kind === "agent" && agent.lines[0] === "Meet Bob at 3pm");

// 2) DISPLAY_CMD progress
const prog = decodeFrame('{"kind":"progress","p":42}');
ok("decode DISPLAY_CMD progress", prog.progress === 42);

// 3) grid is exactly 4x18
const grid = layoutToGrid({ kind: "agent", lines: ["Meet Bob at 3pm", "bring cable"], progress: 42, hr: 72, spo2: 97, batt: 80 });
ok("grid is 4 rows", grid.length === MAX_LINES);
ok("grid is 18 cols", grid.every((r) => r.length === MAX_COLS));

// 4) banner content survives into grid
const flat = grid.map((r) => r.join("")).join("\n");
ok("banner shows kind + health", flat.includes("agent") && flat.includes("H72") && flat.includes("S97") && flat.includes("B80"));
ok("banner shows progress", flat.includes("42%"));

// 5) long line wraps within 18 cols
const longGrid = layoutToGrid({ kind: "HOME", lines: ["x".repeat(40)] });
ok("long line wrapped <=18 per row", longGrid.every((r) => r.join("").length <= MAX_COLS));

console.log("PASS g2-plugin/test/layout.test.js (" + n + " assertions)");
