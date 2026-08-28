# Windows 定时任务

让脚本每天固定时间自动跑。这篇是完整模块，单独看这一篇就够。

---

## 一、任务在哪

`Win + R` → 输入 `taskschd.msc` → 回车 → **左侧点一下「任务计划程序库」** → 右侧列表里找任务名。

列表里找不到 = 还没建，不是藏起来了。

---

## 二、从零新建一个任务（图形界面）

右侧点「**创建任务**」——不是「创建基本任务」，那个选项太少，没有起始位置和电源设置。

### 第 1 步：常规页

| 项 | 怎么填 |
|---|---|
| 名称 | 起个英文名，如 `MyDailyTask` |
| 只在用户登录时运行 | 勾上 |
| 使用最高权限运行 | **不勾** |
| **配置为** | **保持默认的 `Windows Vista / Windows Server 2008`，不要改成 Windows 10** |

「配置为」这个下拉框**不是让你选自己的系统版本**，它决定的是这个任务允许使用哪些任务计划程序功能。选 Windows 10 会启用新特性，反而可能引入兼容性问题；选默认的老版本，功能集合最小最稳，在所有 Windows 上都能跑。

### 第 2 步：触发器页

新建 → 每天 → 开始时间填 `09:00:00` → 勾「已启用」。

高级设置里勾上「**如果错过了计划的开始时间，请尽快运行任务**」——关机错过了，开机后会补跑。

### 第 3 步：操作页

新建 → 三项都要填：

| 项 | 值 | 说明 |
|---|---|---|
| 程序或脚本 | `C:\Users\Htryone\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe` | 用 **pythonw** 不是 python，否则每次触发弹黑框 |
| 添加参数 | `D:\xxx\your_script.py` | 脚本完整路径 |
| **起始于** | `D:\xxx` | 脚本所在目录，**必须填** |

「起始于」不填，系统默认用 `C:\Windows\System32`。脚本里任何相对路径（日志目录、配置文件、数据目录）都会基于它解析 —— 日志写到别的地方去，配置文件找不到。

### 第 4 步：设置页

- 勾「允许任务按需运行」
- 勾「如果任务失败，按以下频率重新启动」→ 3 次 / 5 分钟
- 「如果任务运行时间超过」→ 10 分钟 → 停止任务
- 电源区域：**取消**「只有在计算机使用交流电源时才启动此任务」

### 第 5 步：验证

列表里右键任务 → 「运行」。然后去看脚本写的日志文件有没有新记录。**看到日志才算真的成功**。

---

## 三、一键建（PowerShell）

普通权限即可，不用管理员。整段复制粘贴：

```powershell
$pyw = "C:\Users\Htryone\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"
$dir = "D:\perca\zidqdworkbuddy\wb-checkin"

$action   = New-ScheduledTaskAction -Execute $pyw `
              -Argument "$dir\checkin.py" -WorkingDirectory $dir
$trigger  = New-ScheduledTaskTrigger -Daily -At 09:00
$settings = New-ScheduledTaskSettingsSet `
              -AllowStartIfOnBatteries `
              -DontStopIfGoingOnBatteries `
              -StartWhenAvailable `
              -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

Register-ScheduledTask -TaskName "MyDailyTask" `
  -Action $action -Trigger $trigger -Settings $settings -Force
```

改时间只动 `-At 09:00`；任务已存在时 `-Force` 覆盖。

建完验证：

```powershell
schtasks /run /tn MyDailyTask
Get-Content "D:\perca\zidqdworkbuddy\wb-checkin\logs\checkin.log" -Tail 20
```

---

## 四、日常管理

```powershell
schtasks /run    /tn MyDailyTask              # 立刻跑一次
schtasks /change /tn MyDailyTask /st 08:00    # 改时间
schtasks /end    /tn MyDailyTask              # 停掉正在跑的
schtasks /delete /tn MyDailyTask /f           # 删除
schtasks /query  /tn MyDailyTask /v /fo list  # 看详细配置
```

PowerShell 5.1 不支持 `&&`，串联命令用换行或 `A; if ($?) { B }`。

---

## 五、排查为什么没跑

先看基本状态：

```powershell
schtasks /query /tn MyDailyTask /v /fo list
```

重点三项：

| 字段 | 含义 |
|---|---|
| 上次运行时间 | 空 = 从没触发过 |
| 上次运行结果 | `0x0` 成功，`0x1` 脚本报错，`0x41306` 错过计划时间 |
| 登录类型 | Interactive = 用户没登录就不跑 |

### 直接读 Settings 属性会拿到空值

`Get-ScheduledTask` 返回的对象里，`Settings.AllowStartIfOnBatteries` 这类字段经常是空的，不是真的没勾。要看真实值必须导出 XML：

```powershell
$xml = [xml](Export-ScheduledTask -TaskName "MyDailyTask")
$ns  = New-Object Xml.XmlNamespaceManager($xml.NameTable)
$ns.AddNamespace("t", "http://schemas.microsoft.com/windows/2004/02/mit/task")
$xml.SelectNodes("//t:Settings/*", $ns) | ForEach-Object { "$($_.Name) = $($_.InnerText)" }
```

### 常见原因

| 现象 | 原因 |
|---|---|
| 从没触发过 | 触发器没勾「已启用」，或用户未登录（Interactive 类型） |
| 结果 `0x1` | 脚本本身报错。手动跑一次 `python.exe` 版本看输出 |
| 结果 `0x41306` | 到点时机没开机，且没勾 StartWhenAvailable |
| 跑了但日志没更新 | 「起始于」没填，日志写到 `C:\Windows\System32` 去了 |

---

## 六、常见坑

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 用 `python.exe` 不用 `pythonw.exe` | 每次触发弹黑框 | 定时任务一律 `pythonw.exe` |
| 「起始于」留空 | 相对路径全错位，日志写到 System32 | 必填脚本所在目录 |
| 「配置为」改成 Windows 10 | 启用不必要的新特性，可能兼容问题 | 保持默认 Vista / Server 2008 |
| 用「创建基本任务」 | 没有起始位置、没有电源设置 | 用「创建任务」 |
| 勾了「只用交流电源」 | 拔电就不跑 | 取消勾选 |
| 脚本只 print 不写文件 | pythonw 下输出全丢，无从排查 | 日志必须写文件 |

脚本本身要保证**幂等**（重复跑不会有副作用），因为失败重试和错过补跑都会导致一次触发多次执行。
