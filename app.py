"""
AWS Multi-Region Flask Application
Webserver: EC2 (Mumbai ap-south-1)
DB: MySQL (DB Private Subnet)
S3: App code + logs storage
EDR: Elastic Disaster Recovery integration
"""

import os
import logging
import boto3
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# ─────────────────────────────────────────────
# App Configuration
# ─────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production')

# MySQL Config (DB Private Subnet via internal DNS / private IP)
app.config['MYSQL_HOST']     = os.environ.get('DB_HOST', '10.0.3.10')  # DB private IP
app.config['MYSQL_USER']     = os.environ.get('DB_USER', 'appuser')
app.config['MYSQL_PASSWORD'] = os.environ.get('DB_PASS', 'StrongPass123!')
app.config['MYSQL_DB']       = os.environ.get('DB_NAME', 'appdb')
app.config['MYSQL_PORT']     = int(os.environ.get('DB_PORT', 3306))
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# S3 Config
S3_BUCKET   = os.environ.get('S3_BUCKET', 'my-app-bucket-mumbai')
S3_REGION   = os.environ.get('AWS_REGION', 'ap-south-1')
s3_client   = boto3.client('s3', region_name=S3_REGION)

# ─────────────────────────────────────────────
# Logging — writes to file + S3
# ─────────────────────────────────────────────
LOG_FILE = '/var/log/webapp/app.log'
os.makedirs('/var/log/webapp', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def upload_log_to_s3():
    """Push current log file to S3 logs/ prefix."""
    try:
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        key = f'logs/webserver/app_{timestamp}.log'
        s3_client.upload_file(LOG_FILE, S3_BUCKET, key)
        logger.info(f'Log uploaded to s3://{S3_BUCKET}/{key}')
    except Exception as e:
        logger.error(f'S3 log upload failed: {e}')


# ─────────────────────────────────────────────
# Auth helper
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if not user:
            flash('No account found. Please sign up first.', 'error')
            logger.warning(f'Login failed — no account: {email}')
            return redirect(url_for('signup'))

        if check_password_hash(user['password_hash'], password):
            session['user_id']  = user['id']
            session['username'] = user['username']
            logger.info(f'User logged in: {email}')
            return redirect(url_for('dashboard'))
        else:
            flash('Incorrect password.', 'error')
            logger.warning(f'Login failed — wrong password: {email}')

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('signup.html')

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing = cur.fetchone()

        if existing:
            cur.close()
            flash('Email already registered. Please log in.', 'warning')
            return redirect(url_for('login'))

        pw_hash = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (%s, %s, %s, NOW())",
            (username, email, pw_hash)
        )
        mysql.connection.commit()
        new_id = cur.lastrowid
        cur.close()

        session['user_id']  = new_id
        session['username'] = username
        logger.info(f'New user registered: {email}')
        flash(f'Welcome, {username}! Account created successfully.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('signup.html')


@app.route('/dashboard')
@login_required
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT username, email, created_at FROM users WHERE id = %s", (session['user_id'],))
    user = cur.fetchone()
    cur.close()
    return render_template('dashboard.html', user=user)


@app.route('/logout')
@login_required
def logout():
    username = session.get('username')
    session.clear()
    logger.info(f'User logged out: {username}')
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/health')
def health():
    """ALB / ELB health check endpoint."""
    return {'status': 'ok', 'region': S3_REGION}, 200


# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
