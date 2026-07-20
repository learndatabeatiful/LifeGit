const WIDTH = 1080;
const HEIGHT = 1350;

const escapeXml = value => String(value).replace(/[&<>"']/g, char => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&apos;",
})[char]);

const lines = (value, width = 12) => {
  const chars = Array.from(String(value).trim());
  const result = [];
  for (let index = 0; index < chars.length; index += width) {
    result.push(chars.slice(index, index + width).join(""));
  }
  return result.length ? result : [""];
};

const tspans = (value, x, startY, gap, width = 12) => lines(value, width)
  .map((line, index) => (
    `<tspan x="${x}" y="${startY + index * gap}">${escapeXml(line)}</tspan>`
  ))
  .join("");

export function buildCardSvg({
  themeText,
  coreText,
  footerText,
  backgroundDataUrl = null,
  aiGenerated = false,
}) {
  const safeBackground = /^data:image\/(png|jpeg|webp);base64,/.test(backgroundDataUrl || "")
    ? `<image href="${escapeXml(backgroundDataUrl)}" width="1080" height="1350" preserveAspectRatio="xMidYMid slice" opacity="0.38"/>`
    : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
<rect width="1080" height="1350" fill="#06101f"/>${safeBackground}
<circle cx="944" cy="112" r="286" fill="#bf3840" opacity=".12"/>
<rect x="0" y="0" width="10" height="1350" fill="#df474c"/>
<text x="92" y="74" fill="#df474c" font-size="24" font-weight="700" letter-spacing="5" font-family="PingFang SC,Microsoft YaHei,sans-serif">LIFEGIT · 人生片段</text>
<text fill="#c2cad5" font-size="29" font-family="PingFang SC,Microsoft YaHei,sans-serif">${tspans(themeText, 92, 150, 42, 30)}</text>
<path d="M92 620 C220 602 330 640 476 615" stroke="#bf3840" stroke-width="24" stroke-linecap="round" opacity=".88"/>
<text fill="#f2f5f8" font-size="78" font-weight="700" font-family="Songti SC,STSong,serif">${tspans(coreText, 92, 735, 112)}</text>
<text x="92" y="1248" fill="#8290a3" font-size="27" font-family="PingFang SC,Microsoft YaHei,sans-serif">${escapeXml(footerText)}</text>
${aiGenerated ? '<text x="844" y="1248" fill="#8290a3" font-size="24" font-family="sans-serif">AI 生成背景</text>' : ""}
</svg>`;
}

export async function renderCardPng(model) {
  const svg = buildCardSvg(model);
  const source = URL.createObjectURL(
    new Blob([svg], {type: "image/svg+xml;charset=utf-8"}),
  );
  try {
    const image = new Image();
    image.src = source;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = WIDTH;
    canvas.height = HEIGHT;
    canvas.getContext("2d").drawImage(image, 0, 0, WIDTH, HEIGHT);
    return await new Promise((resolve, reject) => canvas.toBlob(
      blob => blob ? resolve(blob) : reject(new Error("PNG 生成失败")),
      "image/png",
    ));
  } finally {
    URL.revokeObjectURL(source);
  }
}

export function svgPreviewUrl(model) {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(buildCardSvg(model))}`;
}

export async function saveAndDownloadCard(sessionId, model, exportCard) {
  const blob = await renderCardPng(model);
  const saved = await exportCard(sessionId, blob);
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = saved.filename;
    document.body.append(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
  return saved;
}
