#!/usr/bin/env node
// Agent 2 — Cut Mistakes & Repeats : candidate finder
// Scans a word-level transcript for likely mistakes the speaker would want gone:
//   - stutters / immediate word repeats ("the the", "I-I-I", "that that")
//   - retakes / duplicate sentences (a line re-recorded; keep the clean take)
//   - false starts (an abandoned phrase that restarts)
//
// This is MECHANICAL detection only. It proposes candidate cut ranges with rich
// context + a confidence + a default recommendation, but it does NOT decide.
// The agent reviews each candidate in context (review-gate) before apply-cuts
// renders anything.
//
// Input: any { words: [{ text, start, end, type? }] } transcript — typically
// Agent 1's <stem>.silence-transcript.json (so cuts land on the silenced timeline).
//
// Output (next to the transcript, or --out-dir):
//   <stem>.cut-candidates.json   structured candidates for the agent to review
//   <stem>.cut-candidates.md     human-readable proposal
//
// Usage:
//   node find-cut-candidates.mjs <transcript.json> [--out-dir dir]

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve, basename, extname } from "node:path";
import { argv, exit } from "node:process";

const args = argv.slice(2);
if (args.length === 0 || args.includes("--help")) {
  console.log("Usage: node find-cut-candidates.mjs <transcript.json> [--out-dir dir]");
  exit(args.length === 0 ? 1 : 0);
}
let transcriptArg = null, outDirArg = null;
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--out-dir") outDirArg = args[++i];
  else if (!transcriptArg) transcriptArg = args[i];
}
const transcriptPath = resolve(transcriptArg);
const transcript = JSON.parse(readFileSync(transcriptPath, "utf8"));
if (!Array.isArray(transcript.words)) { console.error("transcript has no words[]"); exit(1); }

function cleanToken(text) {
  return (text ?? "").toLowerCase().replace(/^[^a-z0-9$%]+|[^a-z0-9$%]+$/g, "");
}
function displayText(ws) {
  return ws.map((w) => w.text).join(" ").replace(/\s+([,.!?;:])/g, "$1");
}
function fmt(s) {
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${(s - m * 60).toFixed(2).padStart(5, "0")}`;
}

const words = transcript.words
  .filter((w) => (w.type ? w.type === "word" : true))
  .filter((w) => Number.isFinite(Number(w.start)) && Number.isFinite(Number(w.end)))
  .map((w, index) => ({ index, text: w.text, token: cleanToken(w.text), start: Number(w.start), end: Number(w.end) }));

if (words.length === 0) { console.error("no timed words"); exit(1); }

const candidates = [];
let cid = 0;
const ctx = (i, before = 6, after = 6) =>
  displayText(words.slice(Math.max(0, i - before), Math.min(words.length, i + after)));

// ---- 1) stutters / immediate repeats ----
for (let i = 1; i < words.length; i++) {
  const a = words[i - 1], b = words[i];
  if (!b.token || b.token.length < 1) continue;
  const closeGap = b.start - a.end < 0.5;
  if (a.token === b.token && closeGap) {
    candidates.push({
      id: `c${String(++cid).padStart(3, "0")}`,
      type: "stutter",
      confidence: "high",
      recommend: "cut",
      // remove the first utterance, keep the second
      cut: { start: Number(a.start.toFixed(3)), end: Number(b.start.toFixed(3)) },
      removes: a.text,
      keeps: b.text,
      context: ctx(i),
      note: `repeated "${a.token}"`,
    });
  }
}

// ---- 1b) restarted phrases inside one breath ("today I will show you, um, today I will show you three ...") ----
// The segment pass below only pairs stretches split by a pause over 0.85 s, so a quick restart without a real pause
// stays inside one segment and is never compared. Here: a run of 3+ words that is said again from its first word,
// within 6 s, is a false start; the cut runs from the first take to the start of the second, fillers included.
const FILLERS = new Set(["um", "uh", "er", "ah", "like"]);
for (let i = 0; i < words.length; i++) {
  if (!words[i].token || FILLERS.has(words[i].token)) continue;
  for (let j = i + 3; j < Math.min(words.length, i + 40) && words[j].start - words[i].start <= 6; j++) {
    let k = 0;
    while (i + k < j && j + k < words.length && words[i + k].token && words[i + k].token === words[j + k].token) k++;
    if (k < 3) continue;
    // Words between the end of the run and the restart: none (or only fillers) is a clean false start. A longer first
    // take is a retake said again with a change ("our conduit" then "the conduit"), but it is also how deliberate
    // repetition sounds ("we will fight on the beaches, we will fight on the ..."), so it needs a 4-word run, stays
    // within 12 words, and goes to the human review instead of the cut list.
    const between = words.slice(i + k, j).filter((w) => w.token && !FILLERS.has(w.token));
    if (between.length > 2 && (k < 4 || between.length > 12)) continue;
    const clean = between.length <= 2;
    candidates.push({
      id: `c${String(++cid).padStart(3, "0")}`,
      type: clean ? "false_start" : "retake",
      confidence: clean ? (k >= 4 ? "high" : "medium") : "medium",
      recommend: clean ? "cut" : "review",
      cut: { start: Number(words[i].start.toFixed(3)), end: Number(words[j].start.toFixed(3)) },
      removes: displayText(words.slice(i, j)),
      keeps: displayText(words.slice(j, Math.min(words.length, j + k + 3))),
      context: ctx(j),
      note: `"${displayText(words.slice(i, i + k))}" said again ${(words[j].start - words[i].start).toFixed(2)} s later`,
    });
    i = j - 1; // continue after the abandoned take
    break;
  }
}

// ---- build segments (for retake / false-start detection) ----
const segments = [];
let segStart = 0;
for (let i = 1; i < words.length; i++) {
  const prev = words[i - 1], cur = words[i];
  const gap = cur.start - prev.end;
  const elapsed = cur.end - words[segStart].start;
  const sentenceEnd = /[.!?]$/.test(prev.text ?? "");
  if (gap > 0.85 || (sentenceEnd && elapsed >= 7.5) || elapsed >= 16) {
    segments.push({ id: segments.length + 1, wordStart: segStart, wordEnd: i - 1, start: words[segStart].start, end: prev.end, text: displayText(words.slice(segStart, i)) });
    segStart = i;
  }
}
segments.push({ id: segments.length + 1, wordStart: segStart, wordEnd: words.length - 1, start: words[segStart].start, end: words.at(-1).end, text: displayText(words.slice(segStart)) });

const stop = new Set("a an and are as at be but by for from i if in is it of on or so that this to was we with you your they their there what when where why how like um uh".split(" "));
function signature(seg) {
  return seg.text.toLowerCase().replace(/[^a-z0-9\s$%]/g, " ").split(/\s+/).filter((t) => t.length > 2 && !stop.has(t)).slice(0, 18);
}
function jaccard(a, b) {
  const as = new Set(a), bs = new Set(b);
  let overlap = 0;
  for (const x of as) if (bs.has(x)) overlap++;
  return overlap / Math.max(1, new Set([...as, ...bs]).size);
}
const sigs = segments.map(signature);

// ---- 2) retakes / duplicate sentences (keep the later, cleaner take) ----
for (let i = 0; i < segments.length; i++) {
  for (let j = i + 1; j < Math.min(segments.length, i + 9); j++) {
    if (segments[j].start - segments[i].end > 75) break;
    const score = jaccard(sigs[i], sigs[j]);
    const sameOpening = sigs[i].slice(0, 4).filter((t, idx) => t === sigs[j][idx]).length >= 2;
    if (score >= 0.34 || (score >= 0.24 && sameOpening)) {
      const firstLen = segments[i].end - segments[i].start;
      // A short first take that restarts soon after reads as a false start.
      const isFalseStart = sameOpening && firstLen < 6 && segments[j].start - segments[i].end < 12;
      // Start the cut where the earlier take of the restarted line begins, not at the top of its segment: a segment
      // can hold a good sentence before the flubbed one, and cutting from the top deletes it. Find the last place in
      // segment i where segment j's first three words appear; without one, keep the segment start but only propose it.
      const head = words.slice(segments[j].wordStart, segments[j].wordStart + 3).map((w) => w.token);
      let from = -1;
      for (let p = segments[i].wordEnd - head.length + 1; p >= segments[i].wordStart; p--) {
        if (head.every((t, q) => words[p + q] && words[p + q].token === t)) { from = p; break; }
      }
      const cutFrom = from >= 0 ? from : segments[i].wordStart;
      candidates.push({
        id: `c${String(++cid).padStart(3, "0")}`,
        type: isFalseStart ? "false_start" : "retake",
        confidence: score >= 0.45 ? "high" : score >= 0.34 ? "medium" : "low",
        // a cut that also takes the segments between the two takes is never an automatic yes
        recommend: score >= 0.34 && from >= 0 && j === i + 1 ? "cut" : "review",
        score: Number(score.toFixed(3)),
        // remove the earlier take of the line up to the start of the cleaner restart
        cut: { start: Number(words[cutFrom].start.toFixed(3)), end: Number(segments[j].start.toFixed(3)) },
        // everything the cut takes, the segments between the two takes included
        removes: displayText(words.slice(cutFrom, segments[j].wordStart)),
        keeps: segments[j].text,
        gapBetween: Number((segments[j].start - segments[i].end).toFixed(2)),
        note: `seg ${segments[i].id} ~ seg ${segments[j].id} (jaccard ${score.toFixed(2)}${sameOpening ? ", same opening" : ""})`,
      });
    }
  }
}

// sort by time, de-dupe overlapping retake/false-start proposals (keep highest score)
candidates.sort((a, b) => a.cut.start - b.cut.start);
// Two rules can find the same flub (the in-breath pass and the segment pass). Where two proposals overlap by more
// than half of the shorter one, keep one: a "cut" over a "review", then the higher confidence, then the longer range.
// (This step was described here but not done, so duplicates reached the review and the proposed total counted twice.)
{
  const rank = (c) => (c.recommend === "cut" ? 10 : 0) + ({ high: 3, medium: 2, low: 1 }[c.confidence] ?? 0);
  const kept = [];
  for (const c of candidates) {
    const o = kept.findIndex((k) => {
      const ov = Math.min(k.cut.end, c.cut.end) - Math.max(k.cut.start, c.cut.start);
      return ov > 0.5 * Math.min(k.cut.end - k.cut.start, c.cut.end - c.cut.start);
    });
    if (o < 0) { kept.push(c); continue; }
    const k = kept[o];
    if (rank(c) > rank(k) || (rank(c) === rank(k) && c.cut.end - c.cut.start > k.cut.end - k.cut.start)) kept[o] = c;
  }
  candidates.length = 0;
  candidates.push(...kept);
}

const byType = candidates.reduce((m, c) => ((m[c.type] = (m[c.type] || 0) + 1), m), {});
const totalProposed = candidates.filter((c) => c.recommend === "cut").reduce((s, c) => s + (c.cut.end - c.cut.start), 0);

const stem = basename(transcriptPath, extname(transcriptPath)).replace(/[-.]?(silence-)?transcript.*$/i, "") || "source";
const outDir = outDirArg ? resolve(outDirArg) : dirname(transcriptPath);
mkdirSync(outDir, { recursive: true });

const out = {
  agent: "cut-mistakes",
  source_transcript: transcriptPath,
  word_count: words.length,
  segment_count: segments.length,
  counts: byType,
  proposed_cut_seconds: Number(totalProposed.toFixed(2)),
  candidates,
};
const jsonPath = join(outDir, `${stem}.cut-candidates.json`);
writeFileSync(jsonPath, JSON.stringify(out, null, 2));

const md = [
  "# Cut-Mistakes Candidates",
  "",
  `Transcript: ${basename(transcriptPath)} · ${words.length} words · ${segments.length} segments`,
  `Found: ${candidates.length} candidates (` + Object.entries(byType).map(([k, v]) => `${v} ${k}`).join(", ") + ")",
  `Default proposed cuts total ~${totalProposed.toFixed(1)}s. **Review before applying.**`,
  "",
  ...candidates.map((c) =>
    [
      `## ${c.id} · ${c.type} · ${c.confidence} · recommend: ${c.recommend}`,
      `cut ${fmt(c.cut.start)}–${fmt(c.cut.end)} (${(c.cut.end - c.cut.start).toFixed(2)}s) — ${c.note}`,
      "",
      `- removes: ${c.removes}`,
      c.keeps ? `- keeps:   ${c.keeps}` : null,
      c.context ? `- context: …${c.context}…` : null,
      "",
    ].filter(Boolean).join("\n")),
].join("\n");
writeFileSync(join(outDir, `${stem}.cut-candidates.md`), md);

console.log(JSON.stringify({ candidates: candidates.length, counts: byType, proposedCutSeconds: Number(totalProposed.toFixed(2)), outputs: { json: jsonPath, md: join(outDir, `${stem}.cut-candidates.md`) } }, null, 2));
