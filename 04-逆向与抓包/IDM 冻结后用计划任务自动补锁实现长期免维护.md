# IDM 冻结后用计划任务自动补锁，实现长期免维护

**结论**：锁死 CLSID 键后 IDM 虽然一直正常，但 IDM 自动更新会重写该键的权限（锁失效），所以要用 Windows 计划任务定期重新补锁。用 `schtasks` 以**当前用户身份**注册任务即可，不需要管理员，也不弹 UAC。

## 为什么

- 锁（Deny ACL）挂在 CLSID 键的 DACL 上。IDM 升级时可能删除/重建该键，新键回到默认 DACL → 锁没了 → 试用重新开始倒计时。
- 用高频率（每天 + 登录时）补锁，把窗口缩到最小：即使被重写，最多影响一次启动。
- `schtasks /Create` 用当前用户上下文（不指定 `/RU`、不指定 `/RL HIGHEST`）时不需要管理员；指定 `/RL HIGHEST` 或 `/RU SYSTEM` 才要提权。

## 怎么做

```powershell
# 注册：每天 09:00 静默调用本工具的 --autofix（只补锁，不重置、不下载）
$exe = '<你的工具完整路径>.exe'
schtasks /Create /TN "idmtool_AutoRenew" /TR "`"$exe`" --autofix --quiet" /SC DAILY /MO 1 /ST 09:00 /F

# 登录时也触发一次（可选，把任务加上登录触发器更稳）
# 验证
schtasks /Query /TN "idmtool_AutoRenew" /V /FO LIST

# 删除（回滚时）
schtasks /Delete /TN "idmtool_AutoRenew" /F
```

`--autofix` 内部必须做的事（顺序）：

1. 不弹 UAC（计划任务上下文没有交互桌面，弹框会挂住）。
2. 只扫描带 `Model/Therad` 的 CLSID 键 → 若已锁（打开报拒绝访问）就跳过 → 只补锁未锁住的。
3. 锁失败要让进程以非 0 退出，便于排查。

## 坑

- **`/TR` 里的引号**：路径含空格时，整个 `"exe" 参数` 要作为一个带引号的字符串传 —— PowerShell 里用反引号转义双引号，批处理里写 `\"`。
- **`schtasks` 输出是本地化中文**：判断"任务不存在"不能只匹配英文 `cannot find`，要同时匹配 `找不到` / `ERROR:`。
- **杀软误报**：计划任务 + 改注册表 DACL 的组合容易被启发式引擎盯上，报毒属常见误报。
- **别用 `/SC ONLOGON` 单独建**：部分系统上非管理员建登录任务会失败，用 `/SC DAILY` 更稳，需要登录触发就 `/SC ONLOGON` 单独测。
