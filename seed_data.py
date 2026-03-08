"""
EduMind Database Seed Script
Populates the database with:
- 1 Admin user
- 5 Teacher/Lecturer users
- 10 Student users
- 3 Parent users
- 20 Courses with 10 modules each
"""

import sqlite3
import hashlib
import random
from datetime import datetime

DB_NAME = 'edumind.db'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def seed_users():
    """Create users with different roles"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    users_data = [
        # Admin
        {'username': 'admin', 'email': 'admin@edumind.com', 'password': 'admin123', 'full_name': 'System Administrator', 'role': 'admin', 'is_verified': 1},
        
        # Teachers/Lecturers (5)
        {'username': 'johnsmith', 'email': 'john.smith@edumind.com', 'password': 'teacher123', 'full_name': 'John Smith', 'role': 'teacher', 'is_verified': 1},
        {'username': 'sarahjohnson', 'email': 'sarah.johnson@edumind.com', 'password': 'teacher123', 'full_name': 'Sarah Johnson', 'role': 'teacher', 'is_verified': 1},
        {'username': 'michaelbrown', 'email': 'michael.brown@edumind.com', 'password': 'teacher123', 'full_name': 'Michael Brown', 'role': 'teacher', 'is_verified': 1},
        {'username': 'emilydavis', 'email': 'emily.davis@edumind.com', 'password': 'teacher123', 'full_name': 'Emily Davis', 'role': 'teacher', 'is_verified': 1},
        {'username': 'davidwilson', 'email': 'david.wilson@edumind.com', 'password': 'teacher123', 'full_name': 'David Wilson', 'role': 'teacher', 'is_verified': 1},
        
        # Students (10)
        {'username': 'student1', 'email': 'student1@edumind.com', 'password': 'student123', 'full_name': 'Alice Anderson', 'role': 'student', 'is_verified': 1},
        {'username': 'student2', 'email': 'student2@edumind.com', 'password': 'student123', 'full_name': 'Bob Baker', 'role': 'student', 'is_verified': 1},
        {'username': 'student3', 'email': 'student3@edumind.com', 'password': 'student123', 'full_name': 'Charlie Clark', 'role': 'student', 'is_verified': 1},
        {'username': 'student4', 'email': 'student4@edumind.com', 'password': 'student123', 'full_name': 'Diana Davis', 'role': 'student', 'is_verified': 1},
        {'username': 'student5', 'email': 'student5@edumind.com', 'password': 'student123', 'full_name': 'Edward Evans', 'role': 'student', 'is_verified': 1},
        {'username': 'student6', 'email': 'student6@edumind.com', 'password': 'student123', 'full_name': 'Fiona Foster', 'role': 'student', 'is_verified': 1},
        {'username': 'student7', 'email': 'student7@edumind.com', 'password': 'student123', 'full_name': 'George Garcia', 'role': 'student', 'is_verified': 1},
        {'username': 'student8', 'email': 'student8@edumind.com', 'password': 'student123', 'full_name': 'Hannah Hill', 'role': 'student', 'is_verified': 1},
        {'username': 'student9', 'email': 'student9@edumind.com', 'password': 'student123', 'full_name': 'Ian Irwin', 'role': 'student', 'is_verified': 1},
        {'username': 'student10', 'email': 'student10@edumind.com', 'password': 'student123', 'full_name': 'Julia James', 'role': 'student', 'is_verified': 1},
        
        # Parents (3)
        {'username': 'parent1', 'email': 'parent1@edumind.com', 'password': 'parent123', 'full_name': 'Robert Anderson', 'role': 'parent', 'is_verified': 1},
        {'username': 'parent2', 'email': 'parent2@edumind.com', 'password': 'parent123', 'full_name': 'Mary Baker', 'role': 'parent', 'is_verified': 1},
        {'username': 'parent3', 'email': 'parent3@edumind.com', 'password': 'parent123', 'full_name': 'Patricia Clark', 'role': 'parent', 'is_verified': 1},
    ]
    
    user_ids = {}
    for user in users_data:
        password_hash = hash_password(user['password'])
        try:
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, full_name, role, is_verified, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user['username'], user['email'], password_hash, user['full_name'], user['role'], user['is_verified'], datetime.now()))
            user_ids[user['username']] = cursor.lastrowid
            print(f"Created user: {user['username']} ({user['role']})")
        except sqlite3.IntegrityError as e:
            print(f"User {user['username']} already exists: {e}")
            # Get existing user id
            cursor.execute('SELECT id FROM users WHERE username = ?', (user['username'],))
            row = cursor.fetchone()
            if row:
                user_ids[user['username']] = row['id']
    
    conn.commit()
    conn.close()
    return user_ids

def seed_courses_and_modules(teacher_ids):
    """Create 20 courses with 10 modules each"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Course categories and templates
    course_templates = [
        # Technology (5 courses)
        {'title': 'Introduction to Python Programming', 'description': 'Learn Python from scratch', 'subject': 'Computer Science', 'course_code': 'CS101'},
        {'title': 'Web Development Fundamentals', 'description': 'HTML, CSS, and JavaScript basics', 'subject': 'Computer Science', 'course_code': 'CS102'},
        {'title': 'Database Management Systems', 'description': 'SQL and database design', 'subject': 'Computer Science', 'course_code': 'CS201'},
        {'title': 'Data Structures and Algorithms', 'description': 'Essential CS concepts', 'subject': 'Computer Science', 'course_code': 'CS202'},
        {'title': 'Machine Learning Basics', 'description': 'Introduction to ML concepts', 'subject': 'Computer Science', 'course_code': 'CS301'},
        
        # Mathematics (4 courses)
        {'title': 'Calculus I', 'description': 'Differential calculus', 'subject': 'Mathematics', 'course_code': 'MATH101'},
        {'title': 'Linear Algebra', 'description': 'Vectors and matrices', 'subject': 'Mathematics', 'course_code': 'MATH201'},
        {'title': 'Statistics and Probability', 'description': 'Statistical analysis', 'subject': 'Mathematics', 'course_code': 'MATH202'},
        {'title': 'Discrete Mathematics', 'description': 'Mathematical structures', 'subject': 'Mathematics', 'course_code': 'MATH102'},
        
        # Science (4 courses)
        {'title': 'Physics I', 'description': 'Mechanics and thermodynamics', 'subject': 'Physics', 'course_code': 'PHY101'},
        {'title': 'Chemistry Fundamentals', 'description': 'Organic and inorganic chemistry', 'subject': 'Chemistry', 'course_code': 'CHEM101'},
        {'title': 'Biology Introduction', 'description': 'Cell biology and genetics', 'subject': 'Biology', 'course_code': 'BIO101'},
        {'title': 'Environmental Science', 'description': 'Ecosystems and sustainability', 'subject': 'Science', 'course_code': 'ENV101'},
        
        # Business (3 courses)
        {'title': 'Principles of Marketing', 'description': 'Marketing strategies', 'subject': 'Business', 'course_code': 'BUS101'},
        {'title': 'Financial Accounting', 'description': 'Accounting fundamentals', 'subject': 'Business', 'course_code': 'BUS201'},
        {'title': 'Business Management', 'description': 'Management principles', 'subject': 'Business', 'course_code': 'BUS102'},
        
        # Language (2 courses)
        {'title': 'English Composition', 'description': 'Academic writing', 'subject': 'English', 'course_code': 'ENG101'},
        {'title': 'Spanish for Beginners', 'description': 'Basic Spanish language', 'subject': 'Language', 'course_code': 'LAN101'},
        
        # Arts (2 courses)
        {'title': 'Art History', 'description': 'Western art movements', 'subject': 'Arts', 'course_code': 'ART101'},
        {'title': 'Music Theory', 'description': 'Fundamentals of music', 'subject': 'Arts', 'course_code': 'MUS101'},
    ]
    
    # Module titles for each course (10 modules per course)
    module_templates = [
        'Introduction and Overview',
        'Core Concepts and Foundations',
        'Fundamental Principles',
        'Intermediate Topics',
        'Practical Applications',
        'Advanced Techniques',
        'Case Studies',
        'Best Practices',
        'Real-world Projects',
        'Review and Assessment'
    ]
    
    course_ids = []
    
    for i, course_template in enumerate(course_templates):
        # Assign teacher round-robin style
        teacher_id = teacher_ids[i % len(teacher_ids)]
        
        try:
            cursor.execute('''
                INSERT INTO courses (title, description, subject, course_code, teacher_id, is_published, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (course_template['title'], course_template['description'], course_template['subject'], 
                  course_template['course_code'], teacher_id, 1, datetime.now()))
            course_id = cursor.lastrowid
            course_ids.append(course_id)
            print(f"Created course: {course_template['title']} (ID: {course_id})")
            
            # Create 10 modules for this course
            for j, module_title in enumerate(module_templates):
                module_code = f"{course_template['course_code']}-M{j+1:02d}"
                cursor.execute('''
                    INSERT INTO modules (course_id, title, description, code, chapter_number, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (course_id, module_title, f"Module {j+1}: {module_title}", module_code, j+1, 1, datetime.now()))
                module_id = cursor.lastrowid
                print(f"  - Created module: {module_title} (ID: {module_id})")
            
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Error creating course {course_template['title']}: {e}")
            conn.rollback()
    
    conn.close()
    return course_ids

def seed_enrollments(student_ids, course_ids):
    """Enroll students in random courses"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Each student enrolls in 3-5 random courses
    for student_id in student_ids:
        num_courses = random.randint(3, 5)
        selected_courses = random.sample(course_ids, min(num_courses, len(course_ids)))
        
        for course_id in selected_courses:
            try:
                cursor.execute('''
                    INSERT INTO enrollments (student_id, course_id, status, enrolled_at)
                    VALUES (?, ?, ?, ?)
                ''', (student_id, course_id, 'approved', datetime.now()))
                print(f"Enrolled student {student_id} in course {course_id}")
            except sqlite3.IntegrityError:
                pass  # Already enrolled
    
    conn.commit()
    conn.close()

def seed_parent_student_links(parent_ids, student_ids):
    """Link parents to students"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Link first parent to first 4 students, second parent to next 3, third to last 3
    links = [
        (parent_ids[0], student_ids[0]),
        (parent_ids[0], student_ids[1]),
        (parent_ids[0], student_ids[2]),
        (parent_ids[0], student_ids[3]),
        (parent_ids[1], student_ids[4]),
        (parent_ids[1], student_ids[5]),
        (parent_ids[1], student_ids[6]),
        (parent_ids[2], student_ids[7]),
        (parent_ids[2], student_ids[8]),
        (parent_ids[2], student_ids[9]),
    ]
    
    for parent_id, student_id in links:
        try:
            cursor.execute('''
                INSERT INTO parent_students (parent_id, student_id)
                VALUES (?, ?)
            ''', (parent_id, student_id))
            print(f"Linked parent {parent_id} to student {student_id}")
        except sqlite3.IntegrityError:
            pass  # Already linked
    
    conn.commit()
    conn.close()

def main():
    print("=" * 50)
    print("Starting Database Seeding...")
    print("=" * 50)
    
    # Step 1: Create Users
    print("\n--- Creating Users ---")
    user_ids = seed_users()
    
    # Extract user IDs by role
    admin_ids = [user_ids['admin']]
    teacher_ids = [user_ids['johnsmith'], user_ids['sarahjohnson'], user_ids['michaelbrown'], 
                   user_ids['emilydavis'], user_ids['davidwilson']]
    student_ids = [user_ids[f'student{i}'] for i in range(1, 11)]
    parent_ids = [user_ids['parent1'], user_ids['parent2'], user_ids['parent3']]
    
    print(f"\nAdmin IDs: {admin_ids}")
    print(f"Teacher IDs: {teacher_ids}")
    print(f"Student IDs: {student_ids}")
    print(f"Parent IDs: {parent_ids}")
    
    # Step 2: Create Courses and Modules
    print("\n--- Creating Courses and Modules ---")
    course_ids = seed_courses_and_modules(teacher_ids)
    
    # Step 3: Create Enrollments
    print("\n--- Creating Enrollments ---")
    seed_enrollments(student_ids, course_ids)
    
    # Step 4: Link Parents to Students
    print("\n--- Linking Parents to Students ---")
    seed_parent_student_links(parent_ids, student_ids)
    
    print("\n" + "=" * 50)
    print("Database Seeding Complete!")
    print("=" * 50)
    
    # Summary
    print("\n--- Summary ---")
    print(f"Total Users: 1 admin + 5 teachers + 10 students + 3 parents = 19 users")
    print(f"Total Courses: {len(course_ids)}")
    print(f"Total Modules: {len(course_ids) * 10} (10 per course)")
    print(f"Total Enrollments: ~40 (3-5 per student)")

if __name__ == '__main__':
    main()
