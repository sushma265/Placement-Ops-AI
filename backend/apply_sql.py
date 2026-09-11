import os
import sys
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sqlalchemy import create_engine, text

def apply_sql():
    db_url = os.environ.get("DATABASE_URL")
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    print(f"Connecting to: {db_url}")
    engine = create_engine(db_url)
    
    with engine.begin() as conn:
        with open("C:/Users/valla/.gemini/antigravity-ide/brain/48d54ed8-ef98-459c-9ad0-c5dd32383549/agent13_schema.sql", "r") as f:
            sql = f.read()
            
        print("Executing SQL...")
        # Split by semicolon to avoid multiple statements errors in some drivers
        statements = [s.strip() for s in sql.split(';') if s.strip()]
        for stmt in statements:
            if stmt:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    print(f"Error executing statement: {stmt[:50]}... \n{e}")
                    
    print("Schema applied!")

if __name__ == "__main__":
    apply_sql()
