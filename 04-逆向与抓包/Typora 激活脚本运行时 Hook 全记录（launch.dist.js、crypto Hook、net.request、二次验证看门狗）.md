# Typora 激活脚本运行时 Hook 全记录（launch.dist.js、crypto Hook、net.request、二次验证看门狗）

> 本篇是 typora_patcher 项目（Typora 1.13.7 / 1.14.6，Electron 35.x）的**专属记录**，只写 Typora 的具体值、路径、键名、坑。通用原理另见 `Electron 客户端运行时 Hook 与补丁`（手法总览）与 `Electron 客户端试用数据清哪几个目录`（清哪些目录）。换别的 Electron 客户端，照搬本篇的具体值会失效，请按通用篇的思路重探。

## 背景

Typora 是 Electron 客户端，许可校验在本地完成：RSA 解密 license blob、运行时拉 `api/client/` 验活、每 12h 续订、概率性 `2nd` 二次验签。激活脚本 `typora_crack.js` 把 Hook 注入 `launch.dist.js`，伪造解密结果与接口响应，并用看门狗抵消二次验证清空。

## 一、注入入口：launch.dist.js + fs 重定向

- Typora 解包后入口是 `resources/app/launch.dist.js`（**不是** `app.asar`，先 `ls resources/` 确认形态）。
- 原文件备份到 `app.bak/`；运行时把 `fs` 读取重定向到 `app.bak/`，让原始逻辑在 Hook 之后仍按原样跑。
- 证据：`typora_crack.js:660` `const LaunchDistJS = path.join(appDir, "launch.dist.js");`
- **通用提示**：入口形态（asar vs `launch.js`）各 App 不同；注入必须在主逻辑加载前。

## 二、Hook crypto.publicDecrypt / privateDecrypt 绕过 RSA 校验

- `crypto.publicDecrypt`（部分版本 `privateDecrypt`）被 Hook，返回伪造 license entity，`date` 用当天日期动态生成。
- 证据：`typora_crack.js:485-494`。
- **坑**：entity 写死激活当天 → 次日过期（7-1 修复，7-13 又因续订绕过复现）。`date` 必须运行时动态。
- **通用提示**：Hook 加密原语适用于任何用 Node `crypto` 做许可解密 / 验签的客户端，entity 字段结构因 App 而异。

## 三、拦截网络双通道

- 渲染进程：`protocol.handle("https", ...)` 拦（`typora_crack.js:579`），但只覆盖渲染进程。
- 主进程：`electron.net.fetch`（`:591`）+ `electron.net.request`（`:503`）。
- **关键坑**：`electron-fetch` 在 Electron 里 `useElectronNet=true`，走 `electron.net.request` 而非 `net.fetch`（`:500-504` 注释）。只 Hook `net.fetch` 会漏掉每 12h 续订 → license 被撤销 → 试用期。两个通道都要 Hook，拦截 `/api/client/`。
- **通用提示**：`electron-fetch` 走 `net.request`、以及 `protocol.handle` 只拦渲染进程，是 Electron 通用事实，所有 App 一致。

## 四、反制二次验证：看门狗 + 定时器拦截 + IDate 兜底

- 概率性 `2nd` 二次验证：本地纯 JS 验 SLicense 签名，失败 `onUnfillLicense` 清空 `HKCU\Software\Typora\SLicense`（2026-07-23 实测：激活 6 天后触发）。
- SLicense 值 `RHJlYW1OeWE=#0#1/1/2059`（DreamNya 格式）不是有效 RSA 签名，必失败。
- 反制一（7-26）：`restoreSLicense` 看门狗写回，启动先跑一次防首屏空（`:556-576`）；9-10 起周期从 2s 降为 5s（右路不读注册表，2s 纯浪费）。
- **反制二（9-10，关键）**：`2nd` 由启动后固定 ~530s 的 `setTimeout` 触发，触发前先掷随机数——rand < 0.8 读注册表 → renew → pass；rand > 0.8（约 20%）走**无条件吊销**分支，不读注册表、不看门狗拦得住的内存态照样清。15 个日志样本分界干净：0.7658 及以下全 pass，0.8392 及以上全 unfill。对策：Hook `global.setTimeout` + `require('timers').setTimeout`，拦截启动 120s 内注册的第一个 delay ∈ [520000, 545000] 的定时器（即 2nd 定时器），返回 `_destroyed:true` 假 timer → 2nd 永不触发；同区间后续定时器放行。
- **反制三（9-10，兜底）**：`refreshIDate()` 启动即刷 + 每 30 分钟把注册表 `IDate` 写成当天（每天只实际写一次），保证漏网时剩余天数显示 15 天而非 0 天。
- **通用提示**：本地二次验证失败清注册表是 anti-tamper 通用套路；看门狗只保证「下次启动」正常，拦不住运行中的无条件吊销——有概率性吊销分支时必须拦定时器本身（详见通用篇「Electron 客户端运行时 Hook 与补丁」第四节）。换 App 改键名 / delay 区间。

## 五、激活前清试用数据（Typora 专属路径 / 键名）

- 删 Chrome 存储（Chromium 标准目录，所有 Electron 客户端同名）：`%APPDATA%\Typora\Local Storage\`、`Session Storage\`、`DIPS\`。
- 清注册表：`reg delete "HKCU\Software\Typora" /v SLicense /f`。
- **通用提示**：目录名通用；注册表键名 `SLicense` 是 Typora 专属，换 App 需在代码里搜 `HKCU\Software\` 跟出真实键名。

## 避坑（Typora 实测时间线）

| 日期 | 现象 | 根因 |
|---|---|---|
| 7-1 | 显示 12 天剩余 | `protocol.handle` 只拦渲染进程 + 试用数据未清 |
| 7-13 | 又提示 3 天到期 | `electron-fetch` 走 `net.request`，续订绕过 |
| 7-23 | 运行几天后变试用 | `2nd` 二次验证清 SLicense，无看门狗 |
| 7-26 | 加 `setInterval` 看门狗 | 恢复 SLicense，稳定 |
| 9-8 | 运行中弹「试用 0 天」，重启恢复 | `2nd` 约 20% 概率走无条件吊销分支（不读注册表），看门狗拦不住；IDate 固定激活日、超 15 天窗口后吊销算出 0 天 |
| 9-10 | 拦截 `2nd` 定时器 + IDate 兜底 | 启动 120s 内第一个 delay ∈ [520000, 545000] 的 `setTimeout` 返回假 timer；`refreshIDate()` 每 30 分钟刷 IDate 成当天；看门狗降频 5s |
