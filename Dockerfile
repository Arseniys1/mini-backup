# Используем последний официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Порт, который будет слушать FastAPI
EXPOSE 5000

# Команда для запуска сервера
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5000"]