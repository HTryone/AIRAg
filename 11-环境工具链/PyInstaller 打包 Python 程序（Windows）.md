# PyInstaller 打包 Python 程序（Windows）

把 Python 脚本打成单个 exe，别人不用装 Python 就能跑。这篇讲 Windows 上打包 GUI / 带第三方库程序时的 hiddenimports、构建卫生和常见坑。

---

## 一、为什么需要 hiddenimports

PyInstaller 靠**静态分析**找 import。很多库是**动态导入**子模块的（按文件名、按平台分支），静态扫不到，打包不报错，但运行到那行才 `ModuleNotFoundError`。

典型要加 hiddenimports 的库：

| 库 | 为什么要加 | 触发场景 |
|---|---|---|
| `send2trash` | 平台后端（Windows 走 COM）动态加载 | 删文件到回收站 |
| `win32com` | 大量子模块动态导入 | 操作 Windows COM / shell |
| `mutagen` | 各音频格式解析器动态加载 | 读 mp3 / flac 等标签 |
| `pywin32` | win32api / win32gui 等子模块 | 调用 Windows API |
| `requests` | 发 HTTP 时部分解析器动态加载 | 走 WebDAV / 接口 |

## 二、怎么做

### 命令（一次性打包）

```bash
pyinstaller --onefile --windowed --hidden-import send2trash --hidden-import win32com --hidden-import mutagen --hidden-import pywin32 --hidden-import requests "你的脚本.py"
```

- `--onefile`：打成单个 exe（分发方便）；`--onedir` 是一堆文件，启动快、好排查
- `--windowed`：GUI 程序不弹黑框；命令行程序不要加

### spec 文件（反复打包推荐）

反复打包用 `.spec` 文件锁死配置，比一长串命令行好维护：

```python
# 你的脚本.spec
a = Analysis(
    ["你的脚本.py"],
    hiddenimports=["send2trash", "win32com", "mutagen", "pywin32", "requests"],
    ...
)
```

打包：`pyinstaller "你的脚本.spec"`

## 三、构建卫生（避免垃圾和失败）

| 步骤 | 做法 | 为什么 |
|---|---|---|
| 构建前先关旧 exe | 任务管理器结束旧的 `你的脚本.exe` | 旧进程占着文件，`pyinstaller` 写不进，还可能残留 `*.exe~` |
| 打包后清 dist | 删 `*.exe~` / `*.bak` / `*.log` / 空目录 | 旧进程未关会残留备份文件，dist 要保持干净 |
| 别把配置打进 exe | 配置走外部文件或运行时生成 | 换机器 / 换账号不用重新打包 |

`*.exe~` 是构建链在文件被占用时的备份垃圾，关掉旧进程再构建就不会有。

## 四、验证

打包完**双击 exe** 跑一遍，看有没有 `ModuleNotFoundError` / 闪退。命令行程序能直接看到报错；GUI 程序闪退就临时去掉 `--windowed` 看报错。

## 五、避坑表

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 漏 hiddenimports | 运行才报 `ModuleNotFoundError` | 按第一节清单加 |
| GUI 加了 `--windowed` 还弹黑框 | 有未捕获异常 | 先去掉 `--windowed` 看报错 |
| 旧 exe 没关就构建 | 写不进 / `*.exe~` 残留 | 构建前结束旧进程 |
| 配置写死进 exe | 换环境要重新打包 | 配置外置 |
| 用系统 Python 直接装包 | 污染用户环境 | 用 venv 隔离（见 [Node 与 Python 多版本管理](Node%20与%20Python%20多版本管理.md)） |

## 相关

- 多版本 / 隔离环境：[Node 与 Python 多版本管理](Node%20与%20Python%20多版本管理.md)
- GUI 高 DPI 适配：[Tkinter 高 DPI 适配（Windows）](../03-桌面与移动端/Tkinter%20高%20DPI%20适配（Windows）.md)
