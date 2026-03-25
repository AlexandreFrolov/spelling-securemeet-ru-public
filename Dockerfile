FROM python:3.11-slim

LABEL maintainer="Securemeet.ru Pipeline Team"
LABEL description="Standalone spell checker for meeting reports using llama.cpp"
LABEL version="1.0.0"

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY src/correct_report.py /app/correct_report.py

# Настройка переменных окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Точка входа
ENTRYPOINT ["python3", "/app/correct_report.py"]
