from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
import json


app = Flask(__name__)

app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    requests = db.relationship('Request', backref='user', lazy=True)  # Связь с заявками


    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'requests': self.requests
        }

# Модель заявки
class Request(db.Model):
    __tablename__ = 'requests'
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.Boolean, nullable=True)
    # Добавьте другие поля для вашей модели запроса


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

class BookReturn(db.Model):
    __tablename__ = 'book_returns'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('requests.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id'), nullable=False)
    is_returned = db.Column(db.Boolean, nullable=False, default=False)

    # Отношения с другими таблицами
    request = db.relationship('Request', backref=db.backref('returns', lazy=True))
    user = db.relationship('User', backref=db.backref('returns', lazy=True))
    book = db.relationship('Book', backref=db.backref('returns', lazy=True))

    def __repr__(self):
        return f'<BookReturn {self.id}>'


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
    app.app_context().push()
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

# @app.route('/requests', methods=['GET'])
# def get_requests():
#     requests = Request.query.all()  # Получаем все заявки из базы данных
#     return jsonify([req.to_dict() for req in requests]), 200

@app.route('/requests', methods=['GET'])
def get_requests():
    # This will send all current requests as an initial load.
    requests = Request.query.all()
    requests_data = [{'id': req.id, 'status': req.status, 'book_id': req.book_id, 'user_id': req.user_id} for req in requests]
    return jsonify(requests_data)

@socketio.on('subscribe_requests')
def handle_requests_subscription():
    # Emit updates about requests as they change
    while True:
        requests = Request.query.all()  # Get updated requests
        requests_data = [{'id': req.id, 'status': req.status, 'book_id': req.book_id, 'user_id': req.user_id} for req in requests]
        emit('request_update', requests_data)
        socketio.sleep(1)

@app.route('/create_request', methods=['POST'])
def create_request():
    data = request.get_json()
    user_id = data.get('userId')
    book_id = data.get('bookId')
    user = User.query.get(user_id)
    book = Book.query.get(book_id)

    if not user or not book:
        return jsonify({'message': 'User or book not found'}), 404

    if not book.isFree:
        return jsonify({'message': 'Book is not available'}), 400  # Книга уже занята

    new_request = Request(user_id=user_id, book_id=book_id, status=None)
    db.session.add(new_request)
    db.session.commit()

    if user.requests is None:
        user.requests = []
    user.requests.append(new_request.id)
    db.session.commit()
    socketio.emit('request_update', [req.to_dict() for req in Request.query.all()])

    return jsonify({'message': 'Request created successfully'}), 201

@app.route('/book_title/<int:book_id>', methods=['GET'])
def get_book_title(book_id):
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'message': 'Book not found'}), 404
    return jsonify({'title': book.title}), 200

@app.route('/getUserAndBook', methods=['GET'])
def get_book_and_user_by_ids():
    book_id = request.args.get('book_id', type=int)
    user_id = request.args.get('user_id', type=int)

    # Получаем книгу по ID
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'message': 'Book not found'}), 404

    # Получаем пользователя по ID
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Возвращаем название книги и имя пользователя
    return jsonify({
        'book_title': book.title,
        'username': user.username,
    }), 200


@app.route('/update_request_status', methods=['POST'])
def update_request_status(request_id):
    # Находим заявку по ID
    request = Request.query.get(request_id)
    if not request:
        return jsonify({'message': 'Request not found'}), 404

    # Проверяем, доступна ли книга
    book = Book.query.get(request.book_id)
    if not book:
        return jsonify({'message': 'Book not found'}), 404

    if not book.is_free:
        return jsonify({'message': 'The book has already been taken'}), 400  # Книга уже взята

    # Если книга доступна, обновляем статус заявки
    request.status = True  # Подтверждаем заявку
    book.is_free = False  # Книга больше не доступна

    db.session.commit()

    return jsonify({'message': 'Request confirmed successfully'}), 200
@app.route('/user_requests_by_id/<int:user_id>', methods=['GET'])
def get_user_requests_by_id(user_id):
    # Проверяем, существует ли пользователь
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Формируем список заявок пользователя
    user_requests = [
        {
            'book_title': request.book.title if request.book else None,  # Название книги
            'status': request.status  # Статус заявки
        }
        for request in user.requests_made  # Обход всех заявок пользователя
    ]

    return jsonify(user_requests), 200

@app.route('/search_books', methods=['GET'])
def search_books():
    query = request.args.get('query', '').strip().lower()  # Получаем параметр "query"
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    # Попробуем интерпретировать query как ID, если это возможно
    try:
        query_id = int(query)
    except ValueError:
        query_id = None

    # Поиск книг по ID, названию или автору
    books = Book.query.filter(
        (Book.id == query_id) |  # Поиск по ID
        (Book.title.ilike(f"%{query}%")) |  # Поиск по названию
        (Book.author.ilike(f"%{query}%"))   # Поиск по автору
    ).all()

    # Возвращаем найденные книги
    return jsonify([book.to_dict() for book in books]), 200

@app.route('/return_book', methods=['POST'])
def return_book():
    data = request.get_json()
    request_id = data.get('request_id')
    user_id = data.get('user_id')
    book_id = data.get('book_id')  # ID книги, которую возвращают

    if not request_id or not user_id or not book_id:
        return jsonify({'message': 'Missing data'}), 400

    # Проверяем, существует ли заявка с таким request_id
    request = Request.query.get(request_id)
    if not request:
        return jsonify({'message': 'Request not found'}), 404

    # Проверяем, что заявка принадлежит этому пользователю
    if request.user_id != user_id:
        return jsonify({'message': 'This request does not belong to the user'}), 400

    # Создаем новую запись в таблице возвратов
    new_return = BookReturn(request_id=request_id, user_id=user_id, book_id=book_id, is_returned=True)
    db.session.add(new_return)
    db.session.commit()

    return jsonify({'message': 'Return request added successfully'}), 201

@app.route('/update_request_status/<int:request_id>', methods=['POST'])
def update_request_status(request_id):
    # Находим заявку по ID
    request = Request.query.get(request_id)
    if not request:
        return jsonify({'message': 'Request not found'}), 404

    # Проверяем, доступна ли книга
    book = Book.query.get(request.book_id)
    if not book:
        return jsonify({'message': 'Book not found'}), 404

    if not book.isFree:
        return jsonify({'message': 'The book has already been taken'}), 400  # Книга уже взята

    # Если книга доступна, обновляем статус заявки
    request.status = True  # Подтверждаем заявку
    book.isFree = False  # Книга больше не доступна

    db.session.commit()

    return jsonify({'message': 'Request confirmed successfully'}), 200


@app.route('/returns', methods=['GET'])
def get_returns():
    returns = BookReturn.query.all()
    return jsonify([{
        'id': return_record.id,
        'request_id': return_record.request_id,
        'user_id': return_record.user_id,
        'book_id': return_record.book_id,
        'is_returned': return_record.is_returned
    } for return_record in returns]), 200


@socketio.on('subscribe_requests')
def handle_subscribe_requests():
    emit('request_update', [req.to_dict() for req in Request.query.all()])

# Запуск приложения
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)