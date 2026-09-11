import os
import sys
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import Student, ResumeClaim, Agent13Recommendation, ResearchProject, ProjectRequirement, ProjectMember, ProfileRole
from backend.agents.talent_discovery_agent import TalentDiscoveryAgent

def run_test():
    db = SessionLocal()
    try:
        print("--- Setting up test data ---")
        # 1. Create a fake student
        student = db.query(Student).filter(Student.email == "test_agent13@example.com").first()
        if not student:
            student = Student(
                name="Test Agent13 Student",
                email="test_agent13@example.com",
                branch="CSE",
                cgpa=8.5,
                tenth_pct=90.0,
                twelfth_pct=90.0,
                skills=[{"skill": "Python", "level": "Advanced"}], # Verified institutional evidence
            )
            db.add(student)
            db.commit()
            db.refresh(student)
            print(f"Created student {student.id}")
        else:
            print(f"Using existing student {student.id}")

        # 2. Add PROVISIONAL Resume Claim (as if Agent 64 extracted it)
        db.query(ResumeClaim).filter(ResumeClaim.student_id == student.id).delete()
        claim = ResumeClaim(
            student_id=student.id,
            claim_type="SKILL",
            claim_text="Claims proficiency in Machine Learning",
            normalized_skill="machine learning",
            verification_status="PROVISIONAL",
            extraction_confidence=0.8
        )
        db.add(claim)
        
        # Add REJECTED Resume Claim
        rejected_claim = ResumeClaim(
            student_id=student.id,
            claim_type="SKILL",
            claim_text="Claims proficiency in Rust",
            normalized_skill="rust",
            verification_status="REJECTED",
            extraction_confidence=0.8
        )
        db.add(rejected_claim)
        db.commit()
        print("Inserted PROVISIONAL and REJECTED resume claims.")

        # 3. Create an opportunity (Research Project)
        project = db.query(ResearchProject).filter(ResearchProject.title == "Agent 13 Test Project").first()
        if not project:
            from backend.models import FacultyExpertise
            faculty = db.query(FacultyExpertise).first()
            if not faculty:
                # Add fake faculty
                prof_role = ProfileRole(profile_id="test_faculty_id", email="faculty@example.com", role="faculty")
                db.add(prof_role)
                db.commit()
                faculty = FacultyExpertise(profile_id="test_faculty_id", name="Test Faculty", department="CSE")
                db.add(faculty)
                db.commit()

            project = ResearchProject(
                faculty_id=faculty.faculty_id,
                title="Agent 13 Test Project",
                description="Testing Agent 13",
                status="ACTIVE",
                capacity=5
            )
            db.add(project)
            db.commit()
            db.refresh(project)

            # Add requirements
            req1 = ProjectRequirement(project_id=project.project_id, skill="python", weight=1.0, is_required=True)
            req2 = ProjectRequirement(project_id=project.project_id, skill="machine learning", weight=1.0, is_required=False)
            req3 = ProjectRequirement(project_id=project.project_id, skill="rust", weight=1.0, is_required=False)
            db.add_all([req1, req2, req3])
            db.commit()
            print(f"Created opportunity {project.project_id}")
        else:
            print(f"Using existing opportunity {project.project_id}")

        # --- RUN AGENT 13 ---
        print("\n--- Running Agent 13 Discovery ---")
        db.query(Agent13Recommendation).filter(Agent13Recommendation.student_id == student.id).delete()
        db.commit()
        
        TalentDiscoveryAgent.run_discovery_for_student(db, student.id, "system_test")
        
        # Verify Recommendation created correctly
        rec = db.query(Agent13Recommendation).filter(
            Agent13Recommendation.student_id == student.id,
            Agent13Recommendation.opportunity_id == project.project_id
        ).first()
        
        assert rec is not None, "Agent 13 failed to create a recommendation!"
        print(f"Recommendation created! Fit Score: {rec.fit_score}")
        print(f"Hidden Talent: {rec.hidden_talent}")
        print(f"Evidence Breakdown: {rec.evidence_breakdown}")
        
        # Verify execution safety (unapproved)
        print("\n--- Testing Action Gate (Unapproved) ---")
        try:
            from backend.main import execute_agent13_recommendation, CurrentUser
            execute_agent13_recommendation(rec.recommendation_id, db=db, user=CurrentUser(profile_id="test_faculty_id", role="faculty", email="fac@example.com", name="Test Fac"))
            assert False, "Should have raised exception because recommendation is not approved!"
        except Exception as e:
            if "must be APPROVED" in str(e):
                print("Action Gate blocked execution correctly.")
            else:
                print(f"Unexpected error: {e}")
                
        # Approve and Execute
        print("\n--- Testing Action Gate (Approved) ---")
        rec.status = "APPROVED"
        db.commit()
        
        execute_agent13_recommendation(rec.recommendation_id, db=db, user=CurrentUser(profile_id="test_faculty_id", role="faculty", email="fac@example.com", name="Test Fac"))
        
        member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project.project_id,
            ProjectMember.student_id == student.id
        ).first()
        
        assert member is not None, "Failed to insert into project_member!"
        print("Successfully executed ACT_WITH_APPROVAL and inserted into project_member!")
        
        print("\nALL AGENT 13 END-TO-END TESTS PASSED.")

    except Exception as e:
        print(f"TEST FAILED: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
