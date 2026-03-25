#!/bin/bash
# =============================================================================
# Запуск контейнера коррекции орфографии
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ────────────────────────────────────────────────
# Конфигурация
# ────────────────────────────────────────────────
INPUT_FILE="${1:-/home/ubuntu/output/final_report.md}"
OUTPUT_FILE="${2:-/home/ubuntu/output/final_report_corrected.md}"
LLAMA_URL="${LLAMA_SERVER_URL:-http://127.0.0.1:8080}"
QUICK_MODE="${QUICK_MODE:-false}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Базовая директория на хосте (должна совпадать с volume в docker-compose.yml)
HOST_BASE_DIR="/home/ubuntu/output"

# Базовая директория ВНУТРИ контейнера (должна совпадать с docker-compose.yml!)
CONTAINER_BASE_DIR="/app/rw"

# ────────────────────────────────────────────────
# Функции
# ────────────────────────────────────────────────
log_info() { echo -e "\n[INFO] $1"; }
log_error() { echo -e "\n[ERROR] $1"; }
log_success() { echo -e "\n[OK] $1"; }

# ────────────────────────────────────────────────
# Проверки
# ────────────────────────────────────────────────
log_info "Проверка входных файлов..."

if [ ! -f "$INPUT_FILE" ]; then
    log_error "Входной файл не найден: $INPUT_FILE"
    exit 1
fi

log_info "Проверка доступности llama-server..."
if ! curl -s --max-time 5 "$LLAMA_URL/health" > /dev/null 2>&1; then
    log_error "llama-server недоступен: $LLAMA_URL"
    echo "Запустите: sudo systemctl start llama-server.service"
    exit 1
fi
log_success "llama-server доступен"

# ────────────────────────────────────────────────
# Расчёт путей для контейнера
# ────────────────────────────────────────────────
# Преобразуем абсолютный путь хоста в относительный
INPUT_REL_PATH="${INPUT_FILE#$HOST_BASE_DIR/}"
OUTPUT_REL_PATH="${OUTPUT_FILE#$HOST_BASE_DIR/}"

# Пути ВНУТРИ контейнера (используем CONTAINER_BASE_DIR из docker-compose.yml)
CONTAINER_INPUT="$CONTAINER_BASE_DIR/$INPUT_REL_PATH"
CONTAINER_OUTPUT="$CONTAINER_BASE_DIR/$OUTPUT_REL_PATH"

log_info "Маппинг путей:"
log_info "  Хост вход:   $INPUT_FILE"
log_info "  Контейнер:   $CONTAINER_INPUT"
log_info "  Хост выход:  $OUTPUT_FILE"
log_info "  Контейнер:   $CONTAINER_OUTPUT"

# ────────────────────────────────────────────────
# Запуск контейнера
# ────────────────────────────────────────────────
log_info "Запуск контейнера коррекции..."

docker compose run --rm \
    -e INPUT_FILE="$CONTAINER_INPUT" \
    -e OUTPUT_FILE="$CONTAINER_OUTPUT" \
    -e LLAMA_SERVER_URL="$LLAMA_URL" \
    -e QUICK_MODE="$QUICK_MODE" \
    -e LOG_LEVEL="$LOG_LEVEL" \
    corrector

EXIT_CODE=$?

# ────────────────────────────────────────────────
# Финализация
# ────────────────────────────────────────────────
if [ $EXIT_CODE -eq 0 ] && [ -f "$OUTPUT_FILE" ]; then
    log_success "Коррекция завершена успешно"
    echo ""
    echo "Файлы:"
    echo "  Оригинал:   $INPUT_FILE ($(wc -c < "$INPUT_FILE") байт)"
    echo "  Исправлено: $OUTPUT_FILE ($(wc -c < "$OUTPUT_FILE") байт)"
else
    log_error "Коррекция завершилась с ошибкой (код: $EXIT_CODE)"
fi

exit $EXIT_CODE
