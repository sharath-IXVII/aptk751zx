// Domain scenes for the GetYr templates: code (CSE), terminal + network (CYBERSEC), flow diagrams (all).
// Colours come from the channel theme in lab.tsx (L), so each channel keeps its own look.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { SANS, fade, rise, prog } from "./theme";
import { L, MONO } from "./lab";

const useU = () => {
  const { width, height } = useVideoConfig(); const tall = height > width;
  return { u: (Math.min(width, height) / 1080) * (tall ? 1.35 : 1), tall };
};

// --------------------------------------------------------------- code editor (CSE)
// props: lang, code (string with \n), steps: [{line, out?, note?}] -> the highlighted line moves step by step,
// output appears in the console, and an optional note explains the current line.
const KW = /\b(def|return|if|else|elif|for|while|in|import|from|class|int|void|public|static|new|let|const|function|print|range|True|False|None|and|or|not)\b/g;
const tokenize = (line: string) => {
  const parts: { t: string; c: string }[] = []; let last = 0;
  const re = /("[^"]*"|'[^']*'|#.*$|\/\/.*$|\b\d+\b|\b(?:def|return|if|else|elif|for|while|in|import|from|class|int|void|public|static|new|let|const|function|print|range|True|False|None|and|or|not)\b)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line))) {
    if (m.index > last) parts.push({ t: line.slice(last, m.index), c: L.text });
    const tok = m[0];
    const c = /^["']/.test(tok) ? L.amber : /^(#|\/\/)/.test(tok) ? L.dim : /^\d/.test(tok) ? L.red : L.cyan;
    parts.push({ t: tok, c }); last = m.index + tok.length;
  }
  if (last < line.length) parts.push({ t: line.slice(last), c: L.text });
  return parts;
};
void KW;

export const CodeLab: React.FC<any> = ({ dur, lang = "python", code = "", steps = [] }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const lines: string[] = code.split("\n");
  const typed = Math.floor(interpolate(f, [4, Math.min(dur * 0.3, 4 + lines.length * 7)], [0, lines.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const sStart = Math.min(dur * 0.3, 4 + lines.length * 7) + 6;
  const k = steps.length ? Math.min(steps.length - 1, Math.floor(interpolate(f, [sStart, dur - 10], [0, steps.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }))) : -1;
  const cur = k >= 0 && f >= sStart ? steps[k] : null;
  const outLines = k >= 0 && f >= sStart ? steps.slice(0, k + 1).filter((s: any) => s.out !== undefined).map((s: any) => s.out) : [];
  return (
    <AbsoluteFill style={{ flexDirection: tall ? "column" : "row", padding: tall ? "16% 5% 22%" : "8% 5% 11%", gap: 28 * u }}>
      <div style={{ flex: tall ? "0 0 55%" : "0 0 60%", background: L.panel, border: `${2 * u}px solid ${L.off}`, borderRadius: 16 * u, overflow: "hidden", opacity: fade(f, 0) }}>
        <div style={{ display: "flex", gap: 10 * u, padding: `${14 * u}px ${18 * u}px`, borderBottom: `${2 * u}px solid ${L.off}`, alignItems: "center" }}>
          {[L.red, L.amber, L.green].map((c, i) => <div key={i} style={{ width: 14 * u, height: 14 * u, borderRadius: "50%", background: c, opacity: 0.8 }} />)}
          <div style={{ fontFamily: MONO, color: L.dim, fontSize: 20 * u, marginLeft: 12 * u }}>main.{lang === "python" ? "py" : lang === "java" ? "java" : lang === "c" ? "c" : "js"}</div>
        </div>
        <div style={{ padding: `${18 * u}px 0`, fontFamily: MONO, fontSize: 30 * u, lineHeight: 1.55 }}>
          {lines.slice(0, typed).map((ln, i) => {
            const active = cur && cur.line === i + 1;
            return <div key={i} style={{ display: "flex", background: active ? L.hi : "transparent", borderLeft: `${5 * u}px solid ${active ? L.amber : "transparent"}`, paddingRight: 20 * u }}>
              <span style={{ color: L.dim, width: 64 * u, textAlign: "right", paddingRight: 20 * u, opacity: 0.6 }}>{i + 1}</span>
              <span style={{ whiteSpace: "pre" }}>{tokenize(ln).map((p, j) => <span key={j} style={{ color: p.c }}>{p.t}</span>)}</span>
            </div>;
          })}
          {typed < lines.length && <span style={{ marginLeft: 84 * u, color: L.cyan, opacity: f % 20 < 10 ? 1 : 0 }}>▋</span>}
        </div>
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20 * u }}>
        <div style={{ background: L.panel, border: `${2 * u}px solid ${L.off}`, borderRadius: 16 * u, padding: 20 * u, minHeight: 200 * u, opacity: fade(f, sStart - 10) }}>
          <div style={{ fontFamily: MONO, color: L.dim, fontSize: 20 * u, letterSpacing: 3 * u, marginBottom: 12 * u }}>OUTPUT</div>
          {outLines.map((o: string, i: number) => <div key={i} style={{ fontFamily: MONO, color: L.green, fontSize: 30 * u }}>{o}</div>)}
        </div>
        {cur?.note && <div style={{ fontFamily: SANS, color: L.text, fontSize: 32 * u, lineHeight: 1.35, borderLeft: `${5 * u}px solid ${L.amber}`, paddingLeft: 20 * u }}>
          <span style={{ fontFamily: MONO, color: L.amber, fontSize: 22 * u, display: "block", marginBottom: 6 * u }}>LINE {cur.line}</span>{cur.note}</div>}
        {cur?.vars && <div style={{ display: "flex", flexWrap: "wrap", gap: 14 * u }}>
          {Object.entries(cur.vars).map(([k2, v]: any) => <div key={k2} style={{ fontFamily: MONO, fontSize: 26 * u, border: `${2 * u}px solid ${L.cyan}`, borderRadius: 10 * u, padding: `${8 * u}px ${16 * u}px`, color: L.text }}>
            <span style={{ color: L.cyan }}>{k2}</span> = {String(v)}</div>)}
        </div>}
      </div>
    </AbsoluteFill>
  );
};

// --------------------------------------------------------------- array / memory boxes (CSE)
// props: values, steps: [{i, j?, note, swap?: true, done?: number[]}] - pointers i / j move, swaps animate.
export const ArrayLab: React.FC<any> = ({ dur, title, values = [], steps = [] }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const n = steps.length || 1; const per = (dur - 20) / n;
  const k = Math.min(n - 1, Math.max(0, Math.floor((f - 10) / per)));
  const local = (f - 10 - k * per) / per;
  // apply swaps up to the current step
  const arr = [...values]; for (let s = 0; s < k; s++) { const st = steps[s]; if (st?.swap) [arr[st.i], arr[st.j]] = [arr[st.j], arr[st.i]]; }
  const st = steps[k] || {}; const box = 130 * u, gap = 18 * u, W = values.length * (box + gap);
  const pos = (idx: number) => idx * (box + gap);
  const swapT = st.swap ? prog(local * per, per * 0.35, per * 0.8) : 0;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      {title && <div style={{ fontFamily: MONO, color: L.cyan, fontSize: 32 * u, letterSpacing: 4 * u, marginBottom: 60 * u, opacity: fade(f, 0) }}>{title.toUpperCase()}</div>}
      <div style={{ position: "relative", width: W, height: box + 140 * u }}>
        {arr.map((v: any, idx: number) => {
          let x = pos(idx); let y = 0;
          if (st.swap && (idx === st.i || idx === st.j)) { const other = idx === st.i ? st.j : st.i; x = pos(idx) + (pos(other) - pos(idx)) * swapT; y = -Math.sin(Math.PI * swapT) * 70 * u * (idx === st.i ? 1 : -1); }
          const done = (st.done || []).includes(idx);
          const hot = idx === st.i || idx === st.j;
          return <div key={idx} style={{ position: "absolute", left: x, top: y, width: box, height: box, borderRadius: 14 * u, display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: MONO, fontSize: 52 * u, fontWeight: 700, color: done ? L.bg0 : L.text, background: done ? L.green : hot ? L.hi : L.panel,
            border: `${3 * u}px solid ${hot ? L.amber : L.off}`, opacity: fade(f, idx * 3) }}>{v}</div>;
        })}
        {values.map((_: any, idx: number) => <div key={idx} style={{ position: "absolute", left: pos(idx), top: box + 10 * u, width: box, textAlign: "center", fontFamily: MONO, color: L.dim, fontSize: 22 * u }}>[{idx}]</div>)}
        {["i", "j"].map((p) => st[p] !== undefined && <div key={p} style={{ position: "absolute", left: pos(st[p]), top: box + 46 * u, width: box, textAlign: "center", fontFamily: MONO, color: L.amber, fontSize: 34 * u, fontWeight: 700 }}>▲ {p}</div>)}
      </div>
      {st.note && <div style={{ fontFamily: SANS, color: L.text, fontSize: 38 * u, marginTop: 40 * u, opacity: fade(local * per, 0, 8) }}>{st.note}</div>}
    </AbsoluteFill>
  );
};

// --------------------------------------------------------------- flow diagram (all channels)
// props: nodes: ["Input", "Process", ...] (left to right), active: index lit up step by step, notes per node.
export const FlowLab: React.FC<any> = ({ dur, title, nodes = [], notes = [] }) => {
  const f = useCurrentFrame(); const { u, tall } = useU();
  const n = nodes.length || 1; const per = (dur - 16) / n;
  const k = Math.min(n - 1, Math.max(0, Math.floor((f - 8) / per)));
  const tok = interpolate(f, [8, dur - 8], [0, n - 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: "0 5%" }}>
      {title && <div style={{ fontFamily: MONO, color: L.cyan, fontSize: 32 * u, letterSpacing: 4 * u, marginBottom: 50 * u, opacity: fade(f, 0) }}>{title.toUpperCase()}</div>}
      <div style={{ display: "flex", flexDirection: tall ? "column" : "row", alignItems: "center", gap: 0 }}>
        {nodes.map((nd: string, i: number) => <React.Fragment key={i}>
          <div style={{ minWidth: 220 * u, padding: `${28 * u}px ${24 * u}px`, borderRadius: 18 * u, textAlign: "center", fontFamily: SANS, fontWeight: 700, fontSize: 34 * u,
            color: i <= k ? L.text : L.dim, background: i === k ? L.hi : L.panel, border: `${3 * u}px solid ${i === k ? L.amber : i < k ? L.cyan : L.off}`,
            boxShadow: i === k ? `0 0 ${40 * u}px ${L.amber}55` : "none", opacity: fade(f, i * 6), transform: `translateY(${rise(f, i * 6)}px)` }}>{nd}</div>
          {i < n - 1 && <div style={{ position: "relative", width: tall ? 6 * u : 110 * u, height: tall ? 70 * u : 6 * u, background: i < k ? L.cyan : L.off }}>
            {Math.floor(tok) === i && <div style={{ position: "absolute", width: 22 * u, height: 22 * u, borderRadius: "50%", background: L.amber,
              left: tall ? -8 * u : `${(tok - i) * 100}%`, top: tall ? `${(tok - i) * 100}%` : -8 * u, boxShadow: `0 0 ${20 * u}px ${L.amber}` }} />}
          </div>}
        </React.Fragment>)}
      </div>
      {notes[k] && <div style={{ fontFamily: SANS, color: L.text, fontSize: 38 * u, marginTop: 60 * u, maxWidth: "80%", textAlign: "center", lineHeight: 1.35 }}>{notes[k]}</div>}
    </AbsoluteFill>
  );
};

// --------------------------------------------------------------- terminal (CYBERSEC)
// props: lines: [{cmd} | {out}] typed / printed in order; prompt text.
export const TerminalLab: React.FC<any> = ({ dur, lines = [], prompt = "student@lab:~$", title = "terminal" }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const per = (dur - 20) / Math.max(1, lines.length);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: "8% 8% 12%" }}>
      <div style={{ width: "100%", height: "100%", background: L.panel, border: `${2 * u}px solid ${L.off}`, borderRadius: 16 * u, overflow: "hidden", opacity: fade(f, 0) }}>
        <div style={{ padding: `${12 * u}px ${18 * u}px`, borderBottom: `${2 * u}px solid ${L.off}`, fontFamily: MONO, color: L.dim, fontSize: 20 * u }}>● ● ●  {title}</div>
        <div style={{ padding: 26 * u, fontFamily: MONO, fontSize: 30 * u, lineHeight: 1.5 }}>
          {lines.map((ln: any, i: number) => {
            const start = 10 + i * per; if (f < start) return null;
            if (ln.cmd !== undefined) {
              const shown = ln.cmd.slice(0, Math.floor((f - start) / 1.1));
              return <div key={i}><span style={{ color: L.cyan }}>{prompt} </span><span style={{ color: L.text }}>{shown}</span>
                {shown.length < ln.cmd.length && <span style={{ color: L.cyan }}>▋</span>}</div>;
            }
            return <div key={i} style={{ color: ln.bad ? L.red : ln.good ? L.green : L.dim, whiteSpace: "pre-wrap", opacity: fade(f, start, 6) }}>{ln.out}</div>;
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// --------------------------------------------------------------- network (CYBERSEC)
// props: nodes: [{id, label, x, y, kind: attacker|server|router|user|firewall}], links: [[a,b]],
// packets: [{from, to, label, bad?, blocked?}] sent one after another.
const ICON: Record<string, string> = { attacker: "☠", server: "▤", router: "⇄", user: "☺", firewall: "▦", db: "◉", cloud: "☁" };
export const NetworkLab: React.FC<any> = ({ dur, nodes = [], links = [], packets = [], title }) => {
  const f = useCurrentFrame(); const { u } = useU();
  const by: Record<string, any> = Object.fromEntries(nodes.map((n: any) => [n.id, n]));
  const per = (dur - 20) / Math.max(1, packets.length);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      {title && <div style={{ position: "absolute", top: "11%", fontFamily: MONO, color: L.cyan, fontSize: 30 * u, letterSpacing: 4 * u }}>{title.toUpperCase()}</div>}
      <svg viewBox="0 0 1600 800" width="88%" height="72%">
        {links.map(([a, b]: string[], i: number) => <line key={i} x1={by[a].x} y1={by[a].y} x2={by[b].x} y2={by[b].y} stroke={L.off} strokeWidth={5} strokeDasharray="14 10" />)}
        {packets.map((p: any, i: number) => {
          const t0 = 10 + i * per; const t = (f - t0) / (per * 0.75); if (t < 0 || t > 1.25) return null;
          const A = by[p.from], B = by[p.to]; const stop = p.blocked ? 0.62 : 1; const tt = Math.min(stop, t);
          const x = A.x + (B.x - A.x) * tt, y = A.y + (B.y - A.y) * tt; const c = p.bad ? L.red : L.green;
          return <g key={i}>
            <rect x={x - 70} y={y - 26} width={140} height={52} rx={10} fill={L.panel} stroke={c} strokeWidth={4} />
            <text x={x} y={y + 9} textAnchor="middle" fill={c} fontFamily={MONO} fontSize={24} fontWeight={700}>{p.label}</text>
            {p.blocked && t >= stop && <text x={x} y={y - 44} textAnchor="middle" fill={L.red} fontFamily={MONO} fontSize={30} fontWeight={700}>✕ BLOCKED</text>}
          </g>;
        })}
        {nodes.map((n: any, i: number) => <g key={n.id} opacity={fade(f, i * 5)}>
          <circle cx={n.x} cy={n.y} r={70} fill={L.panel} stroke={n.kind === "attacker" ? L.red : L.cyan} strokeWidth={5} />
          <text x={n.x} y={n.y + 22} textAnchor="middle" fill={n.kind === "attacker" ? L.red : L.cyan} fontSize={60}>{ICON[n.kind] || "●"}</text>
          <text x={n.x} y={n.y + 116} textAnchor="middle" fill={L.text} fontFamily={MONO} fontSize={28} fontWeight={700}>{n.label}</text>
        </g>)}
      </svg>
    </AbsoluteFill>
  );
};

export const DOMAIN_SCENES: Record<string, React.FC<any>> = { code: CodeLab, array: ArrayLab, flow: FlowLab, terminal: TerminalLab, network: NetworkLab };
