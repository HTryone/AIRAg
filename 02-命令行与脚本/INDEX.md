# 02-命令行与脚本

> ⚙️ 本文件由 `update_index.py` **自动生成**（扫描本目录里的文件）：新加条目只要把文件放进本目录，再跑一次 `python update_index.py` 就会自动出现。请勿手改。
> 分类总览见根目录 [`INDEX.md`](../INDEX.md)。

| 类型 | 条目 | 一句话 |
|---|---|---|
| 单条 | [Git Bash 路径写法.md](Git Bash 路径写法.md) | `/d/...` 传给 Windows 程序会变成 `d:\d\...` |
| 单条 | [PowerShell 与 Bash 不能互调.md](PowerShell 与 Bash 不能互调.md) | 各有各的工具，硬调会被安全策略拦截 |
| 模块 | [Tauri v2 构建打包.md](Tauri v2 构建打包.md) | 环境 → 从零做 → 一键构建 → 排查 → 避坑，产出 Windows NSIS + Android APK |
| 单条 | [bat 文件用 ASCII 内容.md](bat 文件用 ASCII 内容.md) | 中文内容会乱码 |
| 单条 | [pythonw 与 python 的区别.md](pythonw 与 python 的区别.md) | 后台用 pythonw，调试用 python |
| 单条 | [禁止在文档里引入 shell 变量.md](禁止在文档里引入 shell 变量.md) | `$VAR` 换个窗口就失效 |
| 模块 | [重复文件清理.md](重复文件清理.md) | 分级筛选（大小 → 部分哈希 → 全哈希）→ 干跑 → 处理策略 → py/go 取舍 |

## 备注（历史）

2026-09-29 清完硬编码机器路径（Windows 定时任务 2 处 + bat ASCII 1 处 + Git Bash 路径写法 4 处 + 禁止引入 shell 变量 1 处，统一改 `<你的项目路径>` / `C:\Users\<你的用户名>\...` 并补「怎么查出你自己的」命令）
