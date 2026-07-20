import test from "node:test";
import assert from "node:assert/strict";
import {buildCardSvg} from "./card-renderer.js";


test("builds an exact 1080 x 1350 Chinese card", () => {
  const svg = buildCardSvg({
    themeText: "还记得第一次看到海的那一天吗？",
    coreText: "那一刻我终于放松下来",
    footerText: "2026.07.19 · 海边",
  });
  assert.match(svg, /width="1080" height="1350"/);
  assert.match(svg, /那一刻我终于放松下来/);
  assert.match(svg, /2026\.07\.19 · 海边/);
  assert.doesNotMatch(svg, /AI 生成背景/);
});


test("escapes user text and marks AI backgrounds", () => {
  const svg = buildCardSvg({
    themeText: "<script>alert(1)</script>",
    coreText: "保留原话",
    footerText: "",
    backgroundDataUrl: "data:image/png;base64,AAAA",
    aiGenerated: true,
  });
  assert.doesNotMatch(svg, /<script>/);
  assert.match(svg, /&lt;script&gt;/);
  assert.match(svg, /AI 生成背景/);
});
