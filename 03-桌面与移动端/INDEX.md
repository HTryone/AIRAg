# 03-桌面与移动端

> ⚙️ 本文件由 `update_index.py` **自动生成**（扫描本目录里的文件）：新加条目只要把文件放进本目录，再跑一次 `python update_index.py` 就会自动出现。请勿手改。
> 分类总览见根目录 [`INDEX.md`](../INDEX.md)。

| 类型 | 条目 | 一句话 |
|---|---|---|
| 单条 | [Electron 客户端试用数据清哪几个目录.md](Electron 客户端试用数据清哪几个目录.md) | 重置试用要删 Local Storage / DIPS / Session Storage，不只清注册表；注册表键名各 App 不同 |
| 模块 | [Go 桌面程序的 Windows 原生能力（Win32 调用、UAC 清单）.md](Go 桌面程序的 Windows 原生能力（Win32 调用、UAC 清单）.md) | 零依赖方案取舍 → 声明调用 API → 结构体尺寸断言 → 内嵌清单实现启动即提权 → 两步验证 → 避坑表 |
| 模块 | [Rust 与 Tauri 后端改动怎么验证.md](Rust 与 Tauri 后端改动怎么验证.md) | 四步验证按顺序跑；涉平台接口时桌面和移动两端都要验 |
| 模块 | [Tauri 安卓插件（Kotlin 侧）.md](Tauri 安卓插件（Kotlin 侧）.md) | 原生代码必须独立建插件；读参数、取返回值、传参格式各有各的坑 |
| 模块 | [Tauri 权限配置（capability、命令清单、远程域白名单）.md](Tauri 权限配置（capability、命令清单、远程域白名单）.md) | 三层权限缺一不可；壳加载线上页面时必须加远程域白名单 |
| 单条 | [Tkinter 高 DPI 适配（Windows）.md](Tkinter 高 DPI 适配（Windows）.md) | SetProcessDpiAwareness(2)+tk scaling 1.0 原生像素渲染；Combobox 下拉 Listbox 需单独设字体 |
| 单条 | [Windows 中文乱码与编码.md](Windows 中文乱码与编码.md) | 读的编码和存的编码对不上，三个环节逐个查 |
| 模块 | [Windows 定时任务.md](Windows 定时任务.md) | 在哪 → 从零新建 → 一键建 → 日常管理 → 排查 → 避坑 |
| 单条 | [Windows 环境变量什么时候生效.md](Windows 环境变量什么时候生效.md) | `setx` 只对之后新开的窗口生效；Git Bash 子进程链可能拿不到用户变量 |
| 模块 | [安卓文件落盘（MediaStore、SAF、文件描述符）.md](安卓文件落盘（MediaStore、SAF、文件描述符）.md) | 四条路线按顺序降级；媒体库写入有 3.5MB/s 天花板，卡住就换文件描述符流式写 |
| 单条 | [安卓运行时权限与存储授权.md](安卓运行时权限与存储授权.md) | 首次启动就要、只问一次、授权要持久化、验证必须卸载重装 |

## 备注（历史）

2026-08-29 由「Windows 系统」改名扩类，装 Windows + Tauri + Rust + Kotlin + 安卓；2026-09-13 新增 Go 桌面程序的 Windows 原生能力（Win32 调用、UAC 清单）（模块，11 条）。2026-09-29 清完 Windows 定时任务 2 处硬编码路径（`C:\Users\Htryone\...` 与 `D:\perca\zidqdworkbuddy`）。**已超 8 条**，其中 Tauri 相关 4 条（权限配置 / 安卓插件 / 后端改动验证 / 与 Rust 的配合）是能合并的候选，待用户决定
