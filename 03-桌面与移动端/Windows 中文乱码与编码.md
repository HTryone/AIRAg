# Windows 中文乱码与编码

**结论**：乱码不是随机的，是**读的时候用的编码和写的时候不一致**。查乱码就是查这条链路上哪一环对不上。

---

## 一、三个地方必须对上

一份文本从产生到显示，经过三个环节。任意两个不一致就乱码：

```
文件存的编码  →  程序读取时指定的编码  →  终端/编辑器显示用的编码
```

| 环节 | 由什么决定 | 怎么看 |
|---|---|---|
| 文件存的编码 | 保存时选的 | 用支持编码显示的编辑器（VS Code、Notepad++）看右下角 |
| 程序读取的编码 | 代码里写的 `encoding=` 参数，或程序默认值 | 看代码 |
| 终端显示编码 | 代码页（`chcp`） | `chcp` 命令 |

**最常见的原因**：程序没显式指定编码，用了系统默认。中文 Windows 默认是 GBK，而文件是 UTF-8 存的，读出来就是乱码。

---

## 二、代码页是什么

Windows 用数字编号表示字符集：

| 代码页 | 字符集 | 场景 |
|---|---|---|
| 936 | GBK | 中文 Windows 默认 |
| 65001 | UTF-8 | 跨平台通用 |

看当前的：

```powershell
chcp
```

临时切到 UTF-8：

```powershell
chcp 65001
```

**只影响当前这个窗口**，新开一个还是 936。

永久改（注册表，改完重开窗口生效）：

```powershell
Set-ItemProperty HKCU:\Console VirtualTerminalLevel -Type DWord 1
New-ItemProperty HKCU:\Console CodePage -Value 65001 -PropertyType DWord -Force
```

永久改有副作用：一些老程序在 65001 下会输出异常。不是必须的话，建议只在需要时临时 `chcp`。

---

## 三、Python 里的处理

### 读写文件一律显式指定

```python
with open('data.txt', encoding='utf-8') as f:
    content = f.read()

with open('out.txt', 'w', encoding='utf-8') as f:
    f.write(content)
```

**不写 `encoding=` 参数就会用系统默认**，在中文 Windows 上是 GBK。这就是为什么同一段代码在别人机器上正常、在你机器上报 `UnicodeDecodeError`。

### 三种典型报错

| 报错 | 含义 |
|---|---|
| `UnicodeDecodeError: 'gbk' codec can't decode byte` | 用 GBK 去读了 UTF-8 文件 |
| `UnicodeDecodeError: 'utf-8' codec can't decode byte` | 用 UTF-8 去读了 GBK 文件 |
| 打印出来是 `\xe4\xb8\xad` 这种 | 拿到的是字节不是字符串 |

### 已经乱码了怎么救

不知道原编码时，按概率试：

```python
raw = open('mess.txt', 'rb').read()
for enc in ['utf-8', 'gbk', 'gb18030', 'big5']:
    try:
        print(enc, '->', raw.decode(enc)[:50])
    except UnicodeDecodeError:
        print(enc, '-> 失败')
```

`gb18030` 是 GBK 的超集，GBK 读不了的时候先试它。

---

## 四、bat 文件是特例

bat 脚本必须用 ASCII 内容，写了中文会乱码甚至执行失败。详见 [bat 文件用 ASCII 内容](../02-命令行与脚本/bat%20文件用%20ASCII%20内容.md)。

---

## 五、常见现象对照表

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 只有中文乱，英文正常 | 典型编码不匹配 | 按第一节查三个环节 |
| 显示成 `?????` | 编码转换时字符无法映射，已不可逆 | 回到源头用正确编码重新读 |
| 显示成 `锟斤拷` | UTF-8 字节被当成 GBK 读了 | 用 UTF-8 重读 |
| 显示成 `\u4e2d\u6587` | 是转义序列不是乱码 | 做一次 unicode 转义解码 |
| Git Bash 里中文文件名显示为转义 | Git 配置了路径转义 | `git config --global core.quotepath false` |
| 代码在自己机器正常，CI 上乱码 | CI 环境默认 UTF-8，本地默认 GBK | 代码里显式指定编码 |

`锟斤拷` 是 UTF-8 的中文被 GBK 解读后的经典产物，看到这三个字基本可以锁定是这个方向错了。

---

## 六、预防措施

| 场景 | 做法 |
|---|---|
| 写 Python 脚本 | 所有 `open()` 都带 `encoding='utf-8'` |
| 新建文本文件 | 统一存 UTF-8（无 BOM） |
| Git 仓库 | 加 `.gitattributes`：`* text=auto eol=lf` |
| 跨平台脚本 | 不依赖系统默认编码，全部显式指定 |
| bat 脚本 | 内容保持 ASCII |

**UTF-8 带不带 BOM**：Windows 老程序（如记事本旧版）需要 BOM 才认 UTF-8，但 BOM 会让 Linux 上的脚本解释器报错。跨平台项目用无 BOM 的 UTF-8。

---

## 相关

- [bat 文件用 ASCII 内容](../02-命令行与脚本/bat%20文件用%20ASCII%20内容.md)
- [Git Bash 路径写法](../02-命令行与脚本/Git%20Bash%20路径写法.md)
- 文档本身该怎么写：[说明文档用纯中文](../06-文档与表达/说明文档用纯中文.md)
