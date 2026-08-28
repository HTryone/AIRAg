# 禁止在文档里引入 shell 变量

**结论**：给用户看的命令里，绝不出现 `=` 定义变量、`$VAR` 引用、`export`。宁可让命令长一点、重复一点，也不要"优化"成变量。

## 为什么

2026-08-29 我在文档里写了：

```bash
PY="C:/Users/xxx/.workbuddy/binaries/python/versions/3.13.12/python.exe"
"$PY" checkin.py --status
```

**变量只在定义它的那个终端窗口有效。** 用户新开一个窗口，`$PY` 展开成空字符串，bash 收到的是 `"" checkin.py --status`，直接报 `command not found`。

结果是用户原本能跑的命令，被我的"优化"搞成跑不了。用户原话："你为什么要引入新的变量？"

## 怎么做

直接写全，用系统本来就认得的命令（`python`、`node`、`git` 这些在 PATH 里的）：

```bash
cd /d/perca/zidqdworkbuddy/wb-checkin
python checkin.py --status
```

长路径只在脚本文件、bat、配置文件内部写死 —— 那些是文件，不是临时窗口，不存在失效问题。

## 自检

写完文档扫一遍：有没有 `=`、有没有 `$`、有没有 `export`。有就重写。
