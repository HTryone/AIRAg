# conntrack 开机持久化

**结论**：任何依赖连接跟踪的 Linux 服务器（跑防火墙、代理、反向代理都算），必须显式保证 `nf_conntrack` 模块开机加载，并让相关 sysctl 在模块加载之后才生效。Debian / Ubuntu 默认**不保证**开机自动加载这个模块。

## 为什么

- 证据：一台 Debian 12 云服务器（内核 6.1.x），配过 `net.netfilter.nf_conntrack_max` 等 sysctl，重启后发现连接跟踪表上限仍是内核默认值——相关 sysctl 静默没生效。根因是模块没被加载，`sysctl --system` 在模块缺席时会跳过 netfilter 项且不报错。
- 这个模块历史上常被某个服务（早年 iptables / nftables 规则加载）顺带拉起。一旦关掉防火墙、改用纯代理，就再没有东西加载它，重启即丢。
- 教训：连接跟踪表上限这类参数，靠"系统默认会加载模块"是假的，必须自己钉死。

## 怎么做

两步，缺一不可。

### 第 1 步：写 modules-load.d，强制开机加载模块

```bash
echo "nf_conntrack" > /etc/modules-load.d/conntrack.conf
```

这保证开机把模块挂上。

### 第 2 步：写独立的 systemd service，在模块加载后再 apply sysctl

不能只靠 `/etc/sysctl.d/99-*.conf` + `systemctl restart systemd-sysctl`——因为 sysctl 服务可能跑在模块之前，模块没挂着时 netfilter 项被静默跳过。做法：

```bash
cat > /etc/systemd/system/conntrack-sysctl.service <<'EOF'
[Unit]
Description=Apply netfilter conntrack sysctl after module loaded
After=systemd-modules-load.service
Requires=systemd-modules-load.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/sbin/modprobe nf_conntrack
ExecStart=/sbin/sysctl -p /etc/sysctl.d/99-conntrack.conf

[Install]
WantedBy=multi-user.target
EOF
```

```bash
systemctl daemon-reload
systemctl enable --now conntrack-sysctl.service
```

把 conntrack 相关参数单独放一个文件：

```bash
cat > /etc/sysctl.d/99-conntrack.conf <<'EOF'
net.netfilter.nf_conntrack_max = 16384
EOF
```

| 参数 | 作用 |
|---|---|
| `nf_conntrack_max` | 连接跟踪表上限，小内存机压到 16384 省内存 |

### 关键顺序

**必须先 `modprobe nf_conntrack`，再 `sysctl -p`**。反过来 sysctl 静默跳过 netfilter 项，重启后参数回到默认。

### 验证

```bash
lsmod | grep nf_conntrack                      # 看到模块 = 已加载
cat /proc/sys/net/netfilter/nf_conntrack_max   # 看到你设的值 = 生效
```

重启后重跑这两行，确认仍然成立——开机自启是否真生效只能重启复验。

## 反例

- 只写 `/etc/sysctl.d/99-*.conf` 就以为 conntrack 参数开机生效——模块没加载，sysctl 静默跳过。
- 在 `sysctl --system` 之后才 `modprobe`——顺序反了，参数没被 apply。
- 以为"关了防火墙 conntrack 就没用了"——代理 / 反向代理照样要用连接跟踪表，关防火墙只是没人帮你加载模块。

## 相关

- [小内存服务器优化](小内存服务器优化.md)
- [改生产配置前先备份并停服务](改生产配置前先备份并停服务.md)
