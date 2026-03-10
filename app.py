"""
EduMind AI - Complete Learning Management System
Production-Ready AI-Powered Education Platform
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from functools import wraps
import sqlite3
import os
import hashlib
import random
import string
from datetime import datetime, timedelta
import re
import requests
import json
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

app = Flask(__name__)

# Production configuration using environment variables
app.secret_key = os.environ.get('SECRET_KEY', 'edumind_ai_lms_secret_key_2024_production')

# Database configuration - use absolute path for PythonAnywhere
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Check if DATABASE_URL is set (for PostgreSQL on Render)
database_url = os.environ.get('DATABASE_URL')

if database_url:
    # Use PostgreSQL on Render
    import psycopg2
    DB_NAME = database_url
else:
    # Use SQLite locally
    DB_NAME = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'edumind.db'))

# Upload folder configuration
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'static/uploads'))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# Debug mode - False for production
DEBUG_MODE = os.environ.get('DEBUG', 'False').lower() == 'true'
app.debug = DEBUG_MODE

# Built-in AI Response Generator (No external API needed)
# Uses intelligent rule-based responses for educational content

# Create directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(f'{UPLOAD_FOLDER}/course_materials', exist_ok=True)
os.makedirs(f'{UPLOAD_FOLDER}/profile_pictures', exist_ok=True)
os.makedirs(f'{UPLOAD_FOLDER}/module_materials', exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'mp4', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    # Check if using PostgreSQL (DATABASE_URL set on Render)
    if os.environ.get('DATABASE_URL'):
        try:
            import psycopg2
            conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
            return conn
        except ImportError:
            print("psycopg2 not installed, falling back to SQLite")
    
    # Use SQLite
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== OLLAMA AI INTEGRATION ====================

# Ollama API Configuration
OLLAMA_API_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'phi'  # Smaller, faster model that works well on weaker GPUs

# Google Gemini API Configuration
GEMINI_API_KEY = 'AIzaSyCKr-mpGshEn8Z6vDCIl9hiTdrh3GwkvNY'  # User provided key
GEMINI_MODEL = 'gemini-1.5-flash'

def generate_gemini_response(prompt, system_prompt=None, max_tokens=500):
    """
    Generate response using Google Gemini API
    Returns None if API key is invalid or quota exceeded
    """
    try:
        import google.generativeai as genai
        
        # Configure the API
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Create the model
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # Build the full prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"
        
        # Generate response
        response = model.generate_content(
            full_prompt,
            generation_config={
                'max_output_tokens': max_tokens,
                'temperature': 0.7,
            }
        )
        
        if response and response.text:
            return response.text.strip()
        return None
        
    except Exception as e:
        print(f"[GEMINI] Error: {str(e)}")
        return None

def generate_ollama_response(prompt, system_prompt=None, max_tokens=500):
    """
    Generate response using Ollama API or Google Gemini API
    Tries Gemini first, then falls back to Ollama
    """
    # Try Google Gemini first (works in production)
    gemini_response = generate_gemini_response(prompt, system_prompt, max_tokens)
    if gemini_response:
        print("[GEMINI] Generated response successfully")
        return gemini_response
    
    # Fall back to Ollama (only works locally)
    try:
        payload = {
            'model': OLLAMA_MODEL,
            'prompt': prompt,
            'stream': False,
            'options': {
                'num_predict': max_tokens,
                'temperature': 0.7,
            }
        }
        
        if system_prompt:
            payload['system'] = system_prompt
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=120)  # Increased timeout to 120 seconds
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            print(f"[OLLAMA] API returned status {response.status_code}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("[OLLAMA] Could not connect to Ollama. Make sure Ollama is running (ollama serve)")
        return None
    except requests.exceptions.Timeout:
        print("[OLLAMA] Request timed out - model may be loading. Try again in a moment.")
        return None
    except Exception as e:
        print(f"[OLLAMA] Error: {str(e)}")
        return None

def check_ollama_available():
    """Check if Ollama is running and accessible"""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        return response.status_code == 200
    except:
        return False


def _parse_ollama_quiz_questions(ollama_response, difficulty):
    """
    Parse quiz questions from Ollama response
    Returns list of tuples: (question, option_a, option_b, option_c, option_d, correct_answer)
    """
    questions = []
    lines = ollama_response.strip().split('\n')
    
    current_question = None
    options = {}
    correct_answer = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check for question line
        if line.startswith('Q:') or line.startswith('Q1') or line.startswith('1.') or line.startswith('Question'):
            # Save previous question if exists
            if current_question and options and correct_answer:
                # Ensure we have all options
                opt_a = options.get('A', options.get('a', ''))
                opt_b = options.get('B', options.get('b', ''))
                opt_c = options.get('C', options.get('c', ''))
                opt_d = options.get('D', options.get('d', ''))
                
                if opt_a and opt_b and opt_c and opt_d:
                    questions.append((current_question, opt_a, opt_b, opt_c, opt_d, correct_answer))
            
            # Start new question
            current_question = line.split(':', 1)[-1].strip() if ':' in line else line
            options = {}
            correct_answer = None
            
        # Check for answer option
        elif line[0] in ['A', 'B', 'C', 'D'] and ':' in line:
            key = line[0].upper()
            value = line.split(':', 1)[-1].strip()
            options[key] = value
            
        # Check for correct answer
        elif 'ANSWER:' in line.upper() or 'CORRECT:' in line.upper():
            answer_text = line.split(':', 1)[-1].strip().upper()
            if answer_text in ['A', 'B', 'C', 'D']:
                correct_answer = options.get(answer_text, '')
            elif 'A' in answer_text:
                correct_answer = options.get('A', '')
            elif 'B' in answer_text:
                correct_answer = options.get('B', '')
            elif 'C' in answer_text:
                correct_answer = options.get('C', '')
            elif 'D' in answer_text:
                correct_answer = options.get('D', '')
    
    # Don't forget the last question
    if current_question and options and correct_answer:
        opt_a = options.get('A', options.get('a', ''))
        opt_b = options.get('B', options.get('b', ''))
        opt_c = options.get('C', options.get('c', ''))
        opt_d = options.get('D', options.get('d', ''))
        
        if opt_a and opt_b and opt_c and opt_d:
            questions.append((current_question, opt_a, opt_b, opt_c, opt_d, correct_answer))
    
    return questions

# ==================== AUTH HELPERS ====================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    return hash_password(password) == password_hash

def generate_token(length=32):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            role = session.get('role')
            if not role or role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==================== DATABASE ====================

def seed_sample_data():
    """Seed sample data for production (idempotent)"""
    import hashlib
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create Admin (INSERT OR IGNORE - won't fail if exists)
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, email, password_hash, full_name, role, is_verified)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('admin', 'admin@edumind.com', hashlib.sha256('admin123'.encode()).hexdigest(), 
              'System Administrator', 'admin', 1))
        
        # Create Lecturers
        lecturers = [
            ('johnsmith', 'john.smith@edumind.com', 'lecturer123', 'John Smith'),
            ('sarahjohnson', 'sarah.johnson@edumind.com', 'lecturer123', 'Sarah Johnson'),
            ('michaelbrown', 'michael.brown@edumind.com', 'lecturer123', 'Michael Brown'),
            ('emilydavis', 'emily.davis@edumind.com', 'lecturer123', 'Emily Davis'),
            ('davidwilson', 'david.wilson@edumind.com', 'lecturer123', 'David Wilson'),
        ]
        
        for username, email, password, full_name in lecturers:
            cursor.execute('''
                INSERT OR IGNORE INTO users (username, email, password_hash, full_name, role, is_verified)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, email, hashlib.sha256(password.encode()).hexdigest(), full_name, 'lecturer', 1))
        
        # Create Students
        students = [
            ('student1', 'student1@edumind.com', 'student123', 'Alice Anderson'),
            ('student2', 'student2@edumind.com', 'student123', 'Bob Baker'),
            ('student3', 'student3@edumind.com', 'student123', 'Charlie Clark'),
            ('student4', 'student4@edumind.com', 'student123', 'Diana Davis'),
            ('student5', 'student5@edumind.com', 'student123', 'Edward Evans'),
        ]
        
        for username, email, password, full_name in students:
            cursor.execute('''
                INSERT OR IGNORE INTO users (username, email, password_hash, full_name, role, is_verified)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, email, hashlib.sha256(password.encode()).hexdigest(), full_name, 'student', 1))
        
        # Get lecturer IDs
        cursor.execute("SELECT id FROM users WHERE role = 'lecturer'")
        lecturer_ids = [row['id'] for row in cursor.fetchall()]
        
        # Create Courses
        courses = [
            ('Introduction to Computer Science', 'Learn the fundamentals of programming', 'Computer Science', 'CS101'),
            ('Advanced Mathematics', 'Calculus, Linear Algebra, and Differential Equations', 'Mathematics', 'MATH201'),
            ('Web Development Fundamentals', 'HTML, CSS, JavaScript, and web frameworks', 'Web Development', 'WD101'),
            ('Data Science and Analytics', 'Data visualization and machine learning', 'Data Science', 'DS101'),
            ('Artificial Intelligence', 'Neural networks and deep learning', 'Artificial Intelligence', 'AI101'),
        ]
        
        course_ids = []
        for i, (title, description, subject, code) in enumerate(courses):
            teacher_id = lecturer_ids[i % len(lecturer_ids)] if lecturer_ids else 1
            cursor.execute('''
                INSERT OR IGNORE INTO courses (title, description, subject, course_code, teacher_id, is_published)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, description, subject, code, teacher_id, 1))
            if cursor.lastrowid:
                course_ids.append(cursor.lastrowid)
        
        # If no IDs (already exist), fetch them
        if not course_ids:
            cursor.execute("SELECT id FROM courses")
            course_ids = [row['id'] for row in cursor.fetchall()]
        
        # Create Modules
        for course_id in course_ids:
            for j in range(3):
                cursor.execute('''
                    INSERT OR IGNORE INTO modules (course_id, name, description, year, semester)
                    VALUES (?, ?, ?, ?, ?)
                ''', (course_id, f'Module {j+1}', f'Learning module {j+1}', 2024, (j % 2) + 1))
        
        # Get module IDs
        cursor.execute("SELECT id FROM modules")
        module_ids = [row['id'] for row in cursor.fetchall()]
        
        # Create Quizzes
        quiz_titles = ['Python Basics Quiz', 'Data Structures Quiz', 'Web Development Quiz', 'Algorithms Quiz', 'Database Quiz']
        for i, title in enumerate(quiz_titles):
            if i < len(module_ids):
                cursor.execute('''
                    INSERT OR IGNORE INTO quizzes (title, description, module_id, difficulty)
                    VALUES (?, ?, ?, ?)
                ''', (title, f'Test your knowledge of {title}', module_ids[i], 'easy'))
        
        # Create Assignments
        assignment_titles = ['Python Programming Assignment', 'HTML Website Project', 'Database Design Project']
        for i, title in enumerate(assignment_titles):
            if i < len(module_ids):
                cursor.execute('''
                    INSERT OR IGNORE INTO assignments (title, description, module_id, due_date)
                    VALUES (?, ?, ?, datetime('now', '+7 days'))
                ''', (title, f'Complete the {title}', module_ids[i]))
        
        conn.commit()
        print("Sample data seeded successfully!")
        print("Admin: admin / admin123")
        print("Lecturers: johnsmith / lecturer123, etc.")
        print("Students: student1 / student123, etc.")
        
    except Exception as e:
        print(f"Error seeding data: {e}")
        conn.rollback()
    finally:
        conn.close()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL CHECK(role IN ('student', 'lecturer', 'admin')),
            profile_picture TEXT,
            is_verified INTEGER DEFAULT 0,
            verification_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Add columns to existing users table if they don't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN role TEXT CHECK(role IN (\'student\', \'lecturer\', \'admin\', \'parent\'))')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN student_number TEXT')
    except:
        pass
    
    # Add module metadata columns
    try:
        cursor.execute('ALTER TABLE modules ADD COLUMN year INTEGER')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE modules ADD COLUMN semester INTEGER')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE modules ADD COLUMN prerequisites TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE modules ADD COLUMN is_active INTEGER DEFAULT 1')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE job_recommendations ADD COLUMN is_active INTEGER DEFAULT 1')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE quizzes ADD COLUMN module_id INTEGER')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE quizzes ADD COLUMN difficulty TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE quiz_questions ADD COLUMN difficulty TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN profile_picture TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN verification_token TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN last_login TIMESTAMP')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN bio TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN phone TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN address TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN date_of_birth TEXT')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1')
    except:
        pass
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    except:
        pass
    
    # Parent-Student relationships
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parent_students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            FOREIGN KEY (parent_id) REFERENCES users(id),
            FOREIGN KEY (student_id) REFERENCES users(id),
            UNIQUE(parent_id, student_id)
        )
    ''')
    
    # Courses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            subject TEXT,
            course_code TEXT,
            teacher_id INTEGER NOT NULL,
            is_published INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users(id)
        )
    ''')
    
    # Course materials
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            file_path TEXT,
            file_type TEXT,
            uploaded_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        )
    ''')
    
    # Enrollments
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (course_id) REFERENCES courses(id),
            UNIQUE(student_id, course_id)
        )
    ''')
    
    # Quizzes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            difficulty TEXT,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # Quiz questions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct_answer TEXT,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        )
    ''')
    
    # Quiz results
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            score REAL,
            total_questions INTEGER,
            answers TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id),
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    ''')
    
    # AI Feedback
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_result_id INTEGER,
            student_id INTEGER NOT NULL,
            course_id INTEGER,
            feedback_text TEXT,
            weak_topics TEXT,
            recommendations TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_result_id) REFERENCES quiz_results(id),
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    ''')
    
    # Messages
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            course_id INTEGER,
            subject TEXT,
            message_text TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (recipient_id) REFERENCES users(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    ''')
    
    # Announcements
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message_text TEXT NOT NULL,
            is_system INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Notifications
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message_text TEXT,
            link TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # AI Chat history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER,
            user_message TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    ''')
    
    # Study plans
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            title TEXT,
            topics TEXT,
            activities TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    ''')
    
    conn.commit()
    
    # Create all other tables
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parent_students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES users(id),
                FOREIGN KEY (student_id) REFERENCES users(id),
                UNIQUE(parent_id, student_id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                subject TEXT,
                course_code TEXT,
                teacher_id INTEGER NOT NULL,
                is_published INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (teacher_id) REFERENCES users(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS course_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                file_path TEXT,
                file_type TEXT,
                uploaded_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses(id),
                FOREIGN KEY (uploaded_by) REFERENCES users(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
                enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (course_id) REFERENCES courses(id),
                UNIQUE(student_id, course_id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quizzes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                difficulty TEXT,
                FOREIGN KEY (course_id) REFERENCES courses(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                option_a TEXT,
                option_b TEXT,
                option_c TEXT,
                option_d TEXT,
                correct_answer TEXT,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                score REAL,
                total_questions INTEGER,
                answers TEXT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id),
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_result_id INTEGER,
                student_id INTEGER NOT NULL,
                course_id INTEGER,
                feedback_text TEXT,
                weak_topics TEXT,
                recommendations TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_result_id) REFERENCES quiz_results(id),
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (course_id) REFERENCES courses(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                course_id INTEGER,
                subject TEXT,
                message_text TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sender_id) REFERENCES users(id),
                FOREIGN KEY (recipient_id) REFERENCES users(id),
                FOREIGN KEY (course_id) REFERENCES courses(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                message_text TEXT NOT NULL,
                is_system INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                message_text TEXT,
                link TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                course_id INTEGER,
                user_message TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (course_id) REFERENCES courses(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                title TEXT,
                topics TEXT,
                activities TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (course_id) REFERENCES courses(id)
            )
        ''')
    except: pass
    
    # Update role to include lecturer (replace teacher)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT CHECK(role IN ('student', 'lecturer', 'admin', 'parent'))")
    except: pass
    
    # Modules table (subdivisions of courses)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                code TEXT,
                chapter_number INTEGER,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (course_id) REFERENCES courses(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        ''')
    except: pass
    
    # Module materials (organized by topics/chapters)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS module_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                content_type TEXT CHECK(content_type IN ('slide', 'pdf', 'document', 'video', 'link', 'excel')),
                content_text TEXT,
                file_path TEXT,
                chapter_topic TEXT,
                order_index INTEGER DEFAULT 0,
                uploaded_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_id) REFERENCES modules(id),
                FOREIGN KEY (uploaded_by) REFERENCES users(id)
            )
        ''')
    except: pass
    
    # Module lecturers (assigned lecturers to modules)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS module_lecturers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                lecturer_id INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_id) REFERENCES modules(id),
                FOREIGN KEY (lecturer_id) REFERENCES users(id),
                UNIQUE(module_id, lecturer_id)
            )
        ''')
    except: pass
    
    # Module requests (lecturer requests to teach modules)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS module_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                lecturer_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
                request_message TEXT,
                reviewed_by INTEGER,
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_id) REFERENCES modules(id),
                FOREIGN KEY (lecturer_id) REFERENCES users(id),
                FOREIGN KEY (reviewed_by) REFERENCES users(id)
            )
        ''')
    except: pass
    
    # Module enrollments (student enrollments in modules)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS module_enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                module_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
                enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (module_id) REFERENCES modules(id),
                UNIQUE(student_id, module_id)
            )
        ''')
    except: pass
    
    # Study schedules - automatic weekly timetable for students
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                day_of_week TEXT NOT NULL CHECK(day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),
                time_slot TEXT NOT NULL,
                activity_type TEXT NOT NULL CHECK(activity_type IN ('study', 'assignment', 'review', 'practice', 'revision', 'exam_prep')),
                module_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                is_completed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (module_id) REFERENCES modules(id)
            )
        ''')
    except: pass
    
    # Career profiles
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS career_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL UNIQUE,
                interests TEXT,
                career_goals TEXT,
                target_industries TEXT,
                preferred_job_types TEXT,
                location_preference TEXT,
                career_readiness_score REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        ''')
    except: pass
    
    # CVs
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cvs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                title TEXT,
                summary TEXT,
                education TEXT,
                experience TEXT,
                file_path TEXT,
                ai_analysis TEXT,
                ai_suggestions TEXT,
                is_primary INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        ''')
    except: pass
    
    # Projects (for portfolio)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                technologies_used TEXT,
                role TEXT,
                url TEXT,
                file_path TEXT,
                is_academic INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        ''')
    except: pass
    
    # Skills
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                skill_name TEXT NOT NULL,
                proficiency_level TEXT CHECK(proficiency_level IN ('beginner', 'intermediate', 'advanced', 'expert')),
                source_module_id INTEGER,
                verified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (source_module_id) REFERENCES modules(id),
                UNIQUE(student_id, skill_name)
            )
        ''')
    except: pass
    
    # Job recommendations
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                job_title TEXT NOT NULL,
                company TEXT,
                description TEXT,
                requirements TEXT,
                job_type TEXT,
                location TEXT,
                relevance_score REAL,
                is_saved INTEGER DEFAULT 0,
                is_applied INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        ''')
    except: pass
    
    # Interview questions
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interview_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                job_field TEXT,
                question TEXT NOT NULL,
                ideal_answer TEXT,
                user_answer TEXT,
                practice_count INTEGER DEFAULT 0,
                last_practiced TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
        ''')
    except: pass
    
    # Quiz questions with difficulty
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                option_a TEXT,
                option_b TEXT,
                option_c TEXT,
                option_d TEXT,
                correct_answer TEXT,
                difficulty TEXT DEFAULT 'medium' CHECK(difficulty IN ('easy', 'medium', 'hard')),
                chapter_topic TEXT,
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
            )
        ''')
    except: pass
    
    # Student performance tracking (for adaptive quizzes)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                module_id INTEGER,
                quiz_id INTEGER,
                average_score REAL DEFAULT 0,
                total_quizzes INTEGER DEFAULT 0,
                easy_count INTEGER DEFAULT 0,
                medium_count INTEGER DEFAULT 0,
                hard_count INTEGER DEFAULT 0,
                recommended_difficulty TEXT DEFAULT 'medium',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (module_id) REFERENCES modules(id),
                FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
            )
        ''')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_date DATE,
                max_score INTEGER DEFAULT 100,
                instruction_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (module_id) REFERENCES modules(id)
            )
        ''')
    except: pass
    
    # Migration: Add instruction_file column to assignments table if it doesn't exist
    try:
        cursor.execute('ALTER TABLE assignments ADD COLUMN instruction_file TEXT')
    except: pass
    
    # Migration: Add image column to modules table if it doesn't exist
    try:
        cursor.execute('ALTER TABLE modules ADD COLUMN image TEXT')
    except: pass
    
    # Migration: Add question_type column to quiz_questions if it doesn't exist
    try:
        cursor.execute('ALTER TABLE quiz_questions ADD COLUMN question_type TEXT')
    except: pass
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                submission_text TEXT,
                file_path TEXT,
                grade INTEGER,
                feedback TEXT,
                graded_at TIMESTAMP,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignment_id) REFERENCES assignments(id),
                FOREIGN KEY (student_id) REFERENCES users(id),
                UNIQUE(assignment_id, student_id)
            )
        ''')
    except: pass
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")
    
    # Always seed sample data (idempotent - uses INSERT OR IGNORE)
    # This ensures data exists even if database was lost (Render free tier)
    print("Seeding sample data...")
    seed_sample_data()

# ==================== ROUTES ====================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('landing'))

@app.route('/landing')
def landing():
    return render_template('landing.html')

# ==================== AUTH ROUTES ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    conn = get_db_connection()
    
    # Get available courses for the dropdown
    courses = conn.execute('SELECT id, title FROM courses WHERE is_published = 1 ORDER BY title').fetchall()
    conn.close()
    
    if request.method == 'POST':
        # Only students can register themselves - teachers are added by admin
        student_number = request.form.get('student_number', '').strip()
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '')
        university = request.form.get('university', '').strip()
        course_id = request.form.get('course_id')
        year_of_study = request.form.get('year_of_study', '1')
        role = 'student'  # Only students can self-register
        
        # Validate - student number is required for registration
        if not student_number or not email or not password:
            flash('Student number, email and password are required.', 'danger')
            return render_template('register.html', courses=courses)
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html', courses=courses)
        
        if not course_id:
            flash('Please select a course.', 'danger')
            return render_template('register.html', courses=courses)
        
        password_hash = hash_password(password)
        verification_token = generate_token()
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, full_name, role, student_number, 
                                university, course_id, year_of_study, verification_token, is_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (student_number, email, password_hash, full_name, role, student_number, 
                  university, course_id, year_of_study, verification_token))
            
            student_id = cursor.lastrowid
            
            # Auto-enroll student in all modules of the selected course
            modules = conn.execute('SELECT id FROM modules WHERE course_id = ? AND is_active = 1', (course_id,)).fetchall()
            for module in modules:
                cursor.execute('''
                    INSERT INTO module_enrollments (student_id, module_id, status)
                    VALUES (?, ?, 'approved')
                ''', (student_id, module['id']))
            
            # Also create course enrollment
            cursor.execute('''
                INSERT INTO enrollments (student_id, course_id, status)
                VALUES (?, ?, 'approved')
            ''', (student_id, course_id))
            
            conn.commit()
            flash('Registration successful! You have been enrolled in all modules for your course.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Student number or email already exists!', 'danger')
        finally:
            conn.close()
    
    return render_template('register.html', courses=courses)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        # Allow login with username, email, or student_number
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? OR email = ? OR student_number = ?', 
            (username, username, username)
        ).fetchone()
        
        if user and verify_password(password, user['password_hash']):
            # Update last login
            conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            conn.commit()
            
            # Set session
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['profile_picture'] = user['profile_picture']
            
            conn.close()
            flash(f'Welcome back, {user["full_name"] or user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            conn.close()
            flash('Invalid username or password!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('landing'))

# ==================== DASHBOARD ROUTES ====================

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    role = session['role']
    conn = get_db_connection()
    
    if role == 'student':
        # Student dashboard - show enrolled course and modules
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[STUDENT DASHBOARD] User ID: {user_id}, Role: {role}")
        
        # Get student's course info
        student_info = conn.execute('''
            SELECT u.*, c.title as course_title
            FROM users u
            LEFT JOIN courses c ON u.course_id = c.id
            WHERE u.id = ?
        ''', (user_id,)).fetchone()
        
        # Get enrolled modules
        my_modules = conn.execute('''
            SELECT m.*, c.title as course_title,
                   (SELECT COUNT(*) FROM module_enrollments WHERE module_id = m.id AND status = 'approved') as student_count
            FROM modules m
            JOIN courses c ON m.course_id = c.id
            JOIN module_enrollments me ON m.id = me.module_id
            WHERE me.student_id = ? AND me.status = 'approved' AND m.is_active = 1
            ORDER BY c.title, m.chapter_number
        ''', (user_id,)).fetchall()
        logger.info(f"[STUDENT DASHBOARD] Found {len(my_modules)} enrolled modules for student {user_id}")
        
        unread_messages = conn.execute(
            'SELECT COUNT(*) FROM messages WHERE recipient_id = ? AND is_read = 0', (user_id,)
        ).fetchone()[0]
        
        unread_notifications = conn.execute(
            'SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0', (user_id,)
        ).fetchone()[0]
        
        recent_quiz_results = conn.execute('''
            SELECT qr.score, qr.total_questions, q.title, qr.completed_at
            FROM quiz_results qr
            JOIN quizzes q ON qr.quiz_id = q.id
            WHERE qr.student_id = ?
            ORDER BY qr.completed_at DESC LIMIT 5
        ''', (user_id,)).fetchall()
        
        # Calculate basic risk score based on quiz performance
        # Get all quiz results for this student
        all_quiz_results = conn.execute('''
            SELECT score, total_questions FROM quiz_results WHERE student_id = ?
        ''', (user_id,)).fetchall()
        
        if all_quiz_results:
            total_quizzes = len(all_quiz_results)
            avg_score = sum(r['score']/r['total_questions']*100 for r in all_quiz_results) / total_quizzes
            # Risk score: lower average = higher risk
            # 70%+ = Low risk, 50-70% = Medium, 30-50% = High, <30% = Critical
            if avg_score >= 70:
                risk_level = 'Low'
                risk_score = 100 - avg_score  # 0-30
            elif avg_score >= 50:
                risk_level = 'Medium'
                risk_score = 100 - avg_score  # 30-50
            elif avg_score >= 30:
                risk_level = 'High'
                risk_score = 100 - avg_score  # 50-70
            else:
                risk_level = 'Critical'
                risk_score = 100 - avg_score  # 70-100
        else:
            risk_level = 'Low'
            risk_score = 0
            avg_score = 0
        
        # Get upcoming assignments for enrolled modules
        upcoming_assignments = conn.execute('''
            SELECT a.id, a.title, a.due_date, m.title as module_title
            FROM assignments a
            JOIN modules m ON a.module_id = m.id
            JOIN module_enrollments me ON m.id = me.module_id
            WHERE me.student_id = ? AND me.status = 'approved'
            AND (a.due_date IS NULL OR a.due_date >= date('now'))
            ORDER BY a.due_date ASC
            LIMIT 5
        ''', (user_id,)).fetchall()
        
        # Get notifications
        notifications = conn.execute('''
            SELECT id, message_text, is_read, created_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (user_id,)).fetchall()
        
        # Get job recommendations based on course
        job_recommendations = conn.execute('''
            SELECT job_title, company, location
            FROM job_recommendations
            WHERE is_active = 1
            LIMIT 5
        ''').fetchall()
        
        # Calculate study progress for each module (based on quiz performance)
        module_progress = []
        for module in my_modules:
            module_quizzes = conn.execute('''
                SELECT qr.score, qr.total_questions
                FROM quiz_results qr
                JOIN quizzes q ON qr.quiz_id = q.id
                WHERE qr.student_id = ? AND q.module_id = ?
            ''', (user_id, module['id'])).fetchall()
            
            if module_quizzes:
                progress = sum(q['score']/q['total_questions']*100 for q in module_quizzes) / len(module_quizzes)
            else:
                progress = 0
            module_progress.append({
                'id': module['id'],
                'title': module['title'],
                'progress': int(progress)
            })
        
        # Calculate study schedule progress (real-time)
        schedule_stats = conn.execute('''
            SELECT 
                COUNT(*) as total_tasks,
                SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) as completed_tasks
            FROM study_schedules
            WHERE student_id = ?
        ''', (user_id,)).fetchone()
        
        if schedule_stats and schedule_stats['total_tasks'] > 0:
            schedule_completed = schedule_stats['completed_tasks']
            schedule_total = schedule_stats['total_tasks']
            schedule_progress = int((schedule_completed / schedule_total) * 100)
        else:
            schedule_completed = 0
            schedule_total = 0
            schedule_progress = 0
        
        # Calculate overall progress based on multiple factors
        # 1. Module progress from quizzes (40% weight)
        # 2. Schedule completion (30% weight) 
        # 3. Assignments completed (30% weight)
        
        # Get module progress average
        if module_progress:
            avg_module_progress = sum(m['progress'] for m in module_progress) / len(module_progress)
        else:
            avg_module_progress = 0
        
        # Get assignments completed
        completed_assignments = conn.execute('''
            SELECT COUNT(*) as count FROM assignments a
            JOIN module_enrollments me ON a.module_id = me.module_id
            WHERE me.student_id = ? AND me.status = 'approved'
        ''', (user_id,)).fetchone()[0]
        
        total_assignments = conn.execute('''
            SELECT COUNT(*) as count FROM assignments a
            JOIN module_enrollments me ON a.module_id = me.module_id
            WHERE me.student_id = ? AND me.status = 'approved'
        ''', (user_id,)).fetchone()[0]
        
        assignment_progress = int((completed_assignments / total_assignments * 100)) if total_assignments > 0 else 0
        
        # Calculate overall progress (weighted average)
        if module_progress or schedule_total > 0:
            overall_progress = int((avg_module_progress * 0.4) + (schedule_progress * 0.3) + (assignment_progress * 0.3))
        else:
            overall_progress = 0
        
        conn.close()
        logger.info(f"[STUDENT DASHBOARD] Rendering with: student_info={student_info['full_name'] if student_info else 'None'}, modules={len(my_modules)}, progress={overall_progress}%")
        return render_template('dashboard_student.html', 
                             student_info=student_info,
                             my_modules=my_modules,
                             module_progress=module_progress,
                             unread_messages=unread_messages,
                             unread_notifications=unread_notifications,
                             recent_quiz_results=recent_quiz_results,
                             risk_level=risk_level,
                             risk_score=risk_score,
                             avg_score=avg_score,
                             upcoming_assignments=upcoming_assignments,
                             notifications=notifications,
                             job_recommendations=job_recommendations,
                             schedule_progress=schedule_progress,
                             schedule_completed=schedule_completed,
                             schedule_total=schedule_total,
                             overall_progress=overall_progress,
                             assignment_progress=assignment_progress,
                             avg_module_progress=avg_module_progress)
    
    elif role == 'lecturer':
        # Lecturer dashboard - show modules they teach
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[LECTURER DASHBOARD] User ID: {user_id}, Role: {role}")
        
        # Debug: Check if module_lecturers table has data
        try:
            ml_count = conn.execute('SELECT COUNT(*) FROM module_lecturers').fetchone()[0]
            logger.info(f"[LECTURER DASHBOARD] Total module_lecturers records: {ml_count}")
            
            # Check if this lecturer has any module assignments
            my_ml_count = conn.execute('SELECT COUNT(*) FROM module_lecturers WHERE lecturer_id = ?', (user_id,)).fetchone()[0]
            logger.info(f"[LECTURER DASHBOARD] Lecturer {user_id} has {my_ml_count} module assignments")
        except Exception as e:
            logger.error(f"[LECTURER DASHBOARD] Error checking module_lecturers: {e}")
        
        try:
            my_modules = conn.execute('''
                SELECT m.id, m.title, m.description, m.chapter_number, m.code, m.course_id, m.is_active,
                       c.title as course_title, c.id as course_id,
                       (SELECT COUNT(*) FROM module_enrollments WHERE module_id = m.id AND status = 'approved') as student_count,
                       (SELECT COUNT(*) FROM module_enrollments WHERE module_id = m.id AND status = 'pending') as pending_count
                FROM modules m
                JOIN module_lecturers ml ON m.id = ml.module_id
                JOIN courses c ON m.course_id = c.id
                WHERE ml.lecturer_id = ? AND m.is_active = 1
                ORDER BY c.title, m.chapter_number
            ''', (user_id,)).fetchall()
            logger.info(f"[LECTURER DASHBOARD] Found {len(my_modules)} modules for lecturer {user_id}")
        except Exception as e:
            logger.error(f"[LECTURER DASHBOARD] Error loading modules: {str(e)}")
            flash(f'Error loading modules: {str(e)}', 'danger')
            my_modules = []
        
        # Get pending module enrollment requests
        try:
            pending_requests = conn.execute('''
                SELECT me.id, me.module_id, me.student_id, me.status, me.enrolled_at, u.full_name, u.email, m.title as module_title, c.title as course_title
                FROM module_enrollments me
                JOIN modules m ON me.module_id = m.id
                JOIN courses c ON m.course_id = c.id
                JOIN module_lecturers ml ON m.id = ml.module_id
                JOIN users u ON me.student_id = u.id
                WHERE ml.lecturer_id = ? AND me.status = 'pending'
                ORDER BY me.enrolled_at DESC
            ''', (user_id,)).fetchall()
        except Exception as e:
            flash(f'Error loading requests: {str(e)}', 'danger')
            pending_requests = []
        
        try:
            total_students_result = conn.execute('''
                SELECT COUNT(DISTINCT student_id) FROM module_enrollments 
                WHERE module_id IN (
                    SELECT module_id FROM module_lecturers WHERE lecturer_id = ?
                ) AND status = 'approved'
            ''', (user_id,)).fetchone()
            total_students = total_students_result[0] if total_students_result else 0
        except Exception as e:
            total_students = 0
        
        # Get total courses
        try:
            total_courses = conn.execute('''
                SELECT COUNT(DISTINCT course_id) FROM modules m
                JOIN module_lecturers ml ON m.id = ml.module_id
                WHERE ml.lecturer_id = ?
            ''', (user_id,)).fetchone()[0]
        except:
            total_courses = 0
        
        # Get assignments pending grading
        try:
            pending_grading = conn.execute('''
                SELECT COUNT(*) FROM assignment_submissions 
                WHERE grade IS NULL
                AND assignment_id IN (
                    SELECT a.id FROM assignments a
                    JOIN module_lecturers ml ON a.module_id = ml.module_id
                    WHERE ml.lecturer_id = ?
                )
            ''', (user_id,)).fetchone()[0]
        except:
            pending_grading = 0
        
        # Get unread messages count
        try:
            unread_messages = conn.execute('''
                SELECT COUNT(*) FROM messages 
                WHERE recipient_id = ? AND is_read = 0
            ''', (user_id,)).fetchone()[0]
        except:
            unread_messages = 0
        
        # Get student performance data for charts
        try:
            # Get students who have taken quizzes in lecturer's modules
            quiz_students = conn.execute('''
                SELECT DISTINCT qr.student_id, u.full_name, u.email
                FROM quiz_results qr
                JOIN quizzes q ON qr.quiz_id = q.id
                JOIN modules m ON q.module_id = m.id
                JOIN module_lecturers ml ON m.id = ml.module_id
                JOIN users u ON qr.student_id = u.id
                WHERE ml.lecturer_id = ?
            ''', (user_id,)).fetchall()
            
            passing_students = 0
            at_risk_students = 0
            avg_students = 0
            
            for student in quiz_students:
                # Get average score for this student in lecturer's modules
                avg_result = conn.execute('''
                    SELECT AVG(CAST(qr.score AS FLOAT) / CAST(qr.total_questions AS FLOAT) * 100) as avg_score
                    FROM quiz_results qr
                    JOIN quizzes q ON qr.quiz_id = q.id
                    JOIN modules m ON q.module_id = m.id
                    JOIN module_lecturers ml ON m.id = ml.module_id
                    WHERE qr.student_id = ? AND ml.lecturer_id = ?
                ''', (student['student_id'], user_id)).fetchone()
                
                if avg_result and avg_result['avg_score'] is not None:
                    avg_score = avg_result['avg_score']
                    if avg_score >= 70:
                        passing_students += 1
                    elif avg_score < 50:
                        at_risk_students += 1
                    else:
                        avg_students += 1
            
            total_quiz_students = passing_students + avg_students + at_risk_students
        except Exception as e:
            passing_students = 0
            at_risk_students = 0
            avg_students = 0
            total_quiz_students = 0
        
        conn.close()
        logger.info(f"[LECTURER DASHBOARD] Rendering with: my_modules={len(my_modules)}, pending_requests={len(pending_requests)}, total_students={total_students}, total_courses={total_courses}")
        return render_template('dashboard_lecturer.html',
                             my_modules=my_modules,
                             pending_requests=pending_requests,
                             total_students=total_students,
                             total_courses=total_courses,
                             pending_grading=pending_grading,
                             unread_messages=unread_messages,
                             passing_students=passing_students,
                             at_risk_students=at_risk_students,
                             avg_students=avg_students,
                             total_quiz_students=total_quiz_students)
    
    elif role == 'teacher':
        # Teacher dashboard - show courses they created
        my_courses = conn.execute('''
            SELECT c.*, 
                   (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id AND status = 'approved') as enrolled_count,
                   (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id AND status = 'pending') as pending_count
            FROM courses c
            WHERE c.teacher_id = ?
        ''', (user_id,)).fetchall()
        
        pending_requests = conn.execute('''
            SELECT e.id, u.full_name, u.email, c.title, e.enrolled_at
            FROM enrollments e
            JOIN users u ON e.student_id = u.id
            JOIN courses c ON e.course_id = c.id
            WHERE c.teacher_id = ? AND e.status = 'pending'
        ''', (user_id,)).fetchall()
        
        total_students = conn.execute('''
            SELECT COUNT(DISTINCT student_id) FROM enrollments 
            WHERE course_id IN (SELECT id FROM courses WHERE teacher_id = ?) AND status = 'approved'
        ''', (user_id,)).fetchone()[0]
        
        conn.close()
        return render_template('dashboard_teacher.html',
                             my_courses=my_courses,
                             pending_requests=pending_requests,
                             total_students=total_students)
    
    elif role == 'admin':
        # Admin dashboard
        total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        total_courses = conn.execute('SELECT COUNT(*) FROM courses').fetchone()[0]
        total_students = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0]
        total_teachers = conn.execute("SELECT COUNT(*) FROM users WHERE role IN ('teacher', 'lecturer')").fetchone()[0]
        
        recent_users = conn.execute('SELECT * FROM users ORDER BY created_at DESC LIMIT 10').fetchall()
        recent_courses = conn.execute('SELECT c.*, u.username as teacher_name FROM courses c JOIN users u ON c.teacher_id = u.id ORDER BY c.created_at DESC LIMIT 10').fetchall()
        
        conn.close()
        return render_template('dashboard_admin.html',
                             total_users=total_users,
                             total_courses=total_courses,
                             total_students=total_students,
                             total_teachers=total_teachers,
                             recent_users=recent_users,
                             recent_courses=recent_courses)
    
    elif role == 'parent':
        # Parent dashboard
        children = conn.execute('''
            SELECT u.* FROM users u
            JOIN parent_students ps ON u.id = ps.student_id
            WHERE ps.parent_id = ?
        ''', (user_id,)).fetchall()
        
        children_data = []
        for child in children:
            child_courses = conn.execute('''
                SELECT c.*, u.full_name as teacher_name 
                FROM courses c
                JOIN enrollments e ON c.id = e.course_id
                JOIN users u ON c.teacher_id = u.id
                WHERE e.student_id = ? AND e.status = 'approved'
            ''', (child['id'],)).fetchall()
            
            child_quizzes = conn.execute('''
                SELECT q.title, qr.score, qr.total_questions, qr.completed_at
                FROM quiz_results qr
                JOIN quizzes q ON qr.quiz_id = q.id
                WHERE qr.student_id = ?
                ORDER BY qr.completed_at DESC LIMIT 10
            ''', (child['id'],)).fetchall()
            
            # Calculate risk assessment based on quiz performance
            all_quiz_results = conn.execute('''
                SELECT score, total_questions FROM quiz_results WHERE student_id = ?
            ''', (child['id'],)).fetchall()
            
            if all_quiz_results:
                total_quizzes = len(all_quiz_results)
                avg_score = sum(r['score']/r['total_questions']*100 for r in all_quiz_results) / total_quizzes
                if avg_score >= 70:
                    risk_level = 'Low'
                elif avg_score >= 50:
                    risk_level = 'Medium'
                elif avg_score >= 30:
                    risk_level = 'High'
                else:
                    risk_level = 'Critical'
            else:
                risk_level = 'Low'
                avg_score = 0
            
            # Get attendance (placeholder - would need attendance table)
            # For now, we'll use activity as a proxy
            recent_activity = conn.execute('''
                SELECT COUNT(*) as activity_count FROM quiz_results 
                WHERE student_id = ? AND completed_at > datetime('now', '-30 days')
            ''', (child['id'],)).fetchone()
            
            activity_count = recent_activity['activity_count'] if recent_activity else 0
            
            children_data.append({
                'info': child,
                'courses': child_courses,
                'quizzes': child_quizzes,
                'risk_level': risk_level,
                'avg_score': avg_score,
                'activity_count': activity_count
            })
        
        conn.close()
        return render_template('dashboard_parent.html', children_data=children_data)
    
    conn.close()
    return redirect(url_for('landing'))

# ==================== COURSE ROUTES ====================

@app.route('/courses')
@login_required
def courses():
    conn = get_db_connection()
    role = session['role']
    
    if role == 'student':
        # Check if student already has any enrollments (pending or approved)
        existing_enrollment = conn.execute('''
            SELECT status FROM enrollments 
            WHERE student_id = ? AND status IN ('pending', 'approved')
        ''', (session['user_id'],)).fetchone()
        
        if existing_enrollment:
            # Student already has a course - show only their enrolled course
            enrolled_courses = conn.execute('''
                SELECT c.*, u.full_name as teacher_name,
                       e.status as enrollment_status
                FROM courses c
                JOIN enrollments e ON c.id = e.course_id
                JOIN users u ON c.teacher_id = u.id
                WHERE e.student_id = ? AND e.status IN ('pending', 'approved')
            ''', (session['user_id'],)).fetchall()
            conn.close()
            return render_template('courses.html', courses=enrolled_courses, student_enrolled=True)
        else:
            # Student has no enrollments - show available courses
            available_courses = conn.execute('''
                SELECT c.*, u.full_name as teacher_name,
                       (SELECT status FROM enrollments WHERE student_id = ? AND course_id = c.id) as enrollment_status
                FROM courses c
                JOIN users u ON c.teacher_id = u.id
                WHERE c.is_published = 1
            ''', (session['user_id'],)).fetchall()
            conn.close()
            return render_template('courses.html', courses=available_courses)
    
    elif role in ['teacher', 'lecturer']:
        # Teachers/Lecturers see courses they created
        my_courses = conn.execute('''
            SELECT c.*, 
                   (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id AND status = 'approved') as enrolled_count
            FROM courses c
            WHERE c.teacher_id = ?
        ''', (session['user_id'],)).fetchall()
        conn.close()
        return render_template('courses.html', courses=my_courses, my_courses=True)
    
    elif role == 'lecturer':
        # Lecturers see courses they teach (as teacher) OR courses where they're assigned to modules
        my_courses = conn.execute('''
            SELECT c.*, 
                   (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id AND status = 'approved') as enrolled_count
            FROM courses c
            WHERE c.teacher_id = ?
            OR c.id IN (
                SELECT m.course_id FROM modules m
                JOIN module_lecturers ml ON m.id = ml.module_id
                WHERE ml.lecturer_id = ?
            )
        ''', (session['user_id'], session['user_id'])).fetchall()
        conn.close()
        return render_template('courses.html', courses=my_courses, my_courses=True)
    
    elif role == 'admin':
        all_courses = conn.execute('''
            SELECT c.*, u.username as teacher_name,
                   (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id AND status = 'approved') as enrolled_count
            FROM courses c
            JOIN users u ON c.teacher_id = u.id
        ''').fetchall()
        conn.close()
        return render_template('courses.html', courses=all_courses, all_courses=True)
    
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/courses/create', methods=['GET', 'POST'])
@login_required
@role_required('lecturer', 'admin')
def create_course():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        subject = request.form.get('subject', '')
        course_code = request.form.get('course_code', '')
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO courses (title, description, subject, course_code, teacher_id, is_published)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (title, description, subject, course_code, session['user_id']))
            course_id = cursor.lastrowid
            conn.commit()
            
            # Create notification for teacher
            cursor.execute('''
                INSERT INTO notifications (user_id, title, message_text, link)
                VALUES (?, ?, ?, ?)
            ''', (session['user_id'], 'Course Created', f'You have created "{title}"', f'/courses/{course_id}'))
            conn.commit()
            
            flash('Course created successfully!', 'success')
            return redirect(url_for('course_detail', course_id=course_id))
        except Exception as e:
            flash(f'Error creating course: {str(e)}', 'danger')
        finally:
            conn.close()
    
    return render_template('course_form.html', course=None)

@app.route('/courses/<int:course_id>')
@login_required
def course_detail(course_id):
    conn = get_db_connection()
    course = conn.execute('SELECT c.*, u.full_name as teacher_name FROM courses c JOIN users u ON c.teacher_id = u.id WHERE c.id = ?', (course_id,)).fetchone()
    
    if not course:
        conn.close()
        flash('Course not found!', 'danger')
        return redirect(url_for('courses'))
    
    role = session['role']
    user_id = session['user_id']
    
    # Check enrollment status
    enrollment = conn.execute(
        'SELECT * FROM enrollments WHERE student_id = ? AND course_id = ?', (user_id, course_id)
    ).fetchone()
    
    # Get modules in this course (instead of course-level materials)
    modules = conn.execute('''
        SELECT m.*, 
               (SELECT COUNT(*) FROM module_enrollments WHERE module_id = m.id AND status = 'approved') as student_count
        FROM modules m
        WHERE m.course_id = ? AND m.is_active = 1
        ORDER BY m.chapter_number
    ''', (course_id,)).fetchall()
    
    # Get student's module enrollments
    student_module_enrollments = {}
    if enrollment and enrollment['status'] == 'approved':
        module_enrollments = conn.execute('''
            SELECT module_id, status FROM module_enrollments 
            WHERE student_id = ? AND module_id IN (SELECT id FROM modules WHERE course_id = ?)
        ''', (user_id, course_id)).fetchall()
        for me in module_enrollments:
            student_module_enrollments[me['module_id']] = me['status']
    
    # Get enrolled students (for teacher/admin)
    enrolled_students = []
    if role in ['teacher', 'admin', 'lecturer']:
        enrolled_students = conn.execute('''
            SELECT u.id, u.username, u.email, u.full_name, e.enrolled_at
            FROM enrollments e
            JOIN users u ON e.student_id = u.id
            WHERE e.course_id = ? AND e.status = 'approved'
        ''', (course_id,)).fetchall()
    
    # Check if lecturer is assigned to any module in this course
    lecturer_modules = []
    lecturer_module_access = False
    if role == 'lecturer':
        lecturer_modules = conn.execute('''
            SELECT m.* FROM modules m
            JOIN module_lecturers ml ON m.id = ml.module_id
            WHERE ml.lecturer_id = ? AND m.course_id = ?
        ''', (user_id, course_id)).fetchall()
        lecturer_module_access = len(lecturer_modules) > 0
    
    conn.close()
    
    can_access = (role in ['admin'] or 
                  (role in ['teacher', 'lecturer'] and course['teacher_id'] == user_id) or
                  (role == 'lecturer' and lecturer_module_access) or
                  (enrollment and enrollment['status'] == 'approved'))
    
    return render_template('course_detail.html', 
                         course=course, 
                         enrollment=enrollment,
                         modules=modules,
                         student_module_enrollments=student_module_enrollments,
                         lecturer_modules=lecturer_modules,
                         enrolled_students=enrolled_students,
                         can_access=can_access)

@app.route('/courses/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('lecturer', 'admin')
def edit_course(course_id):
    conn = get_db_connection()
    course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    
    if not course:
        conn.close()
        flash('Course not found!', 'danger')
        return redirect(url_for('courses'))
    
    # Check permission
    if session['role'] != 'admin' and course['teacher_id'] != session['user_id']:
        conn.close()
        flash('You do not have permission to edit this course!', 'danger')
        return redirect(url_for('courses'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        subject = request.form.get('subject', '')
        course_code = request.form.get('course_code', '')
        
        conn.execute('''
            UPDATE courses SET title = ?, description = ?, subject = ?, course_code = ?
            WHERE id = ?
        ''', (title, description, subject, course_code, course_id))
        conn.commit()
        conn.close()
        
        flash('Course updated successfully!', 'success')
        return redirect(url_for('course_detail', course_id=course_id))
    
    conn.close()
    return render_template('course_form.html', course=course)

@app.route('/courses/<int:course_id>/delete')
@login_required
@role_required('lecturer', 'admin')
def delete_course(course_id):
    conn = get_db_connection()
    course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    
    if not course:
        conn.close()
        flash('Course not found!', 'danger')
        return redirect(url_for('courses'))
    
    if session['role'] != 'admin' and course['teacher_id'] != session['user_id']:
        conn.close()
        flash('You do not have permission to delete this course!', 'danger')
        return redirect(url_for('courses'))
    
    # Delete related data
    conn.execute('DELETE FROM enrollments WHERE course_id = ?', (course_id,))
    conn.execute('DELETE FROM course_materials WHERE course_id = ?', (course_id,))
    conn.execute('DELETE FROM quizzes WHERE course_id = ?', (course_id,))
    conn.execute('DELETE FROM announcements WHERE course_id = ?', (course_id,))
    conn.execute('DELETE FROM courses WHERE id = ?', (course_id,))
    conn.commit()
    conn.close()
    
    flash('Course deleted successfully!', 'success')
    return redirect(url_for('courses'))

# ==================== ENROLLMENT ROUTES ====================

@app.route('/enroll/<int:course_id>')
@login_required
@role_required('student')
def enroll_course(course_id):
    conn = get_db_connection()
    
    course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    if not course:
        conn.close()
        flash('Course not found!', 'danger')
        return redirect(url_for('courses'))
    
    # Check if already enrolled in THIS course
    existing = conn.execute(
        'SELECT * FROM enrollments WHERE student_id = ? AND course_id = ?',
        (session['user_id'], course_id)
    ).fetchone()
    
    if existing:
        conn.close()
        flash('You are already enrolled in this course!', 'warning')
        return redirect(url_for('course_detail', course_id=course_id))
    
    # Check if student is already enrolled in ANY course (one course per student)
    any_enrollment = conn.execute(
        'SELECT * FROM enrollments WHERE student_id = ? AND status = ?',
        (session['user_id'], 'approved')
    ).fetchone()
    
    if any_enrollment:
        conn.close()
        # Get the course name they're enrolled in
        enrolled_course = conn.execute('SELECT title FROM courses WHERE id = ?', (any_enrollment['course_id'],)).fetchone()
        flash(f'You can only enroll in one course! You are already enrolled in "{enrolled_course["title"]}"', 'warning')
        return redirect(url_for('courses'))
    
    # Check if there's a pending enrollment request
    pending = conn.execute(
        'SELECT * FROM enrollments WHERE student_id = ? AND status = ?',
        (session['user_id'], 'pending')
    ).fetchone()
    
    if pending:
        conn.close()
        flash('You already have a pending enrollment request!', 'warning')
        return redirect(url_for('courses'))
    
    # Create enrollment request
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO enrollments (student_id, course_id, status)
        VALUES (?, ?, 'pending')
    ''', (session['user_id'], course_id))
    enrollment_id = cursor.lastrowid
    
    # Notify teacher
    cursor.execute('''
        INSERT INTO notifications (user_id, title, message_text, link)
        VALUES (?, ?, ?, ?)
    ''', (course['teacher_id'], 'New Enrollment Request', 
          f'{session.get("full_name") or session["username"]} requested to enroll in "{course["title"]}"',
          f'/enrollment-requests'))
    conn.commit()
    conn.close()
    
    flash('Enrollment request sent! Wait for teacher approval.', 'success')
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/enrollment-requests')
@login_required
@role_required('lecturer')
def enrollment_requests():
    conn = get_db_connection()
    
    pending_requests = conn.execute('''
        SELECT e.id, u.id as student_id, u.username, u.email, u.full_name, c.id as course_id, c.title, e.enrolled_at
        FROM enrollments e
        JOIN users u ON e.student_id = u.id
        JOIN courses c ON e.course_id = c.id
        WHERE c.teacher_id = ? AND e.status = 'pending'
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    return render_template('enrollment_requests.html', requests=pending_requests)

@app.route('/enrollment/<int:enrollment_id>/approve')
@login_required
@role_required('lecturer', 'admin')
def approve_enrollment(enrollment_id):
    conn = get_db_connection()
    
    enrollment = conn.execute('''
        SELECT e.*, c.title as course_title, c.teacher_id
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.id = ?
    ''', (enrollment_id,)).fetchone()
    
    if not enrollment:
        conn.close()
        flash('Enrollment request not found!', 'danger')
        return redirect(url_for('enrollment_requests'))
    
    # Check permission
    if session['role'] != 'admin' and enrollment['teacher_id'] != session['user_id']:
        conn.close()
        flash('You do not have permission!', 'danger')
        return redirect(url_for('enrollment_requests'))
    
    conn.execute('UPDATE enrollments SET status = ? WHERE id = ?', ('approved', enrollment_id))
    
    # Notify student
    conn.execute('''
        INSERT INTO notifications (user_id, title, message_text, link)
        VALUES (?, ?, ?, ?)
    ''', (enrollment['student_id'], 'Enrollment Approved', 
          f'Your enrollment in "{enrollment["course_title"]}" has been approved!',
          f'/courses/{enrollment["course_id"]}'))
    conn.commit()
    conn.close()
    
    flash('Enrollment approved!', 'success')
    return redirect(url_for('enrollment_requests'))

@app.route('/enrollment/<int:enrollment_id>/reject')
@login_required
@role_required('lecturer', 'admin')
def reject_enrollment(enrollment_id):
    conn = get_db_connection()
    
    enrollment = conn.execute('''
        SELECT e.*, c.title as course_title, c.teacher_id
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.id = ?
    ''', (enrollment_id,)).fetchone()
    
    if not enrollment:
        conn.close()
        flash('Enrollment request not found!', 'danger')
        return redirect(url_for('enrollment_requests'))
    
    if session['role'] != 'admin' and enrollment['teacher_id'] != session['user_id']:
        conn.close()
        flash('You do not have permission!', 'danger')
        return redirect(url_for('enrollment_requests'))
    
    conn.execute('UPDATE enrollments SET status = ? WHERE id = ?', ('rejected', enrollment_id))
    
    conn.execute('''
        INSERT INTO notifications (user_id, title, message_text, link)
        VALUES (?, ?, ?, ?)
    ''', (enrollment['student_id'], 'Enrollment Rejected', 
          f'Your enrollment in "{enrollment["course_title"]}" has been rejected.',
          f'/courses'))
    conn.commit()
    conn.close()
    
    flash('Enrollment rejected!', 'success')
    return redirect(url_for('enrollment_requests'))

# Student can cancel their enrollment request
@app.route('/enrollment/<int:enrollment_id>/cancel')
@login_required
@role_required('student')
def cancel_enrollment(enrollment_id):
    conn = get_db_connection()
    
    # Get the enrollment
    enrollment = conn.execute('''
        SELECT e.*, c.title as course_title
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.id = ? AND e.student_id = ?
    ''', (enrollment_id, session['user_id'])).fetchone()
    
    if not enrollment:
        conn.close()
        flash('Enrollment not found!', 'danger')
        return redirect(url_for('dashboard'))
    
    # Delete the enrollment request
    conn.execute('DELETE FROM enrollments WHERE id = ?', (enrollment_id,))
    conn.commit()
    conn.close()
    
    flash('Enrollment request cancelled successfully.', 'success')
    return redirect(url_for('dashboard'))

# Student can cancel their enrollment request by course_id
@app.route('/enrollment/cancel/<int:course_id>')
@login_required
@role_required('student')
def cancel_enrollment_by_course(course_id):
    conn = get_db_connection()
    
    # Get the enrollment
    enrollment = conn.execute('''
        SELECT e.*, c.title as course_title
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.course_id = ? AND e.student_id = ?
    ''', (course_id, session['user_id'])).fetchone()
    
    if not enrollment:
        conn.close()
        flash('Enrollment not found!', 'danger')
        return redirect(url_for('courses'))
    
    # Delete the enrollment request
    conn.execute('DELETE FROM enrollments WHERE course_id = ? AND student_id = ?', (course_id, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Enrollment request cancelled successfully. You can now enroll in another course.', 'success')
    return redirect(url_for('courses'))

# ==================== MATERIAL ROUTES ====================

@app.route('/courses/<int:course_id>/materials/add', methods=['GET', 'POST'])
@login_required
@role_required('lecturer', 'admin')
def add_material(course_id):
    conn = get_db_connection()
    course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    
    if not course:
        conn.close()
        flash('Course not found!', 'danger')
        return redirect(url_for('courses'))
    
    if session['role'] != 'admin' and course['teacher_id'] != session['user_id']:
        conn.close()
        flash('You do not have permission!', 'danger')
        return redirect(url_for('course_detail', course_id=course_id))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        file = request.files.get('file')
        
        file_path = None
        file_type = None
        
        if file and file.filename:
            if allowed_file(file.filename):
                filename = f"{course_id}_{int(datetime.now().timestamp())}_{file.filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'course_materials', filename)
                file.save(filepath)
                file_path = f"/static/uploads/course_materials/{filename}"
                file_type = file.filename.rsplit('.', 1)[1].lower()
            else:
                flash('Invalid file type!', 'danger')
                return redirect(url_for('add_material', course_id=course_id))
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO course_materials (course_id, title, description, file_path, file_type, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (course_id, title, description, file_path, file_type, session['user_id']))
        
        # Notify enrolled students
        students = conn.execute('''
            SELECT student_id FROM enrollments WHERE course_id = ? AND status = 'approved'
        ''', (course_id,)).fetchall()
        
        for student in students:
            conn.execute('''
                INSERT INTO notifications (user_id, title, message_text, link)
                VALUES (?, ?, ?, ?)
            ''', (student['student_id'], 'New Material Added', 
                  f'New material "{title}" added to "{course["title"]}"',
                  f'/courses/{course_id}'))
        
        conn.commit()
        conn.close()
        
        flash('Material uploaded successfully!', 'success')
        return redirect(url_for('course_detail', course_id=course_id))
    
    conn.close()
    return render_template('material_form.html', course_id=course_id)

# ==================== QUIZZES LIST ROUTES ====================

@app.route('/quizzes')
@login_required
def quizzes():
    """List all available quizzes for students"""
    if session.get('role') != 'student':
        return redirect(url_for('dashboard'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    
    # Get filters
    selected_course = request.args.get('course_id', '')
    selected_status = request.args.get('status', '')
    
    # Get enrolled courses
    enrolled_courses = conn.execute('''
        SELECT c.id, c.title FROM courses c
        JOIN enrollments e ON c.id = e.course_id
        WHERE e.student_id = ? AND e.status = 'approved'
    ''', (user_id,)).fetchall()
    
    course_ids = [c['id'] for c in enrolled_courses]
    
    # Get quizzes from enrolled courses with result info
    quiz_list = []
    if course_ids:
        for course_id in course_ids:
            quizzes = conn.execute('''
                SELECT q.id, q.title, q.description, q.course_id, q.difficulty, c.title as course_title,
                       (SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = q.id) as total_questions
                FROM quizzes q
                JOIN courses c ON q.course_id = c.id
                WHERE q.course_id = ?
            ''', (course_id,)).fetchall()
            
            for quiz in quizzes:
                # Check if student has completed this quiz
                result = conn.execute('''
                    SELECT id, score, total_questions FROM quiz_results 
                    WHERE quiz_id = ? AND student_id = ? 
                    ORDER BY completed_at DESC LIMIT 1
                ''', (quiz['id'], user_id)).fetchone()
                
                if result and 'score' in result.keys() and 'total_questions' in result.keys():
                    status = 'completed'
                    score = result['score']
                    total = result['total_questions'] if result['total_questions'] else quiz['total_questions']
                    result_id = result['id']
                else:
                    status = 'not_started'
                    score = None
                    total = quiz['total_questions']
                    result_id = None
                
                quiz_list.append({
                    'id': quiz['id'],
                    'title': quiz['title'],
                    'description': quiz['description'],
                    'course_title': quiz['course_title'],
                    'total_questions': total,
                    'difficulty': quiz['difficulty'],
                    'status': status,
                    'result_id': result_id,
                    'score': score,
                    'course_id': quiz['course_id']
                })
    
    # Filter by course
    if selected_course:
        quiz_list = [q for q in quiz_list if str(q['course_id']) == selected_course]
    
    # Filter by status
    if selected_status == 'completed':
        quiz_list = [q for q in quiz_list if q['status'] == 'completed']
    elif selected_status == 'available':
        quiz_list = [q for q in quiz_list if q['status'] == 'not_started']
    
    # Get stats
    total_available = len([q for q in quiz_list if q['status'] == 'not_started'])
    completed_count = len([q for q in quiz_list if q['status'] == 'completed'])
    
    # Calculate average score
    completed_quizzes = [q for q in quiz_list if q['status'] == 'completed' and q['score'] is not None and q['total_questions']]
    if completed_quizzes:
        avg_score = sum(q['score']/q['total_questions']*100 for q in completed_quizzes) / len(completed_quizzes)
    else:
        avg_score = 0
    
    # Get recent results
    recent_results = conn.execute('''
        SELECT qr.id, qr.quiz_id, qr.student_id, qr.score, qr.total_questions, qr.completed_at, q.title as quiz_title, c.title as course_title
        FROM quiz_results qr
        JOIN quizzes q ON qr.quiz_id = q.id
        JOIN courses c ON q.course_id = c.id
        WHERE qr.student_id = ?
        ORDER BY qr.completed_at DESC LIMIT 5
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    return render_template('quizzes.html',
                         quizzes=quiz_list,
                         courses=enrolled_courses,
                         selected_course=selected_course,
                         selected_status=selected_status,
                         total_available=total_available,
                         completed_count=completed_count,
                         avg_score=avg_score,
                         recent_results=recent_results)

# ==================== QUIZ ROUTES ====================

@app.route('/quizzes/<int:quiz_id>')
@login_required
def take_quiz(quiz_id):
    conn = get_db_connection()
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    
    if not quiz:
        conn.close()
        flash('Quiz not found!', 'danger')
        return redirect(url_for('courses'))
    
    # Check enrollment
    enrollment = conn.execute(
        'SELECT * FROM enrollments WHERE student_id = ? AND course_id = ? AND status = ?',
        (session['user_id'], quiz['course_id'], 'approved')
    ).fetchone()
    
    if not enrollment and session['role'] != 'admin':
        conn.close()
        flash('You must be enrolled to take this quiz!', 'danger')
        return redirect(url_for('courses'))
    
    questions = conn.execute('SELECT * FROM quiz_questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
    
    # Check if already completed
    previous_result = conn.execute(
        'SELECT * FROM quiz_results WHERE quiz_id = ? AND student_id = ?',
        (quiz_id, session['user_id'])
    ).fetchone()
    
    conn.close()
    return render_template('quiz.html', quiz=quiz, questions=questions, previous_result=previous_result)

@app.route('/quizzes/<int:quiz_id>/submit', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    conn = get_db_connection()
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    
    if not quiz:
        conn.close()
        flash('Quiz not found!', 'danger')
        return redirect(url_for('courses'))
    
    questions = conn.execute('SELECT * FROM quiz_questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
    
    score = 0
    answers = {}
    
    for question in questions:
        answer = request.form.get(f'answer_{question["id"]}')
        answers[str(question['id'])] = answer
        if answer and answer.lower() == question['correct_answer'].lower():
            score += 1
    
    total = len(questions)
    percentage = (score / total * 100) if total > 0 else 0
    
    # Save result
    import json
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO quiz_results (quiz_id, student_id, score, total_questions, answers)
        VALUES (?, ?, ?, ?, ?)
    ''', (quiz_id, session['user_id'], score, total, json.dumps(answers)))
    result_id = cursor.lastrowid
    
    # Generate AI feedback
    weak_topics = []
    recommendations = []
    
    if percentage < 70:
        weak_topics.append("Review the course materials thoroughly")
        recommendations.append("Consider generating AI summaries from the materials")
    
    if percentage < 50:
        weak_topics.append("Seek additional help from the teacher")
        recommendations.append("Join study groups or discussion forums")
    
    feedback_text = f"You scored {score} out of {total} ({percentage:.1f}%). "
    if percentage >= 70:
        feedback_text += "Great job! You have a good understanding of the material."
    elif percentage >= 50:
        feedback_text += "Good effort! Some areas need improvement."
    else:
        feedback_text += "Keep studying! Review the materials and try again."
    
    cursor.execute('''
        INSERT INTO ai_feedback (quiz_result_id, student_id, course_id, feedback_text, weak_topics, recommendations)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (result_id, session['user_id'], quiz['course_id'], feedback_text, 
          json.dumps(weak_topics), json.dumps(recommendations)))
    
    # Notify teacher
    cursor.execute('''
        INSERT INTO notifications (user_id, title, message_text, link)
        VALUES (?, ?, ?, ?)
    ''', (quiz['created_by'], 'Quiz Completed', 
          f'{session.get("full_name") or session["username"]} completed "{quiz["title"]}" - Score: {percentage:.1f}%',
          f'/quizzes/{quiz_id}/results'))
    
    conn.commit()
    conn.close()
    
    flash(f'Quiz submitted! Score: {score}/{total} ({percentage:.1f}%)', 'success')
    return redirect(url_for('quiz_result', result_id=result_id))

@app.route('/quiz-results/<int:result_id>')
@login_required
def quiz_result(result_id):
    conn = get_db_connection()
    result = conn.execute('''
        SELECT qr.*, q.title as quiz_title, q.course_id
        FROM quiz_results qr
        JOIN quizzes q ON qr.quiz_id = q.id
        WHERE qr.id = ? AND qr.student_id = ?
    ''', (result_id, session['user_id'])).fetchone()
    
    if not result:
        conn.close()
        flash('Result not found!', 'danger')
        return redirect(url_for('courses'))
    
    questions = conn.execute('''
        SELECT qq.*, qr.answers 
        FROM quiz_questions qq
        JOIN quiz_results qr ON qq.quiz_id = qr.quiz_id
        WHERE qr.id = ?
    ''', (result_id,)).fetchall()
    
    feedback = conn.execute(
        'SELECT * FROM ai_feedback WHERE quiz_result_id = ?', (result_id,)
    ).fetchone()
    
    import json
    if feedback:
        feedback = dict(feedback)
        feedback['weak_topics'] = json.loads(feedback['weak_topics']) if feedback['weak_topics'] else []
        feedback['recommendations'] = json.loads(feedback['recommendations']) if feedback['recommendations'] else []
    
    conn.close()
    return render_template('quiz_result.html', result=result, questions=questions, feedback=feedback)

# ==================== BUILT-IN AI RESPONSE GENERATOR (FALLBACK) ====================

def generate_ai_response(message, context_info, weak_areas, course=None):
    """
    Generate intelligent educational responses using Ollama AI.
    Falls back to built-in rule-based generator if Ollama is unavailable.
    """
    
    # Build context for Ollama
    course_context = f" The student is enrolled in: {course['title']}." if course else ""
    weak_areas_context = f" {weak_areas}" if weak_areas else ""
    context_context = f" {context_info}" if context_info else ""
    
    # Create a comprehensive prompt for Ollama
    system_prompt = """You are an intelligent and friendly AI Study Assistant for EduMind, an educational platform. 
Your role is to help students learn and understand any topic. Be conversational, encouraging, and educational.
Use emojis appropriately to make responses engaging. Keep responses comprehensive but not too long.
If you don't know something, be honest and say so."""
    
    user_prompt = f"""Student question: {message}
{course_context}{weak_areas_context}{context_context}

Please provide a helpful, educational response to this question. Use your knowledge to explain concepts clearly and provide examples where appropriate."""
    
    # Try Ollama first
    ollama_response = generate_ollama_response(user_prompt, system_prompt, max_tokens=500)
    
    if ollama_response:
        print(f"[OLLAMA] Generated response for: {message[:50]}...")
        return ollama_response
    
    # Fallback to built-in rule-based generator
    print("[FALLBACK] Using built-in AI response generator")
    return _generate_fallback_response(message, context_info, weak_areas, course)


def _generate_fallback_response(message, context_info, weak_areas, course=None):
    """Fallback rule-based response generator (original implementation)"""
    message_lower = message.lower()
    
    # Topic keywords for categorization
    topics = {
        'programming': ['programming', 'code', 'coding', 'python', 'java', 'javascript', 'c++', 'algorithm', 'developer'],
        'math': ['math', 'mathematics', 'calculate', 'calculation', 'formula', 'equation', 'algebra', 'calculus'],
        'science': ['science', 'physics', 'chemistry', 'biology', 'experiment', 'scientific'],
        'history': ['history', 'historical', 'war', 'ancient', 'modern', 'century'],
        'language': ['language', 'grammar', 'writing', 'essay', 'vocabulary', 'english', 'literature'],
        'business': ['business', 'management', 'marketing', 'economy', 'finance', 'entrepreneur'],
        'technology': ['technology', 'tech', 'computer', 'internet', 'software', 'hardware', 'ai', 'machine learning'],
    }
    
    # Detect topic
    detected_topic = None
    for topic, keywords in topics.items():
        if any(kw in message_lower for kw in keywords):
            detected_topic = topic
            break
    
    # Greeting patterns
    if any(greet in message_lower for greet in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
        course_title = course['title'] if course else ''
        responses = [
            f"Hello! I'm your AI Study Assistant. I'm here to help you learn! What would you like to explore today?{' Since you\'re studying ' + course_title + ', I can help you with that!' if course else ''}",
            "Hi there! Ready to learn something new? Let me know what you'd like to study!",
            f"Hey! Great to see you! How can I help you with your studies today?{' I see you\'re enrolled in ' + course_title + '.' if course else ''}"
        ]
        return random.choice(responses)
    
    # Help patterns
    if 'help' in message_lower or 'what can you do' in message_lower:
        return "I'm your AI Study Assistant! I can help you: 📚 Understand difficult concepts, 📝 Answer questions about your courses, 💡 Explain topics in simple terms, 📖 Create study guides, and 🎯 Help with quiz preparation. Just ask me anything!"
    
    # Who are you / what are you
    if 'who are you' in message_lower or 'what are you' in message_lower:
        return "I'm the EduMind AI Study Assistant! I'm here to help you learn and understand any topic in your courses. I can explain concepts, answer questions, and guide you through your studies. What would you like to learn about?"
    
    # Thank you patterns
    if 'thank' in message_lower:
        responses = [
            "You're welcome! Happy to help! Is there anything else you'd like to learn?",
            "No problem! Feel free to ask more questions anytime!",
            "Glad I could help! What else would you like to explore?"
        ]
        return random.choice(responses)
    
    # Question about the course/lecture
    if any(q in message_lower for q in ['lecture', 'course', 'module', 'class']):
        if course:
            return f"Great question about {course['title']}! Based on your course, here's what you should focus on:\n\n1. 📖 Review the course materials regularly\n2. 📝 Take notes during lessons\n3. 💬 Ask questions when unclear\n4. 🧪 Practice with quizzes\n5. 👥 Discuss with peers\n\nWould you like me to explain any specific concept in {course['title']}?"
        else:
            return "That's a great course-related question! To get the most out of your studies: attend lectures, review materials regularly, participate in discussions, and don't hesitate to ask questions. Would you like me to help with a specific topic?"
    
    # Explain a concept
    if any(exp in message_lower for exp in ['explain', 'what is', 'what are', 'how does', 'define', 'meaning of']):
        if detected_topic == 'programming':
            responses = [
                "Great question about programming! Programming is the art of giving instructions to a computer. Think of it like writing a recipe - you list step-by-step instructions that the computer follows.\n\n🔑 Key concepts:\n• Variables: Containers for storing data\n• Functions: Reusable blocks of code\n• Loops: Repeating actions\n• Conditionals: Making decisions\n\nWould you like me to explain any of these in more detail?",
                "Programming is how we communicate with computers! It's like learning a new language, but instead of speaking to humans, you're giving instructions to a machine.\n\nThe basic steps are:\n1. Write code\n2. Test it\n3. Fix errors (bugs)\n4. Improve\n\nWhat specific programming concept would you like to explore?"
            ]
            return random.choice(responses)
        elif detected_topic == 'math':
            return "Math is the language of numbers and patterns! It helps us quantify, measure, and understand the world around us.\n\n🔢 Key areas:\n• Arithmetic: Basic operations (+, -, ×, ÷)\n• Algebra: Using symbols (x, y) to represent numbers\n• Geometry: Shapes, sizes, and positions\n• Calculus: Rates of change\n\nWhat math concept would you like me to explain?"
        elif detected_topic == 'technology':
            return "Technology is the application of scientific knowledge for practical purposes! It includes computers, software, networks, and digital devices.\n\n💻 Key areas:\n• Hardware: Physical devices (computer, phone, servers)\n• Software: Programs and apps\n• AI/Machine Learning: Systems that learn from data\n• Cloud Computing: Online services and storage\n\nWhich area interests you most?"
        else:
            return f"That's an excellent learning question! To understand new concepts, I recommend:\n\n1. 📚 Start with the basics\n2. 🔍 Research from multiple sources\n3. ✍️ Write notes in your own words\n4. 💬 Teach it to someone else\n5. 🔄 Practice regularly\n\nWould you like me to explain any specific aspect of '{message}'?"
    
    # Study tips
    if any(tip in message_lower for tip in ['study', 'learn', 'tips', 'how to study', 'advice']):
        return "Here are proven study tips for success! 📚\n\n1. 🎯 Set clear goals\n2. 📅 Create a study schedule\n3. 👂 Active learning (not just reading)\n4. 💪 Practice regularly\n5. 😴 Get enough sleep\n6. 🍎 Take breaks & stay healthy\n7. 🔄 Review what you learned\n8. 💡 Connect new info to what you know\n\nWould you like specific study strategies for a particular subject?"
    
    # Weak areas / struggling
    if weak_areas and any(struggle in message_lower for struggle in ['struggling', 'hard', 'difficult', 'confused', 'don\'t understand', 'help me']):
        return f"Don't worry, everyone struggles sometimes! {weak_areas}\n\n💪 Here's how to improve:\n1. Start with the basics\n2. Break complex topics into smaller parts\n3. Practice with examples\n4. Ask questions\n5. Review regularly\n\nYou can do it! Would you like me to explain any of these areas in simpler terms?"
    
    # Default intelligent responses
    course_title = course['title'] if course else ''
    course_context = f" Since you're studying {course_title}, I can relate it to your coursework." if course else ''
    course_study = f"I see you're studying {course_title} - great course!" if course else ''
    
    response_templates = [
        f"That's an interesting question about '{message}'! Let me help you think through this.\n\nTo understand any topic well, start with the basics and build from there. What specific aspect would you like to explore?{course_context}",
        f"Great question! Learning about '{message}' is an important part of your studies.\n\nHere's my advice:\n1. 📖 Read your course materials\n2. 🔍 Look up additional resources\n3. ✍️ Practice with exercises\n4. 💬 Discuss with classmates\n\nWould you like me to elaborate on any part of this?",
        "I'm here to help you learn! Could you tell me more specifically what you'd like to know? For example:\n- What exactly you want to understand\n- What you've already tried\n- What part is confusing\n\nThis will help me give you a better answer!",
        f"That's a thoughtful question! {course_study}\n\nLet me share some insights on this topic:\n\nThe key is to break it down into manageable parts and practice consistently. Don't hesitate to ask follow-up questions!",
        "Excellent curiosity! Questions like this are how learning happens.\n\nHere's my approach:\n1. Understand the 'why' behind concepts\n2. Connect to real-world examples\n3. Practice, practice, practice\n4. Don't fear mistakes - they're learning opportunities!\n\nWhat specifically would you like to dive deeper into?"
    ]
    
    # Add context-specific response if available
    if context_info:
        response_templates.append(f"Based on your module: {context_info}\n\nThis is a key concept in your studies. Focus on understanding the fundamentals first, then build up to more complex ideas. Want me to explain more?")
    
    return random.choice(response_templates)

# ==================== AI ROUTES ====================

@app.route('/ai-chat', methods=['GET', 'POST'])
@login_required
def ai_chat():
    conn = get_db_connection()
    user_id = session['user_id']
    
    # Get user's chat history
    chats = conn.execute('''
        SELECT * FROM ai_chats WHERE user_id = ? ORDER BY created_at DESC LIMIT 50
    ''', (user_id,)).fetchall()
    
    selected_course = request.args.get('course_id') or (request.form.get('course_id') if request.form.get('course_id') else None)
    selected_module = request.args.get('module_id') or (request.form.get('module_id') if request.form.get('module_id') else None)
    
    if request.method == 'POST':
        message = request.form.get('message')
        
        # Only process if there's a message
        if message:
            course_id = request.form.get('course_id')
            module_id = request.form.get('module_id')
            course = None  # Initialize course variable
            
            # Get context from module/chapter if selected
            context_info = ""
            if module_id:
                module = conn.execute('SELECT * FROM modules WHERE id = ?', (module_id,)).fetchone()
                if module:
                    context_info = f" The question is about module: {module['title']}."
                    # Get related materials
                    materials = conn.execute('''
                        SELECT * FROM module_materials 
                        WHERE module_id = ? ORDER BY created_at DESC LIMIT 3
                    ''', (module_id,)).fetchall()
                    if materials:
                        context_info += " Related topics: " + ", ".join([m['title'] for m in materials[:3]])
            elif course_id:
                course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
                if course:
                    context_info = f" The question is about course: {course['title']}."
            
            # Get student's weak areas based on quiz performance
            weak_areas = ""
            if session['role'] == 'student':
                weak_quizzes = conn.execute('''
                    SELECT q.title, qr.score, qr.total_questions
                    FROM quiz_results qr
                    JOIN quizzes q ON qr.quiz_id = q.id
                    WHERE qr.student_id = ? AND CAST(qr.score AS FLOAT) / qr.total_questions < 0.6
                    ORDER BY qr.completed_at DESC LIMIT 5
                ''', (user_id,)).fetchall()
                if weak_quizzes:
                    weak_areas = " Based on your recent quizzes, you may need to review: " + ", ".join([q['title'] for q in weak_quizzes[:3]])
            
            # Generate intelligent AI response using built-in generator
            bot_response = generate_ai_response(message, context_info, weak_areas, course)
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ai_chats (user_id, course_id, user_message, bot_response)
                VALUES (?, ?, ?, ?)
            ''', (user_id, course_id if course_id else None, message, bot_response))
            conn.commit()
            
            # Refresh chats
            chats = conn.execute('''
                SELECT * FROM ai_chats WHERE user_id = ? ORDER BY created_at DESC LIMIT 50
            ''', (user_id,)).fetchall()
        else:
            # Just updating course/module selection, no message
            course_id = request.form.get('course_id')
            module_id = request.form.get('module_id')
    
    # Get enrolled courses for context
    if session['role'] == 'student':
        courses = conn.execute('''
            SELECT c.id, c.title FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            WHERE e.student_id = ? AND e.status = 'approved'
        ''', (user_id,)).fetchall()
        
        # Get modules for selected course
        modules = []
        if selected_course:
            modules = conn.execute('''
                SELECT m.id, m.title FROM modules m
                JOIN module_enrollments me ON m.id = me.module_id
                WHERE me.student_id = ? AND m.course_id = ? AND me.status = 'approved'
            ''', (user_id, selected_course)).fetchall()
    else:
        courses = []
        modules = []
    
    conn.close()
    return render_template('ai_chat.html', chats=chats, courses=courses, modules=modules, 
                         selected_course=selected_course, selected_module=selected_module)

# ==================== AJAX API FOR AI CHAT ====================

@app.route('/api/ai-chat/send', methods=['POST'])
@login_required
def api_ai_chat_send():
    """API endpoint to send a chat message and get AI response"""
    data = request.get_json()
    message = data.get('message', '').strip()
    course_id = data.get('course_id')
    module_id = data.get('module_id')
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    conn = get_db_connection()
    user_id = session['user_id']
    
    # Get context from module/chapter if selected
    context_info = ""
    if module_id:
        module = conn.execute('SELECT * FROM modules WHERE id = ?', (module_id,)).fetchone()
        if module:
            context_info = f" The question is about module: {module['title']}."
            materials = conn.execute('''
                SELECT * FROM module_materials 
                WHERE module_id = ? ORDER BY created_at DESC LIMIT 3
            ''', (module_id,)).fetchall()
            if materials:
                context_info += " Related topics: " + ", ".join([m['title'] for m in materials[:3]])
    elif course_id:
        course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
        if course:
            context_info = f" The question is about course: {course['title']}."
    
    # Get student's weak areas
    weak_areas = ""
    if session['role'] == 'student':
        weak_quizzes = conn.execute('''
            SELECT q.title, qr.score, qr.total_questions
            FROM quiz_results qr
            JOIN quizzes q ON qr.quiz_id = q.id
            WHERE qr.student_id = ? AND CAST(qr.score AS FLOAT) / qr.total_questions < 0.6
            ORDER BY qr.completed_at DESC LIMIT 5
        ''', (user_id,)).fetchall()
        if weak_quizzes:
            weak_areas = " Based on your recent quizzes, you may need to review: " + ", ".join([q['title'] for q in weak_quizzes[:3]])
    
    # Generate AI response
    bot_response = generate_ai_response(message, context_info, weak_areas, None)
    
    # Save to database
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ai_chats (user_id, course_id, user_message, bot_response)
        VALUES (?, ?, ?, ?)
    ''', (user_id, course_id if course_id else None, message, bot_response))
    conn.commit()
    
    # Get the inserted message
    chat_id = cursor.lastrowid
    conn.close()
    
    return jsonify({
        'success': True,
        'chat': {
            'id': chat_id,
            'user_message': message,
            'bot_response': bot_response,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M')
        }
    })

@app.route('/api/ai-chat/clear', methods=['POST'])
@login_required
def api_ai_chat_clear():
    """API endpoint to clear chat history"""
    conn = get_db_connection()
    user_id = session['user_id']
    
    conn.execute('DELETE FROM ai_chats WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/ai-chat/history', methods=['GET'])
@login_required
def api_ai_chat_history():
    """API endpoint to get chat history"""
    conn = get_db_connection()
    user_id = session['user_id']
    
    chats = conn.execute('''
        SELECT * FROM ai_chats WHERE user_id = ? ORDER BY created_at ASC LIMIT 50
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    chat_list = []
    for chat in chats:
        chat_list.append({
            'id': chat['id'],
            'user_message': chat['user_message'],
            'bot_response': chat['bot_response'],
            'created_at': chat['created_at'].strftime('%Y-%m-%d %H:%M') if chat['created_at'] else ''
        })
    
    return jsonify({'chats': chat_list})

@app.route('/ai-summarize/<int:material_id>')
@login_required
def ai_summarize(material_id):
    conn = get_db_connection()
    material = conn.execute('SELECT * FROM course_materials WHERE id = ?', (material_id,)).fetchone()
    
    if not material:
        conn.close()
        flash('Material not found!', 'danger')
        return redirect(url_for('courses'))
    
    # Check enrollment
    enrollment = conn.execute(
        'SELECT * FROM enrollments WHERE student_id = ? AND course_id = ? AND status = ?',
        (session['user_id'], material['course_id'], 'approved')
    ).fetchone()
    
    if not enrollment and session['role'] != 'admin':
        course = conn.execute('SELECT teacher_id FROM courses WHERE id = ?', (material['course_id'],)).fetchone()
        if not course or course['teacher_id'] != session['user_id']:
            conn.close()
            flash('You do not have access to this material!', 'danger')
            return redirect(url_for('courses'))
    
    # Generate summary using Ollama
    material_title = material['title']
    material_description = material.get('description', '')
    
    ollama_prompt = f"""Create a comprehensive educational summary for a study material titled "{material_title}".

Description: {material_description}

Please provide:
1. Key Points (3-5 main concepts covered)
2. Learning Objectives (what students should understand after studying)
3. Study Tips (3-5 practical suggestions)

Format this as a helpful study guide for students."""
    
    ollama_summary = generate_ollama_response(ollama_prompt, max_tokens=800)
    
    if ollama_summary:
        summary = f"AI Summary for: {material_title}\n\n{ollama_summary}"
        print(f"[OLLAMA] Generated summary for: {material_title}")
    else:
        # Fallback to template-based summary
        print("[FALLBACK] Using built-in summary template")
        summary = f"""AI Summary for: {material_title}

Key Points:
- This material covers important concepts related to {material_description or 'the course topic'}
- The content is structured to help students understand the fundamental principles
- Review the main sections carefully to grasp the core ideas
- Practice with the included exercises to reinforce learning

Learning Objectives:
• Understand the core concepts presented
• Apply knowledge to real-world scenarios
• Develop critical thinking skills related to this topic

Study Tips:
1. Read through the material multiple times
2. Take notes on key concepts
3. Create flashcards for important terms
4. Discuss with peers or ask AI for clarification
"""
    
    conn.close()
    return render_template('ai_summary.html', material=material, summary=summary)

@app.route('/ai-notes', methods=['GET', 'POST'])
@login_required
def ai_notes():
    """AI Notes Summary - Students can paste their notes and get AI summary"""
    summary = None
    notes = None
    focus_area = None
    
    if request.method == 'POST':
        notes = request.form.get('notes', '').strip()
        focus_area = request.form.get('focus_area', '').strip()
        
        if not notes:
            flash('Please paste some notes to summarize!', 'warning')
            return redirect(url_for('ai_notes'))
        
        # Build prompt for AI
        focus_instruction = f"Focus on: {focus_area}." if focus_area else ""
        
        ollama_prompt = f"""You are an AI study assistant. A student has pasted the following notes:

---
{notes}
---

{focus_instruction}

Please provide a comprehensive, well-organized summary that includes:
1. **Main Ideas**: 3-5 key concepts from the notes
2. **Key Terms**: Important definitions or vocabulary
3. **Important Details**: Supporting information and examples
4. **Study Focus**: Suggestions on what to emphasize based on the focus area

Format this as a clear, easy-to-study summary for exam preparation."""
        
        # Try Ollama first, then fallback
        ai_summary = generate_ollama_response(ollama_prompt, max_tokens=1000)
        
        if ai_summary:
            summary = ai_summary
            print(f"[OLLAMA] Generated notes summary")
        else:
            # Fallback summary
            summary = f"""**AI Study Summary**

{focus_area if focus_area else 'General'} Summary of Your Notes:

**Main Ideas:**
• The notes cover important concepts related to the topic
• Key information has been organized into study-friendly format
• Focus on understanding the core principles presented

**Key Terms to Remember:**
• Review the important definitions in your notes
• Pay attention to technical terms and their explanations

**Important Details:**
• The content covers foundational concepts
• Practice related exercises to reinforce learning
• Connect ideas with real-world examples

**Study Tips:**
1. Review these notes multiple times for retention
2. Create flashcards for key terms
3. Test yourself on the main concepts
4. Discuss with peers to deepen understanding

*Note: This is a template summary. For more detailed AI-powered summaries, ensure the Ollama service is running locally.*"""
    
    return render_template('ai_notes.html', notes=notes, focus_area=focus_area, summary=summary)

@app.route('/ai-quiz-generator/<int:course_id>', methods=['GET', 'POST'])
@login_required
def ai_quiz_generator(course_id):
    conn = get_db_connection()
    course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    
    if not course:
        conn.close()
        flash('Course not found!', 'danger')
        return redirect(url_for('courses'))
    
    # Check enrollment or ownership
    if session['role'] == 'student':
        enrollment = conn.execute(
            'SELECT * FROM enrollments WHERE student_id = ? AND course_id = ? AND status = ?',
            (session['user_id'], course_id, 'approved')
        ).fetchone()
        if not enrollment:
            conn.close()
            flash('You must be enrolled to generate quizzes!', 'danger')
            return redirect(url_for('courses'))
    
    # Get student's past quiz performance for adaptive difficulty
    student_quizzes = conn.execute('''
        SELECT qr.score, qr.total_questions, q.difficulty
        FROM quiz_results qr
        JOIN quizzes q ON qr.quiz_id = q.id
        WHERE qr.student_id = ? AND q.course_id = ?
        ORDER BY qr.completed_at DESC LIMIT 5
    ''', (session['user_id'], course_id)).fetchall()
    
    # Calculate average score to determine difficulty
    if student_quizzes:
        total_score = sum([(r['score']/r['total_questions']*100) for r in student_quizzes if r['total_questions'] > 0])
        avg_score = total_score / len(student_quizzes)
        
        if avg_score >= 80:
            suggested_difficulty = 'hard'
            difficulty_message = 'Based on your excellent performance, we recommend hard difficulty quizzes.'
        elif avg_score >= 50:
            suggested_difficulty = 'medium'
            difficulty_message = 'Based on your average performance, we recommend medium difficulty quizzes.'
        else:
            suggested_difficulty = 'easy'
            difficulty_message = 'Based on your recent scores, we recommend starting with easier quizzes to build confidence.'
    else:
        suggested_difficulty = 'medium'
        difficulty_message = 'No quiz history found. Starting with medium difficulty.'
    
    if request.method == 'POST':
        num_questions = int(request.form.get('num_questions', 5))
        difficulty = request.form.get('difficulty', suggested_difficulty)
        
        # Generate quiz
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO quizzes (course_id, title, description, created_by, difficulty)
            VALUES (?, ?, ?, ?, ?)
        ''', (course_id, f'AI Generated Quiz - {datetime.now().strftime("%Y-%m-%d")} ({difficulty.title()})', 
              f'Auto-generated {difficulty} quiz for {course["title"]}', session['user_id'], difficulty))
        quiz_id = cursor.lastrowid
        
        # Try to generate questions using Ollama
        ollama_questions = None
        
        # Get course details for context
        course_description = course.get('description', '')
        course_title = course['title']
        
        # Generate questions using Ollama
        ollama_prompt = f"""Generate {num_questions} multiple choice quiz questions about "{course_title}" with difficulty level "{difficulty}".

Course description: {course_description}

Format each question as:
Q: [question]
A: [correct answer]
B: [wrong option 1]
C: [wrong option 2]
D: [wrong option 3]
ANSWER: [letter of correct answer]

Make sure questions are relevant to the course content."""
        
        ollama_result = generate_ollama_response(ollama_prompt, max_tokens=1000)
        
        if ollama_result:
            # Parse Ollama response
            questions = _parse_ollama_quiz_questions(ollama_result, difficulty)
            if questions:
                print(f"[OLLAMA] Generated {len(questions)} quiz questions")
                ollama_questions = questions
        
        # Use Ollama questions if available, otherwise fallback to hardcoded
        if ollama_questions:
            question_pool = ollama_questions
        else:
            # Fallback to built-in questions
            print("[FALLBACK] Using built-in quiz questions")
            easy_questions = [
                ("What is the main concept covered in this course?", "The fundamental principles", "Random facts", "Unrelated topics", "Nothing specific", "The fundamental principles"),
                ("Which of the following is a key learning outcome?", "Memorization only", "Understanding core concepts", "Skipping lessons", "Not attending", "Understanding core concepts"),
                ("How should you approach the course materials?", "Quick scan only", "Read thoroughly and practice", "Ignore them", "Memorize everything", "Read thoroughly and practice"),
            ]
            
            medium_questions = [
                ("What is important for success in this course?", "Natural talent only", "Consistent study and practice", "Luck", "Guessing on tests", "Consistent study and practice"),
                ("When encountering difficult concepts, you should:", "Give up immediately", "Ask questions and seek help", "Skip that section", "Complain to others", "Ask questions and seek help"),
                ("The best way to retain information is:", "Cramming before exams", "Regular review and practice", "Not taking notes", "Only reading once", "Regular review and practice"),
            ]
            
            hard_questions = [
                ("Collaboration with peers helps by:", "Doing your work for you", "Getting different perspectives", "Nothing useful", "Cheating", "Getting different perspectives"),
                ("Critical thinking involves:", "Accepting everything at face value", "Analyzing and evaluating information", "Ignoring evidence", "Following blindly", "Analyzing and evaluating information"),
                ("To apply knowledge effectively, you should:", "Memorize only", "Practice and relate to real situations", "Read passively", "Avoid assignments", "Practice and relate to real situations"),
                ("Feedback helps you improve by:", "Pointing out only mistakes", "Identifying areas for growth", "Discouraging you", "Making you quit", "Identifying areas for growth"),
                ("Which methodology emphasizes iterative development?", "Waterfall", "Agile", "Sequential", "Fixed", "Agile"),
            ]
            
            if difficulty == 'easy':
                question_pool = easy_questions
            elif difficulty == 'hard':
                question_pool = hard_questions + medium_questions
            else:
                question_pool = medium_questions + easy_questions
        
        for i in range(min(num_questions, len(question_pool))):
            q = question_pool[i]
            cursor.execute('''
                INSERT INTO quiz_questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (quiz_id, q[0], q[1], q[2], q[3], q[4], q[5], difficulty))
        
        conn.commit()
        conn.close()
        
        flash(f'Quiz generated with {num_questions} questions ({difficulty.title()} difficulty)!', 'success')
        return redirect(url_for('take_quiz', quiz_id=quiz_id))
    
    conn.close()
    return render_template('ai_quiz_generator.html', course=course, suggested_difficulty=suggested_difficulty, difficulty_message=difficulty_message)

# ==================== MESSAGING ROUTES ====================

@app.route('/messages')
@login_required
def messages():
    conn = get_db_connection()
    user_id = session['user_id']
    
    # Get conversations
    conversations = conn.execute('''
        SELECT DISTINCT 
            CASE WHEN m.sender_id = ? THEN m.recipient_id ELSE m.sender_id END as other_user_id,
            u.username, u.full_name, u.role,
            (SELECT message_text FROM messages WHERE 
                (sender_id = ? AND recipient_id = u.id) OR 
                (sender_id = u.id AND recipient_id = ?) 
             ORDER BY created_at DESC LIMIT 1) as last_message,
            (SELECT COUNT(*) FROM messages WHERE sender_id = u.id AND recipient_id = ? AND is_read = 0) as unread_count
        FROM messages m
        JOIN users u ON u.id = CASE WHEN m.sender_id = ? THEN m.recipient_id ELSE m.sender_id END
        WHERE m.sender_id = ? OR m.recipient_id = ?
        ORDER BY (SELECT created_at FROM messages WHERE 
            (sender_id = ? AND recipient_id = u.id) OR 
            (sender_id = u.id AND recipient_id = ?) 
         ORDER BY created_at DESC LIMIT 1) DESC
    ''', (user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id)).fetchall()
    
    conn.close()
    return render_template('messages.html', conversations=conversations)

@app.route('/messages/<int:user_id>')
@login_required
def conversation(user_id):
    conn = get_db_connection()
    current_user_id = session['user_id']
    
    # Get messages
    messages_list = conn.execute('''
        SELECT m.*, u.username, u.full_name, u.role
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE (m.sender_id = ? AND m.recipient_id = ?) OR (m.sender_id = ? AND m.recipient_id = ?)
        ORDER BY m.created_at ASC
    ''', (current_user_id, user_id, user_id, current_user_id)).fetchall()
    
    # Mark as read
    conn.execute('''
        UPDATE messages SET is_read = 1 WHERE sender_id = ? AND recipient_id = ?
    ''', (user_id, current_user_id))
    conn.commit()
    
    # Get user info
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    conn.close()
    return render_template('conversation.html', messages=messages_list, user=user)

@app.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    recipient_id = request.form.get('recipient_id')
    subject = request.form.get('subject', '')
    message_text = request.form.get('message_text')
    course_id = request.form.get('course_id')
    
    if not recipient_id or not message_text:
        flash('Message and recipient are required!', 'danger')
        return redirect(url_for('messages'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (sender_id, recipient_id, course_id, subject, message_text)
        VALUES (?, ?, ?, ?, ?)
    ''', (session['user_id'], recipient_id, course_id if course_id else None, subject, message_text))
    
    # Notify recipient
    cursor.execute('''
        INSERT INTO notifications (user_id, title, message_text, link)
        VALUES (?, ?, ?, ?)
    ''', (recipient_id, 'New Message', 
          f'{session.get("full_name") or session["username"]} sent you a message',
          f'/messages/{session["user_id"]}'))
    
    conn.commit()
    conn.close()
    
    flash('Message sent!', 'success')
    return redirect(url_for('conversation', user_id=recipient_id))

# ==================== ANNOUNCEMENTS ====================

@app.route('/courses/<int:course_id>/announcements/add', methods=['GET', 'POST'])
@login_required
@role_required('lecturer', 'admin')
def add_announcement(course_id):
    conn = get_db_connection()
    course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
    
    if not course:
        conn.close()
        flash('Course not found!', 'danger')
        return redirect(url_for('courses'))
    
    if session['role'] != 'admin' and course['teacher_id'] != session['user_id']:
        conn.close()
        flash('You do not have permission!', 'danger')
        return redirect(url_for('course_detail', course_id=course_id))
    
    if request.method == 'POST':
        title = request.form['title']
        message_text = request.form['message_text']
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO announcements (course_id, user_id, title, message_text)
            VALUES (?, ?, ?, ?)
        ''', (course_id, session['user_id'], title, message_text))
        
        # Notify enrolled students
        students = conn.execute('''
            SELECT student_id FROM enrollments WHERE course_id = ? AND status = 'approved'
        ''', (course_id,)).fetchall()
        
        for student in students:
            conn.execute('''
                INSERT INTO notifications (user_id, title, message_text, link)
                VALUES (?, ?, ?, ?)
            ''', (student['student_id'], f'Announcement: {title}', message_text, f'/courses/{course_id}'))
        
        conn.commit()
        conn.close()
        
        flash('Announcement posted!', 'success')
        return redirect(url_for('course_detail', course_id=course_id))
    
    conn.close()
    return render_template('announcement_form.html', course_id=course_id)

# ==================== NOTIFICATIONS ====================

@app.route('/notifications')
@app.route('/notifications')
@login_required
def notifications():
    import logging
    logger = logging.getLogger(__name__)
    conn = get_db_connection()
    
    # DEBUG: Log notifications fetch
    logger.info(f"[DEBUG] Fetching notifications for user_id={session['user_id']}")
    
    notifications_list = conn.execute('''
        SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50
    ''', (session['user_id'],)).fetchall()
    
    logger.info(f"[DEBUG] Found {len(notifications_list)} notifications")
    
    # Log first few notifications for debugging
    for i, n in enumerate(notifications_list[:3]):
        logger.info(f"[DEBUG] Notification {i}: title={n['title']}, message={n['message_text']}, is_read={n['is_read']}")
    
    conn.close()
    return render_template('notifications.html', notifications=notifications_list)

@app.route('/notifications/<int:notification_id>/read')
@login_required
def mark_notification_read(notification_id):
    conn = get_db_connection()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?', 
                (notification_id, session['user_id']))
    conn.commit()
    
    notification = conn.execute('SELECT link FROM notifications WHERE id = ?', (notification_id,)).fetchone()
    conn.close()
    
    if notification and notification['link']:
        return redirect(notification['link'])
    return redirect(url_for('notifications'))

# ==================== PROFILE ====================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db_connection()
    user_id = session['user_id']
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '')
        email = request.form.get('email', '')
        
        # Handle file upload
        profile_picture = None
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename and allowed_file(file.filename):
                filename = f"user_{user_id}_{int(datetime.now().timestamp())}.{file.filename.rsplit('.', 1)[1].lower()}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures', filename)
                file.save(filepath)
                profile_picture = f"/static/uploads/profile_pictures/{filename}"
                
                # Delete old picture
                old_user = conn.execute('SELECT profile_picture FROM users WHERE id = ?', (user_id,)).fetchone()
                if old_user and old_user['profile_picture']:
                    try:
                        old_path = old_user['profile_picture'].replace('/static/', '')
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except:
                        pass
        
        if profile_picture:
            conn.execute('UPDATE users SET full_name = ?, email = ?, profile_picture = ? WHERE id = ?',
                        (full_name, email, profile_picture, user_id))
            session['profile_picture'] = profile_picture
        else:
            conn.execute('UPDATE users SET full_name = ?, email = ? WHERE id = ?',
                        (full_name, email, user_id))
        
        session['full_name'] = full_name
        conn.commit()
        conn.close()
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return render_template('profile.html', user=user)

# ==================== ANALYTICS ROUTES ====================

@app.route('/analytics')
@login_required
def analytics():
    """Analytics and Reporting Dashboard"""
    role = session.get('role')
    if role not in ['admin', 'lecturer', 'student', 'parent']:
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    
    # Basic stats
    total_students = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0]
    total_courses = conn.execute('SELECT COUNT(*) FROM courses').fetchone()[0]
    total_quizzes = conn.execute('SELECT COUNT(*) FROM quiz_results').fetchone()[0]
    
    # Average quiz score
    avg_result = conn.execute('''
        SELECT AVG(CAST(score AS FLOAT) / total_questions * 100) as avg_score 
        FROM quiz_results
    ''').fetchone()
    avg_score = avg_result['avg_score'] if avg_result and avg_result['avg_score'] else 0
    
    # Course statistics
    course_stats = conn.execute('''
        SELECT 
            c.id, c.title,
            (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id AND status = 'approved') as enrolled_count,
            (SELECT AVG(CAST(qr.score AS FLOAT) / qr.total_questions * 100) 
             FROM quiz_results qr 
             JOIN quizzes q ON qr.quiz_id = q.id 
             WHERE q.course_id = c.id) as avg_score
        FROM courses c
        ORDER BY enrolled_count DESC
        LIMIT 10
    ''').fetchall()
    
    # Quiz performance trends
    quiz_trends = conn.execute('''
        SELECT 
            q.id, q.title,
            COUNT(qr.id) as attempts,
            AVG(CAST(qr.score AS FLOAT) / qr.total_questions * 100) as avg_score,
            (SELECT COUNT(*) FROM quiz_results qr2 
             WHERE qr2.quiz_id = q.id 
             AND CAST(qr2.score AS FLOAT) / qr2.total_questions >= 0.7) * 100.0 / COUNT(qr.id) as pass_rate
        FROM quizzes q
        LEFT JOIN quiz_results qr ON q.id = qr.quiz_id
        GROUP BY q.id
        HAVING attempts > 0
        ORDER BY attempts DESC
        LIMIT 10
    ''').fetchall()
    
    # Top performing students
    top_students = conn.execute('''
        SELECT u.id, u.username, u.full_name,
               AVG(CAST(qr.score AS FLOAT) / qr.total_questions * 100) as avg_score,
               COUNT(qr.id) as quiz_count
        FROM users u
        JOIN quiz_results qr ON u.id = qr.student_id
        WHERE u.role = 'student'
        GROUP BY u.id
        ORDER BY avg_score DESC
        LIMIT 10
    ''').fetchall()
    
    # At-risk students (avg score < 50%)
    at_risk_students = conn.execute('''
        SELECT u.id, u.username, u.full_name,
               AVG(CAST(qr.score AS FLOAT) / qr.total_questions * 100) as avg_score
        FROM users u
        JOIN quiz_results qr ON u.id = qr.student_id
        WHERE u.role = 'student'
        GROUP BY u.id
        HAVING avg_score < 50
        ORDER BY avg_score ASC
        LIMIT 10
    ''').fetchall()
    
    # Add risk level to at-risk students
    at_risk_list = []
    for student in at_risk_students:
        if student['avg_score'] < 30:
            risk_level = 'Critical'
        elif student['avg_score'] < 40:
            risk_level = 'High'
        else:
            risk_level = 'Medium'
        at_risk_list.append({
            'id': student['id'],
            'username': student['username'],
            'full_name': student['full_name'],
            'avg_score': student['avg_score'],
            'risk_level': risk_level
        })
    
    # Monthly enrollment trends (last 6 months)
    enrollment_trends = conn.execute('''
        SELECT 
            strftime('%Y-%m', enrolled_at) as month,
            COUNT(*) as enrollments,
            (SELECT COUNT(*) FROM users u WHERE strftime('%Y-%m', u.created_at) = month AND u.role = 'student') as new_students,
            0 as completions
        FROM enrollments
        WHERE enrolled_at > datetime('now', '-6 months')
        GROUP BY month
        ORDER BY month DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template('analytics.html',
                         total_students=total_students,
                         total_courses=total_courses,
                         total_quizzes=total_quizzes,
                         avg_score=avg_score,
                         course_stats=course_stats,
                         quiz_trends=quiz_trends,
                         top_students=top_students,
                         at_risk_students=at_risk_list,
                         enrollment_trends=enrollment_trends)

@app.route('/export-analytics')
@login_required
def export_analytics():
    """Export analytics data as CSV"""
    import csv
    import io
    from flask import make_response
    
    export_type = request.args.get('type', 'courses')
    conn = get_db_connection()
    
    if export_type == 'courses':
        data = conn.execute('''
            SELECT c.title, c.description,
                   (SELECT COUNT(*) FROM enrollments WHERE course_id = c.id AND status = 'approved') as enrolled,
                   (SELECT AVG(CAST(qr.score AS FLOAT) / qr.total_questions * 100) 
                    FROM quiz_results qr JOIN quizzes q ON qr.quiz_id = q.id WHERE q.course_id = c.id) as avg_score
            FROM courses c
        ''').fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Course', 'Description', 'Enrolled Students', 'Average Score'])
        for row in data:
            writer.writerow([row['title'], row['description'] or '', row['enrolled'], f"{row['avg_score']:.1f}%" if row['avg_score'] else 'N/A'])
    
    elif export_type == 'quizzes':
        data = conn.execute('''
            SELECT q.title, COUNT(qr.id) as attempts,
                   AVG(CAST(qr.score AS FLOAT) / qr.total_questions * 100) as avg_score
            FROM quizzes q
            LEFT JOIN quiz_results qr ON q.id = qr.quiz_id
            GROUP BY q.id
        ''').fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Quiz Title', 'Attempts', 'Average Score'])
        for row in data:
            writer.writerow([row['title'], row['attempts'], f"{row['avg_score']:.1f}%" if row['avg_score'] else 'N/A'])
    
    elif export_type == 'enrollments':
        data = conn.execute('''
            SELECT strftime('%Y-%m', enrolled_at) as month, COUNT(*) as enrollments
            FROM enrollments
            GROUP BY month
            ORDER BY month DESC
            LIMIT 12
        ''').fetchall()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Month', 'Enrollments'])
        for row in data:
            writer.writerow([row['month'], row['enrollments']])
    
    else:
        conn.close()
        return redirect(url_for('analytics'))
    
    conn.close()
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={export_type}_export.csv'
    return response

# ==================== ADMIN ROUTES ====================

@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_create_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'lecturer')
        
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('admin_user_form.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('admin_user_form.html')
        
        password_hash = hash_password(password)
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, full_name, role, is_verified)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (username, email, password_hash, full_name, role))
            conn.commit()
            flash(f'{role.title()} created successfully!', 'success')
            return redirect(url_for('admin_users'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'danger')
        finally:
            conn.close()
    
    return render_template('admin_user_form.html')

@app.route('/admin/users/<int:user_id>/delete')
@login_required
@role_required('admin')
def admin_delete_user(user_id):
    if user_id == session['user_id']:
        flash('You cannot delete yourself!', 'danger')
        return redirect(url_for('admin_users'))
    
    conn = get_db_connection()
    
    # Delete related data
    conn.execute('DELETE FROM messages WHERE sender_id = ? OR recipient_id = ?', (user_id, user_id))
    conn.execute('DELETE FROM notifications WHERE user_id = ?', (user_id,))
    conn.execute('DELETE FROM enrollments WHERE student_id = ?', (user_id,))
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    flash('User deleted successfully!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/edit-role', methods=['POST'])
@login_required
@role_required('admin')
def admin_edit_role(user_id):
    new_role = request.form.get('role')
    if new_role not in ['student', 'lecturer', 'admin', 'parent']:
        flash('Invalid role!', 'danger')
        return redirect(url_for('admin_users'))
    
    conn = get_db_connection()
    conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
    conn.commit()
    conn.close()
    
    flash('User role updated!', 'success')
    return redirect(url_for('admin_users'))

# ==================== MODULE ROUTES ====================

@app.route('/admin/modules')
@login_required
@role_required('admin')
def admin_modules():
    conn = get_db_connection()
    modules = conn.execute('''
        SELECT m.*, c.title as course_title, u.full_name as creator_name
        FROM modules m
        JOIN courses c ON m.course_id = c.id
        LEFT JOIN users u ON m.created_by = u.id
        ORDER BY m.created_at DESC
    ''').fetchall()
    courses = conn.execute('SELECT * FROM courses WHERE is_published = 1').fetchall()
    conn.close()
    return render_template('admin_modules.html', modules=modules, courses=courses)

@app.route('/admin/modules/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_create_module():
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        title = request.form.get('title')
        description = request.form.get('description')
        code = request.form.get('code')
        chapter_number = request.form.get('chapter_number')
        year = request.form.get('year')
        semester = request.form.get('semester')
        prerequisites = request.form.get('prerequisites')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO modules (course_id, title, description, code, chapter_number, year, semester, prerequisites, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (course_id, title, description, code, chapter_number, year, semester, prerequisites, session['user_id']))
        conn.commit()
        conn.close()
        flash('Module created successfully!', 'success')
        return redirect(url_for('admin_modules'))
    
    conn = get_db_connection()
    courses = conn.execute('SELECT * FROM courses WHERE is_published = 1').fetchall()
    conn.close()
    return render_template('admin_module_form.html', courses=courses)

@app.route('/admin/modules/<int:module_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_module(module_id):
    conn = get_db_connection()
    module = conn.execute('SELECT * FROM modules WHERE id = ?', (module_id,)).fetchone()
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        code = request.form.get('code')
        chapter_number = request.form.get('chapter_number')
        year = request.form.get('year')
        semester = request.form.get('semester')
        prerequisites = request.form.get('prerequisites')
        is_active = 1 if request.form.get('is_active') else 0
        
        conn.execute('''
            UPDATE modules SET title = ?, description = ?, code = ?, 
            chapter_number = ?, year = ?, semester = ?, prerequisites = ?, is_active = ? WHERE id = ?
        ''', (title, description, code, chapter_number, year, semester, prerequisites, is_active, module_id))
        conn.commit()
        conn.close()
        flash('Module updated successfully!', 'success')
        return redirect(url_for('admin_modules'))
    
    courses = conn.execute('SELECT * FROM courses WHERE is_published = 1').fetchall()
    conn.close()
    return render_template('admin_module_form.html', module=module, courses=courses)

@app.route('/admin/modules/<int:module_id>/delete')
@login_required
@role_required('admin')
def admin_delete_module(module_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM modules WHERE id = ?', (module_id,))
    conn.commit()
    conn.close()
    flash('Module deleted successfully!', 'success')
    return redirect(url_for('admin_modules'))

# Lecturer modules list
@app.route('/lecturer/modules')
@login_required
@role_required('lecturer')
def lecturer_modules():
    conn = get_db_connection()
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Please login first.', 'danger')
        return redirect(url_for('login'))
    
    try:
        # Get all modules assigned to this lecturer
        my_modules = conn.execute('''
            SELECT m.id, m.title, m.description, m.chapter_number, m.code, m.course_id, m.is_active,
                   c.title as course_title,
                   (SELECT COUNT(*) FROM module_enrollments WHERE module_id = m.id AND status = 'approved') as student_count,
                   (SELECT COUNT(*) FROM module_enrollments WHERE module_id = m.id AND status = 'pending') as pending_count
            FROM modules m
            JOIN module_lecturers ml ON m.id = ml.module_id
            JOIN courses c ON m.course_id = c.id
            WHERE ml.lecturer_id = ? AND m.is_active = 1
            ORDER BY c.title, m.chapter_number
        ''', (user_id,)).fetchall()
    except Exception as e:
        flash(f'Error loading modules: {str(e)}', 'danger')
        my_modules = []
    
    conn.close()
    return render_template('lecturer_module_list.html', my_modules=my_modules)

# Lecturer assignments list
@app.route('/lecturer/assignments')
@login_required
@role_required('lecturer')
def lecturer_assignments():
    conn = get_db_connection()
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Please login first.', 'danger')
        conn.close()
        return redirect(url_for('login'))
    
    try:
        # Get all assignments from modules assigned to this lecturer
        assignments = conn.execute('''
            SELECT a.*, m.title as module_title, c.title as course_title
            FROM assignments a
            JOIN modules m ON a.module_id = m.id
            JOIN courses c ON m.course_id = c.id
            JOIN module_lecturers ml ON m.id = ml.module_id
            WHERE ml.lecturer_id = ?
            ORDER BY a.due_date DESC, a.created_at DESC
        ''', (user_id,)).fetchall()
    except Exception as e:
        flash(f'Error loading assignments: {str(e)}', 'danger')
        assignments = []
    
    conn.close()
    return render_template('lecturer_assignments.html', assignments=assignments)

# Lecturer quizzes list
@app.route('/lecturer/quizzes')
@login_required
@role_required('lecturer')
def lecturer_quizzes():
    conn = get_db_connection()
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Please login first.', 'danger')
        conn.close()
        return redirect(url_for('login'))
    
    try:
        # Get all quizzes created by this lecturer
        quizzes = conn.execute('''
            SELECT q.*, m.title as module_title, c.title as course_title
            FROM quizzes q
            LEFT JOIN modules m ON q.module_id = m.id
            LEFT JOIN courses c ON q.course_id = c.id
            WHERE q.created_by = ?
            ORDER BY q.created_at DESC
        ''', (user_id,)).fetchall()
    except Exception as e:
        flash(f'Error loading quizzes: {str(e)}', 'danger')
        quizzes = []
    
    conn.close()
    return render_template('lecturer_quizzes.html', quizzes=quizzes)

# Lecturer module requests
@app.route('/lecturer/module-requests')
@login_required
@role_required('lecturer')
def lecturer_module_requests():
    conn = get_db_connection()
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Please login first.', 'danger')
        conn.close()
        return redirect(url_for('login'))
    
    try:
        # Get available modules not yet assigned to this lecturer
        available_modules = conn.execute('''
            SELECT m.id, m.title, m.description, m.chapter_number, m.code, m.course_id, m.is_active,
                   c.title as course_title
            FROM modules m
            JOIN courses c ON m.course_id = c.id
            WHERE m.id NOT IN (SELECT module_id FROM module_lecturers WHERE lecturer_id = ?)
            AND m.is_active = 1
        ''', (user_id,)).fetchall()
        
        # Log for debugging - check for None descriptions
        for mod in available_modules:
            if mod['description'] is None:
                print(f"DEBUG: Module ID {mod['id']} has NULL description")
                
    except Exception as e:
        flash(f'Error loading available modules: {str(e)}', 'danger')
        available_modules = []
    
    try:
        # Get my pending requests
        my_requests = conn.execute('''
            SELECT mr.id, mr.module_id, mr.lecturer_id, mr.status, mr.request_message, mr.created_at,
                   m.title as module_title, c.title as course_title
            FROM module_requests mr
            JOIN modules m ON mr.module_id = m.id
            JOIN courses c ON m.course_id = c.id
            WHERE mr.lecturer_id = ?
            ORDER BY mr.created_at DESC
        ''', (user_id,)).fetchall()
    except Exception as e:
        flash(f'Error loading requests: {str(e)}', 'danger')
        my_requests = []
    
    try:
        # Get my approved modules
        my_modules = conn.execute('''
            SELECT m.id, m.title, m.description, m.chapter_number, m.code, m.course_id, m.is_active,
                   c.title as course_title,
                   (SELECT COUNT(*) FROM module_enrollments WHERE module_id = m.id AND status = 'approved') as student_count
            FROM modules m
            JOIN module_lecturers ml ON m.id = ml.module_id
            JOIN courses c ON m.course_id = c.id
            WHERE ml.lecturer_id = ?
        ''', (user_id,)).fetchall()
    except Exception as e:
        flash(f'Error loading my modules: {str(e)}', 'danger')
        my_modules = []
    
    conn.close()
    return render_template('lecturer_module_requests.html', 
                           available_modules=available_modules,
                           my_requests=my_requests,
                           my_modules=my_modules)

@app.route('/lecturer/module-requests/request/<int:module_id>', methods=['POST'])
@login_required
@role_required('lecturer')
def lecturer_request_module(module_id):
    message = request.form.get('message', '')
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Please login first.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Check if module already has 3 lecturers
    lecturer_result = conn.execute(
        'SELECT COUNT(*) FROM module_lecturers WHERE module_id = ?', 
        (module_id,)
    ).fetchone()
    
    lecturer_count = lecturer_result[0] if lecturer_result else 0
    
    if lecturer_count >= 3:
        flash('This module already has the maximum number of lecturers (3).', 'danger')
        conn.close()
        return redirect(url_for('lecturer_module_requests'))
    
    # Check for existing request
    existing = conn.execute('''
        SELECT * FROM module_requests 
        WHERE module_id = ? AND lecturer_id = ? AND status = 'pending'
    ''', (module_id, user_id)).fetchone()
    
    if existing:
        flash('You already have a pending request for this module.', 'warning')
        conn.close()
        return redirect(url_for('lecturer_module_requests'))
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO module_requests (module_id, lecturer_id, request_message)
        VALUES (?, ?, ?)
    ''', (module_id, user_id, message))
    conn.commit()
    conn.close()
    
    flash('Module request submitted! Waiting for admin approval.', 'success')
    return redirect(url_for('lecturer_module_requests'))

# Admin module request management
@app.route('/admin/module-requests')
@login_required
@role_required('admin')
def admin_module_requests():
    conn = get_db_connection()
    pending_requests = conn.execute('''
        SELECT mr.*, m.title as module_title, c.title as course_title, 
               u.full_name as lecturer_name, u.email as lecturer_email
        FROM module_requests mr
        JOIN modules m ON mr.module_id = m.id
        JOIN courses c ON m.course_id = c.id
        JOIN users u ON mr.lecturer_id = u.id
        WHERE mr.status = 'pending'
        ORDER BY mr.created_at ASC
    ''').fetchall()
    
    # Get module lecturer counts
    module_counts = conn.execute('''
        SELECT module_id, COUNT(*) as count FROM module_lecturers GROUP BY module_id
    ''').fetchall()
    counts_dict = {m['module_id']: m['count'] for m in module_counts}
    
    conn.close()
    return render_template('admin_module_requests.html', 
                           pending_requests=pending_requests,
                           module_counts=counts_dict)

@app.route('/admin/module-requests/<int:request_id>/approve')
@login_required
@role_required('admin')
def admin_approve_module_request(request_id):
    conn = get_db_connection()
    request = conn.execute('SELECT * FROM module_requests WHERE id = ?', (request_id,)).fetchone()
    
    if not request:
        flash('Request not found.', 'danger')
        return redirect(url_for('admin_module_requests'))
    
    # Check if module already has 3 lecturers
    lecturer_count = conn.execute(
        'SELECT COUNT(*) FROM module_lecturers WHERE module_id = ?', 
        (request['module_id'],)
    ).fetchone()[0]
    
    if lecturer_count >= 3:
        conn.execute("UPDATE module_requests SET status = 'rejected' WHERE id = ?", (request_id,))
        conn.commit()
        conn.close()
        flash('Module already has maximum lecturers. Request rejected.', 'warning')
        return redirect(url_for('admin_module_requests'))
    
    # Approve and assign lecturer
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO module_lecturers (module_id, lecturer_id)
        VALUES (?, ?)
    ''', (request['module_id'], request['lecturer_id']))
    
    conn.execute('''
        UPDATE module_requests SET status = 'approved', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (session['user_id'], request_id))
    
    # Notify lecturer
    conn.execute('''
        INSERT INTO notifications (user_id, title, message_text, link)
        VALUES (?, ?, ?, ?)
    ''', (request['lecturer_id'], 'Module Request Approved',
          'Your request to teach a module has been approved!',
          url_for('lecturer_module_requests', _external=True)))
    
    conn.commit()
    conn.close()
    
    flash('Module request approved!', 'success')
    return redirect(url_for('admin_module_requests'))

@app.route('/admin/module-requests/<int:request_id>/reject')
@login_required
@role_required('admin')
def admin_reject_module_request(request_id):
    conn = get_db_connection()
    request = conn.execute('SELECT * FROM module_requests WHERE id = ?', (request_id,)).fetchone()
    
    conn.execute('''
        UPDATE module_requests SET status = 'rejected', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (session['user_id'], request_id))
    
    # Notify lecturer
    conn.execute('''
        INSERT INTO notifications (user_id, title, message_text, link)
        VALUES (?, ?, ?, ?)
    ''', (request['lecturer_id'], 'Module Request Rejected',
          'Your request to teach a module has been rejected.',
          url_for('lecturer_module_requests', _external=True)))
    
    conn.commit()
    conn.close()
    
    flash('Module request rejected.', 'info')
    return redirect(url_for('admin_module_requests'))

# Student module enrollment
@app.route('/student/modules')
@login_required
@role_required('student')
def student_modules():
    conn = get_db_connection()
    
    # Get courses the student is enrolled in
    enrolled_courses = conn.execute('''
        SELECT c.* FROM courses c
        JOIN enrollments e ON c.id = e.course_id
        WHERE e.student_id = ? AND e.status = 'approved'
    ''', (session['user_id'],)).fetchall()
    
    # Get modules from those courses
    course_ids = [c['id'] for c in enrolled_courses]
    modules = []
    if course_ids:
        placeholders = ','.join('?' * len(course_ids))
        modules = conn.execute(f'''
            SELECT m.*, c.title as course_title,
                   (SELECT status FROM module_enrollments 
                    WHERE student_id = ? AND module_id = m.id) as enrollment_status,
                   (SELECT COUNT(*) FROM module_enrollments WHERE module_id = m.id AND status = 'approved') as student_count
            FROM modules m
            JOIN courses c ON m.course_id = c.id
            WHERE m.course_id IN ({placeholders}) AND m.is_active = 1
        ''', (session['user_id'],) + tuple(course_ids)).fetchall()
    
    conn.close()
    return render_template('student_modules.html', modules=modules, courses=enrolled_courses)

# Student Smart Schedule - Automatic weekly study timetable
@app.route('/student/schedule')
@login_required
@role_required('student')
def student_schedule():
    conn = get_db_connection()
    user_id = session['user_id']
    
    # Get existing schedule
    schedule = conn.execute('''
        SELECT ss.*, m.title as module_title, c.title as course_title
        FROM study_schedules ss
        LEFT JOIN modules m ON ss.module_id = m.id
        LEFT JOIN courses c ON m.course_id = c.id
        WHERE ss.student_id = ?
        ORDER BY 
            CASE ss.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END,
            ss.time_slot
    ''', (user_id,)).fetchall()
    
    # Get enrolled modules for generating schedule
    enrolled_modules = conn.execute('''
        SELECT m.*, c.title as course_title
        FROM module_enrollments me
        JOIN modules m ON me.module_id = m.id
        JOIN courses c ON m.course_id = c.id
        WHERE me.student_id = ? AND me.status = 'approved'
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    # Generate schedule if not exists
    if not schedule and enrolled_modules:
        return generate_and_show_schedule(enrolled_modules)
    
    return render_template('student_schedule.html', schedule=schedule, modules=enrolled_modules)

def generate_and_show_schedule(enrolled_modules):
    """Generate automatic weekly study schedule for student"""
    conn = get_db_connection()
    user_id = session['user_id']
    
    # Clear existing schedule
    conn.execute('DELETE FROM study_schedules WHERE student_id = ?', (user_id,))
    
    # Days of the week
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Time slots - morning, afternoon, evening
    time_slots = {
        'Morning': '09:00 AM',
        'Afternoon': '02:00 PM',
        'Evening': '07:00 PM'
    }
    
    # Activity types for variety
    activities = ['study', 'review', 'practice', 'assignment']
    
    # Generate schedule for each module
    module_list = list(enrolled_modules)
    num_modules = len(module_list)
    
    schedule_entries = []
    slot_index = 0
    
    for i, module in enumerate(module_list):
        # Distribute modules across the week
        day_idx = i % 5  # Focus on weekdays primarily
        day = days[day_idx]
        
        # Alternate time slots
        time_keys = list(time_slots.keys())
        time_key = time_keys[slot_index % len(time_keys)]
        time_display = time_slots[time_key]
        
        activity = activities[i % len(activities)]
        
        # Create study entry for this module
        schedule_entries.append({
            'day_of_week': day,
            'time_slot': time_display,
            'activity_type': activity,
            'module_id': module['id'],
            'title': f"{activity.title()} {module['title']}",
            'description': f"{activity.title()} - {module['course_title']}"
        })
        
        slot_index += 1
    
    # Add weekend revision sessions
    if module_list:
        # Saturday morning - catch up/revision
        schedule_entries.append({
            'day_of_week': 'Saturday',
            'time_slot': '10:00 AM',
            'activity_type': 'revision',
            'module_id': module_list[0]['id'] if module_list else None,
            'title': 'Weekend Revision',
            'description': 'Review the week\'s material'
        })
        
        # Sunday - catch up
        schedule_entries.append({
            'day_of_week': 'Sunday',
            'time_slot': '11:00 AM',
            'activity_type': 'revision',
            'module_id': module_list[-1]['id'] if module_list else None,
            'title': 'Weekend Catch-up',
            'description': 'Complete any pending tasks'
        })
    
    # Insert all schedule entries
    for entry in schedule_entries:
        conn.execute('''
            INSERT INTO study_schedules (student_id, day_of_week, time_slot, activity_type, module_id, title, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, entry['day_of_week'], entry['time_slot'], entry['activity_type'], 
              entry['module_id'], entry['title'], entry['description']))
    
    conn.commit()
    
    # Fetch the newly created schedule
    schedule = conn.execute('''
        SELECT ss.*, m.title as module_title, c.title as course_title
        FROM study_schedules ss
        LEFT JOIN modules m ON ss.module_id = m.id
        LEFT JOIN courses c ON m.course_id = c.id
        WHERE ss.student_id = ?
        ORDER BY 
            CASE ss.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END,
            ss.time_slot
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    return render_template('student_schedule.html', schedule=schedule, modules=enrolled_modules)

@app.route('/student/schedule/regenerate')
@login_required
@role_required('student')
def regenerate_schedule():
    """Regenerate the study schedule"""
    conn = get_db_connection()
    user_id = session['user_id']
    
    # Get enrolled modules
    enrolled_modules = conn.execute('''
        SELECT m.*, c.title as course_title
        FROM module_enrollments me
        JOIN modules m ON me.module_id = m.id
        JOIN courses c ON m.course_id = c.id
        WHERE me.student_id = ? AND me.status = 'approved'
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    if not enrolled_modules:
        flash('You need to enroll in modules first to generate a schedule!', 'warning')
        return redirect(url_for('student_modules'))
    
    return generate_and_show_schedule(enrolled_modules)

@app.route('/student/schedule/complete/<int:schedule_id>')
@login_required
@role_required('student')
def complete_schedule_item(schedule_id):
    """Mark a schedule item as completed"""
    conn = get_db_connection()
    user_id = session['user_id']
    
    # Verify ownership
    item = conn.execute('SELECT * FROM study_schedules WHERE id = ? AND student_id = ?', 
                        (schedule_id, user_id)).fetchone()
    
    if item:
        conn.execute('UPDATE study_schedules SET is_completed = 1 WHERE id = ?', (schedule_id,))
        conn.commit()
        flash('Task marked as completed!', 'success')
    
    conn.close()
    return redirect(url_for('student_schedule'))

@app.route('/student/modules/<int:module_id>/request')
@login_required
@role_required('student')
def student_request_module(module_id):
    conn = get_db_connection()
    
    # Check if student is enrolled in the course
    module = conn.execute('''
        SELECT m.*, c.id as course_id FROM modules m
        JOIN courses c ON m.course_id = c.id
        WHERE m.id = ?
    ''', (module_id,)).fetchone()
    
    enrollment = conn.execute('''
        SELECT * FROM enrollments 
        WHERE student_id = ? AND course_id = ? AND status = 'approved'
    ''', (session['user_id'], module['course_id'])).fetchone()
    
    if not enrollment:
        flash('You must be enrolled in the course first.', 'warning')
        conn.close()
        return redirect(url_for('student_modules'))
    
    # Check for existing request
    existing = conn.execute('''
        SELECT * FROM module_enrollments 
        WHERE student_id = ? AND module_id = ? AND status = 'pending'
    ''', (session['user_id'], module_id)).fetchone()
    
    if existing:
        flash('You already have a pending request for this module.', 'warning')
        conn.close()
        return redirect(url_for('student_modules'))
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO module_enrollments (student_id, module_id)
        VALUES (?, ?)
    ''', (session['user_id'], module_id))
    
    # Notify assigned lecturers
    lecturers = conn.execute('''
        SELECT u.id FROM users u
        JOIN module_lecturers ml ON u.id = ml.lecturer_id
        WHERE ml.module_id = ?
    ''', (module_id,)).fetchall()
    
    for lecturer in lecturers:
        conn.execute('''
            INSERT INTO notifications (user_id, title, message_text, link)
            VALUES (?, ?, ?, ?)
        ''', (lecturer['id'], 'New Module Enrollment Request',
              f'A student has requested to join your module.',
              url_for('lecturer_module_students', module_id=module_id, _external=True)))
    
    conn.commit()
    conn.close()
    
    flash('Module enrollment request sent!', 'success')
    return redirect(url_for('student_modules'))

# Lecturer module student management
@app.route('/lecturer/modules/<int:module_id>/students')
@login_required
@role_required('lecturer')
def lecturer_module_students(module_id):
    conn = get_db_connection()
    
    # Verify lecturer is assigned to this module
    assignment = conn.execute('''
        SELECT * FROM module_lecturers 
        WHERE module_id = ? AND lecturer_id = ?
    ''', (module_id, session.get('user_id'))).fetchone()
    
    if not assignment:
        flash('You are not assigned to this module.', 'danger')
        conn.close()
        return redirect(url_for('lecturer_module_requests'))
    
    module = conn.execute('SELECT * FROM modules WHERE id = ?', (module_id,)).fetchone()
    
    # Get pending requests
    pending_students = conn.execute('''
        SELECT me.*, u.full_name, u.email
        FROM module_enrollments me
        JOIN users u ON me.student_id = u.id
        WHERE me.module_id = ? AND me.status = 'pending'
    ''', (module_id,)).fetchall()
    
    # Get approved students (without the quiz average subquery that might fail)
    approved_students = conn.execute('''
        SELECT me.*, u.full_name, u.email
        FROM module_enrollments me
        JOIN users u ON me.student_id = u.id
        WHERE me.module_id = ? AND me.status = 'approved'
    ''', (module_id,)).fetchall()
    
    # Get at-risk students (simple check based on enrollments)
    at_risk = []
    
    conn.close()
    return render_template('lecturer_module_students.html',
                           module=module,
                           pending_students=pending_students,
                           approved_students=approved_students,
                           at_risk=at_risk)

@app.route('/lecturer/modules/<int:module_id>/students/<int:enrollment_id>/approve')
@login_required
@role_required('lecturer')
def lecturer_approve_module_student(module_id, enrollment_id):
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Please login first.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Verify lecturer is assigned
    assignment = conn.execute('''
        SELECT * FROM module_lecturers 
        WHERE module_id = ? AND lecturer_id = ?
    ''', (module_id, user_id)).fetchone()
    
    if not assignment:
        flash('You are not assigned to this module.', 'danger')
        conn.close()
        return redirect(url_for('lecturer_module_requests'))
    
    conn.execute("UPDATE module_enrollments SET status = 'approved' WHERE id = ?", (enrollment_id,))
    
    # Notify student
    enrollment = conn.execute('SELECT student_id FROM module_enrollments WHERE id = ?', (enrollment_id,)).fetchone()
    module = conn.execute('SELECT title FROM modules WHERE id = ?', (module_id,)).fetchone()
    
    if enrollment and module:
        conn.execute('''
            INSERT INTO notifications (user_id, title, message_text, link)
            VALUES (?, ?, ?, ?)
        ''', (enrollment['student_id'], 'Module Enrollment Approved',
              f'Your request to join module "{module["title"]}" has been approved!',
              url_for('student_modules', _external=True)))
    
    conn.commit()
    conn.close()
    
    flash('Student approved!', 'success')
    return redirect(url_for('lecturer_module_students', module_id=module_id))

@app.route('/lecturer/modules/<int:module_id>/students/<int:enrollment_id>/reject')
@login_required
@role_required('lecturer')
def lecturer_reject_module_student(module_id, enrollment_id):
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Please login first.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Verify lecturer is assigned
    assignment = conn.execute('''
        SELECT * FROM module_lecturers 
        WHERE module_id = ? AND lecturer_id = ?
    ''', (module_id, user_id)).fetchone()
    
    if not assignment:
        flash('You are not assigned to this module.', 'danger')
        conn.close()
        return redirect(url_for('lecturer_module_requests'))
    
    conn.execute("UPDATE module_enrollments SET status = 'rejected' WHERE id = ?", (enrollment_id,))
    
    # Notify student
    enrollment = conn.execute('SELECT student_id FROM module_enrollments WHERE id = ?', (enrollment_id,)).fetchone()
    module = conn.execute('SELECT title FROM modules WHERE id = ?', (module_id,)).fetchone()
    
    if enrollment and module:
        conn.execute('''
            INSERT INTO notifications (user_id, title, message_text, link)
            VALUES (?, ?, ?, ?)
        ''', (enrollment['student_id'], 'Module Enrollment Rejected',
              f'Your request to join module "{module["title"]}" was not approved.',
              url_for('student_modules', _external=True)))
    
    conn.commit()
    conn.close()
    
    flash('Student rejected.', 'info')
    return redirect(url_for('lecturer_module_students', module_id=module_id))

# Module materials (lecturer upload)
@app.route('/lecturer/modules/<int:module_id>/materials', methods=['GET', 'POST'])
@login_required
@role_required('lecturer')
def lecturer_module_materials(module_id):
    user_id = session.get('user_id')
    
    if not user_id:
        flash('Please login first.', 'danger')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Verify lecturer is assigned
    assignment = conn.execute('''
        SELECT * FROM module_lecturers 
        WHERE module_id = ? AND lecturer_id = ?
    ''', (module_id, user_id)).fetchone()
    
    if not assignment:
        flash('You are not assigned to this module.', 'danger')
        conn.close()
        return redirect(url_for('lecturer_module_requests'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        content_type = request.form.get('content_type')
        content_text = request.form.get('content_text')
        chapter_topic = request.form.get('chapter_topic')
        order_index = request.form.get('order_index', 0)
        
        file_path = None
        file = request.files.get('file')
        
        # Handle file upload
        if file and file.filename:
            # Get allowed extensions based on content type
            allowed_extensions = {
                'pdf': ['pdf'],
                'document': ['doc', 'docx', 'txt', 'rtf'],
                'video': ['mp4', 'webm', 'avi', 'mov', 'mkv'],
                'excel': ['xls', 'xlsx', 'csv'],
                'slide': ['ppt', 'pptx', 'pdf']
            }
            
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            
            # Check if extension is allowed for the content type
            allowed = allowed_extensions.get(content_type, [])
            if ext not in allowed:
                flash(f'Invalid file type. Allowed types for {content_type}: {', '.join(allowed)}', 'danger')
                conn.close()
                return redirect(url_for('lecturer_module_materials', module_id=module_id))
            
            # Generate unique filename
            filename = f"module_{module_id}_{int(datetime.now().timestamp())}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'module_materials', filename)
            file.save(filepath)
            file_path = f'uploads/module_materials/{filename}'
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO module_materials (module_id, title, description, content_type, content_text, file_path, chapter_topic, order_index, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (module_id, title, description, content_type, content_text, file_path, chapter_topic, order_index, user_id))
        conn.commit()
        flash('Material added successfully!', 'success')
        return redirect(url_for('lecturer_module_materials', module_id=module_id))
    
    module = conn.execute('SELECT * FROM modules WHERE id = ?', (module_id,)).fetchone()
    materials = conn.execute('''
        SELECT * FROM module_materials 
        WHERE module_id = ? ORDER BY order_index, created_at
    ''', (module_id,)).fetchall()
    
    conn.close()
    return render_template('lecturer_module_materials.html', module=module, materials=materials)

# Student module materials view
@app.route('/modules/<int:module_id>')
@login_required
def module_detail(module_id):
    """Module detail page - shows module with its content (materials, quizzes)"""
    conn = get_db_connection()
    role = session['role']
    user_id = session['user_id']
    
    # Get module info with course
    module = conn.execute('''
        SELECT m.*, c.title as course_title, c.id as course_id, c.teacher_id, u.full_name as teacher_name
        FROM modules m
        JOIN courses c ON m.course_id = c.id
        JOIN users u ON c.teacher_id = u.id
        WHERE m.id = ?
    ''', (module_id,)).fetchone()
    
    if not module:
        conn.close()
        flash('Module not found!', 'danger')
        return redirect(url_for('courses'))
    
    # Check access
    course_enrollment = conn.execute('''
        SELECT * FROM enrollments 
        WHERE student_id = ? AND course_id = ? AND status = 'approved'
    ''', (user_id, module['course_id'])).fetchone()
    
    # Check if student is enrolled in this module
    module_enrollment = None
    if role == 'student':
        module_enrollment = conn.execute('''
            SELECT * FROM module_enrollments 
            WHERE student_id = ? AND module_id = ?
        ''', (user_id, module_id)).fetchone()
    
    # Check if lecturer is assigned to this module
    lecturer_assigned = False
    if role == 'lecturer':
        assignment = conn.execute('''
            SELECT * FROM module_lecturers 
            WHERE module_id = ? AND lecturer_id = ?
        ''', (module_id, user_id)).fetchone()
        lecturer_assigned = assignment is not None
    
    # Determine if user can access
    can_access = (role in ['admin'] or 
                  (role in ['teacher', 'lecturer'] and module['course_id'] == module['teacher_id']) or
                  (role == 'lecturer' and lecturer_assigned) or
                  (course_enrollment and module_enrollment and module_enrollment['status'] == 'approved'))
    
    # Get module materials
    materials = []
    if can_access:
        materials = conn.execute('''
            SELECT * FROM module_materials 
            WHERE module_id = ? ORDER BY order_index, created_at
        ''', (module_id,)).fetchall()
    
    # Get module assignments
    assignments = []
    if can_access:
        assignments = conn.execute('''
            SELECT * FROM assignments 
            WHERE module_id = ? ORDER BY due_date, created_at
        ''', (module_id,)).fetchall()
    
    # Get module quizzes
    quizzes = []
    if can_access:
        quizzes = conn.execute('''
            SELECT * FROM quizzes 
            WHERE module_id = ? ORDER BY created_at
        ''', (module_id,)).fetchall()
    
    # Get module students (for lecturer/admin)
    module_students = []
    if role in ['admin', 'teacher', 'lecturer'] or lecturer_assigned:
        module_students = conn.execute('''
            SELECT u.id, u.username, u.full_name, u.email, me.status, me.enrolled_at
            FROM module_enrollments me
            JOIN users u ON me.student_id = u.id
            WHERE me.module_id = ?
        ''', (module_id,)).fetchall()
    
    conn.close()
    
    return render_template('module_detail.html',
                         module=module,
                         course_enrollment=course_enrollment,
                         module_enrollment=module_enrollment,
                         materials=materials,
                         quizzes=quizzes,
                         assignments=assignments,
                         module_students=module_students,
                         can_access=can_access)

@app.route('/student/modules/<int:module_id>/materials')
@login_required
@role_required('student')
def student_module_materials(module_id):
    conn = get_db_connection()
    
    # Check enrollment
    enrollment = conn.execute('''
        SELECT * FROM module_enrollments 
        WHERE student_id = ? AND module_id = ? AND status = 'approved'
    ''', (session['user_id'], module_id)).fetchone()
    
    if not enrollment:
        flash('You are not enrolled in this module.', 'danger')
        conn.close()
        return redirect(url_for('student_modules'))
    
    module = conn.execute('''
        SELECT m.*, c.title as course_title
        FROM modules m
        JOIN courses c ON m.course_id = c.id
        WHERE m.id = ?
    ''', (module_id,)).fetchone()
    
    materials = conn.execute('''
        SELECT * FROM module_materials 
        WHERE module_id = ? ORDER BY order_index, created_at
    ''', (module_id,)).fetchall()
    
    conn.close()
    return render_template('student_module_materials.html', module=module, materials=materials)

# ==================== ASSIGNMENT ROUTES ====================

# Lecturer: Create assignment for a module
@app.route('/lecturer/modules/<int:module_id>/assignments/create', methods=['GET', 'POST'])
@login_required
@role_required('lecturer')
def create_assignment(module_id):
    conn = get_db_connection()
    
    # Check if lecturer has access to this module
    module = conn.execute('''
        SELECT m.*, c.id as course_id, c.teacher_id
        FROM modules m
        JOIN courses c ON m.course_id = c.id
        WHERE m.id = ?
    ''', (module_id,)).fetchone()
    
    if not module:
        flash('Module not found.', 'danger')
        conn.close()
        return redirect(url_for('lecturer_modules'))
    
    # Check permission - only the course owner or assigned lecturer can create
    lecturer_assigned = conn.execute('''
        SELECT id FROM module_lecturers
        WHERE module_id = ? AND lecturer_id = ?
    ''', (module_id, session['user_id'])).fetchone()
    
    if module['teacher_id'] != session['user_id'] and not lecturer_assigned:
        flash('You do not have permission to create assignments for this module.', 'danger')
        conn.close()
        return redirect(url_for('lecturer_modules'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        max_score = request.form.get('max_score', 100)
        
        # Handle file upload
        instruction_file = None
        if 'instruction_file' in request.files:
            file = request.files['instruction_file']
            if file and file.filename:
                # Create upload folder if not exists
                upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'assignments')
                os.makedirs(upload_folder, exist_ok=True)
                
                # Save file
                filename = f"assignment_{module_id}_{int(datetime.now().timestamp())}_{file.filename}"
                filepath = os.path.join(upload_folder, filename)
                file.save(filepath)
                instruction_file = f"uploads/assignments/{filename}"
        
        conn.execute('''
            INSERT INTO assignments (module_id, title, description, due_date, max_score, instruction_file)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (module_id, title, description, due_date, max_score, instruction_file))
        conn.commit()
        
        flash('Assignment created successfully!', 'success')
        conn.close()
        return redirect(url_for('module_detail', module_id=module_id))
    
    conn.close()
    return render_template('assignment_form.html', module=module)

# Lecturer: Create quiz for a module
@app.route('/lecturer/modules/<int:module_id>/quizzes/create', methods=['GET', 'POST'])
@login_required
@role_required('lecturer')
def create_quiz(module_id):
    conn = get_db_connection()
    
    # Check if lecturer has access to this module
    module = conn.execute('''
        SELECT m.*, c.id as course_id, c.teacher_id
        FROM modules m
        JOIN courses c ON m.course_id = c.id
        WHERE m.id = ?
    ''', (module_id,)).fetchone()
    
    if not module:
        flash('Module not found.', 'danger')
        conn.close()
        return redirect(url_for('lecturer_modules'))
    
    # Check permission - only the course owner or assigned lecturer can create
    lecturer_assigned = conn.execute('''
        SELECT id FROM module_lecturers
        WHERE module_id = ? AND lecturer_id = ?
    ''', (module_id, session['user_id'])).fetchone()
    
    if module['teacher_id'] != session['user_id'] and not lecturer_assigned:
        flash('You do not have permission to create quizzes for this module.', 'danger')
        conn.close()
        return redirect(url_for('lecturer_modules'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        
        conn.execute('''
            INSERT INTO quizzes (course_id, module_id, title, description, created_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (module['course_id'], module_id, title, description, session['user_id']))
        conn.commit()
        
        flash('Quiz created successfully!', 'success')
        conn.close()
        return redirect(url_for('lecturer_quizzes'))
    
    conn.close()
    return render_template('quiz_form.html', module=module)

# Lecturer: Manage quiz questions
@app.route('/lecturer/quizzes/<int:quiz_id>/questions', methods=['GET', 'POST'])
@login_required
@role_required('lecturer')
def manage_quiz_questions(quiz_id):
    conn = get_db_connection()
    
    # Get quiz
    quiz = conn.execute('SELECT * FROM quizzes WHERE id = ?', (quiz_id,)).fetchone()
    
    if not quiz:
        flash('Quiz not found.', 'danger')
        conn.close()
        return redirect(url_for('lecturer_quizzes'))
    
    # Check permission - only the creator can manage questions
    if quiz['created_by'] != session['user_id'] and session['role'] != 'admin':
        flash('You do not have permission to manage this quiz.', 'danger')
        conn.close()
        return redirect(url_for('lecturer_quizzes'))
    
    # Get existing questions
    questions = conn.execute('SELECT * FROM quiz_questions WHERE quiz_id = ?', (quiz_id,)).fetchall()
    
    if request.method == 'POST':
        question_text = request.form.get('question')
        question_type = request.form.get('question_type')
        option_a = request.form.get('option_a', '')
        option_b = request.form.get('option_b', '')
        option_c = request.form.get('option_c', '')
        option_d = request.form.get('option_d', '')
        
        # Handle True/False vs Multiple Choice
        if question_type == 'true_false':
            correct_answer = request.form.get('correct_answer_tf', 'True')
            option_a = 'True'
            option_b = 'False'
            option_c = ''
            option_d = ''
        else:
            correct_answer = request.form.get('correct_answer')
        
        conn.execute('''
            INSERT INTO quiz_questions (quiz_id, question, question_type, option_a, option_b, option_c, option_d, correct_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (quiz_id, question_text, question_type, option_a, option_b, option_c, option_d, correct_answer))
        conn.commit()
        
        flash('Question added successfully!', 'success')
        return redirect(url_for('manage_quiz_questions', quiz_id=quiz_id))
    
    conn.close()
    return render_template('quiz_questions.html', quiz=quiz, questions=questions)

# View assignment (both students and lecturers)
@app.route('/assignments/<int:assignment_id>')
@login_required
def view_assignment(assignment_id):
    conn = get_db_connection()
    role = session.get('role')
    user_id = session['user_id']
    
    # Get assignment with module info
    assignment = conn.execute('''
        SELECT a.*, m.title as module_title, m.id as module_id, 
               c.title as course_title, c.id as course_id, c.teacher_id
        FROM assignments a
        JOIN modules m ON a.module_id = m.id
        JOIN courses c ON m.course_id = c.id
        WHERE a.id = ?
    ''', (assignment_id,)).fetchone()
    
    if not assignment:
        flash('Assignment not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Check permissions
    can_access = False
    if role == 'admin':
        can_access = True
    elif role == 'lecturer':
        # Check if lecturer owns the course or is assigned to the module
        if assignment['teacher_id'] == user_id:
            can_access = True
        else:
            lecturer_assigned = conn.execute('''
                SELECT id FROM module_lecturers 
                WHERE module_id = ? AND lecturer_id = ?
            ''', (assignment['module_id'], user_id)).fetchone()
            if lecturer_assigned:
                can_access = True
    elif role == 'student':
        # Check if student is enrolled in the module
        enrollment = conn.execute('''
            SELECT id FROM module_enrollments 
            WHERE student_id = ? AND module_id = ? AND status = 'approved'
        ''', (user_id, assignment['module_id'])).fetchone()
        if enrollment:
            can_access = True
    
    if not can_access:
        flash('You do not have permission to view this assignment.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Get student's submission if exists
    submission = None
    if role == 'student':
        submission = conn.execute('''
            SELECT * FROM assignment_submissions 
            WHERE assignment_id = ? AND student_id = ?
        ''', (assignment_id, user_id)).fetchone()
    
    # Get all submissions for lecturer
    submissions = None
    if role == 'lecturer' or role == 'admin':
        submissions = conn.execute('''
            SELECT s.*, u.full_name, u.email
            FROM assignment_submissions s
            JOIN users u ON s.student_id = u.id
            WHERE s.assignment_id = ?
            ORDER BY s.submitted_at DESC
        ''', (assignment_id,)).fetchall()
    
    conn.close()
    return render_template('assignment_detail.html', assignment=assignment, submission=submission, submissions=submissions)

# Student: Submit assignment
@app.route('/assignments/<int:assignment_id>/submit', methods=['POST'])
@login_required
@role_required('student')
def submit_assignment(assignment_id):
    conn = get_db_connection()
    user_id = session['user_id']
    
    # Get assignment
    assignment = conn.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,)).fetchone()
    
    if not assignment:
        flash('Assignment not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Check if student is enrolled
    enrollment = conn.execute('''
        SELECT id FROM module_enrollments 
        WHERE student_id = ? AND module_id = ? AND status = 'approved'
    ''', (user_id, assignment['module_id'])).fetchone()
    
    if not enrollment:
        flash('You are not enrolled in this module.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Check if already submitted
    existing = conn.execute('''
        SELECT id FROM assignment_submissions 
        WHERE assignment_id = ? AND student_id = ?
    ''', (assignment_id, user_id)).fetchone()
    
    submission_text = request.form.get('submission_text')
    
    # Handle file upload
    file_path = None
    if 'submission_file' in request.files:
        file = request.files['submission_file']
        if file and file.filename:
            # Create upload folder if not exists
            upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'submissions')
            os.makedirs(upload_folder, exist_ok=True)
            
            # Save file
            filename = f"submission_{assignment_id}_{user_id}_{int(datetime.now().timestamp())}_{file.filename}"
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            file_path = f"uploads/submissions/{filename}"
    
    if existing:
        # Update existing submission
        conn.execute('''
            UPDATE assignment_submissions 
            SET submission_text = ?, file_path = ?, submitted_at = CURRENT_TIMESTAMP
            WHERE assignment_id = ? AND student_id = ?
        ''', (submission_text, file_path, assignment_id, user_id))
    else:
        # Create new submission
        conn.execute('''
            INSERT INTO assignment_submissions (assignment_id, student_id, submission_text, file_path)
            VALUES (?, ?, ?, ?)
        ''', (assignment_id, user_id, submission_text, file_path))
    
    conn.commit()
    flash('Assignment submitted successfully!', 'success')
    conn.close()
    return redirect(url_for('view_assignment', assignment_id=assignment_id))

# Lecturer: Grade submission
@app.route('/assignments/submissions/<int:submission_id>/grade', methods=['POST'])
@login_required
@role_required('lecturer')
def grade_submission(submission_id):
    conn = get_db_connection()
    
    # Get submission with assignment info
    submission = conn.execute('''
        SELECT s.*, a.max_score, a.module_id
        FROM assignment_submissions s
        JOIN assignments a ON s.assignment_id = a.id
        WHERE s.id = ?
    ''', (submission_id,)).fetchone()
    
    if not submission:
        flash('Submission not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    # Check permission
    module = conn.execute('''
        SELECT m.*, c.teacher_id
        FROM modules m
        JOIN courses c ON m.course_id = c.id
        WHERE m.id = ?
    ''', (submission['module_id'],)).fetchone()
    
    lecturer_assigned = conn.execute('''
        SELECT id FROM module_lecturers 
        WHERE module_id = ? AND lecturer_id = ?
    ''', (submission['module_id'], session['user_id'])).fetchone()
    
    if module['teacher_id'] != session['user_id'] and not lecturer_assigned:
        flash('You do not have permission to grade this submission.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    grade = request.form.get('grade')
    feedback = request.form.get('feedback')
    
    conn.execute('''
        UPDATE assignment_submissions 
        SET grade = ?, feedback = ?, graded_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (grade, feedback, submission_id))
    conn.commit()
    
    # Notify student
    conn.execute('''
        INSERT INTO notifications (user_id, title, message_text, link)
        VALUES (?, ?, ?, ?)
    ''', (submission['student_id'], 'Assignment Graded', 
          f'Your submission for assignment has been graded.', 
          f'/assignments/{submission['assignment_id']}'))
    conn.commit()
    
    flash('Grade saved successfully!', 'success')
    conn.close()
    return redirect(url_for('view_assignment', assignment_id=submission['assignment_id']))

# ==================== CAREER DEVELOPMENT ROUTES ====================

@app.route('/student/career')
@login_required
@role_required('student')
def student_career():
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[DEBUG] student_career called for user_id={session['user_id']}")
    
    conn = get_db_connection()
    
    # Get career profile
    profile = conn.execute('SELECT * FROM career_profiles WHERE student_id = ?', (session['user_id'],)).fetchone()
    logger.info(f"[DEBUG] Found profile: {profile is not None}")
    
    # Get CVs
    cvs = conn.execute('SELECT * FROM cvs WHERE student_id = ? ORDER BY is_primary DESC, created_at DESC', (session['user_id'],)).fetchall()
    logger.info(f"[DEBUG] Found {len(cvs)} CVs")
    
    # Get projects
    projects = conn.execute('SELECT * FROM projects WHERE student_id = ? ORDER BY created_at DESC', (session['user_id'],)).fetchall()
    logger.info(f"[DEBUG] Found {len(projects)} projects")
    
    # Get skills
    skills = conn.execute('SELECT * FROM skills WHERE student_id = ?', (session['user_id'],)).fetchall()
    logger.info(f"[DEBUG] Found {len(skills)} skills")
    
    # Get job recommendations
    jobs = conn.execute('SELECT * FROM job_recommendations WHERE student_id = ? ORDER BY relevance_score DESC LIMIT 10', (session['user_id'],)).fetchall()
    logger.info(f"[DEBUG] Found {len(jobs)} job recommendations")
    
    # Generate job recommendations if none exist
    if len(jobs) == 0:
        logger.info("[DEBUG] No job recommendations found, generating default recommendations")
        recommended_jobs = [
            {'job_title': 'Junior Software Developer', 'company': 'TechCorp', 'description': 'Entry-level developer position', 'job_type': 'Full-time', 'location': 'Remote', 'relevance_score': 0.92},
            {'job_title': 'Data Analyst Intern', 'company': 'DataDriven Inc', 'description': '数据分析实习岗位', 'job_type': 'Internship', 'location': 'Johannesburg', 'relevance_score': 0.88},
            {'job_title': 'Junior ML Engineer', 'company': 'AI Solutions', 'description': '机器学习工程师入门级', 'job_type': 'Full-time', 'location': 'Cape Town', 'relevance_score': 0.85},
            {'job_title': 'IT Support Specialist', 'company': 'TechSupport Ltd', 'description': '技术支持和维护', 'job_type': 'Full-time', 'location': 'Johannesburg', 'relevance_score': 0.82},
        ]
        
        for job in recommended_jobs:
            conn.execute('''
                INSERT INTO job_recommendations 
                (student_id, job_title, company, description, job_type, location, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], job['job_title'], job['company'], job['description'], 
                  job['job_type'], job['location'], job['relevance_score']))
        
        conn.commit()
        
        # Fetch again after inserting
        jobs = conn.execute('SELECT * FROM job_recommendations WHERE student_id = ? ORDER BY relevance_score DESC LIMIT 10', (session['user_id'],)).fetchall()
        logger.info(f"[DEBUG] Generated {len(jobs)} job recommendations")
    
    # Calculate career readiness
    readiness_score = 0
    if profile: readiness_score += 20
    if cvs: readiness_score += 25
    if len(projects) >= 2: readiness_score += 25
    if len(skills) >= 5: readiness_score += 30
    
    conn.close()
    return render_template('student_career.html', 
                           profile=profile, cvs=cvs, projects=projects,
                           skills=skills, jobs=jobs, readiness_score=readiness_score)

@app.route('/student/career/profile', methods=['GET', 'POST'])
@login_required
@role_required('student')
def student_career_profile():
    conn = get_db_connection()
    
    if request.method == 'POST':
        interests = request.form.get('interests')
        career_goals = request.form.get('career_goals')
        target_industries = request.form.get('target_industries')
        preferred_job_types = request.form.get('preferred_job_types')
        location_preference = request.form.get('location_preference')
        
        existing = conn.execute('SELECT id FROM career_profiles WHERE student_id = ?', (session['user_id'],)).fetchone()
        
        if existing:
            conn.execute('''
                UPDATE career_profiles SET 
                    interests = ?, career_goals = ?, target_industries = ?,
                    preferred_job_types = ?, location_preference = ?, updated_at = CURRENT_TIMESTAMP
                WHERE student_id = ?
            ''', (interests, career_goals, target_industries, preferred_job_types, location_preference, session['user_id']))
        else:
            conn.execute('''
                INSERT INTO career_profiles (student_id, interests, career_goals, target_industries, preferred_job_types, location_preference)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], interests, career_goals, target_industries, preferred_job_types, location_preference))
        
        conn.commit()
        conn.close()
        flash('Career profile updated!', 'success')
        return redirect(url_for('student_career'))
    
    profile = conn.execute('SELECT * FROM career_profiles WHERE student_id = ?', (session['user_id'],)).fetchone()
    conn.close()
    return render_template('student_career_profile.html', profile=profile)

@app.route('/student/career/cv', methods=['GET', 'POST'])
@login_required
@role_required('student')
def student_career_cv():
    import logging
    import time
    logger = logging.getLogger(__name__)
    conn = get_db_connection()
    
    logger.info(f"[DEBUG] student_career_cv called with method={request.method} for user_id={session['user_id']}")
    
    if request.method == 'POST':
        title = request.form.get('title')
        summary = request.form.get('summary')
        education = request.form.get('education')
        experience = request.form.get('experience')
        
        logger.info(f"[DEBUG] CV upload - title={title}, summary={summary}, education={education}, experience={experience}")
        
        # Handle file upload if provided
        file_path = None
        if 'cv_file' in request.files and request.files['cv_file'].filename:
            file = request.files['cv_file']
            upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'cvs')
            os.makedirs(upload_folder, exist_ok=True)
            filename = f"{session['user_id']}_{int(time.time())}_{file.filename}"
            file.save(os.path.join(upload_folder, filename))
            file_path = f"uploads/cvs/{filename}"
            logger.info(f"[DEBUG] CV file saved to {file_path}")
        
        # AI analysis simulation
        ai_analysis = "CV looks good! Consider adding more quantifiable achievements."
        ai_suggestions = "- Add specific numbers and metrics\n- Include relevant keywords\n- Highlight leadership experience"
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO cvs (student_id, title, summary, education, experience, file_path, ai_analysis, ai_suggestions, is_primary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], title, summary, education, experience, file_path, ai_analysis, ai_suggestions, 0))
        conn.commit()
        logger.info(f"[DEBUG] CV inserted into database with is_primary=0")
        flash('CV uploaded! AI analysis complete.', 'success')
        return redirect(url_for('student_career'))
    
    conn.close()
    return render_template('student_career_cv.html')

@app.route('/student/career/cv/<int:cv_id>/delete')
@login_required
@role_required('student')
def student_delete_cv(cv_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM cvs WHERE id = ? AND student_id = ?', (cv_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('CV deleted.', 'info')
    return redirect(url_for('student_career'))

@app.route('/student/career/projects', methods=['GET', 'POST'])
@login_required
@role_required('student')
def student_career_projects():
    conn = get_db_connection()
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        technologies = request.form.get('technologies')
        role = request.form.get('role')
        url = request.form.get('url')
        is_academic = 1 if request.form.get('is_academic') else 0
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO projects (student_id, title, description, technologies_used, role, url, is_academic)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], title, description, technologies, role, url, is_academic))
        conn.commit()
        flash('Project added to portfolio!', 'success')
        return redirect(url_for('student_career'))
    
    projects = conn.execute('SELECT * FROM projects WHERE student_id = ? ORDER BY created_at DESC', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('student_career_projects.html', projects=projects)

@app.route('/student/career/projects/<int:project_id>/delete')
@login_required
@role_required('student')
def student_delete_project(project_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM projects WHERE id = ? AND student_id = ?', (project_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('Project removed.', 'info')
    return redirect(url_for('student_career'))

@app.route('/student/career/skills')
@login_required
@role_required('student')
def student_career_skills():
    conn = get_db_connection()
    
    # Get skills from completed modules
    enrolled_modules = conn.execute('''
        SELECT m.id, m.title FROM modules m
        JOIN module_enrollments me ON m.id = me.module_id
        WHERE me.student_id = ? AND me.status = 'approved'
    ''', (session['user_id'],)).fetchall()
    
    current_skills = conn.execute('SELECT * FROM skills WHERE student_id = ?', (session['user_id'],)).fetchall()
    
    # Simulated skill gap analysis
    suggested_skills = [
        {'name': 'Python Programming', 'category': 'Technical'},
        {'name': 'Data Analysis', 'category': 'Technical'},
        {'name': 'Project Management', 'category': 'Soft Skills'},
        {'name': 'Machine Learning', 'category': 'Advanced'},
    ]
    
    conn.close()
    return render_template('student_career_skills.html', 
                           skills=current_skills,
                           modules=enrolled_modules,
                           suggested_skills=suggested_skills)

@app.route('/student/career/skills/add', methods=['POST'])
@login_required
@role_required('student')
def student_add_skill():
    skill_name = request.form.get('skill_name')
    proficiency = request.form.get('proficiency')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO skills (student_id, skill_name, proficiency_level)
        VALUES (?, ?, ?)
    ''', (session['user_id'], skill_name, proficiency))
    conn.commit()
    conn.close()
    
    flash('Skill added!', 'success')
    return redirect(url_for('student_career_skills'))

@app.route('/student/career/jobs')
@login_required
@role_required('student')
def student_career_jobs():
    import logging
    logger = logging.getLogger(__name__)
    conn = get_db_connection()
    
    # DEBUG: Log what's being fetched
    logger.info(f"[DEBUG] student_career_jobs called for user_id={session['user_id']}")
    
    # Get all job recommendations (not just saved ones) so users can browse and save
    all_jobs = conn.execute('''
        SELECT * FROM job_recommendations 
        WHERE student_id = ?
        ORDER BY relevance_score DESC, is_saved DESC
    ''', (session['user_id'],)).fetchall()
    
    logger.info(f"[DEBUG] Found {len(all_jobs)} total job recommendations for user")
    
    # If no jobs exist, generate AI job recommendations (simulated)
    if len(all_jobs) == 0:
        logger.info("[DEBUG] No jobs found, generating recommendations")
        recommended_jobs = [
            {'job_title': 'Junior Software Developer', 'company': 'TechCorp', 'description': 'Entry-level developer position', 'job_type': 'Full-time', 'location': 'Remote', 'relevance_score': 0.92},
            {'job_title': 'Data Analyst Intern', 'company': 'DataDriven Inc', 'description': '数据分析实习岗位', 'job_type': 'Internship', 'location': 'Johannesburg', 'relevance_score': 0.88},
            {'job_title': 'Junior ML Engineer', 'company': 'AI Solutions', 'description': '机器学习工程师入门级', 'job_type': 'Full-time', 'location': 'Cape Town', 'relevance_score': 0.85},
            {'job_title': 'IT Support Specialist', 'company': 'TechSupport Ltd', 'description': '技术支持和维护', 'job_type': 'Full-time', 'location': 'Johannesburg', 'relevance_score': 0.82},
        ]
        
        # Save to database
        for job in recommended_jobs:
            conn.execute('''
                INSERT INTO job_recommendations 
                (student_id, job_title, company, description, job_type, location, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], job['job_title'], job['company'], job['description'], 
                  job['job_type'], job['location'], job['relevance_score']))
        
        conn.commit()
        
        # Fetch again after inserting
        all_jobs = conn.execute('''
            SELECT * FROM job_recommendations 
            WHERE student_id = ?
            ORDER BY relevance_score DESC, is_saved DESC
        ''', (session['user_id'],)).fetchall()
        logger.info(f"[DEBUG] Generated {len(all_jobs)} job recommendations")
    
    conn.close()
    
    return render_template('student_career_jobs.html', jobs=all_jobs)

@app.route('/student/career/jobs/<int:job_id>/save')
@login_required
@role_required('student')
def student_save_job(job_id):
    conn = get_db_connection()
    conn.execute('UPDATE job_recommendations SET is_saved = 1 WHERE id = ? AND student_id = ?', 
                 (job_id, session['user_id']))
    conn.commit()
    conn.close()
    flash('Job saved!', 'success')
    return redirect(url_for('student_career_jobs'))

@app.route('/student/career/interview-practice', methods=['GET', 'POST'])
@login_required
@role_required('student')
def student_interview_practice():
    import logging
    logger = logging.getLogger(__name__)
    conn = get_db_connection()
    
    logger.info(f"[DEBUG] student_interview_practice called with method={request.method} for user_id={session['user_id']}")
    
    if request.method == 'POST':
        job_field = request.form.get('job_field')
        logger.info(f"[DEBUG] Generating questions for job_field={job_field}")
        
        # Generate AI practice questions (simulated)
        questions = [
            {'question': 'Tell me about a challenging project you worked on.', 'ideal_answer': 'Use the STAR method to describe a specific situation.'},
            {'question': 'What are your greatest strengths and weaknesses?', 'ideal_answer': 'Be honest but frame weaknesses as areas for growth.'},
            {'question': 'Why do you want to work in this field?', 'ideal_answer': 'Show passion and research the company.'},
            {'question': 'Describe a time you worked in a team.', 'ideal_answer': 'Highlight collaboration and conflict resolution.'},
            {'question': 'Where do you see yourself in 5 years?', 'ideal_answer': 'Show ambition while being realistic.'},
        ]
        
        for q in questions:
            conn.execute('''
                INSERT INTO interview_questions (student_id, job_field, question, ideal_answer)
                VALUES (?, ?, ?, ?)
            ''', (session['user_id'], job_field, q['question'], q['ideal_answer']))
        
        conn.commit()
        flash('Interview questions generated!', 'success')
        logger.info(f"[DEBUG] Inserted {len(questions)} questions for user")
        # Redirect after POST to prevent re-submission
        return redirect(url_for('student_interview_practice'))
    
    my_questions = conn.execute('''
        SELECT * FROM interview_questions 
        WHERE student_id = ? ORDER BY last_practiced DESC, created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    logger.info(f"[DEBUG] Found {len(my_questions)} existing questions for user")
    
    conn.close()
    return render_template('student_career_interview.html', questions=my_questions)

@app.route('/student/career/interview/<int:question_id>/practice', methods=['POST'])
@login_required
@role_required('student')
def student_practice_interview(question_id):
    user_answer = request.form.get('user_answer')
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE interview_questions 
        SET user_answer = ?, practice_count = practice_count + 1, last_practiced = CURRENT_TIMESTAMP
        WHERE id = ? AND student_id = ?
    ''', (user_answer, question_id, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Answer saved! Keep practicing.', 'success')
    return redirect(url_for('student_interview_practice'))

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='Page not found', code=404), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error='Server error. Please try again later.', code=500), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', error='Access forbidden. You do not have permission to access this resource.', code=403), 403

@app.errorhandler(400)
def bad_request(e):
    return render_template('error.html', error='Bad request. Please check your input.', code=400), 400

@app.errorhandler(401)
def unauthorized(e):
    return render_template('error.html', error='Unauthorized. Please log in to access this resource.', code=401), 401

# Global exception handler for unhandled exceptions (but not Flask's internal errors)
@app.errorhandler(Exception)
def handle_exception(e):
    # Don't handle Flask's internal HTTP exceptions
    if hasattr(e, 'code'):
        return e
    # Log the error for debugging
    app.logger.error(f'Unhandled exception: {str(e)}')
    return render_template('error.html', error='An unexpected error occurred. Please try again later.', code=500), 500

# ==================== DATABASE ERROR HANDLING ====================

def get_db_connection():
    """Get database connection with error handling"""
    try:
        conn = sqlite3.connect('edumind.db')
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        app.logger.error(f'Database connection error: {str(e)}')
        flash('Database connection error. Please try again.', 'danger')
        return None

def execute_query(query, params=(), fetch_one=False, fetch_all=True, commit=False):
    """Execute database query with comprehensive error handling"""
    conn = get_db_connection()
    if conn is None:
        return None if fetch_one else []
    
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if commit:
            conn.commit()
            result = cursor.lastrowid if fetch_one else True
        elif fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()
        else:
            result = True
            
        conn.close()
        return result
        
    except sqlite3.IntegrityError as e:
        conn.close()
        app.logger.error(f'Integrity error: {str(e)}')
        flash('Data integrity error. This action may violate database constraints.', 'danger')
        return None if fetch_one else []
    
    except sqlite3.OperationalError as e:
        conn.close()
        app.logger.error(f'Operational error: {str(e)}')
        flash('Database operation failed. Please try again.', 'danger')
        return None if fetch_one else []
    
    except sqlite3.Error as e:
        conn.close()
        app.logger.error(f'Database error: {str(e)}')
        flash('Database error occurred. Please try again.', 'danger')
        return None if fetch_one else []

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
else:
    # Initialize database when running with gunicorn
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
