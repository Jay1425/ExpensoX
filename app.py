from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.secret_key = 'your_secret_key'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    return render_template('auth/login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    return render_template('auth/signup.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    return render_template('auth/forgot_password.html')

@app.route('/expenses')
def expenses():
    return render_template('employee/expenses.html')

@app.route('/submit_expense')
def submit_expense():
    return render_template('employee/submit_expense.html')

if __name__ == '__main__':
    app.run(debug=True)