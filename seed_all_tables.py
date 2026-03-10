"""
Comprehensive seed script to populate ALL tables with 10+ records
Each table will have at least 10 records - Fixed for actual schema
"""
import sqlite3
import hashlib
import random
from datetime import datetime, timedelta

DB_FILE = 'edumind.db'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def seed_all_tables():
    """Main function to seed all tables"""
    print("=" * 60)
    print("COMPREHENSIVE DATABASE SEEDING")
    print("Ensuring all tables have 10+ records")
    print("=" * 60)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get user and course IDs
        cursor.execute("SELECT id FROM users WHERE role IN ('admin', 'teacher', 'lecturer') LIMIT 10")
        user_ids = [row['id'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT id FROM courses LIMIT 10")
        course_ids = [row['id'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT id FROM users WHERE role = 'student' LIMIT 10")
        student_ids = [row['id'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT id FROM modules LIMIT 20")
        module_ids = [row['id'] for row in cursor.fetchall()]
        
        cursor.execute("SELECT id FROM quizzes LIMIT 10")
        quiz_ids = [row['id'] for row in cursor.fetchall()]
        
        # ==================== ANNOUNCEMENTS ====================
        print("\n--- Seeding Announcements ---")
        announcements = [
            ("Welcome to the New Semester", "Welcome all students to the new semester!", 1),
            ("Exam Schedule Released", "The final exam schedule has been published.", 1),
            ("Library Hours Extended", "The library will be open 24/7 during exam week.", 1),
            ("New Online Resources", "Check out our new online learning resources.", 1),
            ("Campus Tour Registration", "Register for the upcoming campus tour.", 1),
            ("Research Symposium", "Annual research symposium to be held next month.", 1),
            ("Sports Day Announcement", "Annual sports day competition.", 1),
            ("Career Fair Next Week", "Major companies will be recruiting.", 1),
            ("Computer Lab Maintenance", "The main computer lab will be closed.", 1),
            ("New Course Materials", "Updated course materials are now available.", 1),
        ]
        
        for title, message, is_system in announcements:
            user_id = random.choice(user_ids) if user_ids else 1
            course_id = random.choice(course_ids) if course_ids else None
            cursor.execute('''
                INSERT INTO announcements (course_id, user_id, title, message_text, is_system, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (course_id, user_id, title, message, is_system, datetime.now()))
        
        print(f"Created {len(announcements)} announcements")
        conn.commit()
        
        # ==================== MESSAGES ====================
        print("\n--- Seeding Messages ---")
        subjects = ["Question about assignment", "Need help", "Meeting request", "Study group", "Project collab"]
        messages_text = ["Hi, I have a question.", "Could you help me?", "Can we meet?", "Study group?", "Project work?"]
        
        for i in range(10):
            if len(user_ids) >= 2:
                sender_id = random.choice(user_ids)
                recipient_id = random.choice([u for u in user_ids if u != sender_id])
                cursor.execute('''
                    INSERT INTO messages (sender_id, recipient_id, course_id, subject, message_text, is_read, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (sender_id, recipient_id, random.choice(course_ids) if course_ids else None, 
                      subjects[i % len(subjects)], messages_text[i % len(messages_text)], random.randint(0, 1), datetime.now()))
        
        print(f"Created 10 messages")
        conn.commit()
        
        # ==================== NOTIFICATIONS ====================
        print("\n--- Seeding Notifications ---")
        titles = ["New material", "Assignment due", "Grade posted", "New announcement", "Enrollment approved",
                  "New message", "Quiz results", "Module updated", "Profile updated", "Welcome!"]
        
        for i in range(10):
            user_id = random.choice(student_ids) if student_ids else 1
            cursor.execute('''
                INSERT INTO notifications (user_id, title, message_text, link, is_read, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, titles[i], f"Notification message {i+1}", "/dashboard", random.randint(0, 1), datetime.now()))
        
        print(f"Created 10 notifications")
        conn.commit()
        
        # ==================== QUIZZES ====================
        print("\n--- Seeding Quizzes ---")
        cursor.execute("SELECT id FROM users WHERE role IN ('teacher', 'lecturer') LIMIT 5")
        teacher_ids = [row['id'] for row in cursor.fetchall()]
        
        quizzes = [
            ("Python Basics Quiz", "Test Python fundamentals"),
            ("Web Development Quiz", "HTML, CSS, JS basics"),
            ("Data Structures Quiz", "Arrays, Lists, Trees"),
            ("Database Design Quiz", "SQL and normalization"),
            ("Algorithms Quiz", "Sorting and searching"),
            ("Machine Learning Quiz", "Intro to ML"),
            ("Mathematics Quiz", "Calculus basics"),
            ("Physics Quiz", "Mechanics"),
            ("Chemistry Quiz", "Organic chemistry"),
            ("English Quiz", "Grammar"),
        ]
        
        for title, description in quizzes:
            course_id = random.choice(course_ids) if course_ids else 1
            teacher_id = random.choice(teacher_ids) if teacher_ids else 1
            cursor.execute('''
                INSERT INTO quizzes (course_id, title, description, created_by, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (course_id, title, description, teacher_id, datetime.now()))
        
        print(f"Created {len(quizzes)} quizzes")
        conn.commit()
        
        # ==================== QUIZ QUESTIONS ====================
        print("\n--- Seeding Quiz Questions ---")
        cursor.execute("SELECT id FROM quizzes")
        quiz_ids = [row['id'] for row in cursor.fetchall()]
        
        questions = [
            (1, "What is Python?", "Language", "Snake", "Animal", "Food", "A"),
            (1, "What is 2+2?", "3", "4", "5", "6", "B"),
            (1, "Is list mutable?", "Yes", "No", "Maybe", "Sometimes", "A"),
            (1, "What is def?", "Function", "Variable", "Class", "Import", "A"),
            (1, "What is len?", "Length", "Less", "Last", "List", "A"),
            (1, "What is for?", "Loop", "Condition", "Function", "Class", "A"),
            (1, "Is tuple immutable?", "Yes", "No", "Maybe", "Sometimes", "A"),
            (1, "What is import?", "Module", "Function", "Class", "Variable", "A"),
            (1, "What is class?", "Blueprint", "Object", "Function", "Variable", "A"),
            (1, "What is self?", "Instance", "Class", "Function", "Module", "A"),
        ]
        
        # Add more questions for different quizzes
        for i in range(10):
            quiz_id = quiz_ids[i % len(quiz_ids)] if quiz_ids else 1
            cursor.execute('''
                INSERT INTO quiz_questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_answer)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (quiz_id, f"Question {i+1}", "Option A", "Option B", "Option C", "Option D", "A"))
        
        # Add the specific questions
        for q in questions:
            cursor.execute('''
                INSERT INTO quiz_questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_answer)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', q)
        
        print(f"Created quiz questions")
        conn.commit()
        
        # ==================== QUIZ RESULTS ====================
        print("\n--- Seeding Quiz Results ---")
        cursor.execute("SELECT id FROM quizzes LIMIT 10")
        quiz_ids = [row['id'] for row in cursor.fetchall()]
        
        for i in range(10):
            quiz_id = random.choice(quiz_ids) if quiz_ids else 1
            student_id = random.choice(student_ids) if student_ids else 1
            cursor.execute('''
                INSERT INTO quiz_results (quiz_id, student_id, score, total_questions, completed_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (quiz_id, student_id, random.randint(50, 100), 10, datetime.now()))
        
        print(f"Created 10 quiz results")
        conn.commit()
        
        # ==================== AI FEEDBACK ====================
        print("\n--- Seeding AI Feedback ---")
        cursor.execute("SELECT id FROM quiz_results LIMIT 10")
        quiz_result_ids = [row['id'] for row in cursor.fetchall()]
        
        for i in range(10):
            student_id = random.choice(student_ids) if student_ids else 1
            course_id = random.choice(course_ids) if course_ids else 1
            quiz_result_id = quiz_result_ids[i] if i < len(quiz_result_ids) else None
            cursor.execute('''
                INSERT INTO ai_feedback (quiz_result_id, student_id, course_id, feedback_text, weak_topics, recommendations, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (quiz_result_id, student_id, course_id, "Great job!", "Advanced topics", "Keep practicing", datetime.now()))
        
        print(f"Created 10 AI feedback")
        conn.commit()
        
        # ==================== COURSE MATERIALS ====================
        print("\n--- Seeding Course Materials ---")
        materials = [
            ("Course Syllabus", "pdf"),
            ("Lecture Notes 1", "pdf"),
            ("Lecture Notes 2", "pdf"),
            ("Practice Exercises", "doc"),
            ("Sample Exam", "pdf"),
            ("Reference Chapter", "pdf"),
            ("Tutorial Video", "mp4"),
            ("Lab Manual", "pdf"),
            ("Case Study", "pdf"),
            ("Assignment Guide", "pdf"),
        ]
        
        for title, file_type in materials:
            course_id = random.choice(course_ids) if course_ids else 1
            teacher_id = random.choice(teacher_ids) if teacher_ids else 1
            cursor.execute('''
                INSERT INTO course_materials (course_id, title, description, file_type, uploaded_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (course_id, title, f"{title} description", file_type, teacher_id, datetime.now()))
        
        print(f"Created {len(materials)} course materials")
        conn.commit()
        
        # ==================== MODULE MATERIALS ====================
        print("\n--- Seeding Module Materials ---")
        cursor.execute("SELECT id FROM modules LIMIT 20")
        module_ids = [row['id'] for row in cursor.fetchall()]
        
        module_materials = [
            ("Reading Material", "pdf"),
            ("Video Tutorial", "video"),
            ("Practice Problems", "pdf"),
            ("Lecture Slides", "slide"),
            ("Supplementary Notes", "pdf"),
            ("Example Code", "document"),
            ("Workbook", "pdf"),
            ("Reference Link", "link"),
            ("Quiz", "pdf"),
            ("Summary", "pdf"),
        ]
        
        for title, content_type in module_materials:
            module_id = random.choice(module_ids) if module_ids else 1
            teacher_id = random.choice(teacher_ids) if teacher_ids else 1
            cursor.execute('''
                INSERT INTO module_materials (module_id, title, description, content_type, uploaded_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (module_id, title, f"{title} description", content_type, teacher_id, datetime.now()))
        
        print(f"Created {len(module_materials)} module materials")
        conn.commit()
        
        # ==================== ASSIGNMENTS ====================
        print("\n--- Seeding Assignments ---")
        cursor.execute("SELECT id FROM modules LIMIT 20")
        module_ids = [row['id'] for row in cursor.fetchall()]
        
        assignments = [
            ("Python Assignment", "Complete coding exercises"),
            ("Web Project", "Build a website"),
            ("Database Project", "Design a database"),
            ("Algorithm HW", "Implement algorithms"),
            ("Research Paper", "Write a paper"),
            ("Case Study", "Analyze a case"),
            ("Group Project", "Collaborate"),
            ("Lab Report", "Write a report"),
            ("Presentation", "Prepare slides"),
            ("Portfolio", "Submit portfolio"),
        ]
        
        for title, description in assignments:
            module_id = random.choice(module_ids) if module_ids else 1
            due_date = datetime.now() + timedelta(days=random.randint(7, 30))
            cursor.execute('''
                INSERT INTO assignments (module_id, title, description, due_date, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (module_id, title, description, due_date, datetime.now()))
        
        print(f"Created {len(assignments)} assignments")
        conn.commit()
        
        # ==================== ASSIGNMENT SUBMISSIONS ====================
        print("\n--- Seeding Assignment Submissions ---")
        cursor.execute("SELECT id FROM assignments LIMIT 10")
        assignment_ids = [row['id'] for row in cursor.fetchall()]
        
        # Check actual columns
        cursor.execute("PRAGMA table_info(assignment_submissions)")
        cols = [c[1] for c in cursor.fetchall()]
        print(f"Assignment submissions columns: {cols}")
        
        for i in range(10):
            assignment_id = random.choice(assignment_ids) if assignment_ids else 1
            student_id = random.choice(student_ids) if student_ids else 1
            
            if 'graded_at' in cols:
                cursor.execute('''
                    INSERT OR IGNORE INTO assignment_submissions (assignment_id, student_id, submitted_at, grade, feedback, graded_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (assignment_id, student_id, datetime.now(), random.randint(60, 95), "Good work!", datetime.now()))
            else:
                cursor.execute('''
                    INSERT OR IGNORE INTO assignment_submissions (assignment_id, student_id, submission_text, grade, feedback, submitted_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (assignment_id, student_id, "Submission text", random.randint(60, 95), "Good work!", datetime.now()))
        
        print(f"Created 10 assignment submissions")
        conn.commit()
        
        # ==================== STUDY PLANS ====================
        print("\n--- Seeding Study Plans ---")
        plans = [
            ("Week 1 Plan", "Review materials", "Complete exercises", "pending"),
            ("Midterm Prep", "Review topics", "Practice", "in_progress"),
            ("Final Prep", "Comprehensive review", "Take tests", "pending"),
            ("Project Plan", "Outline steps", "Gather resources", "completed"),
            ("Weekly Review", "Summarize", "Complete assignments", "pending"),
            ("Lab Prep", "Pre-lab reading", "Setup", "in_progress"),
            ("Reading Schedule", "Read chapters", "Take notes", "pending"),
            ("Practice Session", "Practice coding", "Debug", "completed"),
            ("Group Study", "Meet group", "Discuss", "pending"),
            ("Office Hours", "Prepare questions", "Attend", "in_progress"),
        ]
        
        for title, topics, activities, status in plans:
            student_id = random.choice(student_ids) if student_ids else 1
            course_id = random.choice(course_ids) if course_ids else 1
            cursor.execute('''
                INSERT INTO study_plans (student_id, course_id, title, topics, activities, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, course_id, title, topics, activities, status, datetime.now()))
        
        print(f"Created {len(plans)} study plans")
        conn.commit()
        
        # ==================== CAREER PROFILES ====================
        print("\n--- Seeding Career Profiles ---")
        # Check actual columns
        cursor.execute("PRAGMA table_info(career_profiles)")
        cols = [c[1] for c in cursor.fetchall()]
        print(f"Career profiles columns: {cols}")
        
        career_goals_list = [
            "Software Developer", "Data Scientist", "Web Developer", "ML Engineer", "DBA",
            "DevOps Engineer", "Full Stack Dev", "Mobile Dev", "Cloud Architect", "Security Analyst"
        ]
        
        for i in range(10):
            student_id = student_ids[i] if i < len(student_ids) else 1
            if 'career_goals' in cols:
                cursor.execute('''
                    INSERT OR IGNORE INTO career_profiles (student_id, career_goals, interests, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (student_id, career_goals_list[i], "Technology", datetime.now()))
            else:
                cursor.execute('''
                    INSERT OR IGNORE INTO career_profiles (student_id, career_goal, interests, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (student_id, career_goals_list[i], "Technology", datetime.now()))
        
        print(f"Created 10 career profiles")
        conn.commit()
        
        # ==================== CVS ====================
        print("\n--- Seeding CVs ---")
        summaries = [
            "Computer Science graduate", "Web developer", "Data science enthusiast",
            "Software engineering student", "Full stack developer", "Mobile app developer",
            "Cloud computing specialist", "ML student", "Database admin", "Security aspirant"
        ]
        
        for i in range(10):
            student_id = student_ids[i] if i < len(student_ids) else 1
            cursor.execute('''
                INSERT OR IGNORE INTO cvs (student_id, title, summary, education, experience, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, f"CV {i+1}", summaries[i], "BS Computer Science", "Internship", datetime.now()))
        
        print(f"Created 10 CVs")
        conn.commit()
        
        # ==================== PROJECTS ====================
        print("\n--- Seeding Projects ---")
        projects = [
            ("E-commerce Website", "Full platform", "Python, Django"),
            ("Weather App", "Real-time app", "JavaScript, API"),
            ("Chat Application", "Real-time chat", "Node.js, Socket.io"),
            ("Portfolio Website", "Personal site", "HTML, CSS, JS"),
            ("ML Model", "Prediction model", "Python, TensorFlow"),
            ("Mobile App", "Task app", "React Native"),
            ("Database System", "Inventory DB", "PostgreSQL"),
            ("Game Development", "2D game", "Unity, C#"),
            ("Web Scraper", "Data extraction", "Python, BeautifulSoup"),
            ("API Integration", "Third-party API", "REST, JSON")
        ]
        
        for i in range(10):
            student_id = student_ids[i] if i < len(student_ids) else 1
            cursor.execute('''
                INSERT OR IGNORE INTO projects (student_id, title, description, technologies_used, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (student_id, projects[i][0], projects[i][1], projects[i][2], datetime.now()))
        
        print(f"Created 10 projects")
        conn.commit()
        
        # ==================== SKILLS ====================
        print("\n--- Seeding Skills ---")
        skills_list = [
            "Python", "JavaScript", "HTML/CSS", "SQL", "Java",
            "React", "Node.js", "Git", "Linux", "Docker"
        ]
        
        for i in range(10):
            student_id = student_ids[i] if i < len(student_ids) else 1
            skill = skills_list[i] if i < len(skills_list) else "Python"
            cursor.execute('''
                INSERT OR IGNORE INTO skills (student_id, skill_name, proficiency_level, created_at)
                VALUES (?, ?, ?, ?)
            ''', (student_id, skill, "intermediate", datetime.now()))
        
        print(f"Created skills")
        conn.commit()
        
        # ==================== JOB RECOMMENDATIONS ====================
        print("\n--- Seeding Job Recommendations ---")
        jobs = [
            ("Software Developer", "Tech Corp", "Develop software", "CS degree"),
            ("Web Developer", "Web Solutions", "Build websites", "Web tech"),
            ("Data Analyst", "Data Insights", "Analyze data", "SQL, Python"),
            ("ML Engineer", "AI Labs", "ML models", "ML knowledge"),
            ("QA Engineer", "Quality First", "Test apps", "Testing"),
            ("DevOps Engineer", "Cloud Systems", "Infrastructure", "Cloud"),
            ("Mobile Developer", "App Makers", "Create apps", "Mobile"),
            ("DBA", "Data Systems", "Manage DBs", "Database"),
            ("Security Analyst", "SecureTech", "Security", "Security"),
            ("Product Manager", "Product Co", "Products", "Business")
        ]
        
        for i in range(10):
            student_id = random.choice(student_ids) if student_ids else 1
            cursor.execute('''
                INSERT INTO job_recommendations (student_id, job_title, company, description, requirements, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, jobs[i][0], jobs[i][1], jobs[i][2], jobs[i][3], datetime.now()))
        
        print(f"Created {len(jobs)} job recommendations")
        conn.commit()
        
        # ==================== INTERVIEW QUESTIONS ====================
        print("\n--- Seeding Interview Questions ---")
        questions = [
            ("Tell me about yourself", "I am motivated...", "General"),
            ("Why work here?", "Your company...", "Company"),
            ("Your strengths?", "Quick learner...", "Skills"),
            ("Challenging project", "Web app project...", "Experience"),
            ("5 year plan", "Lead developer...", "Career"),
            ("Weakness", "Time management...", "General"),
            ("Why hire you?", "I bring skills...", "General"),
            ("Handle stress", "Prioritize tasks...", "Behavioral"),
            ("Conflict", "Resolved issue...", "Behavioral"),
            ("Questions for us", "Team culture?", "Company")
        ]
        
        for i in range(10):
            student_id = random.choice(student_ids) if student_ids else 1
            cursor.execute('''
                INSERT INTO interview_questions (student_id, job_field, question, ideal_answer, practice_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, questions[i][2], questions[i][0], questions[i][1], 0, datetime.now()))
        
        print(f"Created {len(questions)} interview questions")
        conn.commit()
        
        # ==================== STUDENT PERFORMANCE ====================
        print("\n--- Seeding Student Performance ---")
        
        for i in range(10):
            student_id = random.choice(student_ids) if student_ids else 1
            cursor.execute('''
                INSERT INTO student_performance (student_id, module_id, quiz_id, average_score, total_quizzes, easy_count, medium_count, hard_count, recommended_difficulty, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, random.choice(module_ids) if module_ids else None, 
                  random.choice(quiz_ids) if quiz_ids else None,
                  random.randint(60, 95), random.randint(3, 10), 
                  random.randint(1, 5), random.randint(1, 5), random.randint(1, 3), 
                  "medium", datetime.now()))
        
        print(f"Created 10 student performance records")
        conn.commit()
        
        # ==================== MODULE REQUESTS ====================
        print("\n--- Seeding Module Requests ---")
        cursor.execute("SELECT id FROM modules LIMIT 20")
        module_ids = [row['id'] for row in cursor.fetchall()]
        
        statuses = ["pending", "approved", "rejected"]
        
        for i in range(10):
            lecturer_id = random.choice(teacher_ids) if teacher_ids else 1
            module_id = random.choice(module_ids) if module_ids else 1
            cursor.execute('''
                INSERT INTO module_requests (module_id, lecturer_id, status, request_message, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (module_id, lecturer_id, random.choice(statuses), "Please assign me to this module", datetime.now()))
        
        print(f"Created 10 module requests")
        conn.commit()
        
        print("\n" + "=" * 60)
        print("ALL TABLES SEEDED SUCCESSFULLY!")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error seeding tables: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    seed_all_tables()
