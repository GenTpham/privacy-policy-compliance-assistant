import sqlite3
import os

db_path = r'D:\data\code\privacy-policy-compliance-assistant\backend\data\users.db'

conn = sqlite3.connect(db_path)
try:
    # Check if there is a unique index on title
    cursor = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='documents'")
    indexes = cursor.fetchall()
    for name, sql in indexes:
        print(f"Index: {name}, SQL: {sql}")
        if 'title' in sql.lower() and 'unique' in sql.lower():
            print(f"Dropping unique index {name}...")
            conn.execute(f"DROP INDEX {name}")
            print(f"Recreating non-unique index {name}...")
            conn.execute(f"CREATE INDEX {name} ON documents(title)")
            conn.commit()
            print("Done.")
            break
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
