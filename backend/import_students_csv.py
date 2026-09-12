import sys
import os
import csv
import re
from sqlalchemy import text
from dotenv import load_dotenv

# Ensure backend directory is in path and env loaded
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# Supabase direct connection (direct hostname avoids pgBouncer session hangs)
db_url = os.environ.get("DATABASE_URL", "")
if "pooler.supabase.com" in db_url:
    # Direct host uses user 'postgres' instead of pooler format 'postgres.tenant'
    db_url = db_url.replace("postgres.fvnwqeumcxifqjqovemg:", "postgres:")
    db_url = re.sub(r'@[^/]+', '@db.fvnwqeumcxifqjqovemg.supabase.co:5432', db_url)
    os.environ["DATABASE_URL"] = db_url

from backend.database import SessionLocal
from backend.models import Student, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create dedicated engine with use_native_hstore=False to avoid psycopg2 OID lookup hang on Supabase
engine = create_engine(db_url, use_native_hstore=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

DEFAULT_CSV_PATH = r"C:\Users\valla\.gemini\antigravity-ide\brain\48d54ed8-ef98-459c-9ad0-c5dd32383549\.user_uploaded\media_1789148464295.csv"

def ensure_columns_exist():
    """Ensure roll_number and section columns exist in the database table."""
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE public.students ADD COLUMN IF NOT EXISTS roll_number VARCHAR;"))
        conn.execute(text("ALTER TABLE public.students ADD COLUMN IF NOT EXISTS section VARCHAR;"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_students_roll_number ON public.students (roll_number) WHERE roll_number IS NOT NULL;"))
        conn.commit()
    print("Database: Columns roll_number and section verified/added in public.students.")

def clean_value(val):
    if not val:
        return ""
    val = val.strip()
    if val.upper() in ["NA", "N/A", "NONE", "NULL", "-"]:
        return ""
    return val

def import_csv(csv_path):
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at: {csv_path}")
        sys.exit(1)

    print(f"Reading CSV from: {csv_path}")
    ensure_columns_exist()

    db = SessionLocal()

    total_rows = 0
    new_inserted = 0
    existing_updated = 0
    skipped_count = 0
    duplicates_prevented = 0

    seen_roll_numbers = set()
    sample_records = []

    try:
        # Pre-fetch existing students to avoid N+1 network queries over remote database connection
        print("Pre-fetching existing student records from database...")
        all_students = db.query(Student).all()
        by_roll = {s.roll_number.upper(): s for s in all_students if s.roll_number}
        by_email = {s.email.lower(): s for s in all_students if s.email}
        existing_emails_set = set(by_email.keys())

        print(f"Found {len(all_students)} existing student records in database.")

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            raw_lines = list(reader)

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
            print("Error: Could not find header row containing ROLL_NUMBER and NAME.")
            sys.exit(1)

        headers = [c.strip().upper().replace(" ", "_") for c in raw_lines[header_idx]]
        print(f"Found headers at row {header_idx + 1}: {headers}")
        print(f"Inferred Branch: {inferred_branch}")

        roll_col = next((i for i, h in enumerate(headers) if "ROLL" in h), None)
        name_col = next((i for i, h in enumerate(headers) if "NAME" in h), None)
        email_col = next((i for i, h in enumerate(headers) if "EMAIL" in h), None)
        sec_col = next((i for i, h in enumerate(headers) if "SEC" in h or h == "S"), None)
        main_col = next((i for i, h in enumerate(headers) if h in ["MAIN", "BRANCH", "DEPARTMENT"]), None)

        data_rows = raw_lines[header_idx + 1:]

        for row in data_rows:
            if not row or not any(row):
                continue

            roll_num = clean_value(row[roll_col]) if roll_col is not None and roll_col < len(row) else ""
            name = clean_value(row[name_col]) if name_col is not None and name_col < len(row) else ""
            raw_email = clean_value(row[email_col]) if email_col is not None and email_col < len(row) else ""
            section = clean_value(row[sec_col]) if sec_col is not None and sec_col < len(row) else ""
            branch = clean_value(row[main_col]) if main_col is not None and main_col < len(row) else inferred_branch

            if not branch:
                branch = inferred_branch

            if not roll_num and not raw_email and not name:
                skipped_count += 1
                continue

            total_rows += 1
            roll_num_upper = roll_num.upper() if roll_num else ""

            # Check duplicate within file
            if roll_num_upper and roll_num_upper in seen_roll_numbers:
                duplicates_prevented += 1
            elif roll_num_upper:
                seen_roll_numbers.add(roll_num_upper)

            email = raw_email.lower() if raw_email else ""

            # In-memory matching
            student = None
            if roll_num_upper and roll_num_upper in by_roll:
                student = by_roll[roll_num_upper]
            elif email and email in by_email:
                student = by_email[email]

            if student:
                # Update existing student
                if roll_num_upper and not student.roll_number:
                    student.roll_number = roll_num_upper
                    by_roll[roll_num_upper] = student
                if name:
                    student.name = name
                if section:
                    student.section = section
                if branch:
                    student.branch = branch
                if email and ("placera.ai" in student.email or not student.email):
                    if email not in existing_emails_set or by_email.get(email) == student:
                        student.email = email
                        by_email[email] = student
                        existing_emails_set.add(email)

                existing_updated += 1
                if len(sample_records) < 5:
                    sample_records.append({
                        "action": "UPDATED",
                        "id": student.id,
                        "roll_number": student.roll_number,
                        "name": student.name,
                        "email": student.email,
                        "branch": student.branch,
                        "section": student.section
                    })
            else:
                # Insert new student record
                final_email = email
                if not final_email or final_email in existing_emails_set:
                    base_email = f"{roll_num_upper.lower()}@student.placera.ai" if roll_num_upper else f"student_{total_rows}@student.placera.ai"
                    if base_email in existing_emails_set:
                        final_email = f"{roll_num_upper.lower()}_{total_rows}@student.placera.ai"
                    else:
                        final_email = base_email

                new_student = Student(
                    roll_number=roll_num_upper if roll_num_upper else None,
                    name=name if name else f"Student {roll_num_upper}",
                    email=final_email,
                    branch=branch,
                    section=section if section else None,
                    cgpa=0.0,
                    tenth_pct=0.0,
                    twelfth_pct=0.0,
                    backlog_count=0
                )
                db.add(new_student)
                
                # Update in-memory caches
                if roll_num_upper:
                    by_roll[roll_num_upper] = new_student
                by_email[final_email] = new_student
                existing_emails_set.add(final_email)

                new_inserted += 1

                if len(sample_records) < 5:
                    sample_records.append({
                        "action": "INSERTED",
                        "id": "PENDING",
                        "roll_number": roll_num_upper,
                        "name": new_student.name,
                        "email": new_student.email,
                        "branch": new_student.branch,
                        "section": new_student.section
                    })

        print("Committing changes to database...")
        db.commit()

        print("\n==========================================")
        print("         STUDENT CSV IMPORT METRICS       ")
        print("==========================================")
        print(f"Total Rows Processed   : {total_rows}")
        print(f"New Students Inserted  : {new_inserted}")
        print(f"Existing Updated       : {existing_updated}")
        print(f"Skipped / Invalid      : {skipped_count}")
        print(f"Duplicates Prevented   : {duplicates_prevented}")
        print("==========================================")
        print("\nSample Processed Database Records:")
        for r in sample_records:
            print(f" [{r['action']}] Roll: {r['roll_number']} | Name: {r['name']} | Branch: {r['branch']} | Sec: {r['section']} | Email: {r['email']}")
        print("==========================================\n")

    except Exception as e:
        db.rollback()
        print(f"Error during import: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV_PATH
    import_csv(csv_file)
