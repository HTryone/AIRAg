# bat 文件用 ASCII 内容

**结论**：`.bat` 文件正文全部用英文 / ASCII 字符，中文提示交给被调用的 Python 脚本输出。文件里加 `chcp 65001` 只用于让脚本的中文正常显示。

## 为什么

Windows 按 ANSI 代码页解析 bat 文件，中文内容会乱码，尤其在非中文系统上。

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
