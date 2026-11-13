// ENT "Sketchbook News": the story of what actually happened, told with ink-drawn characters on
// cream paper, a live news HUD, phone alerts, market charts and rubber-stamp words.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { SANS, fade, rise, prog, ease } from "./theme";
import { L, MONO } from "./lab";

const useU = () => {
  const { width, height } = useVideoConfig(); const tall = height > width;
  return { u: (Math.min(width, height) / 1080) * (tall ? 1.35 : 1), tall, width, height };
};
const INK = () => L.text;
const GROUND = 600;

// ------------------------------------------------------------------ news HUD (any story scene can show it)
export const Hud: React.FC<{ hud: any; dur: number }> = ({ hud, dur }) => {
  const f = useCurrentFrame(); const { u } = useU();
  if (!hud) return null;
  // the clock ticks forward a few minutes during the scene, like a live feed
  let time = hud.time || "";
  const m = /^(\d{1,2}):(\d{2})\s*(AM|PM)?$/i.exec(time);
  if (m && hud.tick !== false) {
    const add = Math.floor(interpolate(f, [0, dur], [0, hud.minutes ?? 2])); let mm = +m[2] + add, hh = +m[1];
    hh += Math.floor(mm / 60); mm %= 60; time = `${hh}:${String(mm).padStart(2, "0")}${m[3] ? " " + m[3].toUpperCase() : ""}`;
  }
  return (
    <div style={{ position: "absolute", left: 44 * u, top: 90 * u, fontFamily: MONO, color: INK(), opacity: fade(f, 0) }}>
      <div style={{ color: L.red, fontSize: 20 * u, letterSpacing: 4 * u, fontWeight: 700 }}>
        <span style={{ opacity: f % 30 < 18 ? 1 : 0.2 }}>●</span> {hud.date || "TODAY"}{hud.place ? ` · ${hud.place}` : ""}</div>
      <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: 76 * u, lineHeight: 1.05, letterSpacing: -2 * u }}>{time}</div>
      <div style={{ width: 300 * u, height: 2 * u, background: L.off, margin: `${8 * u}px 0` }} />
      {(hud.stats || []).map((s: string, i: number) => <div key={i} style={{ fontSize: 20 * u, letterSpacing: 2 * u, color: L.dim }}>
        {s.replace(/[▼▲]/g, "")}<span style={{ color: s.includes("▼") ? L.red : L.green, fontWeight: 700 }}>{s.includes("▼") ? " ▼" : s.includes("▲") ? " ▲" : ""}</span></div>)}
    </div>
  );
};

// ------------------------------------------------------------------ ink stick figure
type Pose = "stand" | "walk" | "point" | "shock" | "think" | "phone" | "sit" | "cheer" | "sad";
export const Figure: React.FC<{ pose?: Pose; x: number; y: number; s?: number; label?: string; t: number; flip?: boolean; prop?: string }> =
  ({ pose = "stand", x, y, s = 1, label, t, flip, prop }) => {
  const ink = INK(); const sw = 7;
  const bob = Math.sin(t * 0.12) * 3;
  const swing = pose === "walk" ? Math.sin(t * 0.3) * 22 : 0;
  // arm end points relative to the shoulder (0,-120)
  const arms: Record<string, [number[], number[]]> = {
    stand: [[-30, -60], [30, -60]], walk: [[-25 + swing, -60], [25 - swing, -60]], point: [[-28, -62], [70, -150]],
    shock: [[-60, -190], [60, -190]], think: [[-30, -60], [12, -150]], phone: [[-28, -62], [22, -148]],
    sit: [[-34, -78], [34, -78]], cheer: [[-55, -200 + Math.sin(t * 0.4) * 10], [55, -200 - Math.sin(t * 0.4) * 10]], sad: [[-20, -55], [20, -55]],
  };
  const [la, ra] = arms[pose] || arms.stand;
  const legs = pose === "sit" ? "M0,-60 L-40,-60 L-40,0 M0,-60 L40,-60 L40,0" :
    `M0,-60 L${-22 + swing},0 M0,-60 L${22 - swing},0`;
  const headY = pose === "sad" ? -152 : -160;
  return (
    <g transform={`translate(${x},${y + bob}) scale(${(flip ? -1 : 1) * s},${s})`}>
      <ellipse cx={0} cy={2} rx={46} ry={8} fill={ink} opacity={0.1} />
      <path d={legs} stroke={ink} strokeWidth={sw} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <line x1={0} y1={-60} x2={0} y2={-125} stroke={ink} strokeWidth={sw} strokeLinecap="round" />
      <path d={`M0,-118 L${la[0]},${la[1]} M0,-118 L${ra[0]},${ra[1]}`} stroke={ink} strokeWidth={sw} fill="none" strokeLinecap="round" />
      <circle cx={0} cy={headY} r={30} fill={L.bg0} stroke={ink} strokeWidth={sw} />
      {pose === "shock" && <><circle cx={-10} cy={headY - 4} r={4} fill={ink} /><circle cx={10} cy={headY - 4} r={4} fill={ink} /><ellipse cx={0} cy={headY + 12} rx={6} ry={8} fill={ink} /></>}
      {pose === "sad" && <path d={`M-10,${headY + 14} q10,-8 20,0`} stroke={ink} strokeWidth={4} fill="none" />}
      {pose === "cheer" && <path d={`M-10,${headY + 8} q10,10 20,0`} stroke={ink} strokeWidth={4} fill="none" />}
      {pose === "phone" && <rect x={14} y={-178} width={24} height={40} rx={5} fill={L.cyan} stroke={ink} strokeWidth={4} />}
      {prop === "briefcase" && <rect x={-58} y={-62} width={36} height={28} rx={4} fill="none" stroke={ink} strokeWidth={5} />}
      {prop === "mic" && <><line x1={70} y1={-150} x2={92} y2={-178} stroke={ink} strokeWidth={6} /><circle cx={96} cy={-184} r={10} fill={ink} /></>}
      {label && <text x={0} y={46} transform={flip ? "scale(-1,1)" : undefined} textAnchor="middle" fill={L.dim} fontFamily={MONO} fontSize={26} fontWeight={700}>{label.toUpperCase()}</text>}
    </g>
  );
};

const Bubble: React.FC<{ x: number; y: number; text: string; f: number }> = ({ x, y, text, f }) => {
  const shown = text.slice(0, Math.floor(f / 1.2)); const w = Math.min(560, 40 + text.length * 15);
  return <g opacity={fade(f, 0, 6)}>
    <rect x={x - w / 2} y={y - 120} width={w} height={90} rx={22} fill={L.panel} stroke={INK()} strokeWidth={5} />
    <path d={`M${x - 20},${y - 32} L${x - 4},${y} L${x + 8},${y - 32}`} fill={L.panel} stroke={INK()} strokeWidth={5} strokeLinejoin="round" />
    <rect x={x - 22} y={y - 36} width={34} height={8} fill={L.panel} />
    <text x={x} y={y - 64} textAnchor="middle" fill={INK()} fontFamily={SANS} fontSize={30} fontWeight={600}>{shown}</text>
  </g>;
};

const PROPS: Record<string, (ink: string) => React.ReactNode> = {
  desk: (ink) => <g transform="translate(0,-160)"><rect x={300} y={600} width={1000} height={18} fill={ink} /><line x1={340} y1={618} x2={340} y2={760} stroke={ink} strokeWidth={8} /><line x1={1260} y1={618} x2={1260} y2={760} stroke={ink} strokeWidth={8} /></g>,
  screen: (ink) => <g><rect x={1050} y={250} width={420} height={260} rx={12} fill="none" stroke={ink} strokeWidth={7} /><polyline points="1080,330 1160,360 1230,340 1300,430 1370,470 1440,480" fill="none" stroke={L.red} strokeWidth={8} /></g>,
  podium: (ink) => <g transform="translate(0,-160)"><path d="M720,760 L740,560 L860,560 L880,760 Z" fill="none" stroke={ink} strokeWidth={7} /><line x1={800} y1={560} x2={800} y2={520} stroke={ink} strokeWidth={5} /></g>,
  city: (ink) => <g opacity={0.35}>{[[100, 300], [230, 220], [380, 340], [1180, 260], [1320, 200], [1460, 320]].map(([x, h], i) =>
    <rect key={i} x={x} y={GROUND - h} width={110} height={h} fill="none" stroke={ink} strokeWidth={4} />)}</g>,
  rocket: (ink) => <g transform="translate(0,-160)"><path d="M1250,560 q40,-160 0,-300 q-40,140 0,300 Z" fill="none" stroke={ink} strokeWidth={7} /></g>,
};

/** A moment in the story: 1-3 characters, a prop, an optional speech bubble, the news HUD. */
export const StoryScene: React.FC<any> = ({ dur, figures = [], bubble, prop, hud, caption }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const n = Math.max(1, figures.length); const ink = INK();
  return (
    <AbsoluteFill>
      <svg viewBox="0 0 1600 900" width="100%" height="100%" style={{ position: "absolute", top: tall ? "12%" : 0 }}>
        <line x1={0} y1={GROUND} x2={1600} y2={GROUND} stroke={ink} strokeWidth={4} opacity={0.5} />
        {prop && PROPS[prop]?.(ink)}
        {figures.map((fg: any, i: number) => {
          const baseX = fg.x ?? (n === 1 ? 800 : 500 + (i * 600) / (n - 1));
          const x = fg.pose === "walk" ? baseX + interpolate(f, [0, dur], [-120, 120]) : baseX;
          return <g key={i} opacity={fade(f, i * 6)}><Figure pose={fg.pose} x={x} y={GROUND} s={1.45} label={fg.label} t={f + i * 20} flip={fg.flip} prop={fg.prop} /></g>;
        })}
        {bubble && figures[bubble.who ?? 0] && <Bubble x={(figures[bubble.who ?? 0].x ?? (n === 1 ? 800 : 500 + ((bubble.who ?? 0) * 600) / (n - 1))) + 60} y={GROUND - 300} text={bubble.text} f={f - 12} />}
      </svg>
      <Hud hud={hud} dur={dur} />
      {caption && <div style={{ position: "absolute", right: 60 * u, top: 90 * u, fontFamily: MONO, color: L.dim, fontSize: 22 * u }}>{caption}</div>}
    </AbsoluteFill>
  );
};

/** Phone with news alerts / messages / a market app. */
export const PhoneScene: React.FC<any> = ({ dur, app = "News", items = [], hud }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const per = (dur - 20) / Math.max(1, items.length);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 520 * u, height: 900 * u, borderRadius: 60 * u, border: `${10 * u}px solid ${INK()}`, background: L.panel, padding: `${70 * u}px ${28 * u}px`,
        transform: `rotate(${interpolate(f, [0, 20], [-6, -2], { extrapolateRight: "clamp" })}deg) translateY(${rise(f, 0, 60)}px)`, boxShadow: `0 ${30 * u}px ${60 * u}px rgba(0,0,0,0.12)` }}>
        <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: 34 * u, color: INK(), marginBottom: 24 * u }}>{app}</div>
        {items.map((it: any, i: number) => f >= 10 + i * per && <div key={i} style={{ background: it.alert ? L.red : L.bg1, color: it.alert ? "#fff" : INK(), borderRadius: 22 * u,
          padding: `${18 * u}px ${20 * u}px`, marginBottom: 18 * u, fontFamily: SANS, fontSize: 28 * u, lineHeight: 1.25, opacity: fade(f, 10 + i * per, 6),
          transform: `translateY(${rise(f, 10 + i * per, 20, 8)}px)` }}>
          {it.from && <div style={{ fontFamily: MONO, fontSize: 18 * u, opacity: 0.75, marginBottom: 6 * u }}>{it.from}</div>}{it.text}</div>)}
      </div>
      <Hud hud={hud} dur={dur} />
    </AbsoluteFill>
  );
};

/** A market / number chart drawn live with a counter: {"label": "SENSEX", "points": [82000, 81800, 80950], "unit": ""} */
export const ChartScene: React.FC<any> = ({ dur, label = "", points = [], unit = "", note, hud, bad = "down" }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const p = prog(f, 6, dur * 0.8, ease); const n = points.length;
  if (n < 2) return null;
  const lo = Math.min(...points), hi = Math.max(...points), span = hi - lo || 1;
  const X = (i: number) => 120 + (i / (n - 1)) * 1360, Y = (v: number) => 600 - ((v - lo) / span) * 380;
  const upto = p * (n - 1); const k = Math.floor(upto); const r = upto - k;
  const pts = points.slice(0, k + 1).map((v: number, i: number) => `${X(i)},${Y(v)}`);
  const cur = k < n - 1 ? points[k] + (points[k + 1] - points[k]) * r : points[n - 1];
  if (k < n - 1) pts.push(`${X(k + r)},${Y(cur)}`);
  const down = points[n - 1] < points[0]; const worse = bad === "up" ? !down : down; const c = worse ? L.red : L.green;
  const ch = ((cur - points[0]) / points[0]) * 100; const pct = unit === "%";
  const dec = Math.max(...points.map((v: number) => (String(v).split(".")[1] || "").length)); const shown = dec ? cur.toFixed(Math.min(2, dec)) : Math.round(cur).toLocaleString("en-IN");
  return (
    <AbsoluteFill>
      <svg viewBox="0 0 1600 900" width="100%" height="100%">
        {[0, 1, 2, 3].map((i) => <line key={i} x1={120} x2={1480} y1={220 + i * 153} y2={220 + i * 153} stroke={L.off} strokeDasharray="6 10" />)}
        <polyline points={pts.join(" ")} fill="none" stroke={c} strokeWidth={10} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={X(Math.min(upto, n - 1))} cy={Y(cur)} r={16} fill={c} />
      </svg>
      <div style={{ position: "absolute", right: 80 * u, top: 110 * u, textAlign: "right", fontFamily: SANS }}>
        <div style={{ fontFamily: MONO, color: L.dim, fontSize: 26 * u, letterSpacing: 4 * u }}>{label}</div>
        <div style={{ fontWeight: 800, fontSize: 96 * u, color: INK() }}>{shown}{unit}</div>
        <div style={{ fontWeight: 800, fontSize: 40 * u, color: c }}>{cur >= points[0] ? "▲" : "▼"} {pct ? `${Math.abs(cur - points[0]).toFixed(dec ? Math.min(2, dec) : 0)} pts` : `${Math.abs(ch).toFixed(2)}%`}</div>
      </div>
      {note && <div style={{ position: "absolute", left: 120 * u, top: 140 * u, maxWidth: "55%", fontFamily: SANS, fontWeight: 700, color: INK(), fontSize: 40 * u, opacity: fade(f, dur * 0.5) }}>{note}</div>}
      <Hud hud={hud} dur={dur} />
    </AbsoluteFill>
  );
};

/** Rubber-stamp word: BREAKING / WHY? / CONFIRMED... */
export const StampScene: React.FC<any> = ({ text = "BREAKING", sub, hud, dur }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const sc = interpolate(f, [0, 6, 10], [2.2, 0.92, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ transform: `rotate(-6deg) scale(${sc})`, border: `${10 * u}px solid ${L.red}`, color: L.red, fontFamily: SANS, fontWeight: 900,
        fontSize: 150 * u, letterSpacing: 6 * u, padding: `${10 * u}px ${44 * u}px`, borderRadius: 18 * u, opacity: Math.min(1, f / 4) * 0.92 }}>{text}</div>
      {sub && <div style={{ marginTop: 60 * u, fontFamily: SANS, fontWeight: 700, fontSize: 46 * u, color: INK(), opacity: fade(f, 14), maxWidth: "80%", textAlign: "center" }}>{sub}</div>}
      <Hud hud={hud} dur={dur} />
    </AbsoluteFill>
  );
};

export const STORY_SCENES: Record<string, React.FC<any>> = { story: StoryScene, phone: PhoneScene, chart: ChartScene, stamp: StampScene };
