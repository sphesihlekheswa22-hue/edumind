"""
University LMS Seed Script
Creates realistic university courses and modules
"""
import sqlite3
import hashlib
import os

DB_FILE = 'edumind.db'

def create_tables(conn):
    """Create all required tables"""
    cursor = conn.cursor()
    
    # Users table - extended with university fields
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'lecturer', 'admin', 'parent')),
            student_number TEXT,
            university TEXT,
            course_id INTEGER,
            year_of_study INTEGER DEFAULT 1,
            profile_picture TEXT,
            is_verified INTEGER DEFAULT 1,
            verification_token TEXT,
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
    
    # Modules table - with year field
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            code TEXT,
            chapter_number INTEGER,
            year INTEGER DEFAULT 1,
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
    return hashlib.sha256(password.encode()).hexdigest()

def seed_data():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    create_tables(conn)
    
    # Create users
    users = [
        ('admin', 'admin@edumind.com', 'admin123', 'System Administrator', 'admin', None, None, None, None),
        ('lecturer1', 'dr.smith@edumind.com', 'lecturer123', 'Dr. John Smith', 'lecturer', 'LEC001', 'EduMind University', None, None),
        ('lecturer2', 'dr.jones@edumind.com', 'lecturer123', 'Dr. Sarah Jones', 'lecturer', 'LEC002', 'EduMind University', None, None),
        ('lecturer3', 'dr.wilson@edumind.com', 'lecturer123', 'Dr. Michael Wilson', 'lecturer', 'LEC003', 'EduMind University', None, None),
        ('lecturer4', 'dr.lee@edumind.com', 'lecturer123', 'Dr. Emily Lee', 'lecturer', 'LEC004', 'EduMind University', None, None),
        ('lecturer5', 'dr.chen@edumind.com', 'lecturer123', 'Dr. David Chen', 'lecturer', 'LEC005', 'EduMind University', None, None),
    ]
    
    user_ids = {'admin': None, 'lecturer': []}
    for username, email, password, full_name, role, student_num, uni, course_id, year in users:
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name, role, student_number, university, course_id, year_of_study)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, email, hash_password(password), full_name, role, student_num, uni, course_id, year))
        if role == 'admin':
            user_ids['admin'] = cursor.lastrowid
        else:
            user_ids['lecturer'].append(cursor.lastrowid)
    
    print(f"Created {len(users)} users")
    
    # Create courses
    courses = [
        (1, 'Computer Science', 'Study of computation, algorithms, and information processing', 'Computing', 'CS'),
        (2, 'Information Technology', 'Use of computers to manage and process information', 'Computing', 'IT'),
        (3, 'Software Engineering', 'Design and development of software systems', 'Computing', 'SE'),
        (4, 'Business Administration', 'Management of business operations and decision-making', 'Business', 'BA'),
        (5, 'Accounting', 'Measurement and communication of financial information', 'Business', 'ACC'),
        (6, 'Mechanical Engineering', 'Design and analysis of mechanical systems', 'Engineering', 'ME'),
        (7, 'Electrical Engineering', 'Study of electricity, electronics, and electromagnetism', 'Engineering', 'EE'),
        (8, 'Civil Engineering', 'Design and construction of infrastructure', 'Engineering', 'CE'),
        (9, 'Marketing', 'Creating and communicating value to customers', 'Business', 'MKT'),
        (10, 'Data Science', 'Extracting knowledge from data using scientific methods', 'Computing', 'DS'),
    ]
    
    course_ids = []
    for order, title, desc, subject, code in courses:
        cursor.execute('''
            INSERT INTO courses (id, title, description, subject, course_code, teacher_id, is_published)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', (order, title, desc, subject, code, user_ids['admin']))
        course_ids.append(order)
    
    print(f"Created {len(courses)} courses")
    
    # Create modules - using exact data from user
    modules = [
        # Computer Science (course_id = 1)
        (1, 1, 'Introduction to Programming', 1),
        (1, 1, 'Computer Fundamentals', 1),
        (1, 1, 'Discrete Mathematics', 1),
        (1, 1, 'Data Structures', 2),
        (1, 1, 'Internet Programming', 2),
        (1, 1, 'Database Systems', 2),
        (1, 1, 'Operating Systems', 3),
        (1, 1, 'Artificial Intelligence', 3),
        (1, 1, 'Software Engineering', 3),
        (1, 1, 'Computer Networks', 3),
        # Information Technology (course_id = 2)
        (2, 2, 'IT Fundamentals', 1),
        (2, 2, 'Programming Basics', 1),
        (2, 2, 'Web Development', 1),
        (2, 2, 'Networking Basics', 2),
        (2, 2, 'Database Management', 2),
        (2, 2, 'Systems Analysis', 2),
        (2, 2, 'Cybersecurity', 3),
        (2, 2, 'Cloud Computing', 3),
        (2, 2, 'Mobile App Development', 3),
        (2, 2, 'IT Project Management', 3),
        # Data Science (course_id = 10)
        (3, 10, 'Introduction to Data Science', 1),
        (3, 10, 'Statistics for Data Science', 1),
        (3, 10, 'Python for Data Analysis', 1),
        (3, 10, 'Data Visualization', 2),
        (3, 10, 'Machine Learning', 2),
        (3, 10, 'Big Data Technologies', 2),
        (3, 10, 'Deep Learning', 3),
        (3, 10, 'Natural Language Processing', 3),
        (3, 10, 'Data Mining', 3),
        (3, 10, 'AI Applications', 3),
    ]
    
    module_ids = []
    for i, (course_id, cid, title, year) in enumerate(modules, 1):
        cursor.execute('''
            INSERT INTO modules (id, course_id, title, year, chapter_number, created_by, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', (i, course_id, title, year, year, user_ids['admin']))
        module_ids.append(i)
    
    print(f"Created {len(modules)} modules")
    
    # Assign lecturers to modules
    lecturer_assignments = [
        (module_ids[0], user_ids['lecturer'][0]),  # Intro to Programming -> Dr. Smith
        (module_ids[3], user_ids['lecturer'][0]),  # Data Structures -> Dr. Smith
        (module_ids[6], user_ids['lecturer'][0]),  # Operating Systems -> Dr. Smith
        (module_ids[7], user_ids['lecturer'][1]),  # AI -> Dr. Jones
        (module_ids[10], user_ids['lecturer'][1]), # IT Fundamentals -> Dr. Jones
        (module_ids[13], user_ids['lecturer'][2]), # Networking -> Dr. Wilson
        (module_ids[16], user_ids['lecturer'][2]), # Cybersecurity -> Dr. Wilson
        (module_ids[19], user_ids['lecturer'][3]), # Mobile App -> Dr. Lee
        (module_ids[20], user_ids['lecturer'][4]), # Intro to DS -> Dr. Chen
        (module_ids[23], user_ids['lecturer'][4]), # Machine Learning -> Dr. Chen
    ]
    
    for module_id, lecturer_id in lecturer_assignments:
        cursor.execute('''
            INSERT INTO module_lecturers (module_id, lecturer_id)
            VALUES (?, ?)
        ''', (module_id, lecturer_id))
    
    print(f"Assigned {len(lecturer_assignments)} lecturers to modules")
    
    # Create sample quizzes
    quizzes = [
        (1, module_ids[0], 'Python Basics Quiz', 'Test your Python knowledge'),
        (2, module_ids[3], 'Data Structures Quiz', 'Arrays, Linked Lists, Trees'),
        (3, module_ids[20], 'Data Science Intro Quiz', 'Basic Data Science concepts'),
    ]
    
    for course_id, module_id, title, desc in quizzes:
        cursor.execute('''
            INSERT INTO quizzes (course_id, module_id, title, description, created_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (course_id, module_id, title, desc, user_ids['admin']))
    
    print(f"Created {len(quizzes)} quizzes")
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*50)
    print("University LMS Database Seeded Successfully!")
    print("="*50)
    print("\n📋 User Credentials:")
    print("  Admin: admin / admin123")
    print("  Lecturer: lecturer1 / lecturer123")
    print("  Lecturer: lecturer2 / lecturer123")
    print("  Lecturer: lecturer3 / lecturer123")
    print("  Lecturer: lecturer4 / lecturer123")
    print("  Lecturer: lecturer5 / lecturer123")
    print("\n📚 10 Courses Created:")
    for title in ['Computer Science', 'Information Technology', 'Software Engineering', 
                  'Business Administration', 'Accounting', 'Mechanical Engineering', 
                  'Electrical Engineering', 'Civil Engineering', 'Marketing', 'Data Science']:
        print(f"  - {title}")
    print("\n📖 30 Modules Created across courses")
    print("👨‍🏫 Lecturers assigned to various modules")
    print("\n✅ Students can register and will be auto-enrolled in their course modules")

if __name__ == '__main__':
    seed_data()
