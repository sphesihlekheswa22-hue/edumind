import sqlite3
conn = sqlite3.connect('edumind.db')
c = conn.cursor()

# Get student and course IDs
students = [r[0] for r in c.execute('SELECT id FROM users WHERE role = "student" LIMIT 10').fetchall()]
courses = [r[0] for r in c.execute('SELECT id FROM courses').fetchall()]

print('Students:', students)
print('Courses:', courses)

# Enroll each student in 3 courses
for i, student_id in enumerate(students):
    for j in range(3):
        course_id = courses[(i + j) % len(courses)]
        try:
            c.execute('INSERT INTO enrollments (student_id, course_id, status) VALUES (?, ?, ?)', 
                     (student_id, course_id, 'approved'))
            print(f'Enrolled student {student_id} in course {course_id}')
        except Exception as e:
            print(f'Error: {e}')

conn.commit()
print('Total enrollments:', c.execute('SELECT COUNT(*) FROM enrollments').fetchone()[0])
conn.close()
