# GitHub 操作脚本（gh.sh）

**结论**：把「取令牌 → 查仓库状态 → 提 PR / 提 issue / 回评论 / 贴标签 / 关 issue → 任意 API」收进一个**不绑定任何项目**的 bash 脚本 `gh.sh`。**写操作必须由用户明确授权，并在命令里加 `--yes`**；读操作随时可用。

## 这是什么

一个纯 bash 脚本（Git Bash 直接跑），把 GitHub 常见操作固化成子命令，避免每次手拼带占位符的长命令，也避免凭据出现在命令历史里。

- **令牌来源**：脚本内部调 `git credential fill` 现取现用，**不落盘、不回显**，不读环境变量里的令牌。
- **目标仓库**：不写 `--repo` 时，自动用「当前目录（或 `--dir`）所在 git 仓库的 `origin`」推断 `owner/name`。
- **代理**：`api.github.com` 直连不通时设 `GH_PROXY`，脚本把它作为 curl 的 `-x` 参数。
- **JSON 解析**：脚本自己找 `python` / `python3` / `py`，不要求特定版本。

## 在哪

`<知识库根>\05-Git 与版本控制\gh.sh`

> 具体项目的工作区里通常还会放一份同名副本（配该项目自己的说明）。**本库这份是通用基准**，改脚本时两边都要同步。

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

实测（2026-10-06，改完当场验的）：

- 填 `DEFAULT_REPO` → `repo-info` 直接采用，**不需要在 git 目录里跑**；
- 填 `DEFAULT_LOGIN` → `pr-create --dry-run` 的 head 直接组成 `<登录名>:<分支>`，**不再调 `/user`**；
- 填 `GH_PROXY_FALLBACK` → `pr-list` 正常返回（同一台机器上 curl 直连是失败的）。

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
bash gh.sh api GET "/repos/<owner>/<repo>/pulls?state=all"
bash gh.sh api POST "/repos/<owner>/<repo>/issues" payload.json --yes
```

**`--dry-run` 只有 `pr-create` / `issue-create` / `issue-comment` 支持**（打印将要提交的正文前 400 字，不发请求）；`issue-label` / `issue-close` 没有 dry-run，只认 `--yes`。

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

- 令牌只经 `git credential fill` 取得，**不要**把令牌贴进命令、写进文件或提交进 git（见 `../10-凭据与安全/凭据存放与不进 git.md`）。

## 排查

| 症状 | 原因 / 处理 |
|---|---|
| `401` | 令牌失效或没取到 → 重跑 `token-check`；查 `credential.helper` 是否配置 |
| `403` | 令牌权限不足（缺 `repo` / `workflow`），或被限流 → 读响应体里的 `message` |
| `404` | 仓库名写错，或令牌无权访问私有仓库 —— **私有库权限不足也返回 404，不是 403** |
| `422` | 参数不合法：`--base` / `--head` 分支不存在、PR 重复、payload 字段名错 |
| curl 报错但不是 HTTP 状态码 | 网络不通 → 设代理：`export GH_PROXY=socks5h://127.0.0.1:<你的代理端口>` |
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
| 推送（不是 API）也要代理 | — | 见 `Windows 非交互推 GitHub 全流程（建仓、取凭据、代理、askpass）.md`（同目录） |
| 提 PR 重复 | — | 脚本已内置「同 head 未关闭 PR」预检查 |
| 把「并入 main」当成推送授权 | — | 见 `push 必须用户明确授权.md`（同目录） |

## 和其它条目的关系

- 「本地提交怎么推上去（凭据 / 代理 / askpass 的具体流程）」→ 见 05 目录那篇；本文只管**脚本能做什么、怎么安全地用**。
- 「授权范围一次只动一处」→ 见 `../01-AI 协作/授权与改动边界.md`。
