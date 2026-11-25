# IDM 试用冻结：锁死 CLSID 的 Model 键才是判定依据，radxcnt 不是

**结论**：IDM（6.43 实测）判定「试用是否过期」看的是 `HKCU\Software\Classes\WOW6432Node\CLSID\{07999AC3-058B-40BF-984F-69EB1E554CA7}` 下的 `Model` 值（实测 `Model=328`），把这个键用 Deny ACL 锁死，IDM 读不到它，就一直按「未过期」处理。`DownloadManager\radxcnt` 只是启动计数，**不参与过期判定**——实测把它改成 999、9999，IDM 依然正常启动、无过期弹窗、能正常下载。

## 为什么

2026-11-25 在 IDM 6.43b18 上做对照实验（全部为真机实测输出）：

| 实验 | 操作 | 结果 |
|---|---|---|
| A | 试用已过期（radxcnt=5），清 CLSID 键 + radxcnt，仅启动 IDM | `{07999AC3}` 重建，`Model=328`，`radxcnt=1`，无过期弹窗 |
| B | 不下载、仅启动 IDM | 同样重建 `{07999AC3}` + `radxcnt=1` → **不需要触发下载** |
| C | 锁死 `{07999AC3}` 后连续启动 6 次 | 全部正常，无过期弹窗，`radxcnt` 1→9 递增（不影响） |
| D | `radxcnt` 设 999 / 9999 + 清 LstCheck，启动 IDM | 依然正常、无弹窗、下载成功 → **radxcnt 非判定依据** |

结论来源：C 与 D 对照——radxcnt 无限制增长但从不触发过期，而 CLSID 键一被锁死就稳定正常。IDM 的真实试用计时藏在 `{07999AC3}` 的 `Model/Therad` 里（`Model=328` 疑为到期日编码），它读不到该键即无法判定到期。

## 怎么做

```powershell
# 1) 确认试用跟踪键（带 Model/Therad 值的就是它）
$base = 'Registry::HKEY_CURRENT_USER\Software\Classes\WOW6432Node\CLSID'
Get-ChildItem $base | ForEach-Object {
  $p = Get-ItemProperty $_.PSPath -EA SilentlyContinue
  if ($p.Model -or $p.Therad) { "$($_.PSChildName) Model=$($p.Model) Therad=$($p.Therad)" }
}

# 2) 重置：删掉试用计数与跟踪键（IDM 下次启动会重建为"新试用"）
Remove-Item "$base\{07999AC3-058B-40BF-984F-69EB1E554CA7}" -Recurse -Force -EA SilentlyContinue
foreach ($v in 'radxcnt','scansk','tvfrdt','LstCheck') {
  Remove-ItemProperty 'HKCU:\Software\DownloadManager' -Name $v -Force -EA SilentlyContinue
}

# 3) 启动一次 IDM 让它重建跟踪键，然后关闭
Start-Process 'IDMan.exe 的完整路径'; Start-Sleep 6
Get-Process IDMan -EA SilentlyContinue | Stop-Process -Force
```

锁死这一步要用代码做（PowerShell 改 DACL 需要 `Set-Acl` 且对 Deny ACE 支持不直观，Go/Python 直接调 `RegSetKeySecurity` 更可靠），要点：

- `RegSetKeySecurity` 的 ACE 用 **SID 形式**（`S-1-1-0`），不要用名字 `"Everyone"`——中文 Windows 上名字解析会失败，函数返回成功但生成**空 ACL**（ACE count=0），锁静默失效。
- `ACCESS_MODE` 常量：`GRANT_ACCESS=1`、`SET_ACCESS=2`、`DENY_ACCESS=3`。**deny 写 1 是致命错误**（变成 Everyone 完全控制）。
- Deny ACE 必须以**现有 DACL 为基底**（`SetEntriesInAcl` 的 OldAcl 传现值），保留继承 Allow 项，Deny 才排最前。
- HKCU 下自己的键**不需要管理员**：当前用户本就有 WRITE_DAC，直接改 DACL 即可；只有 HKLM 键和"抢 owner 为 Administrators"才要提权。

## 反例

- 以为要"触发 IDM 下载"才能生成试用键 → 实测**仅启动 IDM 就会重建**，下载纯属多余，还会弹下载窗、往磁盘写垃圾。
- 以为要清 `radxcnt` 来"续期" → 实测 radxcnt 涨到 9999 都不影响，改它没用。
- 用随机序列号"激活"（IAS `--act`）→ IDM 6.42+ 联网校验判假序列号，弹窗并让 IDM 自动退出，反而把 IDM 搞得不能启动。冻结（不写序列号）才稳。
