#!/usr/bin/env python3
"""
Корректор орфографии, синтаксиса и пунктуации для отчётов
Использует локальный llama-server API
Standalone version для /home/ubuntu/spelling
"""

import os
import sys
import time
import requests
from pathlib import Path
from datetime import datetime

SERVER_URL = "http://127.0.0.1:8080"
MODEL_NAME = os.environ.get("LLAMA_MODEL", "Qwen2.5-14B-Instruct-Q6_K_M.gguf")
INPUT_FILE = os.environ.get("INPUT_FILE", "/app/input/final_report.md")
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "/app/output/final_report_corrected.md")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "15000"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "4000"))
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.1"))
TIMEOUT = int(os.environ.get("TIMEOUT", "900"))
QUICK_MODE = os.environ.get("QUICK_MODE", "false").lower() == "true"
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "30"))
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", "2"))

# ────────────────────────────────────────────────
# Промпты для коррекции
# ────────────────────────────────────────────────
CORRECTION_SYSTEM_PROMPT = """Ты профессиональный редактор деловых документов на русском языке.
Твоя задача — исправить орфографические, синтаксические и пунктуационные ошибки в тексте.

ПРАВИЛА:
1. Исправляй только ошибки, не меняй смысл и структуру документа
2. Сохраняй форматирование Markdown (заголовки #, списки -, таблицы |)
3. Сохраняй все таймкоды, имена участников, технические данные и цифры
4. Не добавляй новую информацию и не удаляй существующие разделы
5. Отвечай ТОЛЬКО исправленным текстом, без комментариев и объяснений

ИСПРАВЛЯЙ:
- Орфографические ошибки (неправильное написание слов)
- Пунктуационные ошибки (запятые, тире, двоеточия, кавычки)
- Грамматические ошибки (согласование родов, чисел, падежей)
- Опечатки и повторы слов
- Неправильное употребление предлогов

НЕ ИСПРАВЛЯЙ:
- Специфические термины, аббревиатуры и технические названия
- Имена собственные и фамилии участников
- Форматирование Markdown и структуру документа
- Таймкоды, даты, числа и технические данные
- URL и пути к файлам"""

QUICK_CORRECTION_PROMPT = """Исправь ТОЛЬКО критические ошибки: орфография, пунктуация в концах предложений, явные опечатки.
Не меняй стиль, структуру и форматирование Markdown. Только исправленный текст без комментариев."""

# ────────────────────────────────────────────────
# Логирование
# ────────────────────────────────────────────────
def log(level, message):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if LOG_LEVEL == "DEBUG" or level in ["INFO", "ERROR", "FATAL"]:
        out = sys.stderr if level in ["ERROR", "FATAL"] else sys.stdout
        print(f"[{ts}] [{level}] {message}", file=out)

def log_info(msg): log("INFO", msg)
def log_error(msg): log("ERROR", msg)
def log_fatal(msg): log("FATAL", msg)
def log_debug(msg): log("DEBUG", msg)

# ────────────────────────────────────────────────
# Проверка доступности сервера
# ────────────────────────────────────────────────
def check_server_available():
    log_info(f"Проверка llama-server: {SERVER_URL}")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(f"{SERVER_URL}/health", timeout=5)
            if r.status_code == 200:
                log_info(f"llama-server доступен (попытка {attempt}/{MAX_RETRIES})")
                return True
        except Exception as e:
            log_debug(f"Попытка {attempt} не удалась: {e}")
        if attempt < MAX_RETRIES:
            log_info(f"Повторная попытка через {RETRY_DELAY} сек...")
            time.sleep(RETRY_DELAY)
    log_error(f"llama-server недоступен после {MAX_RETRIES} попыток")
    return False

# ────────────────────────────────────────────────
# Функции коррекции
# ────────────────────────────────────────────────
def correct_text(text, use_quick=False):
    prompt = QUICK_CORRECTION_PROMPT if use_quick else CORRECTION_SYSTEM_PROMPT
    try:
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Исправь ошибки:\n\n{text}"}
            ],
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "repeat_penalty": 1.05,
            "stream": False
        }
        log_info(f"Отправка на коррекцию ({len(text)} симв.)...")
        r = requests.post(f"{SERVER_URL}/v1/chat/completions", json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        corrected = r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if corrected:
            log_info(f"Коррекция завершена ({len(corrected)} симв.)")
            return corrected
        log_error("Пустой ответ от LLM")
        return text
    except Exception as e:
        log_error(f"Ошибка коррекции: {e}")
        return text

def correct_in_chunks(text):
    if len(text) <= CHUNK_SIZE:
        return correct_text(text, use_quick=QUICK_MODE)
    
    log_info(f"Текст большой ({len(text)} симв.), разбиваем на части...")
    sections = text.split('\n## ')
    
    if len(sections) <= 1:
        chunks = [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
        corrected = []
        for i, chunk in enumerate(chunks):
            log_info(f"Коррекция части {i+1}/{len(chunks)}...")
            corrected.append(correct_text(chunk, use_quick=QUICK_MODE))
        return '\n'.join(corrected)
    
    corrected_sections = []
    for i, section in enumerate(sections):
        if i == 0:
            corrected_sections.append(correct_text(section[:CHUNK_SIZE], use_quick=QUICK_MODE))
        else:
            section_text = f"## {section}"
            corrected_sections.append(correct_text(section_text[:CHUNK_SIZE], use_quick=QUICK_MODE))
        log_info(f"Раздел {i+1}/{len(sections)} обработан")
    
    return '\n'.join(corrected_sections)

# ────────────────────────────────────────────────
# Основная функция
# ────────────────────────────────────────────────
def main():
    log_info(f"Старт коррекции: {INPUT_FILE}")
    
    if not Path(INPUT_FILE).exists():
        log_fatal(f"Файл не найден: {INPUT_FILE}")
        sys.exit(1)
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        original_text = f.read()
    
    log_info(f"Исходный размер: {len(original_text)} символов")
    corrected_text = correct_in_chunks(original_text)
    
    output_path = Path(OUTPUT_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(corrected_text)
    
    log_info(f"Исправленный отчёт сохранён: {OUTPUT_FILE}")
    log_info(f"Изменение размера: {len(corrected_text) - len(original_text)} символов")

# ────────────────────────────────────────────────
# Точка входа
# ────────────────────────────────────────────────
if __name__ == "__main__":
    # Переопределение из аргументов командной строки
    if len(sys.argv) >= 2:
        INPUT_FILE = sys.argv[1]
    if len(sys.argv) >= 3:
        OUTPUT_FILE = sys.argv[2]
    
    if not check_server_available():
        sys.exit(1)
    
    try:
        main()
    except KeyboardInterrupt:
        log_info("Прервано пользователем")
        sys.exit(130)
    except Exception as e:
        log_fatal(f"Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)