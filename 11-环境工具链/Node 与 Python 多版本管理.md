# Node 与 Python 多版本管理

一台机器上同时装好几个版本的 Node 和 Python 是常态。这篇讲怎么查清自己有哪些、怎么指定用哪个、包装到哪。

---

## 一、为什么会有多个版本

四个来源叠在一起：

| 来源 | 说明 |
|---|---|
| 系统自带 | 操作系统预装的 |
| 自己装的 | 从官网下载安装的 |
| 工具链管理的 | 由某个平台工具装在特定目录下，跟系统那份互不干扰 |
| 项目内置的 | 有的项目会自带一份运行时 |

**靠命令名（`python`、`node`）猜自己用的是哪一个，是这类问题的主要来源。** 后面所有做法都指向同一件事：明确指定，别猜。

---

## 二、先查清自己有哪些

不要凭印象。先列出来：

| 系统 | 查 Python | 查 Node |
|---|---|---|
| Windows（PowerShell） | `where python` | `where node` |
| Windows（Git Bash） | `where python` | `where node` |
| Linux / macOS | `which -a python3` | `which -a node` |

`where` / `which -a` 会按优先级列出所有匹配项，**第一个就是直接敲命令时会用到的那个**。

确认版本：

```bash
python --version
node --version
```

重点是**用完整路径查版本**，这样才能知道每个位置分别是什么版本：

```bash
C:\你的安装路径\python.exe --version
```

---

## 三、怎么指定用哪个

### 原则：写完整路径，不依赖 PATH

PATH 会变——换一个终端、换一个用户、改一次环境变量，指向的就可能不是原来那个。

| 场景 | 做法 |
|---|---|
| 手动敲命令 | 用完整路径，不用裸命令名 |
| 写进脚本 | 用完整路径，或脚本开头先探测再调用 |
| 写进定时任务 / 服务 | **必须**用完整路径 |

定时任务里尤其要注意：它的环境变量和普通终端不一样，裸命令名经常指向别处。见 [Windows 定时任务](../03-Windows%20系统/Windows%20定时任务.md)。

### 项目级锁定

在项目根放一个版本声明文件，让工具和人都知道该用哪个版本：

| 语言 | 文件 | 内容 |
|---|---|---|
| Python | `runtime.txt` 或 `pyproject.toml` | 版本号 |
| Node | `.nvmrc` 或 `package.json` 的 `engines` 字段 | 版本号 |

---

## 四、包装到哪

### 铁律：装进项目，不装进系统

全局装的包，换台机器、换个版本就找不到了，而且会污染其他项目。

**Python —— 每个项目一个虚拟环境：**

```bash
cd 你的项目目录
python -m venv .venv                    # 建环境（python 换成你要用的那个完整路径）
.venv\Scripts\python.exe -m pip install 包名     # Windows
.venv/bin/python -m pip install 包名            # Linux / macOS
```

关键：装包时用 `.venv` 里的那个 python，不要先激活再装——激活这一步在不同终端里行为不一致，容易装错地方。

**Node —— 装在项目目录：**

```bash
cd 你的项目目录
npm install 包名
```

装完在项目根目录生成 `node_modules`，只对这个项目生效。

禁止 `npm install -g` 和全局 `pip install`。真装了全局，用下面的命令查出来：

```bash
npm root -g          # 全局包装在哪
npm list -g --depth=0
pip list
```

---

## 五、怎么验证装对了

三件事都确认过才算数：

```bash
where python                      # 1. 用的是不是你想的那个位置
python --version                  # 2. 版本对不对
python -c "import 包名"            # 3. 包在不在（Node 用 node -e "require('包名')"）
```

第 3 步不能省。版本对但包不在，是最常见的"明明装了却说找不到"。

---

## 六、排查

| 现象 | 原因 | 怎么确认 |
|---|---|---|
| 提示"不是内部或外部命令" | 根本没装，或 PATH 里没有 | `where python` 有没有输出 |
| 装完还是找不到包 | 装到了另一个版本的环境里 | 比对 `pip -V` 显示的路径和你运行时的路径 |
| 版本跟预期不符 | PATH 里靠前的是另一个版本 | `where python` 看第一个是哪个 |
| Node 报 `EBADENGINE` | 项目要求的 Node 版本和当前不符 | 看报错里 `required` 和 `current` 两个值 |
| 终端里能跑，定时任务里跑不了 | 两者的环境变量不同 | 定时任务里写完整路径 |
| 在一个终端能跑，另一个不行 | Git Bash 和 PowerShell 的 PATH 各自独立 | 见 [PowerShell 与 Bash 不能互调](../02-命令行与脚本/PowerShell%20与%20Bash%20不能互调.md) |
| Windows 上敲 `python` 打开应用商店 | 命中了系统存根 | `where python` 看第一条，改用完整路径 |

---

## 七、避坑表

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 用裸命令名 `python` / `node` | 用的哪个版本不确定 | 写完整路径 |
| 全局装包 | 换环境就找不到，还污染别的项目 | 装进项目（venv / node_modules） |
| 先激活再装包 | 激活在不同终端行为不一致，容易装错 | 直接用环境里的解释器完整路径装 |
| 以为装了就算装对 | 版本对但包不在 | 按第五节三条都验证 |
| 定时任务里写裸命令名 | 环境变量不同，找不到或找错 | 必写完整路径 |
| 换机器后直接复制旧路径 | 路径不存在 | 路径不写死，先 `where` 查 |
| 手动改 PATH 排优先级 | 越改越乱，还影响其他程序 | 用完整路径，不动 PATH |
