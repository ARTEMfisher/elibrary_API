from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    requests = db.Column(db.JSON, nullable=True)  # Список заявок

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'requests': self.requests
        }

# Модель заявки
class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Связь с пользователем
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)  # Связь с книгой
    status = db.Column(db.Boolean, nullable=True)  # Статус заявки (True/False/None)

    user = db.relationship('User', backref='requests_made')  # Обратная связь с пользователем
    book = db.relationship('Book', backref='requests_received')  # Обратная связь с книгой

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'book_id': self.book_id,
            'status': self.status
        }

# Модель книги
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    holders = db.Column(db.JSON, nullable=True)
    isFree = db.Column(db.Boolean, nullable=False)
    request_status = db.Column(db.JSON, nullable=True)  # Статус заявок

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'image_url': self.image_url,
            'holders': self.holders,
            'isFree': self.isFree,
            'request_status': self.request_status
        }


# Инициализация администратора
def init_admin_user():
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        hashed_password = generate_password_hash("qwerty")
        admin_user = User(username="admin", password=hashed_password)
        db.session.add(admin_user)
        db.session.commit()


# Загрузка книг из JSON
def load_books_from_json(file_path):
    db.session.query(Book).delete()  # Удаляем все существующие книги
    db.session.commit()

    with open(file_path, 'r', encoding='utf-8') as f:
        books_data = json.load(f)
        for book_data in books_data:
            book = Book(
                title=book_data['title'],
                author=book_data['author'],
                image_url=book_data['image_url'],
                holders=book_data.get('holders', []),
                isFree=book_data['isFree'].lower() == 'true'
            )
            db.session.add(book)
        db.session.commit()


# Инициализация базы данных
with app.app_context():
    db.create_all()
    init_admin_user()
    load_books_from_json('books.json')


# Эндпоинт: проверка пользователя
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

@app.route('/get_user_id', methods=['GET'])
def get_user_id():
    username = request.args.get('username')  # Получаем username из параметра запроса
    if not username:
        return jsonify({'message': 'Username is required'}), 400

    user = User.query.filter_by(username=username).first()  # Ищем пользователя по username

    if user:
        return jsonify({'user_id': user.id}), 200  # Возвращаем id пользователя
    else:
        return jsonify({'message': 'User not found'}), 404  # Если пользователя нет

# Эндпоинт: добавление нового пользователя
@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if User.query.filter_by(username=username).first():
        return jsonify({'message': False}), 409

    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': True}), 201


# Эндпоинт: получение списка всех пользователей
@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users]), 200


# Эндпоинт: получение списка всех книг
@app.route('/books', methods=['GET'])
def get_books():
    books = Book.query.all()
    return jsonify([book.to_dict() for book in books]), 200


# Эндпоинт: добавление заявки
@app.route('/add_request', methods=['POST'])
def add_request():
    data = request.get_json()
    user_id = data['userId']
    book_id = data['bookId']
    status = data.get('status', None)

    user = User.query.get(user_id)
    book = Book.query.get(book_id)

    if not user or not book:
        return jsonify({'message': 'User or book not found'}), 404

    # Обновить заявки пользователя
    if user.requests is None:
        user.requests = []
    user.requests.append({'bookId': book_id, 'status': status})

    # Обновить статус заявок на книгу
    if book.request_status is None:
        book.request_status = []
    book.request_status.append({'userId': user_id, 'status': status})

    db.session.commit()
    return jsonify({'message': 'Request added successfully'}), 201


# Эндпоинт: получить заявки пользователя
@app.route('/user_requests/<int:user_id>', methods=['GET'])
def get_user_requests(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    return jsonify(user.requests), 200


# Эндпоинт: получить статус заявок на книгу
@app.route('/book_requests/<int:book_id>', methods=['GET'])
def get_book_requests(book_id):
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'message': 'Book not found'}), 404
    return jsonify(book.request_status), 200

@app.route('/requests', methods=['GET'])
def get_requests():
    requests = Request.query.all()  # Получаем все заявки из базы данных
    return jsonify([req.to_dict() for req in requests]), 200

@app.route('/create_request', methods=['POST'])
def create_request():
    data = request.get_json()

    # Извлекаем данные из тела запроса
    user_id = data.get('user_id')
    book_id = data.get('book_id')

    # Проверяем наличие необходимых данных
    if not user_id or not book_id:
        return jsonify({'message': 'user_id and book_id are required'}), 400

    # Проверяем, существует ли пользователь и книга
    user = User.query.get(user_id)
    book = Book.query.get(book_id)

    if not user:
        return jsonify({'message': 'User not found'}), 404
    if not book:
        return jsonify({'message': 'Book not found'}), 404

    # Создаём новую заявку
    new_request = Request(
        user_id=user_id,
        book_id=book_id,
        status=None  # Устанавливаем статус заявки в NULL
    )

    # Сохраняем заявку в базе данных
    db.session.add(new_request)
    db.session.commit()

    return jsonify({
        'message': 'Request created successfully',
        'request': new_request.to_dict()
    }), 201

# Запуск приложения
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
