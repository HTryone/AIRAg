# Git Bash 路径写法

**结论**：Git Bash 里给 Windows 程序传路径，用 `D:/perca/...` 这种带盘符的正斜杠写法，或者先 `cd` 进目录再用相对文件名。

## 为什么

Git Bash 的 `/d/perca/...` 是它自己的虚拟路径，Windows 版 Python 不认，会解析成 `d:\d\perca\...`：

```
can't open file 'd:\d\perca\zidqdworkbuddy\wb-checkin\checkin.py'
```

## 怎么做

推荐先 cd 再执行（也顺带避免变量问题）：

```bash
cd /d/perca/zidqdworkbuddy/wb-checkin
python checkin.py --status
```

必须传绝对路径时写成：

```bash
python D:/perca/zidqdworkbuddy/wb-checkin/checkin.py
```

## 反例

```bash
python /d/perca/zidqdworkbuddy/wb-checkin/checkin.py   # 会变成 d:\d\...
```
