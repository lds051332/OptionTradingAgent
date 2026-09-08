import brandIconLocal from "./assets/morgan-dashan-icon.png";
import brandMarkLocal from "./assets/morgan-dashan-mark.png";

/**
 * OSS 地址写这里。非空就用 URL，运行时不再请求对应的本地文件。
 * 留空则回退到仓库里的文件（`qrcode/` 仍 gitignore，仅本机 / Docker 构建时可选）。
 */
export const REMOTE_MEDIA = {
  qrWechat: "https://option-trading-agent.oss-cn-beijing.aliyuncs.com/wechat.jpg",
  qrAlipay: "https://option-trading-agent.oss-cn-beijing.aliyuncs.com/alipay.jpg",
  qrAddWechat: "https://option-trading-agent.oss-cn-beijing.aliyuncs.com/add_wechat.jpg",
  brandIcon: "https://option-trading-agent.oss-cn-beijing.aliyuncs.com/morgan-dashan-icon.png",
  brandMark: "https://option-trading-agent.oss-cn-beijing.aliyuncs.com/morgan-dashan-mark.png",
  favicon: "https://option-trading-agent.oss-cn-beijing.aliyuncs.com/morgan-dashan-icon.png",
  appleTouchIcon: "https://option-trading-agent.oss-cn-beijing.aliyuncs.com/morgan-dashan-icon.png",
};

function pick(remote: string, local: () => string | undefined): string | undefined {
  const url = remote.trim();
  if (url) return url;
  return local();
}

const qrAssets = import.meta.glob("../../qrcode/*.{png,jpg,jpeg,webp}", {
  eager: true,
  import: "default",
}) as Record<string, string>;

function localQr(stem: string): string | undefined {
  const want = stem.toLowerCase();
  for (const [key, url] of Object.entries(qrAssets)) {
    const base = key.replaceAll("\\", "/").split("/").pop()?.toLowerCase();
    if (!base) continue;
    const name = base.replace(/\.(png|jpe?g|webp)$/i, "");
    if (name === want || base === want) return url;
  }
  return undefined;
}

export const media = {
  qrWechat: pick(REMOTE_MEDIA.qrWechat, () => localQr("wechat")),
  qrAlipay: pick(REMOTE_MEDIA.qrAlipay, () => localQr("alipay")),
  qrAddWechat: pick(REMOTE_MEDIA.qrAddWechat, () => localQr("add_wechat")),
  brandIcon: pick(REMOTE_MEDIA.brandIcon, () => brandIconLocal) ?? brandIconLocal,
  brandMark: pick(REMOTE_MEDIA.brandMark, () => brandMarkLocal) ?? brandMarkLocal,
  favicon: pick(REMOTE_MEDIA.favicon, () => "/favicon.png") ?? "/favicon.png",
  appleTouchIcon: pick(REMOTE_MEDIA.appleTouchIcon, () => "/apple-touch-icon.png") ?? "/apple-touch-icon.png",
};

export function applyHeadIcons(): void {
  const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (icon) icon.href = media.favicon;
  const apple = document.querySelector<HTMLLinkElement>('link[rel="apple-touch-icon"]');
  if (apple) apple.href = media.appleTouchIcon;
}
