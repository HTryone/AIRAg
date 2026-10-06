# 04-逆向与抓包

> ⚙️ 本文件由 `update_index.py` **自动生成**（扫描本目录里的文件）：新加条目只要把文件放进本目录，再跑一次 `python update_index.py` 就会自动出现。请勿手改。
> 分类总览见根目录 [`INDEX.md`](../INDEX.md)。

| 类型 | 条目 | 一句话 |
|---|---|---|
| 模块 | [Electron 客户端运行时 Hook 与补丁.md](Electron 客户端运行时 Hook 与补丁.md) | 注入入口 → Hook 加密原语 / 网络双通道 / 反制二次验证（通用手法总览） |
| 模块 | [Electron 客户端逆向.md](Electron 客户端逆向.md) | 解包流程：找 asar → 提取 → 找凭据 → 试接口 → 判定能否脚本化 |
| 模块 | [Typora 激活脚本运行时 Hook 全记录（launch.dist.js、crypto Hook、net.request、二次验证看门狗）.md](Typora 激活脚本运行时 Hook 全记录（launch.dist.js、crypto Hook、net.request、二次验证看门狗）.md) | Typora 1.13.7/1.14.6 专属：具体值 / 路径 / 键名 / 坑，通用原理见上篇 |
| 单条 | [安卓 WebView 用 CDP 取证（adb 端口转发）.md](安卓 WebView 用 CDP 取证（adb 端口转发）.md) | 正式包前端日志看不见，转发调试端口后浏览器直调复现 |

## 备注（历史）

2026-08-29 新增：运行时 Hook 与补丁（通用手法总览，模块）+ Typora 激活脚本运行时 Hook 全记录（Typora 专属，模块）；现有 Electron 客户端逆向补了 launch.js 入口坑；2026-09-29 两篇补无条件吊销分支结论（看门狗拦不住 → 拦 setTimeout 定时器 + IDate 兜底）；还可沉淀：抓包代理、protobuf、Web 端接口逆向
