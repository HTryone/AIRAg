# PowerShell 与 Bash 不能互调

**结论**：在 Bash 工具里不能直接调 PowerShell，在 PowerShell 工具里不能调 `cmd.exe`。各用各的入口。

## 为什么

实测报错：

```
Command rejected for security: Invoking PowerShell from Bash bypasses PowerShell security checks
Error: Command blocked for security: cmd.exe cannot be used from the PowerShell tool
```

这是平台的安全策略，不是配置问题，绕不过去。

## 怎么做

- 要跑 PowerShell 命令 → 用 PowerShell 工具
- 要跑 bash / Git Bash 命令 → 用 Bash 工具
- 需要两边配合时：分成两次调用，用文件或输出传递结果

## 附带

PowerShell 5.1 不支持 `&&`、`||`、`??`、`?.` 这些 PowerShell 7+ 语法。
串联命令用换行，条件执行用 `A; if ($?) { B }`。

## 五、一律走 bash，不要用 PowerShell 绕开失败

**结论**：给用户和其他 AI 的命令**一律写成 bash 形式**；执行时 bash 报错就**如实报告 bash 报了什么**，不许换 PowerShell 重跑一遍拿"成功"顶替。

**为什么**：两种外壳语法、引号、转义、管道各不相同，混着给＝每次现场翻译，翻译错就是「照抄了却跑不了」。用户原话（2026-10-18）是硬禁令：「**禁止使用 power shell**」「**禁止使用 shell，使用 bash**」。

| 目的 | 写成 bash | 不要写成 |
|---|---|---|
| 查端口占用 | `netstat -ano \| grep :8080` | `Get-NetTCPConnection` |
| 删除文件 | `rm -f <路径>` | `Remove-Item` |
| 跑脚本 | `bash scripts/x.sh` | `powershell -File x.ps1` |
| 含 `$`、引号、中文、JSON 的长命令 | 先写成 `.sh` 文件再执行 | 内联进 `-Command` |

**唯一例外**：拿不到 bash（例如沙箱报 `couldn't create signal pipe`）才回退 PowerShell，并且要在报告里写明为什么用了一次。

**反例**：bash 报 `unexpected EOF while looking for matching `"`` —— 正确的下一步是把命令**写成脚本文件**再跑，不是换 PowerShell 把结果重新做一遍。
