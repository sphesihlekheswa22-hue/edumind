import sqlite3
conn = sqlite3.connect('edumind.db')
c = conn.cursor()

# Get all students ordered by ID
students = c.execute('SELECT id, username FROM users WHERE role = "student" ORDER BY id').fetchall()
print('Found students:', len(students))

# Update each with student number
for i, (sid, uname) in enumerate(students):
    stu_num = f'STU{i+1:03d}'
    c.execute('UPDATE users SET student_number = ? WHERE id = ?', (stu_num, sid))
    print(f'Updated {uname} (ID {sid}) to {stu_num}')

conn.commit()

# Verify
print('\nVerification:')
rows = c.execute('SELECT username, student_number FROM users WHERE role = "student"').fetchall()
for r in rows:
    print(f'  {r[0]}: {r[1]}')

conn.close()
print('\nDone!')
