# Electron 客户端运行时 Hook 与补丁

和 `Electron 客户端逆向` 的区别：那篇是「读凭据、脚本调接口」（被动提取）；这篇是「改客户端运行时行为」（主动注入），用于击败客户端的本地许可校验、试用限制、接口签名验证。

**流程**：找注入入口 → 在 app 主逻辑加载前注入 Hook → 按目标选 Hook 点（加密原语 / 网络通道 / 注册表）→ 验证。

---

## 一、注入入口在哪

- asar 打包：代码在 `resources/app.asar`，需 extract 后改入口再 repackage；或直接改解包后的 `resources/app/`。
- 已解包：入口常是 `resources/app/launch.js` 或 `launch.dist.js`，**不是** `app.asar`。先 `ls resources/` 确认形态，别默认 asar。
- 注入位置：必须在 app 主逻辑加载**之前**执行你的 Hook（文件顶部，或 preload）。Hook 设晚了，校验已经跑完。
- 留后路：原文件存 `.bak`；必要时用 `fs` 重定向让 app 读 `.bak`，而你的 Hook 代码先跑。

---

## 二、Hook 加密原语绕过 RSA 许可校验

很多 JS 许可校验用 `crypto.publicDecrypt`（或 `privateDecrypt`）解密 license blob 并验签。

```js
const origPublic = crypto.publicDecrypt;
crypto.publicDecrypt = function (key, buf) {
  // 返回伪造的明文 license entity（日期必须运行时动态生成）
  return Buffer.from(JSON.stringify({ date: new Date().toISOString().slice(0, 10), /* 其余字段 */ }));
};
// 部分版本用 privateDecrypt，同样 Hook
if (crypto.privateDecrypt) { /* 同上 */ }
```

要点：
- `entity.date` 必须**运行时动态生成**（用当天日期），不能写死激活当天的静态值，否则次日过期。
- Hook 必须在 `require` 主逻辑前完成。

---

## 三、拦截网络要走两条通道，且要覆盖主进程

客户端的许可/续订 API 常由主进程发起，不止渲染进程。

1. **渲染进程**：`protocol.handle("https", handler)` 能拦。但它**只覆盖渲染进程**的 fetch/navigation，拦不住主进程直接发请求。
2. **主进程 fetch**：`electron.net.fetch` 也要 Hook。
3. **关键坑 — electron-fetch**：若 app 用 `electron-fetch` 模块，Electron 环境里 `useElectronNet = Boolean(process.versions.electron)` 为真，它走 `electron.net.request`，**不是** `net.fetch`。所以只 Hook `electron.net.fetch` 会漏掉这批请求（实测：某 Electron 35.x 客户端每 12h 用 electron-fetch 续订 license，仅 Hook fetch 时续订绕过拦截 → license 被撤销 → 进入试用期）。

```js
const origReq = electron.net.request.bind(electron.net);
electron.net.request = function (options, cb) {
  const url = typeof options === "string" ? options : options.url;
  if (url && url.includes("/api/client/")) {
    // 返回伪造的 ClientRequest + IncomingMessage 事件流，复刻目标字段
    return makeFakeRequest();
  }
  return origReq(options, cb);
};
```

要点：
- 同时 Hook `electron.net.fetch` 和 `electron.net.request`，缺一个就漏。
- 伪造响应要复刻目标接口返回的字段结构（entity / msg 等），否则 app 解析失败仍判失效。

---

## 四、反制二次验证（注册表被清）

有些 app 有概率性/定时的本地二次验证：用**纯 JS** 验 license 签名（不走 crypto API），失败就 `onUnfill` → 清空注册表/文件里的 license。

反制：看门狗 `setInterval` 周期性把 license 写回。

```js
function restore() {
  // 读注册表/文件，缺失或无效就写回固定 license 值
}
restore();                       // 启动先跑一次，防首屏已空
setInterval(restore, 2000);      // 周期按 app 二次验证频率调，2-30s
```

要点：
- 启动时先 `restore()` 一次。
- 周期要短于 app 二次验证触发间隔，否则会有一瞬间空窗弹窗。

---

## 五、避坑表

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 默认入口是 app.asar | 改了 asar 发现代码根本没跑 | 先 `ls resources/` 确认是 asar 还是解包的 launch.js |
| Hook 写在主逻辑之后 | 校验已跑完，Hook 无效 | Hook 必须最先执行（文件顶部 / preload） |
| 只 Hook `electron.net.fetch` | electron-fetch 走 `net.request`，续订绕过 | 同时 Hook `net.request` |
| 只 Hook `protocol.handle` | 主进程请求拦不到 | 主进程用 net.fetch / net.request 通道 |
| license `date` 写死激活当天 | 次日过期 | 运行时动态生成当天日期 |
| 只清注册表不清 Chrome 存储 | 试用倒计时仍在跑 | 见 `03-桌面与移动端/Electron 客户端试用数据清哪几个目录` |
| 二次验证后不看守 | license 被清空 → 试用期 | setInterval 看门狗恢复 |
