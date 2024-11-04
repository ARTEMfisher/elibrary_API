from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import json

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
    image_url = db.Column(db.String(500), nullable=True)
    holders = db.Column(db.JSON, nullable=True)
    isFree = db.Column(db.Boolean, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'image_url': self.image_url,
            'holders': self.holders,
            'isFree': self.isFree
        }


def init_admin_user():
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        hashed_password = generate_password_hash("qwerty")
        admin_user = User(username="admin", password=hashed_password)
        db.session.add(admin_user)
        db.session.commit()


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
                holders=book_data['holders'],
                isFree=book_data['isFree'].lower() == 'true'
            )
            db.session.add(book)
        db.session.commit()


with app.app_context():
    db.create_all()
    init_admin_user()
    load_books_from_json('books.json')


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
        return jsonify({'message': False}), 409

    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': True}), 201


@app.route('/books', methods=['GET'])
def get_books():
    books = Book.query.all()
    return jsonify([book.to_dict() for book in books]), 200

@app.route('/get_users', methods=['GET'])
def get_users():
    users = User.query.all()
    users_list = [{'id':user.id, 'username':user.username} for user in users]
    return jsonify(users_list), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
