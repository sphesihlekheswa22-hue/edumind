"""
Seed script to populate database with test data
Creates 10 users (mix of roles) and courses with modules
No enrollments or module assignments initially - for testing purposes
"""
import sqlite3
import hashlib
import os

# Database file
DB_FILE = 'edumind.db'

def create_tables(conn):
    """Create all required tables"""
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'lecturer', 'admin', 'parent')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
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
            is_published INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users(id)
        )
    ''')
    
    # Modules table
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
    
    # Enrollments table
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
    
    # Module lecturers table
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
    
    # Module enrollments table
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
    
    # Quiz table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            module_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id),
            FOREIGN KEY (module_id) REFERENCES modules(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    conn.commit()

def hash_password(password):
    """Hash a password"""
    return hashlib.sha256(password.encode()).hexdigest()

def seed_data():
    """Seed the database with test data"""
    # Remove existing database
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create tables
    create_tables(conn)
    
    # Create 10 users
    users = [
        # Admin
        ('admin', 'admin@edumind.com', 'admin123', 'System Administrator', 'admin'),
        # Teachers (2)
        ('teacher1', 'teacher1@edumind.com', 'teacher123', 'John Smith', 'teacher'),
        ('teacher2', 'teacher2@edumind.com', 'teacher123', 'Sarah Johnson', 'teacher'),
        # Lecturers (2)
        ('lecturer1', 'lecturer1@edumind.com', 'lecturer123', 'Dr. Michael Brown', 'lecturer'),
        ('lecturer2', 'lecturer2@edumind.com', 'lecturer123', 'Dr. Emily Davis', 'lecturer'),
        # Students (4)
        ('student1', 'student1@edumind.com', 'student123', 'Alice Williams', 'student'),
        ('student2', 'student2@edumind.com', 'student123', 'Bob Miller', 'student'),
        ('student3', 'student3@edumind.com', 'student123', 'Charlie Wilson', 'student'),
        ('student4', 'student4@edumind.com', 'student123', 'Diana Taylor', 'student'),
    ]
    
    user_ids = {}
    for username, email, password, full_name, role in users:
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, email, hash_password(password), full_name, role))
        user_ids[role] = user_ids.get(role, [])
        user_ids[role].append(cursor.lastrowid)
    
    print(f"Created {len(users)} users")
    
    # Create courses
    courses = [
        ('Introduction to Programming', 'Learn the fundamentals of programming using Python', 'Computer Science', 'CS101', user_ids['teacher'][0]),
        ('Web Development', 'Build modern websites with HTML, CSS, and JavaScript', 'Web Development', 'WD201', user_ids['teacher'][1]),
        ('Data Science Fundamentals', 'Introduction to data analysis and machine learning', 'Data Science', 'DS301', user_ids['teacher'][0]),
    ]
    
    course_ids = []
    for title, description, subject, code, teacher_id in courses:
        cursor.execute('''
            INSERT INTO courses (title, description, subject, course_code, teacher_id, is_published)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (title, description, subject, code, teacher_id))
        course_ids.append(cursor.lastrowid)
    
    print(f"Created {len(courses)} courses")
    
    # Create modules for each course
    modules = [
        # Course 1 - Introduction to Programming
        (course_ids[0], 'Getting Started with Python', 'Introduction to Python programming', 'CH01', 1),
        (course_ids[0], 'Variables and Data Types', 'Learn about variables and data types in Python', 'CH02', 2),
        (course_ids[0], 'Control Flow', 'If statements, loops, and conditional logic', 'CH03', 3),
        (course_ids[0], 'Functions', 'Creating and using functions', 'CH04', 4),
        # Course 2 - Web Development
        (course_ids[1], 'HTML Basics', 'Introduction to HTML', 'CH01', 1),
        (course_ids[1], 'CSS Styling', 'Styling web pages with CSS', 'CH02', 2),
        (course_ids[1], 'JavaScript Fundamentals', 'Introduction to JavaScript', 'CH03', 3),
        # Course 3 - Data Science
        (course_ids[2], 'Introduction to Data Science', 'What is data science?', 'CH01', 1),
        (course_ids[2], 'Data Analysis with Pandas', 'Using Pandas for data analysis', 'CH02', 2),
        (course_ids[2], 'Introduction to Machine Learning', 'Basic ML concepts', 'CH03', 3),
    ]
    
    module_ids = []
    for course_id, title, description, chapter, created_by in modules:
        cursor.execute('''
            INSERT INTO modules (course_id, title, description, code, chapter_number, created_by, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', (course_id, title, description, chapter, created_by, created_by))
        module_ids.append(cursor.lastrowid)
    
    print(f"Created {len(modules)} modules")
    
    # Create quizzes for some courses
    quizzes = [
        (course_ids[0], None, 'Python Basics Quiz', 'Test your knowledge of Python basics', user_ids['teacher'][0]),
        (course_ids[0], module_ids[0], 'Python Introduction Quiz', 'Quiz on Python introduction', user_ids['teacher'][0]),
        (course_ids[1], None, 'HTML Quiz', 'Test your HTML knowledge', user_ids['teacher'][1]),
    ]
    
    for course_id, module_id, title, description, created_by in quizzes:
        cursor.execute('''
            INSERT INTO quizzes (course_id, module_id, title, description, created_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (course_id, module_id, title, description, created_by))
    
    print(f"Created {len(quizzes)} quizzes")
    
    conn.commit()
    conn.close()
    
    print("\n=== Database seeded successfully ===")
    print("\nUser credentials:")
    print("  Admin: admin / admin123")
    print("  Teacher 1: teacher1 / teacher123")
    print("  Teacher 2: teacher2 / teacher123")
    print("  Lecturer 1: lecturer1 / lecturer123")
    print("  Lecturer 2: lecturer2 / lecturer123")
    print("  Student 1: student1 / student123")
    print("  Student 2: student2 / student123")
    print("  Student 3: student3 / student123")
    print("  Student 4: student4 / student123")
    print("\nNote: No enrollments or module assignments have been made.")
    print("You can assign courses/modules to test the functionality.")

if __name__ == '__main__':
    seed_data()
