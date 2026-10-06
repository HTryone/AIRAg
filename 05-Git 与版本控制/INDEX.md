# 05-Git 与版本控制

> ⚙️ 本文件由 `update_index.py` **自动生成**（扫描本目录里的文件）：新加条目只要把文件放进本目录，再跑一次 `python update_index.py` 就会自动出现。请勿手改。
> 分类总览见根目录 [`INDEX.md`](../INDEX.md)。

| 类型 | 条目 | 一句话 |
|---|---|---|
| 模块 | [Windows 非交互推 GitHub 全流程（建仓、取凭据、代理、askpass）.md](Windows 非交互推 GitHub 全流程（建仓、取凭据、代理、askpass）.md) | 诊断先行：credential fill 取令牌 + API 建仓 + askpass 注入推送；先分网络挂还是凭据挂 |
| 单条 | [push 必须用户明确授权.md](push 必须用户明确授权.md) | 「并入 main」不等于授权推送 |
| 单条 | [冲突与破坏性 git 操作交用户决策.md](冲突与破坏性 git 操作交用户决策.md) | 冲突、强推、reset --hard 等不可逆操作摆选项等用户拍板 |
| 单条 | [删仓库文件前先查跟踪状态.md](删仓库文件前先查跟踪状态.md) | 别在错误目录 ls 还吞掉报错 |
| 单条 | [回退用 reset --hard 不用 revert.md](回退用 reset --hard 不用 revert.md) | revert 会留一个多余的提交 |

### 📁 GitHub 操作脚本（gh.sh）/

| 类型 | 文件 | 一句话 |
|---|---|---|
| 模块 | [GitHub 操作脚本（gh.sh）.md](GitHub 操作脚本（gh.sh）/GitHub 操作脚本（gh.sh）.md) | 一个脚本包办取令牌 / 查状态 / 提 PR / 建 issue / 贴标签；写操作必须用户授权 + `--yes`（一个工具一个文件夹：脚本 + 用法参考都在文件夹里） |
| 附件 | [gh.sh](GitHub 操作脚本（gh.sh）/gh.sh) | 脚本 / 模板（不计入条目数） |

## 备注（历史）

2026-10-05 新增 Windows 非交互推 GitHub 全流程（建仓、取凭据、代理、askpass）（模块）：MCP 建仓 403、PowerShell 管道喂 credential fill 失败、Git Bash curl TLS 坏、helper-selector 非交互静默 exit 128、askpass 临时注入用完即删。2026-10-06 **并入**通用 GitHub 操作脚本（一个工具一个文件夹 `GitHub 操作脚本（gh.sh）/`：内含 `gh.sh` + 用法参考；脚本顶部带「用之前先看这里」配置区：凭据来源 + 四个占位参数）；该内容原拟新建顶层目录，按用户要求并入本目录
