# Nginx 站点结构（前后端同目录）

前端 SPA 与后端（PHP/Node）共用同一个 web root 的站点部署模式。单独看这一篇就够。

---

## 一、这是什么

一类常见站点：前端用 Vite/Webpack 构建成静态产物，后端是 PHP 或 Node 服务，两者**放在同一个目录**下由 Nginx 同时伺服。

典型结构：

```
<项目>/
├── backend/            # 后端代码
│   └── public/         # ← Nginx 的 root 指向这里
│       ├── index.php   # 后端入口（PHP-FPM 处理）
│       └── ...         # 其他后端静态资源
└── frontend/           # 前端源码
    └── dist/           # ← 构建产物，要复制到 public/
        ├── index.html
        └── assets/
```

Nginx 的 `root` 指向 `backend/public`。前端构建产物复制进去后，和 `index.php` 共存。

---

## 二、正确更新前端流程

```bash
git pull                                  # 拉最新代码
# 确认 frontend/dist/ 已经有构建产物（没有就先跑前端构建）
cp -r frontend/dist/* backend/public/     # 把构建产物复制进 web root
```

`cp` 是覆盖式复制：旧的前端产物被新产物覆盖，后端的 `index.php` 等不受影响。

---

## 三、红线（踩过才懂）

| 红线 | 后果 | 正确做法 |
|---|---|---|
| 用 `rm -rf backend/public/*` 先清空再复制 | **误删 `index.php`**，站点直接 502/空白 | 直接用 `cp -r` 覆盖，或只删前端产物（`assets/`、`index.html`、`favicon.ico`）再复制 |
| 擅自把 `root` 改成项目根目录 | 偏离作者设计，后端入口找不到，整站崩 | `root` 保持指向 `backend/public`，按作者设计来 |
| 改了前端但没重新构建 `dist/` | 复制进去的是旧产物，以为更新了其实没变 | `cp` 前确认 `dist/` 有最新构建 |
| PHP-FPM socket 路径对不上 | 动态请求 502 | `fastcgi_pass` 指向实际 socket，如 `/run/php/phpX.Y-fpm.sock`，版本号按实际装的来 |

`phpX.Y` 是占位：先看机器上实际装的是几（`ls /run/php/` 或 `php -v`），写死版本号换机器就 502。

---

## 四、排查：前端更新不生效

按顺序查：

```bash
nginx -T | grep -E "root|fastcgi_pass"   # root 指向哪、PHP socket 对不对
ls -la backend/public/                    # 里面是旧产物还是新的
ls -la frontend/dist/                     # dist 真有构建产物吗
```

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 页面空白 / 502 | `index.php` 被误删 | 从后端代码恢复 `index.php`，不要重建整个 public |
| 还是旧版样式 | `dist/` 是旧的 | 重新构建前端，再 `cp` |
| 动态请求 502 | PHP-FPM socket 不对 | 改 `fastcgi_pass` 指向实际 socket |

---

## 五、相关

- 证书怎么配：[证书申请与自动续期](证书申请与自动续期.md)
- 服务器怎么连：[SSH 服务器连接与管理](SSH 服务器连接与管理.md)
