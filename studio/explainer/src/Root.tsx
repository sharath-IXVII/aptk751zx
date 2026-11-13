import React from "react";
import { AbsoluteFill, Audio, Composition, Sequence, staticFile, useCurrentFrame, interpolate } from "remotion";
import { Frame } from "./Frame";
import { Title, Ship, MapScene, Counter, Bars, Facts, Clock, Timeline, Quote, Outro, Depth, Valve, Silicon, Mosfet, Circuit, Binary } from "./scenes";
import { C, SERIF, SANS, fade } from "./theme";
import { LabFrame, LAB_SCENES, setTheme, ThumbLab } from "./lab";
import { DOMAIN_SCENES } from "./domains";
import { STORY_SCENES } from "./story";
import sample from "../episodes/titanic.json";

const FPS = 30;
const SCENES: Record<string, React.FC<any>> = { title: Title, ship: Ship, map: MapScene, counter: Counter, bars: Bars,
  facts: Facts, clock: Clock, timeline: Timeline, quote: Quote, outro: Outro, depth: Depth, valve: Valve, silicon: Silicon, mosfet: Mosfet, circuit: Circuit, binary: Binary };
const framesOf = (s: any) => s.frames || Math.round((s.narration.split(" ").length / 2.4 + 1.2) * FPS);

const shortScenes = (ep: any) => (ep.short_scenes || []).map((s: any, i: number) => ({ ...s, idx: `sh${i}` }));
const Film: React.FC<{ ep: any; pick?: number[]; hook?: string; short?: boolean }> = ({ ep, pick, hook, short }) => {
  const scenes = short && ep.short_scenes ? shortScenes(ep)
    : (pick ? pick.map((i) => ({ ...ep.scenes[i], idx: i })) : ep.scenes.map((s: any, i: number) => ({ ...s, idx: i })));
  if (short && ep.short_scenes) hook = undefined;  // a written Short opens on its own hook scene
  let at = hook ? 75 : 0;
  const lab = ep.style === "lab"; if (lab) setTheme(ep.theme);
  const all = scenes.reduce((a: number, s: any) => a + framesOf(s), 0) || 1;
  return (
    <AbsoluteFill style={{ background: C.bg0 }}>
      {hook && <Sequence durationInFrames={75}><Hook text={hook} tag={ep.tag} /></Sequence>}
      {scenes.map((s: any) => {
        const d = framesOf(s); const from = at; at += d; const Comp = LAB_SCENES[s.type] || DOMAIN_SCENES[s.type] || STORY_SCENES[s.type] || SCENES[s.type];
        return (
          <Sequence key={s.idx} from={from} durationInFrames={d}>
            {lab ? <LabFrame caption={s.narration} dur={d} scene={s} ep={ep} progress={(from + d) / all}><Comp {...s} dur={d} /></LabFrame>
                 : <Frame caption={s.narration} dur={d}><Comp {...s} dur={d} /></Frame>}
            {s.audio && <Audio src={staticFile(`audio/${s.audio_key || "s" + s.idx}.mp3`)} />}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const Hook: React.FC<{ text: string; tag?: string }> = ({ text, tag = "GETYR STUDIO" }) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: C.bg0, alignItems: "center", justifyContent: "center", textAlign: "center", padding: "0 8%" }}>
    <div style={{ fontFamily: SERIF, fontSize: 92, color: C.text, opacity: fade(f, 0, 12), transform: `scale(${interpolate(f, [0, 75], [1.1, 1])})` }}>{text}</div>
    <div style={{ fontFamily: SANS, fontSize: 34, letterSpacing: 8, color: C.gold, marginTop: 40, opacity: fade(f, 20) }}>{tag}</div>
  </AbsoluteFill>;
};

const total = (ep: any, pick?: number[], hook?: boolean, short?: boolean) =>
  short && ep.short_scenes ? ep.short_scenes.reduce((a: number, s: any) => a + framesOf(s), 0)
  : (pick ? pick.map((i) => ep.scenes[i]) : ep.scenes).reduce((a: number, s: any) => a + framesOf(s), hook ? 75 : 0);

// the most visual scene of the lesson becomes the thumbnail background
const VISUAL = ["rectifier", "code", "network", "story", "chart", "array", "terminal", "capacitor", "wave", "phone", "flow", "formula"];
const Thumb: React.FC<{ ep: any }> = ({ ep }) => {
  setTheme(ep.theme);
  const pick = (ep.scenes || []).map((s: any, i: number) => [VISUAL.indexOf(s.type), i]).filter(([r]: number[]) => r >= 0)
    .sort((a: number[], b: number[]) => a[0] - b[0] || a[1] - b[1])[0];
  const scene = pick ? { ...ep.scenes[pick[1]], frames: 300 } : null;
  const Scene = scene ? (LAB_SCENES[scene.type] || DOMAIN_SCENES[scene.type] || STORY_SCENES[scene.type]) : undefined;
  return <Sequence from={-200}><ThumbLab ep={ep} Scene={Scene} scene={scene} /></Sequence>;
};

export const Root: React.FC = () => (
  <>
    <Composition id="Thumbnail" component={Thumb as any} fps={FPS} width={1280} height={720} durationInFrames={1} defaultProps={{ ep: sample }} />
    <Composition id="Explainer" component={Film as any} fps={FPS} width={1920} height={1080} durationInFrames={total(sample)}
      defaultProps={{ ep: sample }} calculateMetadata={({ props }: any) => ({ durationInFrames: total(props.ep) })} />
    <Composition id="Short" component={Film as any} fps={FPS} width={1080} height={1920} durationInFrames={total(sample, sample.short, true)}
      defaultProps={{ ep: sample, pick: sample.short, hook: sample.short_hook }}
      calculateMetadata={({ props }: any) => ({ durationInFrames: total(props.ep, props.pick, !props.short, props.short) })} />
  </>
);
