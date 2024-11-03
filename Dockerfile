# Используем базовый образ с Python
FROM python:3.12

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . .

# Создаем виртуальное окружение и устанавливаем зависимости
RUN . venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Указываем контейнеру, что по умолчанию он будет использовать виртуальное окружение
ENV PATH="/app/venv/bin:$PATH"

# Открываем порт, который будет использовать Flask (5000)
EXPOSE 5000

# Запускаем Flask-приложение
CMD ["python3", "app.py"]
