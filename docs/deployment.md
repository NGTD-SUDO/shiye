# 部署指南（自托管）

> 目标读者：想把拾页跑在自己服务器上的人。**本文不含任何具体服务器/域名信息**，按你的环境替换占位符。

## 0. 前置条件

| 项 | 要求 |
|---|---|
| 服务器 | 1 核 2G 起步即可（个人/家庭量级）；RapidOCR 建议 2 核 4G |
| Python | 3.11+（开发环境实测 3.13） |
| Flutter | 3.24+（仅打包客户端时需要，见 `frontend/`） |
| 外部依赖 | 百度智能云 OCR key（或本地 RapidOCR）、DeepSeek API key（AI 功能），都可不配（对应功能降级为不可用） |

## 1. 本地 / 单机跑起来

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env          # 填 SHIYE_SECRET_KEY / OCR key / DeepSeek key
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl http://127.0.0.1:8000/health
```

手机要连得上，注意三点：

1. 后端必须 `--host 0.0.0.0`（默认只听 127.0.0.1）
2. Android 9+ 默认禁明文 HTTP → 内测版 Manifest 已开 `usesCleartextTraffic="true"`（**生产请改用 HTTPS**）
3. 客户端打包时用 `--dart-define=API_BASE_URL=http://<服务器IP>:8000` 注入地址（源码里不硬编码任何域名）

## 2. 用 systemd 常驻

```ini
# /etc/systemd/system/shiye.service
[Unit]
Description=ShiYe backend
After=network.target

[Service]
WorkingDirectory=/opt/shiye/backend
EnvironmentFile=/opt/shiye/backend/.env
ExecStart=/opt/shiye/backend/.venv/bin/python -m uvicorn app.main:app \
          --host 0.0.0.0 --port 8000 --no-access-log
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now shiye
journalctl -u shiye -f
```

## 3. 反向代理 + HTTPS

Nginx 片段（换成你自己的域名与证书路径）：

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.example;

    ssl_certificate     /etc/letsencrypt/live/your-domain.example/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.example/privkey.pem;

    client_max_body_size 20m;          # 笔记原图上传

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

改完代理后，客户端要用 `--dart-define=API_BASE_URL=https://your-domain.example` 重新打包。

## 4. 临时对外演示（无公网服务器时）

用任意隧道工具把本机 8000 暴露出去即可，例如：

```bash
cloudflared tunnel --url http://localhost:8000 --no-autoupdate
# 启动后它会打印一个临时公网地址（形如 https://xxx.<隧道服务域名>）
```

⚠️ **三点务必注意**：

1. 该地址**每次重启都会变**，客户端必须重新打包
2. 临时隧道 = 公开入口，**不要长期开着**，且务必先设置强 `SHIYE_SECRET_KEY`、`SHIYE_DEV_MODE=false`
3. 部分隧道/代理会改写页面里的明文邮箱（这也是本项目把法律文档里的邮箱写成 HTML 实体 `&#64;` 的原因）—— 别把它改回裸 `@`

## 5. 升级与备份

- 备份：SQLite 库文件 + 图片存储目录，两者一起备份即可恢复全量（`SHIYE_DATABASE_URL` / `SHIYE_STORAGE_DIR` 指向的位置）
- 升级：拉新代码 → `pip install -r requirements.txt` → `systemctl restart shiye`（表结构变更由应用启动时处理，无迁移工具依赖）

## 6. 上线前自检

```bash
# 1) 密钥与开关
grep -E "SHIYE_SECRET_KEY|SHIYE_DEV_MODE|SHIYE_CORS_ORIGINS" backend/.env

# 2) 后端测试
cd backend && pytest tests/ -q

# 3) 真实上传一张图，确认 OCR 状态走到 done
curl -F "file=@page.jpg" -H "Authorization: Bearer <token>" http://127.0.0.1:8000/pages/upload
```
