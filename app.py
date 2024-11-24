from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
import json
import re


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

class BookReturn(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    book_id = db.Column(db.Integer, nullable=False)
    is_returned = db.Column(db.Boolean, nullable=False, default=False)


    # def __repr__(self):
    #     return f'<BookReturn {self.id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'request_id': self.request_id,
            'user_id': self.user_id,
            'book_id': self.book_id,
            'is_returned': self.is_returned
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

    # Проверка на пустоту таблицы 'Book'
    if Book.query.count() == 0:  # Если в таблице нет записей
        load_books_from_json('books.json')
        print("Данные из 'books.json' загружены в таблицу 'Book'.")
    else:
        print("Таблица 'Book' уже заполнена, данные из JSON не загружаются.")



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

# @socketio.on('subscribe_requests')
# def handle_requests_subscription():
#     # Emit updates about requests as they change
#     while True:
#         requests = Request.query.all()  # Get updated requests
#         requests_data = [{'id': req.id, 'status': req.status, 'book_id': req.book_id, 'user_id': req.user_id} for req in requests]
#         emit('request_update', requests_data)
#         socketio.sleep(1)

@app.route('/create_request', methods=['POST'])
def create_request():
    data = request.get_json()
    user_id = data.get('userId')
    book_id = data.get('bookId')
    user = User.query.get(user_id)
    book = Book.query.get(book_id)
    if not user or not book:
        return jsonify({'message': 'User or book not found'}), 404
    new_request = Request(user_id=user_id, book_id=book_id, status=None)
    db.session.add(new_request)
    db.session.commit()
    if user.requests is None:
        user.requests = []
    user.requests.append(new_request.id)
    db.session.commit()
    socketio.emit('request_update', [req.to_dict() for req in Request.query.all()])
    return jsonify({'message': 'Request created successfully'}), 201
# Эндпоинт: получить название книги по id
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
def update_request_status():
    data = request.get_json()
    request_id = data.get('requestId')
    status = data.get('status')

    # Проверка наличия необходимых данных
    if request_id is None or status is None:
        return jsonify({'message': 'requestId and status are required'}), 400

    # Проверка, что status это булевое значение
    if not isinstance(status, bool):
        return jsonify({'message': 'Status must be a boolean'}), 400

    # Находим заявку по id
    request_entry = Request.query.get(request_id)
    if not request_entry:
        return jsonify({'message': 'Request not found'}), 404

    # Находим книгу по book_id из заявки
    book_entry = Book.query.get(request_entry.book_id)
    if not book_entry:
        return jsonify({'message': 'Book not found'}), 404

    if status:  # Если статус заявки становится True
        if not book_entry.isFree:  # Если книга уже занята
            return jsonify({'message': 'The book is already taken'}), 400
        # Обновляем статус заявки и книги
        request_entry.status = True
        book_entry.isFree = False
    else:  # Если статус заявки становится False
        request_entry.status = False

    # Сохраняем изменения в базе данных
    db.session.commit()

    return jsonify({
        'message': 'Request status updated successfully',
        'request_id': request_entry.id,
        'new_status': request_entry.status,
        'book_id': book_entry.id,
        'book_isFree': book_entry.isFree
    }), 200

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
            'status': request.status , # Статус заявки
            'id' : request.id,
            'book_id': request.book_id
        }
        for request in user.requests_made  # Обход всех заявок пользователя
    ]

    return jsonify(user_requests), 200

@app.route('/returns', methods=['GET'])
def get_returns():
    returns = BookReturn.query.all()
    return jsonify([return_record.to_dict() for return_record in returns]), 200

@app.route('/return_book', methods=['POST'])
def return_book():
    """
    Обрабатывает возврат книги.
    Ожидает JSON с данными:
    - request_id: ID заявки на книгу
    - user_id: ID пользователя, который возвращает книгу
    - book_id: ID книги
    """
    data = request.get_json()

    request_id = data.get('request_id')
    user_id = data.get('user_id')
    book_id = data.get('book_id')

    if not request_id or not user_id or not book_id:
        return jsonify({'message': 'Missing data'}), 400

    # Проверяем существование заявки
    req = Request.query.get(request_id)
    if not req:
        return jsonify({'message': 'Request not found'}), 404

    # Проверяем, принадлежит ли заявка указанному пользователю
    if req.user_id != user_id:
        return jsonify({'message': 'This request does not belong to the user'}), 403

    # Проверяем существование книги
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'message': 'Book not found'}), 404

    # Проверяем, не была ли книга уже возвращена
    existing_return = BookReturn.query.filter_by(
        request_id=request_id,
        user_id=user_id,
        book_id=book_id
    ).first()
    if existing_return:
        return jsonify({'message': 'Book has already been returned'}), 409

    # Создаём запись о возврате книги
    new_return = BookReturn(
        request_id=request_id,
        user_id=user_id,
        book_id=book_id,
        is_returned=False
    )
    db.session.add(new_return)

    # Обновляем статус заявки и книги
    req.status = False  # Заявка считается завершённой
    book.isFree = True  # Книга становится доступной для новых заявок

    db.session.commit()

    return jsonify({'message': 'Book return processed successfully'}), 201

@app.route('/update_return_status', methods=['PUT'])
def update_return_status():
    data = request.get_json()

    return_id = data.get('return_id')
    is_returned = data.get('is_returned')

    if return_id is None or is_returned is None:
        return jsonify({'message': 'Missing return_id or is_returned'}), 400

    # Проверяем, существует ли запись о возврате
    book_return = BookReturn.query.get(return_id)
    if not book_return:
        return jsonify({'message': 'Return record not found'}), 404

    # Проверяем книгу, связанную с возвратом
    book = Book.query.get(book_return.book_id)
    if not book:
        return jsonify({'message': 'Book not found'}), 404

    if not is_returned:  # Если is_returned == True, ничего не делаем
        return jsonify({'message': 'The book is already marked as free'}), 400


    if is_returned:  # Если is_returned == False
        if not book.isFree:  # Если книга занята (isFree == False)
            # Обновляем статус возврата и книги
            book_return.is_returned = True
            book.isFree = True
        else:  # Если книга уже свободна (isFree == True)
            return jsonify({'message': 'No changes needed, book is already returned'}), 200


    # Сохраняем изменения в базе данных
    db.session.commit()

    return jsonify({
        'message': 'Return status updated successfully',
        'return_id': book_return.id,
        'is_returned': book_return.is_returned,
        'book_id': book.id,
        'book_isFree': book.isFree
    }), 200




@app.route('/search_books', methods=['GET'])
def search_books():
    query = request.args.get('query', '').strip().lower()  # Получаем параметр "query"
    if not query:
        return jsonify([]), 200  # Возвращаем пустой список, если нет запроса

    # Загружаем все книги из базы
    all_books = Book.query.all()

    # Функция для проверки совпадения с использованием регулярных выражений
    def matches(book, query):
        # Создаём паттерн для поиска (чувствительность к пробелам и регистру)
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        return (
            pattern.search(book.title.lower()+book.author.lower()) is not None or
            pattern.search(book.author.lower()) is not None
        )

    # Фильтруем книги, проверяя совпадение через регулярное выражение
    matched_books = [book for book in all_books if matches(book, query)]

    # Возвращаем найденные книги
    return jsonify([book.to_dict() for book in matched_books]), 200


# Запуск приложения
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)