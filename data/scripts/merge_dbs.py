import sqlite3

TARGET_DB = "../fantasy.db"
SOURCE_DB = "./fantasy.db"

conn = sqlite3.connect(TARGET_DB)
cursor = conn.cursor()

cursor.execute(f"ATTACH DATABASE '{SOURCE_DB}' AS source_db")

tables_to_copy = [
    "leagues",
    "roster_requirements",
    "draft_picks"
]

for table in tables_to_copy:

    cursor.execute(f"""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name='{table}'
    """)

    exists = cursor.fetchone()

    if exists:
        print(f"Skipping {table} (already exists)")
        continue

    print(f"Copying {table}")

    cursor.execute(f"""
        CREATE TABLE {table} AS
        SELECT *
        FROM source_db.{table}
    """)

conn.commit()
cursor.execute("DETACH DATABASE source_db")
conn.close()

print("✅ Merge complete")