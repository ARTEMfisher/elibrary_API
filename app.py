from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
import json

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def to_dict(self):
        return {'id': self.id, 'username': self.username}

# Модель книги
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    isFree = db.Column(db.Boolean, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'image_url': self.image_url,
            'isFree': self.isFree,
        }

# Модель заявки
class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    status = db.Column(db.Boolean, nullable=True)  # None = Рассматривается, True/False = Утверждена/Отказано

    user = db.relationship('User', backref='requests')
    book = db.relationship('Book', backref='requests')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'book_id': self.book_id,
            'status': self.status,
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
    if not Book.query.first():  # Загружаем книги только если база данных пуста
        with open(file_path, 'r', encoding='utf-8') as f:
            books_data = json.load(f)
            for book_data in books_data:
                book = Book(
                    title=book_data['title'],
                    author=book_data['author'],
                    image_url=book_data.get('image_url', ''),
                    isFree=book_data['isFree'].lower() == 'true'
                )
                db.session.add(book)
            db.session.commit()

# Инициализация базы данных
with app.app_context():
    db.create_all()
    init_admin_user()
    load_books_from_json('books.json')

# WebSocket: подписка на обновления заявок
@socketio.on('subscribe_requests')
def handle_requests_subscription():
    requests = Request.query.all()
    requests_data = [req.to_dict() for req in requests]
    emit('request_update', requests_data)

# Эндпоинт: проверить пользователя
@app.route('/check_user', methods=['POST'])
def check_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'valid': False, 'message': 'Username and password are required'}), 400

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        return jsonify({'valid': True})
    return jsonify({'valid': False})

# Эндпоинт: добавить нового пользователя
@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'User already exists'}), 409

    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User created successfully'}), 201

# Эндпоинт: получить список книг
@app.route('/books', methods=['GET'])
def get_books():
    books = Book.query.all()
    return jsonify([book.to_dict() for book in books])

# Эндпоинт: создать заявку
@app.route('/create_request', methods=['POST'])
def add_request():
    data = request.get_json()
    user_id = data.get('userId')
    book_id = data.get('bookId')

    if not user_id or not book_id:
        return jsonify({'message': 'User ID and Book ID are required'}), 400

    user = User.query.get(user_id)
    book = Book.query.get(book_id)

    if not user:
        return jsonify({'message': 'User not found'}), 404
    if not book:
        return jsonify({'message': 'Book not found'}), 404

    new_request = Request(user_id=user_id, book_id=book_id, status=None)
    db.session.add(new_request)
    db.session.commit()

    # Оповещение клиентов об обновлении заявок
    emit_all_requests()

    return jsonify({'message': 'Request created successfully', 'request': new_request.to_dict()}), 201

# Эндпоинт: обновить статус заявки
@app.route('/update_request_status', methods=['POST'])
def update_request_status():
    data = request.get_json()
    request_id = data.get('requestId')
    status = data.get('status')

    if request_id is None or status is None:
        return jsonify({'message': 'Request ID and status are required'}), 400

    if not isinstance(status, bool):
        return jsonify({'message': 'Status must be a boolean'}), 400

    req = Request.query.get(request_id)
    if not req:
        return jsonify({'message': 'Request not found'}), 404

    book = Book.query.get(req.book_id)
    req.status = status

    if status:  # Если заявка подтверждена
        book.isFree = False

    db.session.commit()
    emit_all_requests()

    return jsonify({'message': 'Request status updated successfully'})

# Уведомление всех клиентов об обновлении заявок
def emit_all_requests():
    requests = Request.query.all()
    requests_data = [req.to_dict() for req in requests]
    socketio.emit('request_update', requests_data)

# Запуск приложения
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
