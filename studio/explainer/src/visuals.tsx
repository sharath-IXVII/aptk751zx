// Visuals that can SHOW almost any topic:
//  image   - a real, freely licensed photo/diagram (Wikimedia Commons, fetched before render) with a slow zoom
//  screen  - an app window: the menu path is clicked step by step, a dialog opens, boxes tick, the cursor moves
//  diagram - labelled parts anywhere on the canvas, joined by arrows, highlighted one step at a time
import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { SANS, fade, rise, prog } from "./theme";
import { L, MONO } from "./lab";

const useU = () => {
  const { width, height } = useVideoConfig(); const tall = height > width;
  return { u: (Math.min(width, height) / 1080) * (tall ? 1.35 : 1), tall };
};

// ------------------------------------------------------------------ real image
export const ImageScene: React.FC<any> = ({ dur, src, label, credit, points = [] }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const z = interpolate(f, [0, dur], [1.0, 1.12]); const x = interpolate(f, [0, dur], [0, -2]);
  if (!src) return null;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: tall ? "16% 5% 18%" : "7% 6% 9%" }}>
      <div style={{ position: "relative", width: "100%", height: "100%", borderRadius: 24 * u, overflow: "hidden", border: `${3 * u}px solid ${L.off}`,
        boxShadow: `0 ${20 * u}px ${60 * u}px rgba(0,0,0,0.15)`, opacity: fade(f, 0, 10) }}>
        <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${z}) translateX(${x}%)` }} />
        {label && <div style={{ position: "absolute", left: 28 * u, top: 28 * u, background: L.panel, color: L.text, fontFamily: SANS, fontWeight: 800,
          fontSize: 40 * u, padding: `${10 * u}px ${22 * u}px`, borderRadius: 12 * u, opacity: fade(f, 8) }}>{label}</div>}
        {points.map((p: any, i: number) => <div key={i} style={{ position: "absolute", left: `${p.x}%`, top: `${p.y}%`, transform: "translate(-50%,-50%)",
          opacity: fade(f, 20 + i * 18) }}>
          <div style={{ width: 34 * u, height: 34 * u, borderRadius: "50%", border: `${5 * u}px solid ${L.amber}`, background: `${L.amber}55` }} />
          <div style={{ position: "absolute", left: 44 * u, top: -6 * u, whiteSpace: "nowrap", background: L.amber, color: "#fff", fontFamily: SANS, fontWeight: 800,
            fontSize: 28 * u, padding: `${4 * u}px ${12 * u}px`, borderRadius: 8 * u }}>{p.label}</div>
        </div>)}
        {credit && <div style={{ position: "absolute", right: 14 * u, bottom: 10 * u, color: "#fff", fontFamily: MONO, fontSize: 14 * u, textShadow: "0 1px 4px #000", opacity: 0.85 }}>{credit}</div>}
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ app screen walkthrough
export const ScreenScene: React.FC<any> = ({ dur, app = "App", menu = ["File", "Edit", "View", "Tools", "Help"], path = [], dialog, result }) => {
  const f = useCurrentFrame(); const { u } = useU();
  // timeline: menu clicks first, then the dialog with its checks, then the button, then the result
  const steps = path.length + (dialog ? 1 + (dialog.checks || []).length + 1 : 0);
  const per = (dur - 20) / Math.max(1, steps + 1); const k = Math.floor((f - 10) / per);
  const menuOpen = path.length && k >= 0 ? Math.min(path.length - 1, k) : -1;
  const dlg = dialog && k >= path.length; const dk = k - path.length - 1;
  const checks: string[] = dialog?.checks || [];
  const pressed = dialog && dk >= checks.length;
  // cursor target
  let cx = 600, cy = 400;
  if (menuOpen >= 0 && !dlg) { cx = 60 + Math.max(0, menu.indexOf(path[0])) * 120 + 40; cy = menuOpen === 0 ? 30 : 60 + menuOpen * 44; }
  if (dlg && dk >= 0 && dk < checks.length) { cx = 470; cy = 300 + dk * 56; }
  if (pressed) { cx = 860; cy = 300 + checks.length * 56 + 60; }
  const items = ["New", "Open", "Save", ...path.slice(1), "Print", "Exit"];
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <svg viewBox="0 0 1200 760" width="86%" height="80%" style={{ opacity: fade(f, 0) }}>
        <rect x={0} y={0} width={1200} height={760} rx={18} fill={L.panel} stroke={L.off} strokeWidth={3} />
        <rect x={0} y={0} width={1200} height={44} rx={18} fill={L.bg1} />
        <text x={600} y={30} textAnchor="middle" fill={L.dim} fontFamily={SANS} fontSize={20} fontWeight={700}>{app}</text>
        {menu.map((m: string, i: number) => <g key={i}>
          <rect x={60 + i * 120} y={48} width={110} height={36} rx={6} fill={path[0] === m && menuOpen >= 0 && !dlg ? L.cyan : "transparent"} />
          <text x={115 + i * 120} y={73} textAnchor="middle" fill={path[0] === m && menuOpen >= 0 && !dlg ? "#fff" : L.text} fontFamily={SANS} fontSize={22}>{m}</text></g>)}
        {menuOpen >= 1 && !dlg && <g>
          <rect x={60 + Math.max(0, menu.indexOf(path[0])) * 120} y={86} width={300} height={items.length * 44 + 10} rx={8} fill={L.panel} stroke={L.off} strokeWidth={2} />
          {items.map((it, i) => { const on = it === path[menuOpen]; const mx = 60 + Math.max(0, menu.indexOf(path[0])) * 120;
            return <g key={i}><rect x={mx + 4} y={92 + i * 44} width={292} height={40} rx={6} fill={on ? L.cyan : "transparent"} />
              <text x={mx + 20} y={119 + i * 44} fill={on ? "#fff" : L.text} fontFamily={SANS} fontSize={22}>{it}</text></g>; })}
        </g>}
        {dlg && <g opacity={Math.min(1, (f - (10 + path.length * per)) / 8)}>
          <rect x={300} y={160} width={600} height={checks.length * 56 + 200} rx={14} fill={L.panel} stroke={L.cyan} strokeWidth={3} />
          <text x={330} y={210} fill={L.text} fontFamily={SANS} fontSize={28} fontWeight={800}>{dialog.title || path[path.length - 1]}</text>
          {checks.map((c, i) => <g key={i}><rect x={330} y={282 + i * 56} width={30} height={30} rx={6} fill={dk >= i ? L.green : "transparent"} stroke={L.wire} strokeWidth={3} />
            {dk >= i && <path d={`M336,${298 + i * 56} l8,8 l14,-16`} stroke="#fff" strokeWidth={4} fill="none" />}
            <text x={380} y={306 + i * 56} fill={L.text} fontFamily={SANS} fontSize={24}>{c}</text></g>)}
          <rect x={760} y={282 + checks.length * 56 + 30} width={120} height={50} rx={10} fill={pressed ? L.green : L.cyan} />
          <text x={820} y={314 + checks.length * 56 + 30} textAnchor="middle" fill="#fff" fontFamily={SANS} fontSize={24} fontWeight={800}>{dialog.button || "OK"}</text>
        </g>}
        {pressed && result && <g opacity={fade(f, 10 + (steps) * per, 8)}><rect x={300} y={640} width={600} height={70} rx={12} fill={L.green} />
          <text x={600} y={684} textAnchor="middle" fill="#fff" fontFamily={SANS} fontSize={26} fontWeight={800}>✓ {result}</text></g>}
        <g transform={`translate(${interpolate(f % per, [0, 10], [cx - 30, cx], { extrapolateRight: "clamp" })},${cy})`}>
          <path d="M0,0 L0,34 L9,26 L16,42 L22,39 L15,24 L27,24 Z" fill="#111" stroke="#fff" strokeWidth={2} /></g>
      </svg>
      {path.length > 0 && <div style={{ position: "absolute", bottom: "6%", fontFamily: MONO, fontSize: 30 * u, color: L.text, background: L.panel, padding: `${8 * u}px ${20 * u}px`, borderRadius: 10 * u }}>
        {[...path, ...(dialog && (dialog.button || "OK") !== path[path.length - 1] ? [dialog.button || "OK"] : [])].join("  →  ")}</div>}
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ general labelled diagram
// parts: [{id, label, x, y, shape: box|circle|pill, icon?}] (x 0-100, y 0-100), arrows: [[from, to, label?]],
// steps: [{highlight: [ids], note}] shown one after another.
export const DiagramScene: React.FC<any> = ({ dur, title, parts = [], arrows = [], steps = [] }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const by: Record<string, any> = Object.fromEntries(parts.map((p: any) => [p.id, p]));
  const n = Math.max(1, steps.length); const per = (dur - 16) / n; const k = Math.min(n - 1, Math.max(0, Math.floor((f - 10) / per)));
  const hot: string[] = steps[k]?.highlight || [];
  const X = (v: number) => 80 + (v / 100) * 1440, Y = (v: number) => 120 + (v / 100) * 600;
  return (
    <AbsoluteFill>
      {title && <div style={{ position: "absolute", top: "10%", width: "100%", textAlign: "center", fontFamily: MONO, color: L.cyan, fontSize: 30 * u, letterSpacing: 4 * u }}>{title.toUpperCase()}</div>}
      <svg viewBox="0 0 1600 840" width="100%" height="100%">
        <defs><marker id="arr" viewBox="0 0 10 10" refX={9} refY={5} markerWidth={7} markerHeight={7} orient="auto"><path d="M0,0 L10,5 L0,10 z" fill={L.wire} /></marker></defs>
        {arrows.map(([a, b, lab]: any[], i: number) => { const A = by[a], B = by[b]; if (!A || !B) return null;
          const on = hot.includes(a) && hot.includes(b); const p = prog(f, 6 + i * 6, 26 + i * 6);
          const dx = X(B.x) - X(A.x), dy = Y(B.y) - Y(A.y), L2 = Math.hypot(dx, dy) || 1;
          const pad = (q: any) => (q.shape === "circle" ? 86 : Math.min(Math.abs(dx) / L2 > 0.5 ? Math.max(180, q.label.length * 17) / 2 + 10 : 58, 160));
          const sx = X(A.x) + (dx / L2) * pad(A), sy = Y(A.y) + (dy / L2) * pad(A), ex = X(B.x) - (dx / L2) * pad(B), ey = Y(B.y) - (dy / L2) * pad(B);
          const x1 = sx, y1 = sy, x2 = sx + (ex - sx) * p, y2 = sy + (ey - sy) * p;
          return <g key={i}><line x1={x1} y1={y1} x2={x2} y2={y2} stroke={on ? L.amber : L.wire} strokeWidth={on ? 7 : 4} markerEnd="url(#arr)" />
            {lab && <text x={(X(A.x) + X(B.x)) / 2} y={(Y(A.y) + Y(B.y)) / 2 - 14} textAnchor="middle" fill={on ? L.amber : L.dim} fontFamily={MONO} fontSize={24}>{lab}</text>}</g>; })}
        {parts.map((p: any, i: number) => { const on = hot.includes(p.id); const x = X(p.x), y = Y(p.y); const w = Math.max(180, p.label.length * 17);
          return <g key={p.id} opacity={fade(f, i * 4)}>
            {p.shape === "circle" ? <circle cx={x} cy={y} r={78} fill={on ? `${L.amber}33` : L.panel} stroke={on ? L.amber : L.cyan} strokeWidth={on ? 7 : 4} />
              : <rect x={x - w / 2} y={y - 48} width={w} height={96} rx={p.shape === "pill" ? 48 : 16} fill={on ? `${L.amber}33` : L.panel} stroke={on ? L.amber : L.cyan} strokeWidth={on ? 7 : 4} />}
            <text x={x} y={y + 10} textAnchor="middle" fill={L.text} fontFamily={SANS} fontSize={30} fontWeight={800}>{p.label}</text></g>; })}
      </svg>
      {steps[k]?.note && <div style={{ position: "absolute", bottom: "8%", width: "100%", textAlign: "center", fontFamily: SANS, fontWeight: 600, fontSize: 36 * u, color: L.text,
        opacity: fade((f - 10) % per, 0, 6) }}>{steps[k].note}</div>}
    </AbsoluteFill>
  );
};

export const VISUAL_SCENES: Record<string, React.FC<any>> = { image: ImageScene, screen: ScreenScene, diagram: DiagramScene };

// ------------------------------------------------------------------ installer walkthrough
// {"app": "KiCad 8", "site": "kicad.org/download", "pages": ["Welcome", "License agreement", "Choose location", "Installing", "Finish"],
//  "notes": ["...one short note per page..."]} - browser download first, then each wizard page, progress bar, finish.
export const InstallerScene: React.FC<any> = ({ dur, app = "App", site, pages = ["Welcome", "License", "Location", "Installing", "Finish"], notes = [] }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const all: string[] = site ? ["__download", ...pages] : pages;
  const per = (dur - 16) / Math.max(1, all.length); const k = Math.min(all.length - 1, Math.max(0, Math.floor((f - 8) / per)));
  const local = (f - 8 - k * per) / per; const page = all[k]; const note = notes.length >= all.length ? notes[k] : notes[site ? k - 1 : k];
  const isProg = /install|copy|progress/i.test(page) && !/finish/i.test(page);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <svg viewBox="0 0 1200 760" width="84%" height="78%" style={{ opacity: fade(f, 0) }}>
        {page === "__download" ? <g>
          <rect x={0} y={0} width={1200} height={760} rx={18} fill={L.panel} stroke={L.off} strokeWidth={3} />
          <rect x={20} y={16} width={1160} height={44} rx={22} fill={L.bg1} />
          <text x={50} y={46} fill={L.dim} fontFamily={MONO} fontSize={22}>🔒 {site}</text>
          <text x={600} y={250} textAnchor="middle" fill={L.text} fontFamily={SANS} fontSize={54} fontWeight={900}>{app}</text>
          <rect x={430} y={320} width={340} height={84} rx={16} fill={local > 0.5 ? L.green : L.cyan} />
          <text x={600} y={374} textAnchor="middle" fill="#fff" fontFamily={SANS} fontSize={30} fontWeight={800}>{local > 0.5 ? "✓ Downloaded" : "⬇ Download"}</text>
          <g transform={`translate(${interpolate(local, [0, 0.45], [880, 600], { extrapolateRight: "clamp" })},${interpolate(local, [0, 0.45], [620, 370], { extrapolateRight: "clamp" })})`}>
            <path d="M0,0 L0,34 L9,26 L16,42 L22,39 L15,24 L27,24 Z" fill="#111" stroke="#fff" strokeWidth={2} /></g>
        </g> : <g>
          <rect x={200} y={90} width={800} height={560} rx={16} fill={L.panel} stroke={L.cyan} strokeWidth={3} />
          <rect x={200} y={90} width={800} height={56} rx={16} fill={L.bg1} />
          <text x={230} y={126} fill={L.text} fontFamily={SANS} fontSize={24} fontWeight={800}>{app} Setup</text>
          <text x={240} y={220} fill={L.text} fontFamily={SANS} fontSize={40} fontWeight={900}>{page}</text>
          {isProg ? <g><rect x={240} y={330} width={720} height={36} rx={18} fill={L.bg1} />
            <rect x={240} y={330} width={720 * Math.min(1, local * 1.2)} height={36} rx={18} fill={L.green} />
            <text x={600} y={410} textAnchor="middle" fill={L.dim} fontFamily={MONO} fontSize={24}>{Math.round(Math.min(1, local * 1.2) * 100)}%</text></g>
           : /licen/i.test(page) ? <g>{[0, 1, 2, 3, 4].map((i) => <rect key={i} x={240} y={260 + i * 30} width={600 - i * 40} height={12} rx={6} fill={L.off} />)}
             <rect x={240} y={440} width={30} height={30} rx={6} fill={local > 0.4 ? L.green : "transparent"} stroke={L.wire} strokeWidth={3} />
             <text x={285} y={464} fill={L.text} fontFamily={SANS} fontSize={24}>I accept the agreement</text></g>
           : /location|folder|path/i.test(page) ? <g><rect x={240} y={300} width={560} height={50} rx={8} fill={L.bg0} stroke={L.off} strokeWidth={2} />
             <text x={256} y={334} fill={L.text} fontFamily={MONO} fontSize={22}>C:\Program Files\{app}</text>
             <rect x={820} y={300} width={140} height={50} rx={8} fill={L.bg1} /><text x={890} y={334} textAnchor="middle" fill={L.text} fontFamily={SANS} fontSize={22}>Browse…</text></g>
           : /finish|complete|done/i.test(page) ? <text x={600} y={380} textAnchor="middle" fill={L.green} fontFamily={SANS} fontSize={44} fontWeight={900}>✓ {app} is installed</text>
           : <text x={240} y={300} fill={L.dim} fontFamily={SANS} fontSize={26}>This wizard will install {app} on your computer.</text>}
          <rect x={800} y={570} width={160} height={52} rx={10} fill={L.cyan} opacity={local > 0.6 ? 1 : 0.85} />
          <text x={880} y={604} textAnchor="middle" fill="#fff" fontFamily={SANS} fontSize={24} fontWeight={800}>{/finish|complete/i.test(page) ? "Finish" : isProg ? "…" : "Next >"}</text>
          <text x={240} y={612} fill={L.dim} fontFamily={MONO} fontSize={20}>Step {site ? k : k + 1} of {pages.length}</text>
        </g>}
      </svg>
      {note && <div style={{ position: "absolute", bottom: "6%", maxWidth: "80%", textAlign: "center", fontFamily: SANS, fontWeight: 700, fontSize: 34 * u, color: L.text,
        background: L.panel, padding: `${10 * u}px ${24 * u}px`, borderRadius: 12 * u, opacity: fade(local * per, 0, 6) }}>{note}</div>}
    </AbsoluteFill>
  );
};

VISUAL_SCENES.installer = InstallerScene;
