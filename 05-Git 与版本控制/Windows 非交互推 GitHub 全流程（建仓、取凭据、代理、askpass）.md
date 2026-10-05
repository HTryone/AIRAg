# Windows 非交互推 GitHub 全流程（建仓、取凭据、代理、askpass）

> 适用：AI 在 Windows 上替用户建 GitHub 仓库并推送，全程无人值守（用户不在场、不弹窗）。
> 本条目命令由 **AI 在 Git Bash / PowerShell 里执行**（含临时变量，属工具要求的传参方式，不是给用户手打的命令）；给用户看的命令另行去掉变量。

## 结论

三步走，顺序不能换：

1. **诊断**：先区分「网络挂」还是「凭据挂」——用空凭据跑 `ls-remote`，报 `could not read Username` = 网络通、凭据问题；连接超时/拒绝 = 网络问题
2. **建仓**：凭据管理器里的令牌 + GitHub API `POST /user/repos`（GitHub MCP 集成普遍没有建仓权限，gh CLI 不一定装了）
3. **推送**：本地代理 + `GIT_ASKPASS` 临时脚本注入令牌（系统凭据选择器在脚本环境会静默挂掉）

## 为什么（证据）

- GitHub MCP 的 `create_repository` 实测报 `403 Resource not accessible by integration`——集成令牌普遍没有 `repo` 写权限，建仓走不通
- Windows 凭据管理器里只要用户推过一次 GitHub，就有 `git:https://github.com` 条目（cmdkey /list 可查），`git credential fill` 能现取令牌，不用问用户
- 同机另一个能正常推 GitHub 的仓库，`.git/config` 里现成写着本地代理端口——直连失败时照抄它，比猜端口靠谱
- 系统凭据助手（helper-selector）在非交互环境触发时会 **exit 128 且零输出**，像网络断了其实是凭据层挂了——不加区分会白排查半天

## 怎么做

### 第 0 步：诊断网络还是凭据

PowerShell：

```
git -c credential.helper= -c http.proxy=<本地代理地址> ls-remote https://github.com/<owner>/<repo>.git
```

- 报 `could not read Username` → 网络通，走第 2 步取令牌
- 连接超时/拒绝 → 先解决代理（查法见第 3 步），再回来

`<本地代理地址>` 怎么查：翻本机其它**能推 GitHub** 的仓库：`git config --local http.proxy`；没有就开代理软件看混合/HTTP 端口。

### 第 1 步：取令牌（令牌全程只在内存）

PowerShell 里 **不能** 用管道直接喂 `git credential fill`（会取不到），要用 cmd 重定向临时文件：

```powershell
$in = "$env:TEMP\credin.txt"
[IO.File]::WriteAllText($in, "protocol=https`nhost=github.com`n`n")
$out = cmd /c "git credential fill < `"$in`"" 2>$null
Remove-Item $in -Force
$tok = $null
foreach ($l in $out) { if ($l -match '^password=(.+)$') { $tok = $Matches[1] } }
```

临时文件里只有 `protocol` / `host` 两行，无敏感信息；令牌解析进 `$tok` 后全程不回显。

### 第 2 步：API 建仓

```powershell
$body = '{"name":"<仓库名>","private":true}'
Invoke-RestMethod -Uri "https://api.github.com/user/repos" -Method Post `
  -Headers @{Authorization="token $tok"; Accept="application/vnd.github+json"} `
  -Body $body -ContentType "application/json" -TimeoutSec 40
```

- `201` = 建好；`422` = 已存在（当成功继续）；`401` = 令牌过期，让用户在凭据管理器删掉 `github.com` 条目重新登录一次
- 推送前检查：`git ls-files` 过一遍，确认没有凭据、记忆文件、node_modules 之类不该进仓库的东西

### 第 3 步：推送（代理 + askpass 注入）

直接 `git push` 在脚本环境会静默失败。用 askpass 临时文件注入令牌：

```powershell
$ap = "$env:TEMP\askpass.cmd"
[IO.File]::WriteAllText($ap, "@echo off`necho $tok")
$env:GIT_ASKPASS = $ap
$env:GIT_TERMINAL_PROMPT = "0"
git -c credential.helper= -c http.proxy=<本地代理地址> push -u origin main
Remove-Item $ap -Force                       # 用完必须删，令牌落盘就是事故
Remove-Item Env:\GIT_ASKPASS -ErrorAction SilentlyContinue
```

推送后用 `git ls-remote origin main` 对一下本地和远端 commit 是否一致。

## 反例（实测踩过的）

| 反例 | 后果 | 正解 |
|---|---|---|
| 指望 GitHub MCP 集成建仓 | 403，权限写死 | 走 API |
| PowerShell 管道直接喂 `git credential fill` | 取不到令牌 | cmd 重定向临时文件 |
| 用 WorkBuddy 自带 Git Bash 里的 curl 连任何 https | 全部 000/35（TLS 坏），误判为断网 | 网络操作走 PowerShell 或系统工具 |
| 非交互环境触发凭据选择器弹窗 | exit 128 且零输出，像玄学 | `GIT_ASKPASS` 注入 + `-c credential.helper=` 关掉弹窗 |
| 令牌拼进命令行参数（如 push URL） | 进程列表/日志泄漏 | askpass 文件或内存变量 |
| askpass 临时文件用完不删 | 令牌落盘残留 | 当场删除，删完再继续 |
| 代理端口瞎猜 | 白等超时 | 翻同机已能推送仓库的 `.git/config` |

## 排查姿势

`exit 128 且没有任何输出` ≠ 没执行，多半是凭据层静默挂。把输出重定向到临时文件再看；还看不出就 `-c credential.helper=` 关掉凭据助手跑一遍，报错立刻现形。
