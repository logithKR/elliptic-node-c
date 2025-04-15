from flask import Flask, render_template, request, redirect, url_for, session
from ecc_utils import encrypt_data
from pymongo import MongoClient
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sqlite3
import os
from dotenv import load_dotenv
load_dotenv()

import fitz  # PyMuPDF for PDF
from docx import Document
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secret_key_for_session'  # In production, use a strong secret

# === SQLite Setup for User Authentication ===
def init_sqlite_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_sqlite_db()

# === MongoDB Setup for ECC Logging ===
MONGO_URI = os.getenv("MONGO_URI")  # Get from Render env var
NODE_NAME = os.getenv("NODE_NAME", "Node-A")  # Default to Node-A

client = MongoClient(MONGO_URI)
db = client.ecc_load_balancer

# === ROUTES ===

@app.route('/')
def home():
    return render_template('home.html')  # Home with login/register links

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, password))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            session['username'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            return "Login Failed. Try again."
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('index.html')  # ECC form
    return redirect(url_for('login'))

@app.route('/submit', methods=['POST'])
def submit():
    if 'username' not in session:
        return redirect(url_for('login'))

    file = request.files['file']
    if not file:
        return "No file uploaded"

    filename = secure_filename(file.filename)
    content = ""

    if filename.endswith(".pdf"):
        pdf = fitz.open(stream=file.read(), filetype="pdf")
        for page in pdf:
            content += page.get_text()
    elif filename.endswith(".docx"):
        doc = Document(file)
        for para in doc.paragraphs:
            content += para.text + "\n"
    else:
        return "Unsupported file format. Please upload a PDF or DOCX."

    # ECC encryption
    encrypted = encrypt_data(content)

    db.requests.insert_one({
        "filename": filename,
        "encrypted_data": encrypted,
        "assigned_node": NODE_NAME
    })

    # Load counts and chart
    loads = {"Node-A": 0, "Node-B": 0, "Node-C": 0}
    for entry in db.requests.find():
        node = entry.get("assigned_node")
        if node in loads:
            loads[node] += 1

    plt.clf()
    plt.bar(loads.keys(), loads.values(), color=['green', 'orange', 'red'])
    for i, (node, count) in enumerate(loads.items()):
        plt.text(i, count + 0.2, str(count), ha='center', fontsize=10)
    plt.xlabel("Cloud Nodes")
    plt.ylabel("Load (#Requests)")
    plt.title("Load Balancing using ECC Encryption")
    plt.tight_layout()
    plt.savefig("static/chart.png")

    return render_template('index.html', chart='chart.png', encrypted=encrypted, user=filename, node=NODE_NAME)

@app.route('/visualize')
def visualize():
    loads = {"Node-A": 0, "Node-B": 0, "Node-C": 0}
    for entry in db.requests.find():
        node = entry.get("assigned_node")
        if node in loads:
            loads[node] += 1

    plt.clf()
    plt.bar(loads.keys(), loads.values(), color=['green', 'orange', 'red'])
    for i, (node, count) in enumerate(loads.items()):
        plt.text(i, count + 0.2, str(count), ha='center', fontsize=10)
    plt.xlabel("Cloud Nodes")
    plt.ylabel("Load (#Requests)")
    plt.title("Load Balancing using ECC Encryption")
    plt.tight_layout()
    plt.savefig("static/chart.png")

    return render_template('index.html', chart='chart.png')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ['PORT']))
