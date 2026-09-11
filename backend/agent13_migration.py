import os
import sys
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sqlalchemy import text
from backend.database import engine

def migrate():
    with engine.begin() as conn:
        print("Creating agentops schema if not exists...")
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS agentops;"))

        print("Dropping existing studentlife.resume_claim table...")
        conn.execute(text("DROP TABLE IF EXISTS studentlife.resume_claim CASCADE;"))
        
        print("Creating new studentlife.resume_claim table...")
        conn.execute(text("""
            CREATE TABLE studentlife.resume_claim (
                resume_claim_id VARCHAR PRIMARY KEY,
                student_id INTEGER NOT NULL REFERENCES public.students(id),
                claim_type VARCHAR NOT NULL,
                claim_text TEXT NOT NULL,
                normalized_skill VARCHAR,
                source_document_id VARCHAR,
                extraction_confidence FLOAT,
                verification_status VARCHAR DEFAULT 'PROVISIONAL',
                verified_by VARCHAR REFERENCES public.profile_roles(profile_id),
                verified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        print("Creating agentops.agent13_recommendation table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agentops.agent13_recommendation (
                recommendation_id VARCHAR PRIMARY KEY,
                student_id INTEGER NOT NULL REFERENCES public.students(id),
                opportunity_id VARCHAR NOT NULL,
                opportunity_type VARCHAR NOT NULL,
                status VARCHAR DEFAULT 'DISCOVERED',
                hidden_talent BOOLEAN DEFAULT FALSE,
                hidden_talent_explanation TEXT,
                fit_score FLOAT DEFAULT 0.0,
                evidence_breakdown JSON DEFAULT '{}'::json,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        # Add unique constraint to project_member
        print("Adding unique constraint to research.project_member...")
        try:
            conn.execute(text("""
                ALTER TABLE research.project_member 
                ADD CONSTRAINT uq_project_member UNIQUE (student_id, project_id);
            """))
        except Exception as e:
            print(f"Constraint might already exist: {e}")

    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
