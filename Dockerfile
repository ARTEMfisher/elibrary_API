# Используем базовый образ с Python
FROM python:3.12

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . .

# Устанавливаем зависимости
RUN pip install --upgrade pip && pip install -r requirements.txt

# Открываем порт, который будет использовать Flask (5000)
EXPOSE 5000

# Запускаем Flask-приложение
CMD ["python3", "app.py"]
