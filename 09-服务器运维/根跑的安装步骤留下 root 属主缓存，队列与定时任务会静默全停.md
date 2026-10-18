# 根跑的 build 步留下 root 属主缓存，队列与定时任务会"静默全停"

**结论**：安装脚本里凡是**以 root 跑过** `composer install` / `artisan`（`package:discover`、`key:generate`、`migrate`、`db:seed`）的，一定会在 `storage/` 和 `bootstrap/cache/` 留下 root 属主的缓存文件。之后以网站用户跑的队列 worker、调度器再写缓存就 `Permission denied` —— **定时任务全停、面板显示 worker 离线**，而安装过程一路"成功"。

## 为什么

以 Laravel 为例（实测 2026-10-17 读过上游 `install.sh` 的注释与实现）：

| 步骤 | 以谁的身份跑 | 写了哪 |
|---|---|---|
| `composer install`（触发 `package:discover`） | root | `bootstrap/cache/packages.php`、`services.php` |
| `key:generate` / `migrate` / `db:seed` | root | `storage/`、`bootstrap/cache/` |
| 队列 worker / 调度器（`schedule:run`） | 网站用户（`www-data` / nginx worker 用户） | 同一个 `storage/framework/cache` |

两边写同一个目录、属主不同 → worker 写不进去 → 心跳缓存写不进 → 监控面板判它离线 → 定时任务默默不跑。**报错不会出现在安装输出里**，只会出现在 worker 日志或面板状态上。

## 怎么做

安装/升级**末尾**加一步幂等的属主自愈，并且必须排在所有 root 动作之后：

```bash
# 只扫、干净就不动；脏了才 chown
NGINX_USER=$(ps -eo user,comm | grep nginx | awk '{print $1}' | grep -v root | head -1)
NGINX_USER=${NGINX_USER:-www-data}
BAD=$(find <项目>/backend/storage <项目>/backend/bootstrap/cache \
        ! -user "$NGINX_USER" -print -quit 2>/dev/null)
if [ -n "$BAD" ]; then
  chown -R "$NGINX_USER":"$NGINX_USER" <项目>/backend/storage <项目>/backend/bootstrap/cache
fi
```

要点：

1. **`bootstrap/cache` 不能漏** —— root 的 `packages.php` 正写在这里。
2. **扫描失败按"脏"处理**：宁可多做一次幂等 `chown`，也不要静默放过真实污染。
3. **非 root 执行时只提示不动作**（`chown` 必失败、刷屏），报出需要手工执行的那条命令。
4. **修复失败不中断安装**，但要给出可复制的收尾命令。

## 排查症状对照

| 症状 | 先查 |
|---|---|
| 面板显示队列 worker 离线，但进程在跑 | worker 日志里的 `Permission denied`；`ls -ln storage/framework/cache` 的属主 |
| 定时任务"配好了"却从不执行 | `schedule:run` 是否静默失败；`storage/logs` 能不能写 |
| 装完一切正常，过一夜才出问题 | 装完末尾有没有做属主修复 |

## 相关

- 改生产配置与重启服务：[改生产配置前先备份并停服务](改生产配置前先备份并停服务.md)
- 只读审计先看这类"安装脚本副作用"：[改之前先拿证据](../07-排错方法论/改之前先拿证据.md)
