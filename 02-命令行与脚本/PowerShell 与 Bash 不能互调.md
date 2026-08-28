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
