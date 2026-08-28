# 日志与磁盘防撑满（journald 限容、apt 自动清、旧内核清理）

**结论**：系统盘小的服务器（如 5~10G），必须主动限制 journald 日志体积、让 apt 缓存自动清、定期清旧内核。否则日志和缓存会慢慢把盘撑满——撑满后服务起不来，SSH 都可能写不了。

---

## 一、这是什么

三件事，分别防三类"静默吃盘"：

| 措施 | 防什么 |
|---|---|
| journald `SystemMaxUse` | 系统日志无限增长 |
| apt `Clean-Installed=true` | 装包缓存越积越多 |
| 旧内核清理 | 每次升级内核多占几百 MB，从不回收 |

---

## 二、适用

系统盘 < 20G 的云服务器尤其要做。实测一台 4.9G 系统盘的机器，不限制日志，长期跑会逼近满盘。

---

## 三、从零做

### 1. journald 日志限容

```bash
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/limit.conf <<'EOF'
[Journal]
SystemMaxUse=50M
SystemKeepFree=20M
EOF
systemctl restart systemd-journald
```

| 参数 | 作用 |
|---|---|
| `SystemMaxUse` | journald 日志最多占这么多，超出按时间滚掉旧的 |
| `SystemKeepFree` | 始终给磁盘留这么多空闲，避免日志把盘写满 |

验证：`journalctl --disk-usage` 看实际占用，应在上限附近。

### 2. apt 装包缓存自动清

```bash
cat > /etc/apt/apt.conf.d/99auto-clean <<'EOF'
APT::Clean-Installed "true";
EOF
```

效果：`apt install` 装完后自动清掉 `/var/cache/apt/archives/` 里的 .deb 缓存，不留一堆安装包。

### 3. 旧内核清理

Debian / Ubuntu 每次 `apt upgrade` 内核会留旧版本，手动清：

```bash
dpkg -l | grep linux-image          # 列出已装内核
uname -r                            # 确认当前在跑的内核
apt-get autoremove --purge          # 删不再依赖的旧内核（保留正在用的和回退用的一个）
```

危险：别手删正在跑的内核。`autoremove` 默认会保留当前内核，不要手动 `dpkg -r linux-image-<当前>`。

---

## 四、日常管理

| 想查 | 命令 |
|---|---|
| 日志占了多少 | `journalctl --disk-usage` |
| 磁盘还剩多少 | `df -h /` |
| 内核占了哪些 | `dpkg -l | grep linux-image` |
| 缓存占了多少 | `du -sh /var/cache/apt/archives` |

---

## 五、排查（盘快满时）

```bash
df -h /                                    # 先看是不是真快满了
du -x -h / 2>/dev/null | sort -rh | head -20   # 找出最占空间的顶层目录
journalctl --disk-usage                   # 日志是否超上限（没限容时会很大）
apt-get autoremove --purge                # 清旧内核
```

找到大目录后逐层 `du` 下钻，别上来就 `rm -rf`。

---

## 六、避坑表

| 坑 | 后果 | 正确做法 |
|---|---|---|
| 不设 `SystemMaxUse` | 日志几年涨到几百 MB~GB | 一上手就限 50M |
| 手删内核 | 删了正在跑的内核直接开不了机 | 用 `autoremove`，别手动 `dpkg -r` 当前内核 |
| 盘满了才查 | 服务写不了、可能起不来 | `df -h` 当日常，早看到早处理 |
| `rm -rf` 大目录 | 误删系统文件 | 先 `du` 定位，确认再删 |

---

## 相关

- [小内存服务器优化](小内存服务器优化.md)
- [流量监控三件套（vnstat、iftop、nethogs）](流量监控三件套%20（vnstat、iftop、nethogs）.md)
