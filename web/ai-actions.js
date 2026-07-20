export const imageGenerationAvailable = capabilities =>
  capabilities?.image_generation?.available === true;

export const textAiAvailable = capabilities =>
  capabilities?.text_ai?.available === true;

export function buildImagePrompt(cardCopy) {
  return [
    "为一张 4:5 人生记忆文字卡生成无文字的抽象背景。",
    "只使用色彩、光影、纸张肌理或物件意象；不要人物肖像、艺人形象、品牌标志和可读文字。",
    "不得冒充真实现场，不得添加用户没有提供的事件细节。",
    `主题情绪：${cardCopy.theme_text}`,
    `核心感受：${cardCopy.core_text}`,
  ].join("\n");
}
