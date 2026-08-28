# pythonw 与 python 的区别

**结论**：后台 / 定时任务用 `pythonw.exe`，调试验证用 `python.exe`。

## 为什么

- `python.exe`：有控制台窗口，会往终端输出
- `pythonw.exe`：无窗口，**不产生任何控制台输出**

定时任务如果用 `python.exe`，每次触发都会弹一个黑框。反过来，如果用 `pythonw.exe` 去验证脚本，看不到任何输出，会误以为脚本没跑。

## 怎么做

同一个 Python 安装目录下两个 exe 并存：

```
C:\Users\<用户名>\.workbuddy\binaries\python\versions\3.13.12\python.exe
C:\Users\<用户名>\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe
```

- 定时任务、开机启动、后台常驻 → `pythonw.exe`
- 手动执行、排查问题、看输出 → `python.exe`

脚本本身不用改，靠调用哪个 exe 决定行为。日志一定要写文件，不能只靠 print —— pythonw 下 print 全丢。
