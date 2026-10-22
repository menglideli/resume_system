#!/bin/bash
# 启动脚本：等待 MySQL 就绪 → 执行迁移 → 启动服务（指令 9）
set -e

echo "==> 等待 MySQL 就绪..."
python - <<'PY'
import os, socket, sys, time
from urllib.parse import urlparse

url = urlparse(os.environ.get("DATABASE_URL", "mysql+asyncmy://root:root@db:3306/resume_system"))
host, port = url.hostname or "db", url.port or 3306
for i in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            sys.exit(0)
    except OSError:
        time.sleep(1)
sys.exit("MySQL 连接超时")
PY

echo "==> 执行数据库迁移（alembic upgrade head，无迁移版本时跳过，表由 init.sql 保证）..."
if [ -d "alembic/versions" ] && [ "$(ls -A alembic/versions/*.py 2>/dev/null)" ]; then
    alembic upgrade head
else
    echo "    （未发现迁移版本，跳过；表结构由 sql/init.sql 或后续 alembic revision 提供）"
fi

echo "==> 启动服务..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
