# GitHub 操作脚本（gh.sh）

**结论**：把「取令牌 → 查仓库状态 → 提 PR / 建 issue / 回评论 / 贴标签 / 关 issue → 任意 API」收进一个**不绑定任何项目**的 bash 脚本 `gh.sh`；**脚本与说明放在同一文件夹、成对使用**。**所有 GitHub 动作一律走这个脚本**——不许手拼 `curl`、不许临时另写脚本、不许换个工具绕开；**写操作必须由用户明确授权并在命令里加 `--yes`**，读操作随时可用。

## 这是什么

一个纯 bash 脚本（Git Bash 直接跑），把 GitHub 常见操作固化成子命令，避免每次手拼带占位符的长命令，也避免凭据出现在命令历史里。

- **令牌来源**：脚本内部调 `git credential fill` 现取现用，**不落盘、不回显**，不读环境变量里的令牌。
- **目标仓库**：不写 `--repo` 时，自动用「当前目录（或 `--dir`）所在 git 仓库的 `origin`」推断 `owner/name`。
- **代理**：`api.github.com` 直连不通时设 `GH_PROXY`，脚本把它作为 curl 的 `-x` 参数。
- **超时与重试**：单次请求 30s 超时（`GH_TIMEOUT` 可调），网络错误 / 429 / 5xx 自动重试 2 次（`GH_RETRIES` 可调），**不会无限挂起**。
- **JSON 解析**：脚本自己找 `python` / `python3` / `py`，不要求特定版本。

## 在哪：一个工具一个文件夹，脚本与说明成对

```
<知识库根>/05-Git 与版本控制/GitHub 操作脚本（gh.sh）/
├── gh.sh                        ← 脚本本体（唯一权威版）
└── GitHub 操作脚本（gh.sh）.md   ← 本说明（改脚本必须同步改这里）
```

工作区里通常另有一份同名副本（配该项目自己的说明）。**两份必须字节一致**，同步与校验见「怎么同步」一节。

## 硬规矩：走脚本 + 读说明，不许绕开

1. **用之前先读本说明**：至少读「一键怎么做」和「授权边界」两节，按脚本既有参数用，**不自己在外面拼等价命令**。
2. **脚本没覆盖的接口走 `api` 逃生口**（它支持 `--dry-run` 预演、`--raw` 看全文），**仍然算走脚本**。
3. **不许手拼 `curl` 调 API**，也不许为某一次操作临时另写脚本 —— 除非**先拿到用户许可**，并把理由记在本次交付说明里。

为什么这么硬（每条都是踩出来的）：

- 手拼 `curl` 会把令牌暴露在命令行与历史里；本脚本令牌只在管道内存活。
- 手拼命令**没有授权门槛**，写操作可能没经用户同意就发出去；本脚本对写操作强制 `--yes`。
- 手拼命令**没有防重复预检**，容易建出重复 PR；本脚本 `pr-create` 先查同 head 的 open PR。
- 手拼缺 `--max-time` / 重试，容易卡死或无谓失败；本脚本已内置。
- 手拼的一次性命令**没法复现**，别人接手只能重写一遍；脚本命令固定、可复查、可自证。

## 依赖

```bash
bash --version      # Windows 上用 Git Bash：<Git 安装目录>\bin\bash.exe
curl --version
git --version
```

## 用之前要填的四个值（脚本顶部的配置区）

脚本开头有一段用星号标出的「★★★ 用之前先看这里 ★★★」配置区，四个值全是占位符，**留空表示不预设**：

| 变量 | 填什么 | 留空时 |
|---|---|---|
| `GH_PROXY_FALLBACK` | 代理地址，例 `socks5h://127.0.0.1:<你的代理端口>` | 不用代理；也可临时用环境变量 `GH_PROXY` 覆盖（**环境变量优先**） |
| `DEFAULT_REPO` | 默认仓库 `<owner>/<repo>` | 用当前目录（或 `--dir`）git 仓库的 `origin` 推断 |
| `DEFAULT_BASE` | 提 PR 的目标分支 | 用 `main` |
| `DEFAULT_LOGIN` | 你的 GitHub 登录名 | 运行时调 `/user` 查 |

**令牌（凭据）不在这里填**：脚本问 git 凭据管理器要（`git credential fill`），在 Git 里登录过一次就行，`token-check` 可随时验证。令牌不要写进脚本、不要贴进命令、不要提交进 git。

## 从零怎么做

### 1. 确认令牌取得到（读操作）

```bash
bash gh.sh token-check
```

自己查令牌存在哪、仓库指向哪：

```bash
git config --get credential.helper     # manager / store / cache / 空
git remote -v                          # 确认 owner/name 与 host
```

令牌权限：普通操作要 `repo`；**改 `.github/workflows/` 下的文件还要 `workflow` 权限**。

### 2. 确认仓库与分支状态（读操作）

```bash
bash gh.sh repo-info                                   # 当前目录仓库的 owner/name
bash gh.sh verify --dir <仓库目录> --branch main        # 本地与远端是否对齐
```

## 一键怎么做（子命令清单）

```bash
bash gh.sh help

# —— 读（随时可用）——
bash gh.sh token-check
bash gh.sh repo-info
bash gh.sh verify      [--dir <仓库目录>] [--repo <owner>/<repo>] [--branch main]
bash gh.sh pr-list     [--repo <owner>/<repo>] [--state open|closed|all]
bash gh.sh pr-show     <编号> [--repo <owner>/<repo>] [--files]   # 状态/可合并性/改动文件/正文全文
bash gh.sh issue-list  [--repo <owner>/<repo>] [--state open] [--limit 20]
bash gh.sh issue-show  <编号> [--repo <owner>/<repo>]

# —— 写（先 --dry-run 预览，再 --yes 真发；两者都要用户授权）——
bash gh.sh pr-create    "<标题>" <正文.md> [--repo <owner>/<repo>] [--base main] \
                        [--head <owner:branch>] [--dry-run] [--yes]
bash gh.sh issue-create "<标题>" <正文.md> [--repo <owner>/<repo>] [--dry-run] [--yes]
bash gh.sh issue-comment <编号> <正文.md> [--repo <owner>/<repo>] [--dry-run] [--yes]
bash gh.sh issue-label  <编号> "bug,help wanted" [--repo <owner>/<repo>] [--yes]
bash gh.sh issue-close  <编号> [--repo <owner>/<repo>] [--reason completed|not_planned] [--yes]

# —— 逃生口（任意 API；非 GET 也算写操作）——
bash gh.sh api GET  "/repos/<owner>/<repo>/pulls?state=all"
bash gh.sh api GET  "/repos/<owner>/<repo>/pulls/29" --raw          # 不截断输出
bash gh.sh api POST "/repos/<owner>/<repo>/issues" payload.json --dry-run   # 写操作也能预演
bash gh.sh api POST "/repos/<owner>/<repo>/issues" payload.json --yes
```

**`--dry-run` 的覆盖范围**：`pr-create` / `issue-create` / `issue-comment`，以及 `api` 的**非 GET** 方法（打印将要发送的正文或 payload 前 400 字，**不发请求**，因此不需要 `--yes`）；`issue-label` / `issue-close` 没有 dry-run，只认 `--yes`。

**提完必须自证**：用 `pr-show <编号>` 核实真的建出来了、正文没乱码，**不要只信创建时的回执**。

## 怎么同步工作区副本与库内副本

两边都要同步，**以哪边为最新看实际改动发生在哪边**；同步后用 sha256 确认字节一致（文件名含中文和括号，命令必须加引号）：

```bash
# 先看两边差在哪
diff -u "<库内副本路径>/gh.sh" "<工作区副本路径>/gh.sh"

# 再把新的一份覆盖过去（示例：工作区 → 库内，按实际方向改）
cp -f "<工作区副本路径>/gh.sh" "<库内副本路径>/gh.sh"

# 校验：两个哈希必须相同
sha256sum "<工作区副本路径>/gh.sh" "<库内副本路径>/gh.sh"
```

## 授权边界（硬规则）

- 写操作 = 改动别人可见的状态：**执行前必须拿到用户明确授权**，命令再加 `--yes`。缺 `--yes` 时脚本直接拒绝：

  ```
  ✗ 这是写操作（会改动别人可见的状态）：先拿到用户明确授权，再加 --yes 执行
  ```

- 能用 `--dry-run` 的，**先把内容打给用户看**，确认后再真发。
- **提 PR 前脚本会先查「同 head 是否已有未关闭 PR」**，有就报错退出，避免重复提：

  ```
  ✗ 已存在同 head 的 open PR，不再重复创建
  ```

- 令牌只经 `git credential fill` 取得，**不要**把令牌贴进命令、写进文件或提交进 git（见 `../../10-凭据与安全/凭据存放与不进 git.md`）。
- 推送（不是 API 调用）也要用户明确授权，见 `../push 必须用户明确授权.md`（同目录）。

## 提 PR 前自检 + 正文结构

自检（缺一项就别提）：

- [ ] **现象能独立复现**：复现步骤只依赖仓库 + 环境说明，不依赖「我这边刚好怎样」
- [ ] **只含必要文件**：`git show --stat` 看一遍，没有顺手改的无关文件、没有临时脚本、没有凭据
- [ ] **根因有出处**：指到文件:行号，不是「感觉是这样」
- [ ] **改动最小**：能一行解决的不要重写整个函数
- [ ] **老数据 / 兼容性写清楚**：升级会不会影响已有数据、要不要迁移、能不能回滚
- [ ] **本地验证过**（各项目自己的回归清单）
- [ ] **先查有没有重复 PR**：`pr-create` 内部会自动查，单独确认可用 `pr-list --state open`

正文按这个顺序写（给作者直接读）：

1. 一句话结论（现象 + 根因 + 修法）
2. 现象（报错原文 + 复现步骤）
3. 根因（代码路径 + 行号）
4. 修复内容（改了哪些文件、为什么最小化）
5. 实测证据（表格：测试路径 → 结果）
6. 升级影响评估（老数据、幂等性、回滚）
7. PR 范围声明（只含哪些文件、不含什么）

## 仓库与分支约定（用户拍板，不许改）

- **远程只留一个**：`origin` = 自己的仓库；作者仓库不建远程，要拉更新就在命令里临时用镜像地址 fetch，用完不留痕迹。
- **分支只留一个**：`main`，本地与远程一致。
- **镜像 URL 绝不存成 remote**（会触发凭据弹窗），只在临时命令里用。
- 同时修多个互不相干的 bug → **一个 bug 一个分支**（`git switch -c fix/<主题>`），PR 时写 `--head <你的账号>:fix/<主题>`；别让一个 PR 混多件事。
- `pr-create` 不写 `--head` 时自动用「你的登录名:当前分支」，所以**先切好分支再提**。

## 排查

| 症状 | 原因 / 处理 |
|---|---|
| `401` | 令牌失效或没取到 → 重跑 `token-check`；查 `credential.helper` 是否配置 |
| `403` | 令牌权限不足（缺 `repo` / `workflow`），或被限流 → 读响应体里的 `message`；限流会打印恢复时间戳 |
| `404` | 仓库名写错，或令牌无权访问私有仓库 —— **私有库权限不足也返回 404，不是 403** |
| `422` | 参数不合法：`--base` / `--head` 分支不存在、PR 重复、payload 字段名错 |
| `000` / curl 报错但不是 HTTP 状态码 | 网络不通或超时（脚本已重试 `GH_RETRIES` 次）→ 设代理：`export GH_PROXY=socks5h://127.0.0.1:<你的代理端口>` |
| `✗ 无法从 … 的 git remote origin 推断仓库` | 不在 git 目录里跑 → 加 `--repo <owner>/<repo>`，或配置区填 `DEFAULT_REPO` |
| 认证选择器卡住 / 静默 `exit 128` | `credential.helper=manager` 在非交互环境弹不出窗口 → 用临时 askpass，**用完即删** |

代理用法：

```bash
export GH_PROXY=socks5h://127.0.0.1:<你的代理端口>
bash gh.sh pr-list --repo <owner>/<repo>
```

## 避坑表

| 坑 | 事实（日期） | 做法 |
|---|---|---|
| 走 MCP 建仓被拒 | 2026-10-04 实测返回 403 | 改用**本机凭据 + 本脚本**走 REST API |
| PowerShell 里管道喂 `git credential fill` 失败 | 2026-10-04 实测 | 在 **Git Bash** 里执行；别跨 shell 传凭据 |
| Git Bash 自带 curl 走 TLS 报错 | 2026-10-05 实测 | 先用 `curl -v` 分清是 TLS 还是网络，再决定换 curl 或走代理 |
| 认证选择器非交互静默 `exit 128` | 2026-10-05 实测 | 临时 askpass 注入，**用完即删**，不要留在磁盘上 |
| `raw.githubusercontent.com` 直连被挡 | 2026-10-04 实测 | 走镜像，或用 `api.github.com` 的 contents 接口取文件（返回 base64 内容） |
| 库内副本落后于工作区副本 | 2026-10-24 实测：库内 439 行 / 工作区 563 行，缺 `pr-show`、`api --dry-run/--raw`、超时重试 | 改完脚本立刻同步两份并 `sha256sum` 校验 |
| 文件名含中文括号时 `diff`/`cp` 报 `missing operand` | 2026-10-24 实测 | 路径**整体加引号**，或把命令写进 `.sh` 文件再跑 |
| 提 PR 重复 | — | 脚本已内置「同 head 未关闭 PR」预检查 |
| 把「并入 main」当成推送授权 | — | 见 `push 必须用户明确授权.md`（同目录） |

## 实测记录

2026-10-24 把库内副本换成工作区最新版（`gh.sh` 563 行，两边 sha256 相同），逐条验过：

| 项 | 结果 | 证据 |
|---|---|---|
| 令牌 | ✅ | `token-check` → `✓ 令牌可用：login=<你的登录名>`（长度 40，值不外显） |
| 写操作无 `--yes` | ✅ 被拦 | `issue-create` / `issue-label` / `issue-close` 均报「先拿到用户明确授权」 |
| `pr-create --dry-run` | ✅ 只预览 | 打印 `head=<登录名>:<当前分支>  base=main` 与正文，未发请求 |
| `api POST --dry-run` | ✅ 不需 `--yes` | 打印将要发送的 payload，未发请求 |
| `pr-show`（读公开 PR） | ✅ | 状态 / 合并性 / 改动行数 / 正文全文 / `--files` 文件清单均正确 |
| `verify` / `repo-info` | ✅ | 本地 HEAD 与远程 main 哈希一致 |
| 未知参数 / 未知子命令 | ✅ 报错退出 | `api --bogus`、`nosuchcmd` 均有明确提示 |

## 和其它条目的关系

- 「本地提交怎么推上去（凭据 / 代理 / askpass 的具体流程）」→ 见 `../Windows 非交互推 GitHub 全流程（建仓、取凭据、代理、askpass）.md`（同目录上级）；本文只管**脚本能做什么、怎么安全地用**。
- 「授权范围一次只动一处」→ 见 `../../01-AI 协作/授权与改动边界.md`。
- 「有现成工具就先找、照它的说明用」→ 见 `../../01-AI 协作/先找现成工具，别重复造轮子.md`。
