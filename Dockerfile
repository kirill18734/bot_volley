# Этап 1: установка зависимостей
FROM python:3.10 AS builder

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости локально
RUN pip install --user -r requirements.txt

# Этап 2: финальный контейнер
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости из builder
COPY --from=builder /root/.local /root/.local

# Копируем все необходимые файлы и директории
COPY config.py data.json main.py ./
COPY core/ core/
COPY services/ services/
COPY images/ images/

# Обновляем PATH, чтобы видеть пакеты из /root/.local
ENV PATH=/root/.local/bin:$PATH

# Запускаем main.py с логированием вывода
CMD ["python", "-u", "main.py"]
