# 智能简历投递系统 · 后端镜像（指令 9）
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /code

# ---- 系统依赖：Playwright 浏览器依赖 + 中文字体 + 文档处理库依赖 ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg \
    fonts-noto-cjk \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# ---- Python 依赖 ----
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---- Playwright Chromium（PDF 导出） ----
RUN playwright install chromium

# ---- 项目代码 ----
COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
