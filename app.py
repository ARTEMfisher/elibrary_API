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

@app.before_first_request
def create_tables():
    db.create_all()
    init_admin_user()

def init_admin_user():
    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        hashed_password = generate_password_hash("qwerty", method='sha256')
        admin_user = User(username="admin", password=hashed_password)
        db.session.add(admin_user)
        db.session.commit()

@app.route('/check_user', methods=['POST'])
def check_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # Проверка, что данные присутствуют
    if not username or not password:
        return jsonify({'valid': False, 'message': 'Username and password are required.'}), 400

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password, password):
        return jsonify({'valid': True})
    else:
        return jsonify({'valid': False})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
