FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# 为 mysqlclient 构建依赖（若改用 Postgres 可删掉）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential default-libmysqlclient-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV DJANGO_SETTINGS_MODULE=core.settings

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]
