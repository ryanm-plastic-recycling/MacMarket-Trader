import sqlite3
from pathlib import Path

db = Path("macmarket_trader.db")
conn = sqlite3.connect(db)
cur = conn.cursor()

rows = cur.execute(
    "SELECT id, email, display_name, approval_status, app_role FROM app_users"
).fetchall()

print("Current users:")
for row in rows:
    print(row)

target_id = input("Enter the user id to update: ").strip()
target_email = input("Enter email to set (leave blank to keep current): ").strip()
target_name = input("Enter display name to set (leave blank to keep current): ").strip()

if target_email:
    cur.execute(
        """
        UPDATE app_users
        SET email = ?
        WHERE id = ?
        """,
        (target_email, target_id),
    )

if target_name:
    cur.execute(
        """
        UPDATE app_users
        SET display_name = ?
        WHERE id = ?
        """,
        (target_name, target_id),
    )

cur.execute(
    """
    UPDATE app_users
    SET approval_status = 'approved',
        app_role = 'admin',
        approved_by = 'bootstrap-local',
        approved_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """,
    (target_id,),
)

conn.commit()

rows = cur.execute(
    "SELECT id, email, display_name, approval_status, app_role FROM app_users WHERE id = ?",
    (target_id,),
).fetchall()

print("Updated user:")
for row in rows:
    print(row)

conn.close()