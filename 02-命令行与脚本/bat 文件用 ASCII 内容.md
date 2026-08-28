# bat 文件用 ASCII 内容

**结论**：`.bat` 文件正文全部用英文 / ASCII 字符，中文提示交给被调用的 Python 脚本输出。文件里加 `chcp 65001` 只用于让脚本的中文正常显示。

## 为什么：bat 解析器 和 Python 输出是两回事

Windows 解析 bat 时，是按**当前代码页把字节切成 token** 的。中文是多字节字符，解析器会把它当**命令边界**切开——所以 bat 里直接写中文 `echo` 不只是乱码，**会直接被拆成多条命令报错**：

```
'的' is not recognized as an internal or external command
```

关键点：`chcp 65001` 改的是**控制台显示的编码**，改不了 bat 自己被解析的方式。无论怎么设代码页，bat 里写中文都不稳。

而 bat 调用 Python 时，Python 的 `print("中文")` 走的是 **Python 自己的 stdout 管道，不经过 cmd / PowerShell 的 bat 解析器**。所以：

- bat 里写中文 echo → 被解析器切字节 → 报错
- Python 里 print 中文 → UTF-8 直灌控制台 → 正常（前提是 bat 顶部 `chcp 65001` 让控制台能渲染 UTF-8）

一句话：**bat 别碰中文，中文交给 Python，两边各管各的就不乱。**

## 怎么做

标准模板：

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
"C:\Users\Htryone\.workbuddy\binaries\python\versions\3.13.12\python.exe" checkin.py --status
echo.
pause
```

要点：
- `cd /d "%~dp0"` — 切到 bat 所在目录，双击时才找得到脚本
- python 路径写死绝对路径 — bat 是文件，不存在变量失效问题
- `pause` — 双击时窗口不会一闪而过
- 中文全部不出现在 bat 里

---

## 补充：一定要写中文，就存成 UTF-8 BOM

上面的做法（中文交给被调用的脚本输出）最稳。但**如果中文必须写在 bat 里**，解法是存成 UTF-8 BOM 编码。

不带 BOM 时，Windows 按系统默认的 ANSI 代码页解析中文注释，整片炸成：

```
'xxx' 不是内部或外部命令
```

带 BOM 就能正确识别为 UTF-8，中文注释和输出都正常。

**实测（2026-08-15）**：一个启动脚本的中文注释整片乱码，改用 UTF-8 BOM 编码写出后正常。

| 做法 | 适用 |
|---|---|
| 正文纯 ASCII，中文交给被调用脚本 | 首选，最稳，不受编码影响 |
| 存成 UTF-8 BOM | 中文必须写在 bat 里时 |

**注意**：只在本机用、确定系统代码页是中文的环境下，不带 BOM 也可能正常；换个系统就会炸，所以要么纯 ASCII，要么加 BOM，别赌。
