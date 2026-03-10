"""Check table counts in the database"""
import sqlite3
import sys

DB_FILE = 'edumind.db'

def check_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print("=" * 50)
    print("TABLE COUNTS")
    print("=" * 50)
    
    low_tables = []
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        status = "OK" if count >= 10 else "LOW"
        print(f"{status} {table_name}: {count}")
        if count < 10:
            low_tables.append((table_name, count))
    
    print("=" * 50)
    if low_tables:
        print(f"\nTABLES WITH LESS THAN 10 RECORDS:")
        for table_name, count in low_tables:
            print(f"  - {table_name}: {count}")
    else:
        print("\nAll tables have 10+ records!")
    
    conn.close()

if __name__ == '__main__':
    check_tables()
