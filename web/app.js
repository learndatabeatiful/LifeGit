import {api} from "./api.js";
import {saveAndDownloadCard, svgPreviewUrl} from "./card-renderer.js";
import {
  buildImagePrompt,
  imageGenerationAvailable,
  textAiAvailable,
} from "./ai-actions.js";
import {sessionRecoveryTargets} from "./session-routing.js";

const app = document.querySelector("#app");
const state = {bootstrap: null, snapshot: null, view: "entry"};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function reset() {
  app.replaceChildren();
}

function showError(error) {
  let banner = app.querySelector(".error");
  if (!banner) {
    banner = element("p", "error");
    app.prepend(banner);
  }
  banner.textContent = error.message || "操作没有完成，请再试一次。";
  banner.tabIndex = -1;
  banner.focus();
}

const uniqueId = prefix => `${prefix}_${crypto.randomUUID().replaceAll("-", "")}`;

function showNotice(message) {
  const notice = element("p", "notice", message);
  app.prepend(notice);
  return notice;
}

async function waitForJob(jobId) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const job = await api.job(jobId);
    if (job.status === "completed") {
      state.snapshot = await api.session(state.snapshot.session.session_id);
      if (state.view === "card") await renderCardView();
      else renderCompletionView();
      return job;
    }
    if (job.status === "failed") {
      throw new Error(job.error?.message || "AI 增强没有完成");
    }
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
  showNotice("原文成果已完成，AI 增强将在 Agent 连接后继续。");
  return null;
}

async function requestAiJob(kind, fields) {
  const dialog = element("dialog", "privacy-dialog");
  const title = element("h2", "dialog-title", "先确认哪些内容可以交给 AI");
  const list = element("textarea", "answer-input");
  list.placeholder = "每行填写一个希望脱敏的名字、学校、公司或地点；可以留空。";
  list.rows = 5;
  const warning = element(
    "p",
    "why",
    "未列入脱敏清单的信息默认不会脱敏。确认后，下面选中的文字会交给当前 Agent 使用的模型处理。",
  );
  const preview = element("pre", "privacy-preview", "先预览，确认后才会创建 AI 任务。");
  const reviewId = uniqueId("prv");
  let reviewed = null;
  const previewButton = button("预览脱敏结果", async () => {
    if (reviewed) return;
    reviewed = await api.privacyReview(state.snapshot.session.session_id, {
      review_id: reviewId,
      fields,
      redactions: list.value.split("\n").map(item => item.trim()).filter(Boolean),
    });
    preview.textContent = JSON.stringify(reviewed.sanitized_fields, null, 2);
    confirmButton.disabled = false;
  }, "button secondary");
  const confirmButton = button("确认并交给 AI", async () => {
    if (!reviewed) return;
    await api.confirmPrivacy(state.snapshot.session.session_id, reviewId);
    const prefix = kind === "text_enhancement" ? "job_text" : "job_image";
    const jobId = uniqueId(prefix);
    await api.createJob(state.snapshot.session.session_id, {
      job_id: jobId,
      kind,
      privacy_review_id: reviewId,
    });
    dialog.close();
    dialog.remove();
    await waitForJob(jobId);
  }, "button primary");
  confirmButton.disabled = true;
  const cancelButton = button("只用原话", () => {
    dialog.close();
    dialog.remove();
  }, "button secondary");
  const actions = element("div", "actions");
  actions.append(previewButton, confirmButton, cancelButton);
  dialog.append(title, warning, list, preview, actions);
  document.body.append(dialog);
  dialog.addEventListener("cancel", () => dialog.remove(), {once: true});
  dialog.showModal();
  list.focus();
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

async function backgroundModel(projection) {
  const background = projection.background_image;
  if (!background) return {backgroundDataUrl: null, aiGenerated: false};
  const blob = await api.jobAsset(background.origin_job_id);
  return {backgroundDataUrl: await blobToDataUrl(blob), aiGenerated: true};
}

function button(label, action, className = "button") {
  const node = element("button", className, label);
  node.type = "button";
  node.addEventListener("click", async () => {
    node.disabled = true;
    try {
      await action();
    } catch (error) {
      showError(error);
    } finally {
      if (node.isConnected && !node.classList.contains("disabled")) node.disabled = false;
    }
  });
  return node;
}

function pageHeader(kicker, title, subtitle) {
  const fragment = document.createDocumentFragment();
  fragment.append(element("p", "kicker", kicker), element("h1", "page-title", title));
  if (subtitle) fragment.append(element("p", "subtitle", subtitle));
  return fragment;
}

function entryLabel(entryId) {
  return state.bootstrap.entries.find(item => item.id === entryId)?.label || entryId;
}

function renderEntryView() {
  reset();
  app.append(
    pageHeader(
      "写下你的人生片段",
      "今天，你想从哪里开始？",
      "不用想完整。先选一个最接近此刻的入口。",
    ),
  );
  const list = element("div", "entry-list");
  const {resumable, completed} = sessionRecoveryTargets(state.bootstrap.sessions);
  if (resumable) {
    const resume = button("继续上次的人生片段", async () => {
      state.snapshot = resumable.status === "paused"
        ? await api.resume(resumable.session_id)
        : await api.session(resumable.session_id);
      state.view = "question";
      renderQuestionView();
    }, "entry-card resume-card");
    resume.append(element("small", "entry-description", resumable.anchor));
    list.append(resume);
  }
  if (completed) {
    const reopen = button("查看最近完成的人生片段", async () => {
      state.snapshot = await api.session(completed.session_id);
      state.view = "completion";
      renderCompletionView();
    }, "entry-card completed-card");
    reopen.append(element("small", "entry-description", completed.anchor));
    list.append(reopen);
  }
  state.bootstrap.entries.forEach((entry, index) => {
    const item = button(entry.label, () => renderAnchorView(entry), "entry-card");
    item.prepend(element("span", "entry-number", `0${index + 1}`));
    item.append(element("small", "entry-description", entry.anchor_prompt));
    list.append(item);
  });
  app.append(
    list,
    element(
      "p",
      "privacy-note",
      "你的回答默认私密，只保存在你选择的 LifeGit 本地工作区。",
    ),
  );
}

function renderAnchorView(entry) {
  reset();
  const input = element("textarea", "answer-input");
  input.placeholder = entry.anchor_prompt;
  input.rows = 5;
  app.append(
    button("← 返回三个入口", renderEntryView, "text-button"),
    pageHeader(entry.label, entry.anchor_prompt, "一句话也可以。接下来只会再问你三个问题。"),
    input,
    button("开始记录 →", async () => {
      if (!input.value.trim()) return input.focus();
      const sessionId = `ses_${crypto.randomUUID().replaceAll("-", "")}`;
      state.snapshot = await api.start({
        session_id: sessionId,
        entry_id: entry.id,
        anchor: input.value.trim(),
      });
      state.view = "question";
      renderQuestionView();
    }, "button primary"),
  );
  input.focus();
}

function renderQuestionView() {
  const question = state.snapshot.next_question;
  if (!question) return renderReadyToCompleteView();
  reset();
  const input = element("textarea", "answer-input");
  input.rows = 6;
  const session = state.snapshot.session;
  const handled = Object.keys(session.answers).length + session.skipped_question_ids.length;
  app.append(
    element("p", "progress", `问题 ${handled + 1} / 3`),
    pageHeader(entryLabel(session.entry_id), question.prompt),
    element("p", "why", `为什么问：${question.why}`),
    input,
  );
  const actions = element("div", "actions");
  actions.append(
    button("跳过", async () => {
      state.snapshot = await api.answer(session.session_id, {
        question_id: question.id,
        skip: true,
      });
      renderQuestionView();
    }, "button secondary"),
    button("稍后继续", async () => {
      await api.pause(session.session_id);
      state.bootstrap = await api.bootstrap();
      state.view = "entry";
      renderEntryView();
    }, "button secondary"),
    button("保存并继续 →", async () => {
      if (!input.value.trim()) return input.focus();
      state.snapshot = await api.answer(session.session_id, {
        question_id: question.id,
        answer: input.value.trim(),
      });
      renderQuestionView();
    }, "button primary"),
  );
  app.append(actions);
  input.focus();
}

function renderReadyToCompleteView() {
  reset();
  app.append(
    pageHeader(
      "三个问题已经结束",
      "这段片段已经足够完整。",
      "先把它原样交还给你，不需要等待 AI。",
    ),
    button("生成我的人生片段 →", async () => {
      state.snapshot = await api.complete(state.snapshot.session.session_id);
      state.view = "completion";
      renderCompletionView();
    }, "button primary"),
  );
}

function renderCompletionView() {
  reset();
  const projection = state.snapshot.projection;
  app.append(
    pageHeader(
      "片段已保存在本地",
      "那一天，已经被你重新保存。",
      "下面是根据你的原话立即生成的结果。你可以先分享，也可以以后再继续。",
    ),
    element("blockquote", "core-quote", projection.card_copy.core_text),
    element("pre", "fragment", projection.local_fragment_markdown),
    element("h2", "section-title", "接下来，你想怎么做？"),
  );
  const exits = element("div", "exit-list");
  const choices = [
    ["生成可分享产物", "编辑一张适合保存和分享的文字卡", true, () => {
      state.view = "card";
      return renderCardView();
    }],
    ["模拟不同选择", "随后开放：从这个片段推演不同未来", false],
    ["回到那一天", "随后开放：在不改写事实的前提下重访", false],
    ["继续扩展", "随后开放：补充更多细节与人生关系", false],
  ];
  for (const [label, description, enabled, action] of choices) {
    const item = button(label, action || (() => {}), enabled ? "exit enabled" : "exit disabled");
    item.append(element("small", "exit-description", description));
    item.disabled = !enabled;
    exits.append(item);
  }
  app.append(exits);
  if (textAiAvailable(state.bootstrap.capabilities)) {
    app.append(
      button("AI 帮我提炼 3 个核心句", () => requestAiJob("text_enhancement", {
        anchor: state.snapshot.session.anchor,
        ...state.snapshot.session.answers,
      }), "button ai-button"),
    );
  }
}

async function renderCardView() {
  reset();
  const background = await backgroundModel(state.snapshot.projection);
  const copy = state.snapshot.projection.card_copy;
  const theme = element("input", "copy-input");
  const core = element("textarea", "copy-input");
  const footer = element("input", "copy-input");
  theme.value = copy.theme_text;
  core.value = copy.core_text;
  footer.value = copy.footer_text;
  theme.maxLength = 60;
  core.maxLength = 48;
  core.rows = 3;
  footer.maxLength = 40;
  const preview = element("div", "card-preview");
  const previewImage = element("img", "card-preview-image");
  previewImage.alt = "文字卡预览";
  preview.append(previewImage);
  const candidates = element("div", "candidate-list");
  const cardModel = () => ({
    themeText: theme.value || "你的主题",
    coreText: core.value || "你的原话",
    footerText: footer.value || "LIFEGIT · 私密人生片段",
    ...background,
  });
  const refreshPreview = () => {
    previewImage.src = svgPreviewUrl(cardModel());
  };
  for (const candidate of state.snapshot.projection.core_candidates) {
    candidates.append(button(candidate.text, () => {
      core.value = candidate.text;
      refreshPreview();
    }, "candidate"));
  }
  for (const input of [theme, core, footer]) input.addEventListener("input", refreshPreview);
  const form = element("div", "card-editor");
  for (const [label, input] of [["主题", theme], ["核心句", core], ["落款", footer]]) {
    const field = element("label", "field-label", label);
    field.append(input);
    form.append(field);
  }
  const saveCopy = async () => {
    state.snapshot.projection = await api.updateCard(
      state.snapshot.session.session_id,
      {
        theme_text: theme.value,
        core_text: core.value,
        footer_text: footer.value,
      },
    );
  };
  const cardActions = element("div", "actions");
  cardActions.append(
    button("只保存文字", async () => {
      await saveCopy();
      renderCardView();
    }, "button secondary"),
    button("保存并下载 PNG", async () => {
      await saveCopy();
      await saveAndDownloadCard(
        state.snapshot.session.session_id,
        cardModel(),
        api.exportCard,
      );
    }, "button primary"),
  );
  if (imageGenerationAvailable(state.bootstrap.capabilities)) {
    cardActions.append(
      button("生成 AI 背景", () => requestAiJob("image_background", {
        prompt: buildImagePrompt({
          theme_text: theme.value,
          core_text: core.value,
        }),
      }), "button ai-button"),
    );
  }
  app.append(
    button("← 返回人生片段", renderCompletionView, "text-button"),
    pageHeader("生成可分享产物", "编辑你的文字卡", "所有中文都由浏览器准确排版，不交给图片模型写字。"),
    preview,
    element("p", "field-heading", "从你的原话中选择"),
    candidates,
    form,
    cardActions,
  );
  refreshPreview();
}

async function start() {
  try {
    state.bootstrap = await api.bootstrap();
    renderEntryView();
  } catch (error) {
    reset();
    app.append(element("p", "error", error.message));
  }
}

start();
