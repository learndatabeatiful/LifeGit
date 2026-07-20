import test from "node:test";
import assert from "node:assert/strict";
import {buildImagePrompt, imageGenerationAvailable} from "./ai-actions.js";


test("shows image action only for an explicitly available capability", () => {
  assert.equal(imageGenerationAvailable({image_generation: {available: true}}), true);
  assert.equal(imageGenerationAvailable({image_generation: {available: false}}), false);
  assert.equal(imageGenerationAvailable({}), false);
});


test("requests an abstract no-text background and rejects false documentary framing", () => {
  const prompt = buildImagePrompt({
    theme_text: "第一次看到海的那一天",
    core_text: "那一刻我终于放松下来",
  });
  assert.match(prompt, /无文字/);
  assert.match(prompt, /抽象/);
  assert.match(prompt, /不得冒充真实现场/);
});
