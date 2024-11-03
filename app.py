import json
import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    image_url = db.Column(db.String(200), nullable=False)
    holders = db.Column(db.JSON)  # Для хранения списка holders
    isFree = db.Column(db.Boolean, nullable=False)


def init_admin_user():
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        hashed_password = generate_password_hash("qwerty")  # Используем метод по умолчанию
        admin_user = User(username="admin", password=hashed_password)
        db.session.add(admin_user)
        db.session.commit()


def load_books_from_json():
    json_file_path = os.path.join(os.path.dirname(__file__), 'books.json')  # Путь к файлу
    with open(json_file_path, 'r', encoding='utf-8') as json_file:
        books_data = json.load(json_file)

        for book_data in books_data:
            if Book.query.filter_by(id=book_data['id']).first():
                continue  # Пропустить добавление, если книга с таким ID уже существует

            new_book = Book(
                id=book_data['id'],
                title=book_data['title'],
                author=book_data['author'],
                image_url=book_data['image_url'],
                holders=book_data['holders'],
                isFree=book_data['isFree'] == 'true'
            )
            db.session.add(new_book)
        db.session.commit()


# Создаем таблицы и инициализируем администратора
with app.app_context():
    db.create_all()
    init_admin_user()
    load_books_from_json()  # Загрузка книг из JSON файла


@app.route('/check_user', methods=['POST'])
def check_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password, password):
        return jsonify({'valid': True})
    else:
        return jsonify({'valid': False})


@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if User.query.filter_by(username=username).first():
        return jsonify({'message': False}), 409  # Возвращаем 409, если пользователь уже существует

    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password=hashed_password)

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': True}), 201  # Возвращаем 201, если пользователь успешно добавлен


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
