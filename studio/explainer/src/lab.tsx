// GetYr Lab: our own teaching template for engineering channels.
// Blueprint grid, real schematic symbols, electrons that flow along the conducting path,
// a live oscilloscope synced to the circuit, pause-and-think questions and worked formulas.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/700.css";
import { SANS, fade, rise, prog, ease } from "./theme";

export const MONO = `"JetBrains Mono", Menlo, monospace`;
// One look per channel (colours + background pattern). cyan = primary accent, amber = secondary.
export const THEMES: Record<string, any> = {
  ece: { bg0: "#04101c", bg1: "#0a2236", grid: "rgba(80,160,220,0.10)", grid2: "rgba(80,160,220,0.22)",
    cyan: "#38d6ff", amber: "#ffb547", green: "#46f29a", red: "#ff6464", text: "#e8f1f8", dim: "#6f88a0",
    wire: "#9fb6c9", off: "#3b5266", electron: "#7fe7ff", pattern: "grid", badge: "GETYR · ECE LAB" },
  cse: { bg0: "#0d0b16", bg1: "#1b1530", grid: "rgba(160,120,255,0.07)", grid2: "rgba(160,120,255,0.16)",
    cyan: "#a98bff", amber: "#4ee39b", green: "#4ee39b", red: "#ff6b8b", text: "#f1edff", dim: "#8a82a8",
    wire: "#b9b0d8", off: "#3d3757", electron: "#c7b5ff", pattern: "dots", badge: "GETYR · CSE" },
  cyber: { bg0: "#030605", bg1: "#07140e", grid: "rgba(0,255,140,0.06)", grid2: "rgba(0,255,140,0.13)",
    cyan: "#19ff8c", amber: "#ff4d4d", green: "#19ff8c", red: "#ff4d4d", text: "#dfffee", dim: "#5f8a74",
    wire: "#8fbfa6", off: "#2b4236", electron: "#7dffc0", pattern: "scan", badge: "GETYR · CYBERSEC" },
  ent: { bg0: "#0c0906", bg1: "#21170d", grid: "rgba(214,170,92,0.05)", grid2: "rgba(214,170,92,0.10)",
    cyan: "#d6aa5c", amber: "#f1d39a", green: "#9fd38a", red: "#e0533d", text: "#f3ece0", dim: "#9a8b74",
    wire: "#c9b48e", off: "#4a3d2c", electron: "#f1d39a", pattern: "grain", badge: "GETYR · ENT" },
};
// light versions (default): off-white paper, darker accents so everything stays readable
const LIGHT: Record<string, any> = {
  ece: { bg0: "#f7fafc", bg1: "#e3eef6", grid: "rgba(20,90,150,0.07)", grid2: "rgba(20,90,150,0.16)", cyan: "#0077b6", amber: "#d96c00",
    green: "#0a9b55", red: "#d62828", text: "#0d1b2a", dim: "#5c6f80", wire: "#34495e", off: "#b9c6d2", electron: "#0096c7" },
  cse: { bg0: "#ffffff", bg1: "#ffffff", grid: "rgba(106,63,214,0.05)", grid2: "rgba(106,63,214,0.10)", cyan: "#6a3fd6", amber: "#0f9d58",
    green: "#0f9d58", red: "#d6336c", text: "#1b1530", dim: "#6f6890", wire: "#4a4270", off: "#d2cbe8", electron: "#7b5cff" },
  cyber: { bg0: "#f4faf6", bg1: "#dff1e6", grid: "rgba(0,120,80,0.06)", grid2: "rgba(0,120,80,0.14)", cyan: "#00875a", amber: "#d62828",
    green: "#00875a", red: "#d62828", text: "#0b1f15", dim: "#557563", wire: "#2d4a3b", off: "#bdd4c6", electron: "#00a86b" },
  ent: { bg0: "#fbf7ef", bg1: "#f1e4cc", grid: "rgba(150,110,40,0.05)", grid2: "rgba(150,110,40,0.11)", cyan: "#9a6a12", amber: "#c0502a",
    green: "#4b8b3b", red: "#c0392b", text: "#2a2015", dim: "#7d6b52", wire: "#5b4a35", off: "#dccdb3", electron: "#b07d2b" },
};
for (const k of Object.keys(THEMES)) {
  THEMES[k] = { ...THEMES[k], dark: true, panel: "rgba(2,10,18,0.85)", hi: "rgba(255,255,255,0.08)", shadow: "0 2px 10px rgba(0,0,0,0.95)" };
  THEMES[k + "-dark"] = THEMES[k];
  THEMES[k] = { ...THEMES[k], ...LIGHT[k], dark: false, panel: "rgba(255,255,255,0.92)", hi: "rgba(0,0,0,0.06)", shadow: "none" };
}
// CYBERSEC: light sky blue (easy on the eyes for long videos); navy for defence, red for attacks, green for safe
THEMES.cyber = { ...THEMES.cyber, bg0: "#eef7ff", bg1: "#d4eafb", grid: "rgba(10,92,168,0.05)", grid2: "rgba(10,92,168,0.11)",
  cyan: "#0a5ca8", amber: "#d62839", green: "#138a50", red: "#d62839", text: "#0b2540", dim: "#4f6b85", wire: "#2c4a66",
  off: "#b7cde0", electron: "#1f8fe0", pattern: "grid" };
export const L: any = { ...THEMES.ece };
export const setTheme = (name?: string) => Object.assign(L, THEMES[name || "ece"] || THEMES.ece);

const useU = () => {
  const { width, height } = useVideoConfig(); const tall = height > width;
  return { u: (Math.min(width, height) / 1080) * (tall ? 1.35 : 1), w: width, h: height, tall };
};

// ------------------------------------------------------------------ frame (background, badge, captions)
export const LabFrame: React.FC<{ children: React.ReactNode; caption?: string; dur: number; scene?: any; ep?: any; progress?: number }> =
  ({ children, caption, dur, scene, ep, progress = 0 }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const sentences: string[] = (caption || "").match(/[^.!?]+[.!?]+/g) || (caption ? [caption] : []);
  const total = sentences.reduce((a, s) => a + s.length, 0) || 1;
  let acc = 0, current = "";
  for (const s of sentences) {
    const a = (acc / total) * dur, b = ((acc + s.length) / total) * dur;
    if (f >= a && f < b) current = s.trim();
    acc += s.length;
  }
  const out = interpolate(f, [dur - 8, dur], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const g = 54 * u;
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 35%, ${L.bg1} 0%, ${L.bg0} 75%)`, overflow: "hidden" }}>
      {L.pattern === "grid" && <AbsoluteFill style={{ backgroundImage: `linear-gradient(${L.grid} 1px, transparent 1px), linear-gradient(90deg, ${L.grid} 1px, transparent 1px),
        linear-gradient(${L.grid2} 1px, transparent 1px), linear-gradient(90deg, ${L.grid2} 1px, transparent 1px)`,
        backgroundSize: `${g}px ${g}px, ${g}px ${g}px, ${g * 5}px ${g * 5}px, ${g * 5}px ${g * 5}px`, backgroundPosition: `${-f * 0.15}px 0` }} />}
      {L.pattern === "dots" && <AbsoluteFill style={{ backgroundImage: `radial-gradient(${L.grid2} ${1.6 * u}px, transparent ${1.8 * u}px)`, backgroundSize: `${g * 0.7}px ${g * 0.7}px`, backgroundPosition: `0 ${-f * 0.2}px` }} />}
      {L.pattern === "scan" && <AbsoluteFill style={{ backgroundImage: `repeating-linear-gradient(0deg, ${L.grid} 0px, ${L.grid} 1px, transparent 2px, transparent ${4 * u}px)` }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: `${(f * 0.6) % 120 - 10}%`, height: "8%", background: `linear-gradient(transparent, ${L.grid2}, transparent)` }} /></AbsoluteFill>}
      {L.pattern === "grain" && <AbsoluteFill style={{ opacity: 0.08, mixBlendMode: "screen" }}><svg width="100%" height="100%"><filter id="lg"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} seed={f % 50} /></filter><rect width="100%" height="100%" filter="url(#lg)" /></svg></AbsoluteFill>}
      <AbsoluteFill style={{ opacity: scene?.type === "cover" ? 1 : Math.min(fade(f, 0, 8), out) }}>{children}</AbsoluteFill>
      {/* channel badge + chapter */}
      <div style={{ position: "absolute", left: 40 * u, top: 34 * u, display: "flex", alignItems: "center", gap: 14 * u, fontFamily: MONO }}>
        <div style={{ border: `${2 * u}px solid ${L.cyan}`, color: L.cyan, fontSize: 18 * u, fontWeight: 700, padding: `${4 * u}px ${10 * u}px`, letterSpacing: 2 * u }}>
          {ep?.badge || L.badge}</div>
        {scene?.chapter && <div style={{ color: L.dim, fontSize: 18 * u, letterSpacing: 3 * u }}>{scene.chapter.toUpperCase()}</div>}
      </div>
      {/* lesson progress */}
      <div style={{ position: "absolute", left: 0, bottom: 0, height: 5 * u, width: `${progress * 100}%`, background: L.cyan, opacity: 0.8 }} />
      {ep?.captions === "bold" && caption && (() => {
        // big 2-3 word captions, one chunk at a time, the key word in colour (timed by letters)
        const words = caption.replace(/\s+/g, " ").trim().split(" ");
        const chunks: string[][] = []; for (let i = 0; i < words.length; i += 3) chunks.push(words.slice(i, i + 3));
        const lens = chunks.map((c) => c.join(" ").length + 4); const tot = lens.reduce((a, b) => a + b, 0);
        let a2 = 0, k = chunks.length - 1; for (let i = 0; i < chunks.length; i++) { if (f < ((a2 + lens[i]) / tot) * dur) { k = i; break; } a2 += lens[i]; }
        const ch = chunks[k] || []; const key = ch.reduce((b, w, i) => (w.replace(/\W/g, "").length > (ch[b] || "").replace(/\W/g, "").length ? i : b), 0);
        return <div style={{ position: "absolute", left: "5%", right: "5%", bottom: tall ? "16%" : "9%", textAlign: "center", fontFamily: SANS, fontWeight: 900,
          fontSize: 76 * u * (tall ? 1.15 : 1), letterSpacing: -1 * u, lineHeight: 1.05, textTransform: "uppercase", opacity: out }}>
          {ch.map((w, i) => <span key={i} style={{ color: i === key ? L.red : L.text, WebkitTextStroke: `${2 * u}px ${L.bg0}`, paintOrder: "stroke" }}>{w.replace(/[.,!?;:]$/, "")} </span>)}
        </div>;
      })()}
      {current && ep?.captions === "sentences" && (
        <div style={{ position: "absolute", left: "7%", right: "7%", bottom: tall ? "9%" : "5%", textAlign: "center", fontFamily: SANS,
          fontSize: 30 * u * (tall ? 1.25 : 1), fontWeight: tall ? 700 : 500, lineHeight: 1.35, color: L.text,
          textShadow: L.shadow, opacity: out }}>
          <span style={{ background: L.dark ? "transparent" : L.panel, padding: L.dark ? 0 : `${6 * u}px ${18 * u}px`, borderRadius: 10 * u,
            boxShadow: L.dark ? "none" : `0 ${4 * u}px ${18 * u}px rgba(0,0,0,0.08)`, boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone" }}>{current}</span></div>
      )}
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ schematic primitives (viewBox units)
const Wire: React.FC<{ pts: number[][]; on?: boolean; color?: string }> = ({ pts, on, color }) =>
  <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke={color || (on ? L.wire : L.off)} strokeWidth={5} strokeLinejoin="round" />;

/** Diode on a vertical leg, anode at the bottom, cathode (bar) at the top: it conducts upwards. */
const DiodeUp: React.FC<{ x: number; y: number; on: boolean; label: string; labelLeft?: boolean }> = ({ x, y, on, label, labelLeft }) => {
  const c = on ? L.green : L.off;
  return <g>
    <rect x={x - 34} y={y - 34} width={68} height={68} fill={L.bg0} />
    <polygon points={`${x - 26},${y + 22} ${x + 26},${y + 22} ${x},${y - 22}`} fill={on ? "rgba(70,242,154,0.35)" : "none"} stroke={c} strokeWidth={5} strokeLinejoin="round" />
    <line x1={x - 28} y1={y - 22} x2={x + 28} y2={y - 22} stroke={c} strokeWidth={6} />
    <line x1={x} y1={y - 34} x2={x} y2={y - 22} stroke={c} strokeWidth={5} /><line x1={x} y1={y + 22} x2={x} y2={y + 34} stroke={c} strokeWidth={5} />
    {on && <circle cx={x} cy={y} r={46} fill="none" stroke={L.green} strokeOpacity={0.35} strokeWidth={3} />}
    <text x={labelLeft ? x - 52 : x + 52} y={y + 9} textAnchor={labelLeft ? "end" : "start"} fill={on ? L.green : L.dim} fontFamily={MONO} fontSize={30} fontWeight={700}>{label}</text>
    <text x={labelLeft ? x - 52 : x + 52} y={y + 38} textAnchor={labelLeft ? "end" : "start"} fill={on ? L.green : L.dim} fontFamily={MONO} fontSize={20}>{on ? "ON" : "OFF"}</text>
  </g>;
};

/** Capacitor between y-gap: top plate at y-14, bottom plate at y+14. charge 0..1 fills the + plate glow. */
const Cap: React.FC<{ x: number; y: number; charge: number; label?: string; active?: boolean }> = ({ x, y, charge, label = "C", active }) =>
  <g>
    <rect x={x - 50} y={y - 30} width={100} height={60} fill={L.bg0} />
    <line x1={x - 44} y1={y - 14} x2={x + 44} y2={y - 14} stroke={L.amber} strokeWidth={8} />
    <line x1={x - 44} y1={y + 14} x2={x + 44} y2={y + 14} stroke={L.amber} strokeWidth={8} />
    <rect x={x - 44} y={y - 14 - 30 * charge} width={88} height={30 * charge} fill={L.amber} opacity={0.22} />
    <text x={x - 66} y={y - 6} fill={L.amber} fontFamily={MONO} fontSize={28} textAnchor="end">+</text>
    <text x={x + 62} y={y + 10} fill={active ? L.amber : L.dim} fontFamily={MONO} fontSize={28} fontWeight={700}>{label}</text>
  </g>;

const Resistor: React.FC<{ x: number; y: number; on: boolean; label?: string }> = ({ x, y, on, label = "LOAD" }) => {
  const zz = Array.from({ length: 7 }, (_, i) => `${x + (i % 2 ? 22 : -22)},${y - 60 + (i + 1) * 15}`).join(" ");
  return <g>
    <rect x={x - 34} y={y - 70} width={68} height={140} fill={L.bg0} />
    <polyline points={`${x},${y - 70} ${x},${y - 60} ${zz} ${x},${y + 60} ${x},${y + 70}`} fill="none" stroke={on ? L.amber : L.off} strokeWidth={5} strokeLinejoin="round" />
    {on && <circle cx={x} cy={y} r={70} fill="url(#loadglow)" />}
    <text x={x + 44} y={y + 10} fill={on ? L.text : L.dim} fontFamily={MONO} fontSize={26} fontWeight={700}>{label}</text>
  </g>;
};

const ACSource: React.FC<{ x: number; y: number; v: number }> = ({ x, y, v }) =>
  <g>
    <circle cx={x} cy={y} r={50} fill={L.bg0} stroke={L.cyan} strokeWidth={5} />
    <path d={`M${x - 30},${y} q15,-${30 * Math.abs(v) + 6} 30,0 t30,0`} fill="none" stroke={L.cyan} strokeWidth={5} transform={v < 0 ? `rotate(180 ${x} ${y})` : undefined} />
    <text x={x} y={y + 92} fill={L.cyan} fontFamily={MONO} fontSize={24} textAnchor="middle">12 V AC</text>
    {Math.abs(v) > 0.05 && <>
      <text x={x - 78} y={y - 18} fill={v > 0 ? L.red : L.cyan} fontFamily={MONO} fontSize={34} fontWeight={700} textAnchor="middle">{v > 0 ? "+" : "−"}</text>
      <text x={x + 78} y={y - 18} fill={v > 0 ? L.cyan : L.red} fontFamily={MONO} fontSize={34} fontWeight={700} textAnchor="middle">{v > 0 ? "−" : "+"}</text>
    </>}
  </g>;

/** Electrons: dots that travel along a polyline. Conventional current follows `pts`; electrons move the opposite way. */
const Flow: React.FC<{ pts: number[][]; t: number; speed?: number; gap?: number; opacity?: number }> = ({ pts, t, speed = 260, gap = 46, opacity = 1 }) => {
  const seg = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]));
  const len = seg.reduce((a, b) => a + b, 0);
  if (len === 0 || opacity <= 0.01) return null;
  const at = (d: number) => { // point at distance d along the path (from the start)
    let k = 0; while (k < seg.length - 1 && d > seg[k]) { d -= seg[k]; k++; }
    const r = Math.min(1, d / (seg[k] || 1)); return [pts[k][0] + (pts[k + 1][0] - pts[k][0]) * r, pts[k][1] + (pts[k + 1][1] - pts[k][1]) * r];
  };
  const n = Math.floor(len / gap); const off = (t * speed) % gap;
  return <g opacity={opacity}>{Array.from({ length: n }, (_, i) => {
    const d = len - ((i * gap + off) % len); const [x, y] = at(d);   // reversed: electrons go against conventional current
    return <circle key={i} cx={x} cy={y} r={7} fill={L.electron} stroke={L.bg0} strokeOpacity={0.7} strokeWidth={1.5} />;
  })}</g>;
};

// ------------------------------------------------------------------ simulation of a bridge rectifier + capacitor
const DROP = 0.09;            // two diode drops as a fraction of the peak (1.4 V of ~17 V)
/** State at time t (in cycles): source v (-1..1), output voltage, which path conducts. */
const simulate = (t: number, withCap: boolean, tau: number) => {
  const v = Math.sin(2 * Math.PI * t);
  const rect = Math.max(0, Math.abs(v) - DROP);
  if (!withCap) return { v, out: rect, phase: rect > 0 ? (v > 0 ? "pos" : "neg") : "none", vc: rect };
  let vc = 0; const steps = Math.max(1, Math.ceil(t * 400)); const dt = t / steps;
  for (let i = 1; i <= steps; i++) {
    const vi = Math.max(0, Math.abs(Math.sin(2 * Math.PI * i * dt)) - DROP);
    vc = vi > vc ? vi : vc * Math.exp(-dt / tau);
  }
  const charging = rect >= vc - 1e-3 && rect > 0;
  return { v, out: vc, vc, phase: charging ? (v > 0 ? "pos" : "neg") : "dis" };
};

// circuit geometry (viewBox 0 0 1000 800)
const J1 = [150, 400], J2 = [450, 400], TOP = 120, BOT = 680, CX = 690, RX = 880;
const PATH: Record<string, number[][]> = {
  pos: [J1, [150, TOP], [RX, TOP], [RX, BOT], [450, BOT], J2, [350, 400], [250, 400], J1],
  neg: [J2, [450, TOP], [RX, TOP], [RX, BOT], [150, BOT], J1, [250, 400], [350, 400], J2],
  dis: [[CX, 386], [CX, TOP], [RX, TOP], [RX, BOT], [CX, BOT], [CX, 414]],
  capIn: [[CX, TOP], [CX, 386]], capOut: [[CX, 414], [CX, BOT]],
};

const Bridge: React.FC<{ s: ReturnType<typeof simulate>; withCap: boolean; t: number; showLoad: boolean; electrons: boolean }> = ({ s, withCap, t, showLoad, electrons }) => {
  const d1 = s.phase === "pos", d3 = s.phase === "neg";
  const charging = withCap && (d1 || d3);
  return (
    <svg viewBox="0 0 1000 800" width="100%" height="100%">
      <defs><radialGradient id="loadglow"><stop offset="0" stopColor={L.amber} stopOpacity={0.35 * (s.out || 0)} /><stop offset="1" stopColor={L.amber} stopOpacity={0} /></radialGradient></defs>
      {/* rails and legs */}
      <Wire pts={[[150, BOT], [150, TOP], [RX, TOP]]} on /><Wire pts={[[450, BOT], [450, TOP]]} on />
      <Wire pts={[[150, BOT], [RX, BOT]]} on />
      {showLoad && <Wire pts={[[RX, TOP], [RX, BOT]]} on />}
      {withCap && <Wire pts={[[CX, TOP], [CX, BOT]]} on />}
      <Wire pts={[J1, [250, 400]]} on /><Wire pts={[[350, 400], J2]} on />
      {[J1, J2, [150, TOP], [450, TOP], [150, BOT], [450, BOT]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r={8} fill={L.wire} />)}
      {withCap && [[CX, TOP], [CX, BOT]].map(([x, y], i) => <circle key={i} cx={x} cy={y} r={8} fill={L.wire} />)}
      {/* electrons */}
      {electrons && (d1 || d3) && <Flow pts={PATH[s.phase]} t={t * 60} />}
      {electrons && withCap && s.phase === "dis" && <Flow pts={PATH.dis} t={t * 60} speed={140} />}
      {electrons && charging && <><Flow pts={PATH.capIn} t={t * 60} /><Flow pts={PATH.capOut} t={t * 60} /></>}
      {/* parts */}
      <DiodeUp x={150} y={260} on={d1} label="D1" labelLeft /><DiodeUp x={150} y={540} on={d3} label="D4" labelLeft />
      <DiodeUp x={450} y={260} on={d3} label="D3" /><DiodeUp x={450} y={540} on={d1} label="D2" />
      <ACSource x={300} y={400} v={s.v} />
      {withCap && <Cap x={CX} y={400} charge={s.vc} active={charging || s.phase === "dis"} />}
      {showLoad && <Resistor x={RX} y={400} on={s.out > 0.02} />}
      <text x={RX + 30} y={TOP - 18} fill={L.red} fontFamily={MONO} fontSize={34} fontWeight={700}>+</text>
      <text x={RX + 30} y={BOT + 46} fill={L.cyan} fontFamily={MONO} fontSize={34} fontWeight={700}>−</text>
    </svg>
  );
};

// ------------------------------------------------------------------ oscilloscope
const Scope: React.FC<{ upTo: number; cycles: number; withCap: boolean; tau: number; showIn?: boolean; showRect?: boolean; ripple?: boolean; title?: string }> =
  ({ upTo, cycles, withCap, tau, showIn = true, showRect = false, ripple = false, title = "OSCILLOSCOPE" }) => {
  const W = 1000, H = 560, x0 = 60, x1 = W - 30, ym = 300, A = 200;
  const N = 360; const pts = (fn: (t: number) => number) => {
    const out: string[] = []; for (let i = 0; i <= N; i++) { const t = (i / N) * cycles; if (t > upTo) break; out.push(`${x0 + (x1 - x0) * (t / cycles)},${ym - A * fn(t)}`); } return out.join(" ");
  };
  const px = x0 + (x1 - x0) * Math.min(1, upTo / cycles);
  const cur = simulate(upTo, withCap, tau);
  // lowest point of the filtered output in the last full half-cycle drawn (for the ripple bracket)
  let lo = 1; if (withCap) for (let i = 0; i <= 40; i++) { const tt = Math.max(0, upTo - 0.5 + (i / 40) * 0.5); lo = Math.min(lo, simulate(tt, true, tau).vc); }
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%">
      <rect x={10} y={10} width={W - 20} height={H - 20} rx={18} fill={L.panel} stroke={L.cyan} strokeOpacity={0.5} strokeWidth={3} />
      <text x={40} y={58} fill={L.dim} fontFamily={MONO} fontSize={24} letterSpacing={3}>{title}</text>
      {Array.from({ length: 11 }, (_, i) => <line key={i} x1={x0 + ((x1 - x0) * i) / 10} y1={80} x2={x0 + ((x1 - x0) * i) / 10} y2={H - 40} stroke={L.grid2} />)}
      <line x1={x0} y1={ym} x2={x1} y2={ym} stroke={L.dim} strokeWidth={2} />
      {showIn && <polyline points={pts((t) => Math.sin(2 * Math.PI * t))} fill="none" stroke={L.cyan} strokeWidth={4} strokeDasharray="10 8" opacity={0.7} />}
      {showRect && <polyline points={pts((t) => simulate(t, false, tau).out)} fill="none" stroke={L.dim} strokeWidth={4} opacity={withCap ? 0.6 : 1} />}
      <polyline points={pts((t) => simulate(t, withCap, tau).out)} fill="none" stroke={L.amber} strokeWidth={7} strokeLinejoin="round" />
      <line x1={px} y1={80} x2={px} y2={H - 40} stroke={L.text} strokeOpacity={0.5} strokeWidth={2} />
      <circle cx={px} cy={ym - A * cur.out} r={11} fill={L.amber} />
      {showIn && <circle cx={px} cy={ym - A * cur.v} r={8} fill={L.cyan} />}
      {ripple && withCap && upTo > 1 && (() => { const bx = x1 + 6, yt = ym - A * (1 - DROP), yb = ym - A * lo; return <g>
        <line x1={x0} y1={yt} x2={x1} y2={yt} stroke={L.red} strokeOpacity={0.45} strokeDasharray="6 6" strokeWidth={2} />
        <line x1={x0} y1={yb} x2={x1} y2={yb} stroke={L.red} strokeOpacity={0.45} strokeDasharray="6 6" strokeWidth={2} />
        <path d={`M${bx - 12},${yt} H${bx} V${yb} H${bx - 12}`} fill="none" stroke={L.red} strokeWidth={5} />
        <rect x={bx - 128} y={yt - 54} width={128} height={38} rx={6} fill={L.panel} />
        <text x={bx - 8} y={yt - 26} fill={L.red} fontFamily={MONO} fontSize={28} fontWeight={700} textAnchor="end">ripple</text>
      </g>; })()}
      <text x={40} y={H - 10} fill={L.cyan} fontFamily={MONO} fontSize={22}>{showIn ? "- - input AC" : ""}</text>
      <text x={300} y={H - 10} fill={L.amber} fontFamily={MONO} fontSize={22}>━ output across load</text>
    </svg>
  );
};

const PHASE_TEXT: Record<string, [string, string]> = {
  pos: ["POSITIVE HALF-CYCLE", "D1 + D2 conduct"], neg: ["NEGATIVE HALF-CYCLE", "D3 + D4 conduct"],
  dis: ["CAPACITOR DISCHARGING", "all diodes OFF · C feeds the load"], none: ["ZERO CROSSING", "no diode conducts"],
};

/** Circuit + live scope, cycle by cycle. props: cap (bool), cycles (shown in the scene), tau (bigger = bigger capacitor), focus. */
export const RectifierLab: React.FC<any> = ({ dur, cap = false, cycles = 2, start = 0, tau = 1.2, load = true, electrons = true, scope = true, ripple = false, slow = false, freeze }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const t = freeze !== undefined ? freeze : start + interpolate(f, [8, dur - 8], [0, cycles], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const s = simulate(t, cap, tau);
  const [ph, sub] = PHASE_TEXT[s.phase] || PHASE_TEXT.none;
  const ms = Math.round((t % 1) * 20 * 10) / 10;
  return (
    <AbsoluteFill style={{ flexDirection: tall ? "column" : "row", alignItems: "center", justifyContent: "center", padding: tall ? "16% 4% 22%" : "7% 3% 10%", gap: 20 * u }}>
      <div style={{ flex: tall ? "0 0 46%" : "0 0 50%", width: tall ? "100%" : undefined, height: tall ? undefined : "100%", position: "relative", opacity: fade(f, 2) }}>
        <Bridge s={s} withCap={cap} t={f / 30} showLoad={load} electrons={electrons} />
      </div>
      {scope && <div style={{ flex: 1, width: tall ? "100%" : undefined, display: "flex", flexDirection: "column", gap: 14 * u, opacity: fade(f, 10) }}>
        <div style={{ fontFamily: MONO, color: s.phase === "dis" ? L.amber : L.green, fontSize: 34 * u, fontWeight: 700, letterSpacing: 2 * u }}>{ph}</div>
        <div style={{ fontFamily: MONO, color: L.text, fontSize: 24 * u }}>{sub}{slow ? `   ·   t = ${ms} ms of 20 ms` : ""}</div>
        <div style={{ height: tall ? 480 * u * 0.75 : 420 * u }}><Scope upTo={t} cycles={Math.max(1, Math.ceil(start + cycles))} withCap={cap} tau={tau} showRect={cap} ripple={ripple} /></div>
        {electrons && <div style={{ fontFamily: MONO, color: L.electron, fontSize: 20 * u }}>● electrons (they flow from − to +, opposite to conventional current)</div>}
      </div>}
    </AbsoluteFill>
  );
};

/** Just the scope, big: compare waveforms (ac, full-wave, filtered with small/big capacitor). */
export const WaveLab: React.FC<any> = ({ dur, cap = false, tau = 1.2, cycles = 3, title = "OSCILLOSCOPE", label, ripple = false }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const t = interpolate(f, [6, dur * 0.8], [0, cycles], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: tall ? "18% 4%" : "8% 10% 12%" }}>
      {label && <div style={{ fontFamily: MONO, color: L.amber, fontSize: 40 * u, fontWeight: 700, marginBottom: 20 * u, opacity: fade(f, 0) }}>{label}</div>}
      <div style={{ width: "100%", height: tall ? "60%" : "78%" }}><Scope upTo={t} cycles={cycles} withCap={cap} tau={tau} showRect={cap} ripple={ripple} title={title} /></div>
    </AbsoluteFill>
  );
};

/** Close-up of a capacitor: electrons pile onto one plate while charging, leave while discharging. mode: charge | discharge | cycle */
export const CapLab: React.FC<any> = ({ dur, mode = "cycle" }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const p = prog(f, 10, dur - 10, ease);
  const q = mode === "charge" ? p : mode === "discharge" ? 1 - 0.45 * p : (p < 0.5 ? p * 2 : 1 - 0.45 * (p - 0.5) * 2);
  const n = Math.round(q * 28);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <svg viewBox="0 0 1000 700" width={1300 * u} height={900 * u} style={{ opacity: fade(f, 2) }}>
        <rect x={300} y={140} width={400} height={26} rx={6} fill={L.amber} />
        <rect x={300} y={500} width={400} height={26} rx={6} fill={L.amber} />
        <rect x={300} y={166} width={400} height={334} fill="rgba(255,181,71,0.05)" stroke={L.amber} strokeOpacity={0.25} strokeDasharray="8 8" />
        <text x={500} y={340} fill={L.dim} fontFamily={MONO} fontSize={28} textAnchor="middle">insulator (no current flows through)</text>
        <line x1={500} y1={40} x2={500} y2={140} stroke={L.wire} strokeWidth={6} /><line x1={500} y1={526} x2={500} y2={640} stroke={L.wire} strokeWidth={6} />
        {Array.from({ length: 28 }, (_, i) => i < n && <circle key={i} cx={320 + (i % 14) * 28} cy={548 + Math.floor(i / 14) * 24} r={9} fill={L.electron} />)}
        {Array.from({ length: 28 }, (_, i) => i < n && <text key={i} x={320 + (i % 14) * 28} y={128 - Math.floor(i / 14) * 26} fill={L.red} fontFamily={MONO} fontSize={26} textAnchor="middle">+</text>)}
        <text x={725} y={150} fill={L.red} fontFamily={MONO} fontSize={30} fontWeight={700}>+ plate</text>
        <text x={725} y={184} fill={L.dim} fontFamily={MONO} fontSize={22}>electrons pulled away</text>
        <text x={725} y={512} fill={L.electron} fontFamily={MONO} fontSize={30} fontWeight={700}>− plate</text>
        <text x={725} y={546} fill={L.dim} fontFamily={MONO} fontSize={22}>electrons piled up</text>
        <rect x={60} y={200} width={60} height={300} rx={8} fill="none" stroke={L.dim} strokeWidth={4} />
        <rect x={64} y={496 - 292 * q} width={52} height={292 * q} rx={6} fill={L.amber} opacity={0.85} />
        <text x={90} y={540} fill={L.amber} fontFamily={MONO} fontSize={26} textAnchor="middle">{Math.round(q * 100)}%</text>
        <text x={90} y={180} fill={L.dim} fontFamily={MONO} fontSize={22} textAnchor="middle">stored</text>
      </svg>
    </AbsoluteFill>
  );
};

/** Pause & think: the narrator asks, the viewer gets a 3-2-1. With reveal=true it shows the answer. */
export const QuestionLab: React.FC<any> = ({ dur, q, options = [], reveal = false, answer = "", narration = "" }) => {
  const f = useCurrentFrame(); const { u } = useU();
  // while the voice explains "Option A ... Option B ...", that option lights up
  const talk = Math.max(1, dur - 102); const low = narration.toLowerCase();
  const marks = options.map((_: string, i: number) => low.indexOf(`option ${String.fromCharCode(97 + i)}`));
  let speaking = -1;
  if (!reveal) marks.forEach((m: number, i: number) => { if (m >= 0 && f >= (m / Math.max(1, low.length)) * talk) speaking = i; });
  if (f > talk) speaking = -1;
  const left = Math.max(1, 3 - Math.floor(interpolate(f, [dur - 95, dur - 5], [0, 3], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })));
  const norm = (x: string) => String(x).toLowerCase().replace(/[^a-z0-9]/g, "");
  const right = options.findIndex((o: string) => norm(o) === norm(answer) || (norm(answer).length > 2 && norm(o).includes(norm(answer))));
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center", padding: "0 10%" }}>
      <div style={{ fontFamily: MONO, color: reveal ? L.green : L.amber, letterSpacing: 8 * u, fontSize: 28 * u, fontWeight: 700, opacity: fade(f, 0) }}>{reveal ? "ANSWER" : "PAUSE & THINK"}</div>
      <div style={{ fontFamily: SANS, color: L.text, fontSize: 60 * u, fontWeight: 700, lineHeight: 1.2, marginTop: 30 * u, opacity: fade(f, reveal ? 0 : 6), transform: `translateY(${reveal ? 0 : rise(f, 6)}px)` }}>{q}</div>
      <div style={{ display: "flex", gap: 26 * u, marginTop: 50 * u, flexWrap: "wrap", justifyContent: "center" }}>
        {options.map((o: string, i: number) => {
          const ok = reveal && i === right; const dim = reveal && i !== right;
          const on = i === speaking;
          return <div key={i} style={{ fontFamily: MONO, fontSize: 30 * u, color: ok ? L.bg0 : on ? L.bg0 : L.cyan, background: ok ? L.green : on ? L.amber : "transparent",
            border: `${2 * u}px solid ${ok ? L.green : on ? L.amber : L.cyan}`, borderRadius: 12 * u, padding: `${14 * u}px ${26 * u}px`,
            boxShadow: on ? `0 0 ${30 * u}px ${L.amber}88` : "none",
            opacity: dim ? 0.35 : fade(f, reveal ? 0 : 20 + i * 8), transform: `scale(${ok ? interpolate(f, [0, 8, 14], [1, 1.12, 1.06], { extrapolateRight: "clamp" }) : 1})` }}>
            {ok ? "✓ " : `${String.fromCharCode(65 + i)}. `}{o}</div>;
        })}
      </div>
      {reveal && right < 0 && answer && <div style={{ marginTop: 40 * u, fontFamily: SANS, fontWeight: 800, fontSize: 52 * u, color: L.green }}>✓ {answer}</div>}
      {!reveal && <div style={{ marginTop: 50 * u, width: 110 * u, height: 110 * u, borderRadius: "50%", border: `${5 * u}px solid ${L.amber}`, color: L.amber, display: "flex",
        alignItems: "center", justifyContent: "center", fontFamily: MONO, fontSize: 60 * u, fontWeight: 700, opacity: fade(f, dur - 100) }}>{left}</div>}
    </AbsoluteFill>
  );
};

/** A formula that builds up, with what each symbol means and a worked example. */
export const FormulaLab: React.FC<any> = ({ formula, terms = [], example = [] }) => {
  const f = useCurrentFrame(); const { u } = useU();
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: "0 8%" }}>
      <div style={{ fontFamily: MONO, color: L.amber, fontSize: 92 * u, fontWeight: 700, opacity: fade(f, 4), transform: `scale(${interpolate(f, [0, 30], [1.12, 1], { extrapolateRight: "clamp" })})` }}>{formula}</div>
      <div style={{ display: "flex", gap: 40 * u, marginTop: 40 * u, flexWrap: "wrap", justifyContent: "center" }}>
        {terms.map(([k, v]: string[], i: number) => <div key={i} style={{ fontFamily: MONO, fontSize: 28 * u, color: L.text, opacity: fade(f, 16 + i * 9) }}>
          <span style={{ color: L.cyan, fontWeight: 700 }}>{k}</span> = {v}</div>)}
      </div>
      {example.length > 0 && <div style={{ marginTop: 60 * u, borderTop: `${2 * u}px solid ${L.grid2}`, paddingTop: 30 * u, textAlign: "center" }}>
        {example.map((line: string, i: number) => <div key={i} style={{ fontFamily: MONO, fontSize: 36 * u, color: i === example.length - 1 ? L.green : L.text,
          fontWeight: i === example.length - 1 ? 700 : 400, marginTop: 10 * u, opacity: fade(f, 45 + i * 22) }}>{line}</div>)}
      </div>}
    </AbsoluteFill>
  );
};

export const TitleLab: React.FC<any> = ({ kicker, title, subtitle }) => {
  const f = useCurrentFrame(); const { u } = useU();
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center", padding: "0 6%" }}>
      <div style={{ fontFamily: MONO, color: L.cyan, letterSpacing: 8 * u, fontSize: 26 * u, opacity: fade(f, 4) }}>{kicker}</div>
      <div style={{ fontFamily: SANS, fontWeight: 800, color: L.text, fontSize: Math.min(150, 2000 / Math.max(8, title.length)) * u, marginTop: 20 * u, letterSpacing: -2 * u,
        opacity: fade(f, 10, 16), transform: `translateY(${rise(f, 10)}px)` }}>{title}</div>
      <div style={{ width: interpolate(prog(f, 20, 50), [0, 1], [0, 520]) * u, height: 6 * u, background: `linear-gradient(90deg, ${L.cyan}, ${L.amber})`, margin: `${24 * u}px 0` }} />
      <div style={{ fontFamily: SANS, color: L.amber, fontSize: 46 * u, fontWeight: 600, opacity: fade(f, 34) }}>{subtitle}</div>
    </AbsoluteFill>
  );
};

/** Numbered steps / key points that appear one by one. */
export const StepsLab: React.FC<any> = ({ title, items = [], dur }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const gap = Math.max(12, (dur * 0.55) / Math.max(1, items.length));
  return (
    <AbsoluteFill style={{ justifyContent: "center", padding: "0 12%" }}>
      {title && <div style={{ fontFamily: MONO, color: L.cyan, fontSize: 32 * u, letterSpacing: 4 * u, fontWeight: 700, marginBottom: 30 * u, opacity: fade(f, 0) }}>{title.toUpperCase()}</div>}
      {items.map((it: string, i: number) => <div key={i} style={{ display: "flex", gap: 26 * u, alignItems: "baseline", marginTop: 22 * u, opacity: fade(f, 6 + i * gap), transform: `translateX(${rise(f, 6 + i * gap, 40)}px)` }}>
        <div style={{ fontFamily: MONO, color: L.amber, fontSize: 40 * u, fontWeight: 700, minWidth: 60 * u }}>{String(i + 1).padStart(2, "0")}</div>
        <div style={{ fontFamily: SANS, color: L.text, fontSize: 44 * u, fontWeight: 500, lineHeight: 1.25 }}>{it}</div>
      </div>)}
    </AbsoluteFill>
  );
};

export const OutroLab: React.FC<any> = ({ title, lines = [], cta = "Subscribe for the next lesson" }) => {
  const f = useCurrentFrame(); const { u } = useU();
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
      <div style={{ fontFamily: SANS, fontWeight: 800, color: L.text, fontSize: 96 * u, opacity: fade(f, 2) }}>{title}</div>
      {lines.map((l: string, i: number) => <div key={i} style={{ fontFamily: MONO, color: L.cyan, fontSize: 34 * u, marginTop: 18 * u, opacity: fade(f, 14 + i * 10) }}>✓ {l}</div>)}
      <div style={{ marginTop: 50 * u, fontFamily: MONO, color: L.bg0, background: L.amber, fontSize: 30 * u, fontWeight: 700, padding: `${14 * u}px ${30 * u}px`, borderRadius: 10 * u, opacity: fade(f, 40) }}>{cta}</div>
    </AbsoluteFill>
  );
};

/** First frame of a Short: the bold title (works as the Shorts thumbnail / Reel cover). */
export const CoverLab: React.FC<any> = ({ cover = "", cover_highlight = "" }) => {
  const { u } = useU();
  const words: string[] = String(cover).toUpperCase().replace(/[|:]/g, " ").split(/\s+/).filter(Boolean).slice(0, 5);
  const hi = String(cover_highlight).toUpperCase().replace(/\W/g, "");
  let key = words.findIndex((w) => hi && w.replace(/\W/g, "") === hi);
  if (key < 0) key = words.reduce((b, w, i) => (w.length > words[b].length ? i : b), 0);
  return (
    <AbsoluteFill style={{ justifyContent: "center", padding: "0 9%" }}>
      <div style={{ fontFamily: SANS, fontWeight: 900, fontSize: 118 * u, lineHeight: 0.98, letterSpacing: -3 * u, color: L.text }}>
        {words.map((w, i) => <div key={i} style={{ color: i === key ? L.amber : L.text }}>{w}</div>)}
      </div>
      <div style={{ marginTop: 40 * u, width: 200 * u, height: 16 * u, background: L.amber, borderRadius: 8 * u }} />
    </AbsoluteFill>
  );
};

export const LAB_SCENES: Record<string, React.FC<any>> = {
  cover: CoverLab,
  "lab-title": TitleLab, rectifier: RectifierLab, wave: WaveLab, capacitor: CapLab, question: QuestionLab,
  formula: FormulaLab, steps: StepsLab, "lab-outro": OutroLab,
};

// ------------------------------------------------------------------ thumbnail (1280x720 still)
const ICONS: Record<string, (c: string) => React.ReactNode> = {
  ece: (c) => <g fill="none" stroke={c} strokeWidth={14} strokeLinejoin="round"><path d="M40,160 L120,160" /><polygon points="120,100 120,220 220,160" /><line x1={228} y1={96} x2={228} y2={224} /><path d="M228,160 L320,160" />
    <path d="M30,300 Q85,220 140,300 T250,300 T360,300" stroke={c} opacity={0.6} /></g>,
  cse: (c) => <g fill={c} fontFamily="JetBrains Mono, monospace" fontWeight={700}><text x={190} y={230} fontSize={170} textAnchor="middle">{"</>"}</text></g>,
  cyber: (c) => <g fill="none" stroke={c} strokeWidth={16} strokeLinejoin="round"><path d="M190,40 L320,90 Q320,250 190,320 Q60,250 60,90 Z" /><rect x={140} y={160} width={100} height={80} rx={10} fill={c} /><path d="M160,160 V130 a30,30 0 0 1 60,0 V160" /></g>,
  ent: (c) => <g><rect x={30} y={90} width={320} height={130} rx={14} fill="none" stroke={c} strokeWidth={14} transform="rotate(-8 190 155)" />
    <text x={190} y={180} textAnchor="middle" fill={c} fontFamily="Inter, sans-serif" fontWeight={900} fontSize={64} transform="rotate(-8 190 155)">NEWS</text></g>,
};
/** Thumbnail = a real frame of the lesson's most visual scene + the clean bold title on top. */
export const ThumbLab: React.FC<{ ep: any; Scene?: React.FC<any>; scene?: any }> = ({ ep, Scene, scene }) => {
  setTheme(ep.theme);
  const words: string[] = String(ep.cover || ep.title || "").toUpperCase().replace(/[|:]/g, " ").split(/\s+/).filter(Boolean).slice(0, 5);
  const hi = String(ep.cover_highlight || "").toUpperCase().replace(/\W/g, "");
  let key = words.findIndex((w) => hi && w.replace(/\W/g, "") === hi);
  if (key < 0) key = words.reduce((b, w, i) => (w.length > words[b].length ? i : b), 0);
  const len = words.join(" ").length; const fs = len > 22 ? 96 : len > 16 ? 112 : 136;
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 60% 40%, ${L.bg1} 0%, ${L.bg0} 75%)`, overflow: "hidden" }}>
      {Scene && scene && <AbsoluteFill style={{ transform: "translateX(24%) scale(0.74)", transformOrigin: "60% 50%" }}><Scene {...scene} dur={scene.frames || 300} /></AbsoluteFill>}
      <AbsoluteFill style={{ background: `linear-gradient(90deg, ${L.bg0} 0%, ${L.bg0} 40%, ${L.bg0}00 56%)` }} />
      <div style={{ position: "absolute", left: 56, top: 50, border: `5px solid ${L.cyan}`, color: L.cyan, fontFamily: MONO, fontWeight: 700, fontSize: 30, padding: "6px 18px", letterSpacing: 3 }}>
        {ep.badge || L.badge}</div>
      <div style={{ position: "absolute", left: 56, top: 150, width: 560, fontFamily: SANS, fontWeight: 900, fontSize: fs, lineHeight: 0.98, letterSpacing: -3, color: L.text }}>
        {words.map((w, i) => <span key={i} style={{ color: i === key ? L.amber : L.text, display: "inline-block", marginRight: 22 }}>{w}</span>)}
        <div style={{ marginTop: 26, width: 220, height: 16, background: L.amber, borderRadius: 8 }} />
      </div>
    </AbsoluteFill>
  );
};
