# Tkinter 高 DPI 适配（Windows）

**结论**：创建 Tk 窗口前调 `SetProcessDpiAwareness(2)` 并 `tk scaling 1.0`，让 Tkinter 用物理像素渲染；所有尺寸按屏幕高度手动乘缩放比；`ttk.Combobox` 下拉列表要单独设字体，否则高分屏字特别小。

## 为什么

Windows 默认让 Tkinter 走系统自动缩放（DPI 虚拟化），结果：界面糊、控件尺寸错位、高分屏（2K / 4K）下字小到看不清。Tkinter 自己不会读 DPI，得手动接管。

## 怎么做

```python
import ctypes, tkinter as tk

# 1. 创建窗口前，声明进程自己处理 DPI（物理像素渲染）
ctypes.windll.shcore.SetProcessDpiAwareness(2)

root = tk.Tk()
# 2. 锁死 1:1，不让系统再自动缩放
root.tk.call("tk", "scaling", 1.0)

# 3. 手动算缩放比，所有尺寸乘以它
screen_h = root.winfo_screenheight()
scale = max(1.0, min(screen_h / 960, 2.4))
font_size = int(12 * scale)

# 4. ttk.Combobox 下拉 Listbox 不继承 TCombobox 字体，必须单独设
root.option_add("*TCombobox*Listbox.font", ("Microsoft YaHei", font_size))
# 兜底：没显式设字体的 tk 控件也统一字号
root.option_add("*Font", ("Microsoft YaHei", font_size))
```

尺寸、padding、字号全部用 `scale` 乘出来，不要写死像素。

## 反例

- 只设 `SetProcessDpiAwareness` 忘了 `tk scaling 1.0` → 系统仍自动缩放，界面错位
- 给 `TCombobox` 设了 `font` 但没设 `*TCombobox*Listbox.font` → 下拉列表字还是很小（尤其高分屏）
- 尺寸写死 `width=800` 不乘 scale → 4K 屏上窗口只占一角
