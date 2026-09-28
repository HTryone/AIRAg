# Go 桌面程序的 Windows 原生能力（Win32 调用、UAC 清单）

用 Go 写 Windows 桌面程序，要拿到系统级能力（改系统时间、读写注册表、提权），同时不引第三方包、不开 cgo。这篇是完整模块，单独看这一篇就够。

---

## 一、先决定要不要引第三方包

Go 标准库的 `syscall` 自带 `NewLazyDLL` / `NewProc`，可以按名字调用任意 Win32 导出函数，不需要 cgo，也不需要头文件。

| 方案 | 好处 | 代价 |
|---|---|---|
| 引 `golang.org/x/sys/windows` | 结构体、常量都是现成的，写起来快 | 多一个外部依赖；离线或拉不到包的环境会直接卡住构建 |
| 只用标准库 `syscall` | 零依赖，`go build` 一条命令出单文件 exe，不怕拉包失败 | 结构体、常量、参数位宽全部照着 Win32 文档手写 |

判断标准是**依赖数量本身算成本**：要发给别人的绿色小工具、内网拉不到包的环境，选零依赖；依赖管理已经成熟的项目，用 `x/sys` 更省事。

---

## 二、声明并调用一个 Win32 API

三步：加载 DLL → 按名字取函数 → 调用。用包级变量做懒加载，全程只加载一次。

```go
//go:build windows

package main

import "syscall"

var (
	modKernel32 = syscall.NewLazyDLL("kernel32.dll")

	procGetTickCount64 = modKernel32.NewProc("GetTickCount64")
)

// GetTickCount64 返回系统启动至今的毫秒数。
func GetTickCount64() uint64 {
	r, _, _ := procGetTickCount64.Call()
	return uint64(r)
}
```

三个要点：

**1. 函数名必须和 DLL 导出的完全一致，大小写敏感。** Win32 文档里是大驼峰（`GetTickCount64`、`SetSystemTime`），写成 `getTickCount64` 会加载失败。

**2. `Call()` 的第三个返回值只在函数真的报错时非 nil。** 很多 API 正常也返回 0，所以不能拿 `err != nil` 当"调用失败"的判据，要看具体 API 的约定。像 `SetSystemTime` 这种"返回 0 就是失败"的，才这样写：

```go
r, _, callErr := procSetSystemTime.Call(uintptr(unsafe.Pointer(&st)))
if r == 0 {
	return callErr
}
```

**3. 参数一律 `uintptr`，传结构体用 `unsafe.Pointer(&x)`。** 句柄类返回值（`HANDLE`）必须当 `uintptr` 处理，不能声明成 `uint32` —— 64 位下会被截断，句柄失效。

### 有些 API 还要先开特权

即使进程已经是管理员，改系统时间仍然要显式打开 `SeSystemTimePrivilege`，否则 `SetSystemTime` 直接失败。流程是 `OpenProcessToken` → `LookupPrivilegeValueW` → `AdjustTokenPrivileges`，其中 `Attributes` 填 `SE_PRIVILEGE_ENABLED`（`0x00000002`）。

判断"当前是不是管理员"要查令牌的提升标志（`GetTokenInformation` + `TokenElevation`，值为 `20`），**不要用 `IsUserAnAdmin`** —— 后者是未公开接口，且在"属于管理员组但未提权"时语义含混。

---

## 三、手写的结构体必须配尺寸断言测试

结构体字段的顺序、类型、对齐只要错一处，**不会编译报错**，只会让 API 读到错位的内存，表现为返回值莫名其妙或静默出错。所以每个手写的结构体都配一个断言测试，把尺寸钉死：

```go
//go:build windows

package main

import (
	"testing"
	"unsafe"
)

func TestWin32StructLayout(t *testing.T) {
	if got := unsafe.Sizeof(systemTime{}); got != 16 {
		t.Fatalf("SYSTEMTIME 应为 16 字节，实际 %d", got)
	}
	if got := unsafe.Sizeof(shellExecuteInfo{}); got != 112 {
		t.Fatalf("SHELLEXECUTEINFOW 应为 112 字节，实际 %d", got)
	}
	// 句柄字段必须是指针宽度
	if unsafe.Sizeof(uintptr(0)) != unsafe.Sizeof(shellExecuteInfo{}.hProcess) {
		t.Fatal("句柄字段的宽度不是指针宽度")
	}
}
```

两个容易算错的尺寸：

- `SYSTEMTIME` 是 8 个 `uint16` = **16** 字节，全架构一致。
- `SHELLEXECUTEINFOW` 在 64 位下是 **112** 字节 —— `nShow` 之后、`hInstApp` 之前有 4 字节填充，`hIcon` 之前还有一处。漏掉这两处填充，`ShellExecuteExW` 就会读错字段。

含指针或 `HANDLE` 的结构体尺寸随架构变，断言要按 `GOARCH` 分开写。

---

## 四、让程序一启动就提权：内嵌 UAC 清单

默认情况下 Go 编译出的 exe 是 `asInvoker`（普通权限）。需要提权时只能在运行中用 `runas` 再启动一次自己，**代价是多开一个控制台窗口** —— 用户看到两个窗口一闪一换。

正确做法是把 UAC 清单内嵌进 exe，让 Windows 在**第一次启动时**就完成提权，全程只有一个窗口。

### 清单内容

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity type="win32" name="YourApp" version="1.0.0.0" processorArchitecture="*"/>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
</assembly>
```

### 怎么塞进 exe：独立子包 + 构建标签

Go 会自动链接包目录下的 `*.syso`，文件名按 `_GOOS_GOARCH` 后缀区分架构（如 `app_windows_amd64.syso`）。

但**清单不能无条件链进去**，原因是：

> 清单要求管理员权限。一旦它被无条件链进包，`go test` 生成的测试程序也会带上这份清单，普通权限下根本启动不了，直接报「请求的操作需要提升」，所有测试全废。

解法是把 `.syso` 放进一个**独立子包**，再用构建标签决定谁导入它：

```
<你的项目>/src/
├─ winres/
│   ├─ winres.go                       空包，只为承载资源对象
│   ├─ app_windows_amd64.syso
│   └─ app_windows_arm64.syso
└─ manifest_windows.go                 //go:build windows && winmanifest
```

```go
//go:build windows && winmanifest

package main

import _ "你的模块名/winres"
```

于是两条路径分开了：

```bash
# 正式构建：带标签 → 链入清单，启动即提权
go build -tags winmanifest -trimpath -ldflags "-s -w" -o app.exe .

# 跑测试：不带标签 → 测试程序没有清单，普通权限就能跑
go test ./...
```

### .syso 从哪来

`windres`、`rsrc` 这类工具能生成，代价是额外装一套工具链。要彻底零依赖，可以自己按 PE/COFF 规范拼一个目标文件：清单正文放进资源段，再补重定位表。自己拼时的两个关键点：

- **重定位类型按架构取**：amd64 用 `IMAGE_REL_AMD64_ADDR32NB`（`0x0003`），arm64 用 `IMAGE_REL_ARM64_ADDR32NB`（`0x0002`）。
- **COFF 头里的 `Machine` 要填对**：amd64 是 `0x8664`，arm64 是 `0xAA64`。填错会在链接阶段报机器类型不匹配。

资源段的三层结构是「资源类型 → 资源 ID → 语言」：

| 项 | 值 |
|---|---|
| 资源类型 | `RT_MANIFEST` = **24** |
| 资源 ID | **1**（应用程序清单固定用 ID 1） |
| 语言 | **1033**（美式英语，Windows 的常规取值） |

**关键点：目录内部各层的偏移都是「相对资源段开头」的，不是 RVA。** 只有最后数据条目里那个数据指针是 RVA，所以只有它需要重定位，由链接器补上段虚拟地址。

**绝对不能把 `*.syso` 加进 `.gitignore`。** 它看着像编译产物，实际是构建输入 —— 要么入库，要么在构建流程里先重新生成，否则构建出的 exe 不会提权。

---

## 五、怎么验证清单真的生效

### 第 1 步：从成品 exe 里读回来

用标准库 `debug/pe` 打开成品 exe，解析资源目录，把清单读出来，确认数据指针是合法 RVA（说明链接器正确修正了重定位）。读不出来或读到乱码，说明资源段拼错了。

**这一步有个必踩的坑：PE 资源目录的偏移是「相对资源目录的起点」，不是相对当前层的起点。** 三层目录（类型 → 名称/ID → 语言）里的目录偏移和条目偏移全都从资源目录根算起。按"相对当前层"去解析，第二层还能蒙对，第三层就会算出越界地址。

### 第 2 步：差分验证

只确认"清单在 exe 里"还不够，要确认 **Windows 真的按它执行了**。做法是把同一份代码的清单改成 `asInvoker` 再构建一次：

| 构建用的清单 | 普通权限下启动 |
|---|---|
| `asInvoker` | 能启动 |
| `requireAdministrator` | 被拒绝启动 |

两种行为都符合预期，才说明清单不是"格式坏了被系统忽略"，而是真的生效了。

---

## 六、常见坑

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 函数名大小写和导出名不一致 | `NewProc` 取不到函数，调用即崩 | 照 Win32 文档原样写大驼峰 |
| 拿 `Call()` 的 `err` 当失败判据 | 很多 API 正常也返回 0，被误判成出错 | 按各 API 的约定判断，如 `r == 0` |
| 句柄返回值声明成 `uint32` | 64 位下被截断，句柄失效 | 一律用 `uintptr` |
| 手写结构体漏算填充 | API 读到错位内存，返回值莫名其妙 | 写尺寸断言测试钉死 |
| 以为管理员就能改系统时间 | `SetSystemTime` 仍失败 | 先 `AdjustTokenPrivileges` 开 `SeSystemTimePrivilege` |
| 用 `IsUserAnAdmin` 判管理员 | 未公开接口，未提权时语义含混 | 查令牌的 `TokenElevation` |
| 清单无条件链进包 | `go test` 报「请求的操作需要提升」，测试全废 | `.syso` 放独立子包，用构建标签控制导入 |
| 把 `*.syso` 加进 `.gitignore` | 构建出的 exe 不提权 | 它是构建输入，必须入库或构建时生成 |
| 按"相对当前层"解析 PE 资源目录 | 第三层算出越界地址，读不到清单 | 所有目录偏移都相对资源目录起点 |
| 只验证"清单在 exe 里" | 这一步只证明资源段拼对了，不证明 Windows 会按它执行 | 再做一次 `asInvoker` 差分验证 |
