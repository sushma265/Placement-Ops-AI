import sys
import os
import csv
import re
import secrets
import string
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import text
from dotenv import load_dotenv

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Direct Supabase database connection (bypasses pgBouncer session hangs)
db_url = os.environ.get("DATABASE_URL", "")
if "pooler.supabase.com" in db_url:
    db_url = db_url.replace("postgres.fvnwqeumcxifqjqovemg:", "postgres:")
    db_url = re.sub(r'@[^/]+', '@db.fvnwqeumcxifqjqovemg.supabase.co:5432', db_url)
    os.environ["DATABASE_URL"] = db_url

from backend.database import SessionLocal, engine
from backend.models import Student, ProfileRole

DEFAULT_CSV_PATH = r"C:\Users\valla\.gemini\antigravity-ide\brain\48d54ed8-ef98-459c-9ad0-c5dd32383549\.user_uploaded\media_1789148464295.csv"
CREDENTIALS_OUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "student_auth_credentials.csv")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://fvnwqeumcxifqjqovemg.supabase.co").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

def generate_secure_password(length=14):
    """Generate a random password with uppercase, lowercase, digits, and special chars."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in "!@#$%^&*" for c in password)):
            return password

def clean_val(val):
    if not val:
        return ""
    val = str(val).strip()
    if val.upper() in ["NA", "N/A", "NONE", "NULL", "-"]:
        return ""
    return val

def create_supabase_auth_user(email, password, metadata):
    """Create Auth user via official Supabase Auth Admin API endpoint."""
    if not SUPABASE_SERVICE_ROLE_KEY:
        return None, "SUPABASE_SERVICE_ROLE_KEY not configured"

    admin_url = f"{SUPABASE_URL}/auth/v1/admin/users"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": metadata
    }

    try:
        resp = requests.post(admin_url, json=payload, headers=headers, timeout=15)
        if resp.status_code in [200, 201]:
            data = resp.json()
            return data.get("id"), None
        else:
            err_msg = resp.text
            return None, f"HTTP {resp.status_code}: {err_msg}"
    except Exception as e:
        return None, str(e)

def run_import(csv_path):
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at: {csv_path}")
        sys.exit(1)

    print(f"Reading student CSV from: {csv_path}")
    print(f"Supabase Endpoint: {SUPABASE_URL}")
    if not SUPABASE_SERVICE_ROLE_KEY:
        print("\n[WARNING] SUPABASE_SERVICE_ROLE_KEY is not set in environment or backend/.env.")
        print("Existing Auth users will be matched and linked, but new Auth user creation requires SUPABASE_SERVICE_ROLE_KEY.\n")

    db = SessionLocal()

    metrics = {
        "csv_students": 0,
        "existing_auth_users": 0,
        "new_auth_created": 0,
        "already_linked": 0,
        "missing_student_records": 0,
        "conflicts": 0,
        "failed": 0,
        "public_students_linked": 0
    }

    credentials_rows = []

    try:
        # Pre-fetch existing auth.users from database
        print("Pre-fetching existing Supabase Auth users...")
        auth_users_raw = db.execute(text("SELECT id, email FROM auth.users")).fetchall()
        existing_auth_by_email = {r[1].lower(): str(r[0]) for r in auth_users_raw if r[1]}
        existing_auth_by_id = {str(r[0]): r[1].lower() for r in auth_users_raw}
        print(f"Found {len(existing_auth_by_email)} existing Auth users in Supabase.")

        # Pre-fetch existing public.students
        print("Pre-fetching existing public.students records...")
        all_students = db.query(Student).all()
        student_by_roll = {s.roll_number.upper(): s for s in all_students if s.roll_number}
        student_by_email = {s.email.lower(): s for s in all_students if s.email}
        print(f"Found {len(all_students)} student records in public.students.")

        # Pre-fetch existing profile_roles
        all_roles = db.query(ProfileRole).all()
        existing_roles = {r.profile_id for r in all_roles}

        # Parse CSV
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            raw_lines = list(csv.reader(f))

        header_idx = -1
        inferred_branch = "CSE"

        for idx, row in enumerate(raw_lines):
            row_str = " ".join(row).upper()
            if "DEPARTMENT OF CSE" in row_str or "COMPUTER SCIENCE" in row_str:
                inferred_branch = "CSE"
            if any("ROLL" in cell.upper() for cell in row) and any("NAME" in cell.upper() for cell in row):
                header_idx = idx
                break

        if header_idx == -1:
            print("Error: Could not find header row in CSV.")
            sys.exit(1)

        headers = [c.strip().upper().replace(" ", "_") for c in raw_lines[header_idx]]
        roll_col = next((i for i, h in enumerate(headers) if "ROLL" in h), None)
        name_col = next((i for i, h in enumerate(headers) if "NAME" in h), None)
        email_col = next((i for i, h in enumerate(headers) if "EMAIL" in h), None)
        sec_col = next((i for i, h in enumerate(headers) if "SEC" in h or h == "S"), None)
        main_col = next((i for i, h in enumerate(headers) if h in ["MAIN", "BRANCH", "DEPARTMENT"]), None)

        data_rows = raw_lines[header_idx + 1:]

        tasks = []

        for row in data_rows:
            if not row or not any(row):
                continue

            roll_num = clean_val(row[roll_col]) if roll_col is not None and roll_col < len(row) else ""
            name = clean_val(row[name_col]) if name_col is not None and name_col < len(row) else ""
            raw_email = clean_val(row[email_col]) if email_col is not None and email_col < len(row) else ""
            section = clean_val(row[sec_col]) if sec_col is not None and sec_col < len(row) else ""
            branch = clean_val(row[main_col]) if main_col is not None and main_col < len(row) else inferred_branch

            if not branch:
                branch = inferred_branch

            if not roll_num and not raw_email and not name:
                continue

            metrics["csv_students"] += 1

            roll_num_upper = roll_num.upper()
            email = raw_email.lower() if raw_email else f"{roll_num_upper.lower()}@student.placera.ai"

            # Match student record in public.students
            student = None
            if roll_num_upper and roll_num_upper in student_by_roll:
                student = student_by_roll[roll_num_upper]
            elif email and email in student_by_email:
                student = student_by_email[email]

            if not student:
                metrics["missing_student_records"] += 1
                continue

            # Check if student.profile_id is already linked to a valid Auth user
            if student.profile_id and student.profile_id in existing_auth_by_id:
                metrics["already_linked"] += 1
                metrics["existing_auth_users"] += 1
                # Ensure profile_roles entry exists
                if student.profile_id not in existing_roles:
                    db.add(ProfileRole(profile_id=student.profile_id, email=student.email, role="student"))
                    existing_roles.add(student.profile_id)
                continue

            # Check if user already exists in auth.users by email
            if email in existing_auth_by_email:
                auth_id = existing_auth_by_email[email]
                student.profile_id = auth_id
                metrics["existing_auth_users"] += 1
                metrics["public_students_linked"] += 1
                if auth_id not in existing_roles:
                    db.add(ProfileRole(profile_id=auth_id, email=email, role="student"))
                    existing_roles.add(auth_id)
                continue

            # Prepare for new Auth user creation
            tasks.append({
                "student": student,
                "roll_number": roll_num_upper,
                "name": name if name else student.name,
                "email": email,
                "branch": branch,
                "section": section if section else student.section
            })

        print(f"Students ready for Auth creation: {len(tasks)}")

        if tasks and SUPABASE_SERVICE_ROLE_KEY:
            def process_task(item):
                temp_pwd = generate_secure_password()
                meta = {
                    "name": item["name"],
                    "roll_number": item["roll_number"],
                    "branch": item["branch"],
                    "section": item["section"],
                    "role": "student"
                }
                auth_id, err = create_supabase_auth_user(item["email"], temp_pwd, meta)
                return item, temp_pwd, auth_id, err

            print("Creating Supabase Auth users concurrently...")
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(process_task, task) for task in tasks]
                for future in as_completed(futures):
                    item, temp_pwd, auth_id, err = future.result()
                    if auth_id:
                        student = item["student"]
                        student.profile_id = auth_id
                        metrics["new_auth_created"] += 1
                        metrics["public_students_linked"] += 1
                        existing_auth_by_email[item["email"]] = auth_id
                        existing_auth_by_id[auth_id] = item["email"]

                        if auth_id not in existing_roles:
                            db.add(ProfileRole(profile_id=auth_id, email=item["email"], role="student"))
                            existing_roles.add(auth_id)

                        credentials_rows.append([
                            item["roll_number"],
                            item["name"],
                            item["email"],
                            temp_pwd,
                            auth_id
                        ])
                    else:
                        metrics["failed"] += 1
                        if len(credentials_rows) < 3:
                            print(f"Failed to create auth for {item['email']}: {err}")
        elif tasks and not SUPABASE_SERVICE_ROLE_KEY:
            print("\n[NOTE] Skipped creating new Auth users because SUPABASE_SERVICE_ROLE_KEY was not supplied.")
            metrics["failed"] += len(tasks)

        db.commit()

        # Write credentials CSV
        if credentials_rows:
            with open(CREDENTIALS_OUT_PATH, mode="w", newline="", encoding="utf-8") as out_f:
                writer = csv.writer(out_f)
                writer.writerow(["roll_number", "name", "email", "temporary_password", "auth_user_id"])
                writer.writerows(credentials_rows)
            print(f"\nCredentials saved securely to: {CREDENTIALS_OUT_PATH}")

        print("\n========================================")
        print("     STUDENT AUTH IMPORT COMPLETE       ")
        print("========================================")
        print(f"CSV students             : {metrics['csv_students']}")
        print(f"Existing Auth users      : {metrics['existing_auth_users']}")
        print(f"New Auth users created   : {metrics['new_auth_created']}")
        print(f"Already linked           : {metrics['already_linked']}")
        print(f"Missing student records  : {metrics['missing_student_records']}")
        print(f"Conflicts                : {metrics['conflicts']}")
        print(f"Failed                   : {metrics['failed']}")
        print("----------------------------------------")
        print(f"Public students linked   : {metrics['public_students_linked'] + metrics['already_linked']}")
        print("========================================\n")

    except Exception as e:
        db.rollback()
        print(f"Error during Auth import: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV_PATH
    run_import(csv_file)
