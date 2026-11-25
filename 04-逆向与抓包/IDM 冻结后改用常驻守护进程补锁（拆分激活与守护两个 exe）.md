# IDM 冻结后改为「常驻守护进程」补锁，弃用计划任务

**结论**：锁死 CLSID 键后，IDM 自动更新会重写该键权限（锁失效），需要一个长期在跑的守护去补锁。**不要用 `schtasks` 计划任务**——改用「开机启动文件夹放一个 `idmguard.exe` 快捷方式」的**常驻进程**方案，并把它和「界面/激活程序」拆成两个 exe。计划任务最致命的失败模式是：`/TR` 里写死 exe 路径，exe 一改名/移动，任务就指向空气且**静默失效**（实测 `Last Result = 0x80070002` 文件不存在，持续好几天没人发现）。

## 为什么弃用计划任务

| 失败模式 | 计划任务 | 常驻守护 |
|---|---|---|
| exe 改名/移动 | `/TR` 路径失效，静默不再执行（`0x80070002`） | 快捷方式指向谁就启动谁；守护每次启动自检并**自愈**路径 |
| 排查 | 要 `schtasks /query` 看 `Last Result`，不主动看永远不知道 | 日志按天落盘，进程在任务管理器里可见 |
| 频率 | 定时触发，两次之间有大空窗 | 进程活着就看得住，最迟一个检查周期补回 |
| 交互 | 无交互桌面，禁止一切弹框（弹了就挂住） | 无窗口运行，天然不弹 |
| 非管理员 | 可以，但 `/TR` 引号/本地化输出坑多 | 快捷方式放 `Startup`，写文件即可 |

计划任务唯一的优势是"不用常驻一个进程"。但对"必须长期盯住注册表权限"这种需求，常驻进程的可靠性和可观测性都更好，代价（一个几 MB 的空闲进程、6 小时才醒一次）可以接受。

## 进程程序与激活程序分离

**激活是一次性动作，守护是长期常驻，两者目标与生命周期都不同 → 拆成两个 exe。**

| 文件 | 职责 | 生命周期 |
|---|---|---|
| `idmfrost.exe` | 界面 + 激活（重置、锁键、装/卸开机自启） | 只在用户双击期间 |
| `idmguard.exe` | 纯守护，无窗口、单实例，周期补锁 | 常驻后台 |

- 「一键完成」时：`idmfrost.exe` **立即 `exec` 一个 `idmguard.exe`**（`cmd.Process.Release()` 脱离父进程，不 `Wait`），随后写开机启动文件夹快捷方式。界面关掉后守护照跑。
- `idmguard.exe` 用 **`Global\` 命名 Mutex 做单实例**：已在跑时再启动会立即退出（实测 37ms，exit 0），不会出现两个守护互相打架。
- 开机自启快捷方式直接指向 `idmguard.exe --quiet`（`WindowStyle=7` 最小化、`WorkingDirectory` 设为 exe 目录）。
- 「回滚」顺序：先写 `config.enabled=false`（守护下次 tick 自杀式静默）→ 按进程名结束所有 `idmguard.exe` → 删自启快捷方式 → 解锁删键。
- 旧版单 exe 时代留下的 `idmtool 守护.lnk`（指向 `idmfrost.exe --daemon`）必须**主动清掉**，否则升级后旧快捷方式会在开机时拉起界面程序。

## 关键实现点

```go
// 1) 快捷方式指向同目录的 idmguard.exe，不写死绝对路径
func GuardExePath() string {
    exe, _ := os.Executable()
    return filepath.Join(filepath.Dir(exe), "idmguard.exe")
}

// 2) 拉起并脱离（关键：Release 而不是 Wait，否则父进程退出会带走子进程/留僵尸）
cmd := exec.Command(guard, "--quiet")
cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
_ = cmd.Start()
_ = cmd.Process.Release()   // 让守护独立常驻

// 3) 单实例：Global\ 命名互斥，ERROR_ALREADY_EXISTS=183 直接退出
h, _, e := CreateMutexW(nil, true, "Global\\idmguard_single_instance_v1")
if errno, ok := e.(syscall.Errno); ok && uint32(errno) == 183 { return false }
```

守护自身的判定逻辑（状态驱动，不猜天数）保留不变：

- 试用键都锁着 → **什么都不做**，连 IDM 都不碰
- 有未锁的键（被更新重写）→ 只补锁，**不启动、不杀 IDM**
- 键丢了 + IDM 未运行 → 临时启动一次重建，**只结束自己拉起的那个进程**（绝不 `taskkill /im idman.exe`）
- 键丢了 + IDM 正在跑 → 完全不动，等它自己写
- 连续失败 3 次 → 熔断冷却 6 小时，避免空转烧资源

## 坑

- **`kill` 按进程名**：回滚用 `CreateToolhelp32Snapshot` 枚举 `idmguard.exe` 再 `OpenProcess+TerminateProcess`，不 spawn `taskkill`（不闪黑窗、不依赖外部命令）。
- **`Process.Release` vs `Wait`**：回收守候进程若用 `Wait()`，父进程会被挂住；`Release()` 才能让子进程真正独立。反过来，短命的 `exec.Command`（如启动 IDM 生成试用键）**必须** `Kill()+Wait()`，否则僵尸进程拖死界面。
- **快捷方式路径自愈**：守护每次启动检查快捷方式 `TargetPath` 是否存在，不存在就按当前 exe 路径写回——用户把整个文件夹搬走也能自愈（需重启一次让守护跑起来）。
- **杀软误报**：常驻进程 + 改注册表 DACL 的组合容易被启发式引擎盯上，属常见误报。

> 历史方案（计划任务 + `--autofix`）见 [IDM 冻结后用计划任务自动补锁实现长期免维护.md](IDM%20冻结后用计划任务自动补锁实现长期免维护.md)，已不再采用。
