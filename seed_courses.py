"""
EduMind Course Seed Script
Replaces existing courses with 10 new courses (10 modules each)
"""

import sqlite3
from datetime import datetime

DB_NAME = 'edumind.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def clear_courses_and_modules():
    """Delete all existing courses and modules"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Delete in correct order (respecting foreign keys)
    cursor.execute('DELETE FROM module_materials')
    cursor.execute('DELETE FROM modules')
    cursor.execute('DELETE FROM course_materials')
    cursor.execute('DELETE FROM enrollments')
    cursor.execute('DELETE FROM courses')
    
    conn.commit()
    conn.close()
    print("Cleared all existing courses, modules, and enrollments")

def seed_new_courses():
    """Create 10 new courses with 10 modules each"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get a teacher ID to assign courses to
    cursor.execute("SELECT id FROM users WHERE role = 'teacher' LIMIT 1")
    teacher_row = cursor.fetchone()
    if not teacher_row:
        # Try lecturer
        cursor.execute("SELECT id FROM users WHERE role = 'lecturer' LIMIT 1")
        teacher_row = cursor.fetchone()
    
    if not teacher_row:
        print("No teacher/lecturer found! Please create users first.")
        return
    
    teacher_id = teacher_row[0]
    print(f"Using teacher ID: {teacher_id}")
    
    # Course data structure: 10 courses with 10 modules each
    courses_data = [
        {
            "title": "Computer Science",
            "description": "Comprehensive computer science program covering programming, algorithms, and systems",
            "subject": "Computer Science",
            "course_code": "CS",
            "modules": [
                "Programming Fundamentals – Basics of programming in Python, variables, loops, functions.",
                "Data Structures – Arrays, linked lists, stacks, queues, trees.",
                "Algorithms – Sorting, searching, recursion, algorithm complexity.",
                "Databases – SQL, normalization, ER diagrams, transactions.",
                "Operating Systems – Processes, threads, memory management.",
                "Networking – TCP/IP, protocols, network layers.",
                "Software Engineering – SDLC, design patterns, testing.",
                "Web Development – HTML, CSS, JavaScript, front-end frameworks.",
                "Artificial Intelligence – Machine learning, neural networks, AI ethics.",
                "Cybersecurity – Threats, encryption, network security basics."
            ]
        },
        {
            "title": "Information Technology",
            "description": "IT fundamentals including networking, system administration, and emerging technologies",
            "subject": "Information Technology",
            "course_code": "IT",
            "modules": [
                "IT Fundamentals – Hardware, software, and system basics.",
                "Networking Fundamentals – LAN, WAN, routing, switching.",
                "System Administration – Linux, Windows, server management.",
                "Database Management – MySQL, Oracle, database design.",
                "Cloud Computing – AWS, Azure basics, virtualization.",
                "IT Project Management – Planning, risk management, tools.",
                "Web Development – Front-end & back-end technologies.",
                "Mobile Application Development – Android, iOS, hybrid apps.",
                "Cybersecurity Essentials – Firewalls, malware, security policies.",
                "Emerging Technologies – IoT, AI, blockchain overview."
            ]
        },
        {
            "title": "Mechanical Engineering",
            "description": "Mechanical engineering principles from mechanics to robotics",
            "subject": "Mechanical Engineering",
            "course_code": "ME",
            "modules": [
                "Mechanics – Statics, dynamics, forces.",
                "Thermodynamics – Heat, energy, engines.",
                "Materials Science – Metals, polymers, composites.",
                "Fluid Mechanics – Flow, hydraulics, pumps.",
                "Manufacturing Processes – Machining, casting, welding.",
                "CAD/CAM – Design and manufacturing software.",
                "Mechanical Vibrations – Oscillations, damping.",
                "Heat Transfer – Conduction, convection, radiation.",
                "Robotics – Kinematics, sensors, actuators.",
                "Mechatronics – Integration of mechanical, electrical, control systems."
            ]
        },
        {
            "title": "Electrical Engineering",
            "description": "Electrical engineering covering circuits, power systems, and electronics",
            "subject": "Electrical Engineering",
            "course_code": "EE",
            "modules": [
                "Circuits & Electronics – Ohm's law, resistors, capacitors.",
                "Signals & Systems – Fourier, Laplace, system modeling.",
                "Power Systems – Generation, transmission, distribution.",
                "Control Systems – Feedback, PID controllers.",
                "Digital Electronics – Logic gates, flip-flops, microcontrollers.",
                "Electrical Machines – Motors, transformers, generators.",
                "Renewable Energy – Solar, wind, hydro fundamentals.",
                "Instrumentation – Sensors, measurement devices.",
                "Communication Systems – Modulation, transmission.",
                "Embedded Systems – Microcontroller programming, IoT devices."
            ]
        },
        {
            "title": "Civil Engineering",
            "description": "Civil engineering from structural analysis to construction management",
            "subject": "Civil Engineering",
            "course_code": "CE",
            "modules": [
                "Engineering Mechanics – Statics, dynamics, material forces.",
                "Structural Analysis – Beams, trusses, load calculations.",
                "Concrete Technology – Properties, mix design.",
                "Surveying – Measurement techniques, GPS mapping.",
                "Geotechnical Engineering – Soil mechanics, foundations.",
                "Construction Management – Planning, scheduling, cost control.",
                "Water Resources Engineering – Hydrology, dams, canals.",
                "Transportation Engineering – Roads, traffic, highways.",
                "Environmental Engineering – Waste, pollution control.",
                "CAD for Civil Engineering – AutoCAD, Revit basics."
            ]
        },
        {
            "title": "Business Administration",
            "description": "Business management covering marketing, finance, and operations",
            "subject": "Business Administration",
            "course_code": "BA",
            "modules": [
                "Principles of Management – Planning, organizing, leading.",
                "Marketing Fundamentals – Product, price, promotion, place.",
                "Accounting – Financial statements, bookkeeping.",
                "Finance – Investments, corporate finance basics.",
                "Human Resource Management – Recruitment, training, appraisal.",
                "Operations Management – Supply chain, production planning.",
                "Business Law – Contracts, company law basics.",
                "Entrepreneurship – Start-ups, business plans.",
                "Strategic Management – SWOT, competitive strategy.",
                "Business Ethics – Corporate responsibility, ethics in decision making."
            ]
        },
        {
            "title": "Electrical & Electronics Engineering",
            "description": "Electrical and electronics engineering covering circuits and power electronics",
            "subject": "Electrical & Electronics Engineering",
            "course_code": "EEE",
            "modules": [
                "Circuit Theory – AC/DC circuits, Thevenin & Norton.",
                "Digital Systems – Logic circuits, microprocessors.",
                "Power Electronics – Converters, inverters.",
                "Control Engineering – Feedback systems, controllers.",
                "Communication Engineering – Signal processing, transmission.",
                "Instrumentation & Measurements – Sensors, transducers.",
                "Embedded Systems – Microcontroller interfacing.",
                "Electrical Machines – Motors, transformers, generators.",
                "Renewable Energy Systems – Solar, wind, hybrid systems.",
                "Robotics & Automation – Industrial robots, PLC basics."
            ]
        },
        {
            "title": "Software Engineering",
            "description": "Software engineering from development lifecycle to deployment",
            "subject": "Software Engineering",
            "course_code": "SE",
            "modules": [
                "Software Development Life Cycle – Requirements to maintenance.",
                "Programming Principles – OOP, procedural programming.",
                "Web Development – HTML, CSS, JS, frameworks.",
                "Database Systems – SQL, relational databases, NoSQL overview.",
                "Mobile App Development – Android & iOS basics.",
                "Software Testing – Unit, integration, system testing.",
                "DevOps & Deployment – CI/CD, Docker basics.",
                "Cloud Computing – AWS, Azure, cloud services.",
                "Artificial Intelligence – ML basics, algorithms.",
                "Cybersecurity – Security principles, secure coding."
            ]
        },
        {
            "title": "Data Science",
            "description": "Data science from Python programming to machine learning",
            "subject": "Data Science",
            "course_code": "DS",
            "modules": [
                "Introduction to Data Science – Overview & tools.",
                "Python for Data Science – Pandas, NumPy, Matplotlib.",
                "Statistics & Probability – Descriptive & inferential stats.",
                "Data Wrangling – Cleaning and preprocessing.",
                "Data Visualization – Charts, dashboards, Plotly/Seaborn.",
                "Machine Learning – Regression, classification, clustering.",
                "Deep Learning – Neural networks, TensorFlow basics.",
                "Natural Language Processing – Text analytics, tokenization.",
                "Big Data – Hadoop, Spark basics.",
                "Data Ethics & Governance – Privacy, bias, regulations."
            ]
        },
        {
            "title": "Artificial Intelligence",
            "description": "AI from fundamentals to neural networks and robotics",
            "subject": "Artificial Intelligence",
            "course_code": "AI",
            "modules": [
                "AI Fundamentals – History, AI applications, search algorithms.",
                "Python for AI – Programming basics, libraries.",
                "Machine Learning – Supervised & unsupervised learning.",
                "Deep Learning – Neural networks, CNNs, RNNs.",
                "Natural Language Processing – Text processing, sentiment analysis.",
                "Computer Vision – Image recognition, object detection.",
                "Reinforcement Learning – Markov decision processes, Q-learning.",
                "AI Ethics – Bias, fairness, explainable AI.",
                "AI in Robotics – Automation, sensors, actuators.",
                "AI Project Lab – Capstone AI project integrating learned skills."
            ]
        }
    ]
    
    course_ids = []
    
    for course_data in courses_data:
        try:
            cursor.execute('''
                INSERT INTO courses (title, description, subject, course_code, teacher_id, is_published, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (course_data['title'], course_data['description'], course_data['subject'], 
                  course_data['course_code'], teacher_id, 1, datetime.now()))
            course_id = cursor.lastrowid
            course_ids.append(course_id)
            print(f"Created course: {course_data['title']} (ID: {course_id})")
            
            # Create 10 modules for this course
            for j, module_title in enumerate(course_data['modules']):
                # Split module into title and description if contains "–"
                if '–' in module_title:
                    parts = module_title.split('–', 1)
                    title = parts[0].strip()
                    description = parts[1].strip()
                else:
                    title = module_title
                    description = ""
                
                module_code = f"{course_data['course_code']}-M{j+1:02d}"
                cursor.execute('''
                    INSERT INTO modules (course_id, title, description, code, chapter_number, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (course_id, title, description, module_code, j+1, 1, datetime.now()))
                module_id = cursor.lastrowid
                print(f"  - Module {j+1}: {title}")
            
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Error creating course {course_data['title']}: {e}")
            conn.rollback()
    
    conn.close()
    return course_ids

def main():
    print("=" * 60)
    print("Replacing courses with new curriculum...")
    print("=" * 60)
    
    # Clear existing data
    print("\n--- Clearing existing courses and modules ---")
    clear_courses_and_modules()
    
    # Create new courses
    print("\n--- Creating new courses and modules ---")
    course_ids = seed_new_courses()
    
    print("\n" + "=" * 60)
    print("Course seeding complete!")
    print("=" * 60)
    print(f"\nTotal Courses: {len(course_ids)}")
    print(f"Total Modules: {len(course_ids) * 10}")

if __name__ == '__main__':
    main()
