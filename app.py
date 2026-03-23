from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
import mysql.connector
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import random
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- FILE UPLOAD ----------------
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- DATABASE ----------------
conn = mysql.connector.connect(
    host="localhost",
    user="flaskuser",
    password="Flask@123",
    database="grievance_db"
)
cursor = conn.cursor(dictionary=True, buffered=True)

# ---------------- MAIL CONFIG ----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'shwethack691@gmail.com'
app.config['MAIL_PASSWORD'] = 'urlqfyfittoihfel'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)

# ---------------- AUTH DECORATORS ----------------
def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'admin' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return wrap

def user_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'user' not in session:
            return redirect('/user_login')
        return f(*args, **kwargs)
    return wrap

# ---------------- HOME ----------------
@app.route('/', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        data = request.form
        email = session.get('user', data.get('email'))

        tracking_id = "GRV" + str(random.randint(1000, 9999))

        attachment = request.files.get('attachment')
        filename = None

        if attachment and attachment.filename != '':
            filename = attachment.filename
            attachment.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cursor.execute("""
        INSERT INTO grievances (tracking_id,name,email,phone,location,category,grievance,attachment)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (tracking_id, data['name'], email, data['phone'],
              data['location'], data['category'], data['grievance'], filename))

        conn.commit()

        flash(f"Submitted! Tracking ID: {tracking_id}", "success")
        return redirect('/')

    return render_template('form.html')

# ---------------- ADMIN LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']

        cursor.execute("SELECT * FROM admin WHERE username=%s", (user,))
        admin = cursor.fetchone()

        if admin and check_password_hash(admin['password'], pwd):
            session['admin'] = user
            return redirect('/dashboard')
        else:
            flash("Invalid credentials", "danger")

    return render_template('login.html')

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
@admin_required
def dashboard():
    cursor.execute("SELECT COUNT(*) AS total FROM grievances")
    total = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS pending FROM grievances WHERE status='Pending'")
    pending = cursor.fetchone()['pending']

    cursor.execute("SELECT COUNT(*) AS resolved FROM grievances WHERE status='Resolved'")
    resolved = cursor.fetchone()['resolved']

    return render_template('dashboard.html', total=total, pending=pending, resolved=resolved)

# ---------------- VIEW ----------------
@app.route('/view')
@admin_required
def view():
    cursor.execute("SELECT * FROM grievances ORDER BY id DESC")
    data = cursor.fetchall()
    return render_template('view.html', grievances=data)

# ---------------- UPDATE ----------------
@app.route('/update/<int:id>', methods=['GET', 'POST'])
@admin_required
def update(id):
    if request.method == 'POST':
        status = request.form['status']
        cursor.execute("UPDATE grievances SET status=%s WHERE id=%s", (status, id))
        conn.commit()
        flash("Updated successfully", "success")
        return redirect('/view')

    cursor.execute("SELECT * FROM grievances WHERE id=%s", (id,))
    g = cursor.fetchone()
    return render_template('update.html', grievance=g)

# ---------------- DELETE ----------------
@app.route('/delete/<int:id>')
@admin_required
def delete(id):
    cursor.execute("DELETE FROM grievances WHERE id=%s", (id,))
    conn.commit()
    flash("Deleted successfully", "danger")
    return redirect('/view')

# ---------------- USER REGISTER ----------------
@app.route('/user_register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        cursor.execute("INSERT INTO users (name,email,password) VALUES (%s,%s,%s)",
                       (name, email, password))
        conn.commit()

        flash("Registered successfully!", "success")
        return redirect('/user_login')

    return render_template('user_register.html')

# ---------------- USER LOGIN ----------------
@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user'] = user['email']
            return redirect('/user_dashboard')
        else:
            flash("Invalid login", "danger")

    return render_template('user_login.html')

# ---------------- USER DASHBOARD ----------------
@app.route('/user_dashboard')
@user_required
def user_dashboard():
    email = session['user']
    cursor.execute("SELECT * FROM grievances WHERE email=%s", (email,))
    data = cursor.fetchall()
    return render_template('user_dashboard.html', grievances=data)

# ---------------- USER LOGOUT ----------------
@app.route('/user_logout')
def user_logout():
    session.pop('user', None)
    return redirect('/user_login')

# ---------------- FORGOT PASSWORD ----------------
@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form['email']

        cursor.execute("SELECT * FROM admin WHERE email=%s", (email,))
        admin = cursor.fetchone()

        if admin:
            otp = str(random.randint(1000, 9999))

            cursor.execute("UPDATE admin SET otp=%s WHERE email=%s", (otp, email))
            conn.commit()

            msg = Message("OTP Verification",
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[email])
            msg.body = f"Your OTP is: {otp}"
            mail.send(msg)

            session['email'] = email

            return redirect('/verify')   # ✅ FIXED

        flash("Email not found", "danger")

    return render_template('forgot.html')

# ---------------- VERIFY OTP ----------------
@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        otp = request.form['otp']
        email = session.get('email')

        cursor.execute("SELECT * FROM admin WHERE email=%s AND otp=%s", (email, otp))
        if cursor.fetchone():
            return redirect('/reset')

        flash("Invalid OTP", "danger")

    return render_template('verify.html')

# ---------------- RESET PASSWORD ----------------
@app.route('/reset', methods=['GET', 'POST'])
def reset():
    if 'email' not in session:
        return redirect('/forgot')

    if request.method == 'POST':
        password = generate_password_hash(request.form['password'])
        email = session['email']

        cursor.execute("UPDATE admin SET password=%s WHERE email=%s", (password, email))
        conn.commit()

        session.pop('email', None)

        flash("Password updated successfully!", "success")
        return redirect('/login')

    return render_template('reset.html')

# ---------------- TRACK ----------------
@app.route('/track', methods=['GET', 'POST'])
def track():
    g = None
    if request.method == 'POST':
        tid = request.form['tracking_id']
        cursor.execute("SELECT * FROM grievances WHERE tracking_id=%s", (tid,))
        g = cursor.fetchone()

    return render_template('track.html', grievance=g)

# ---------------- FILE VIEW ----------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')