"""
OutcomeTrackingAgent: Tracks student participation and outcomes across research assistantships,
funded projects, hackathons, and learning activities.
Statuses: RECOMMENDED -> ASSIGNED -> ACCEPTED -> IN_PROGRESS -> COMPLETED -> DROPPED.
When COMPLETED, automatically converts the outcome into VERIFIED evidence and recalculates
the student's Agent 13 multidimensional profile (closed feedback loop!).
"""

import logging
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.models import ProjectMember, ResearchProject, ResumeClaim, AuditLog, Student

logger = logging.getLogger(__name__)

VALID_STATUSES = {"RECOMMENDED", "ASSIGNED", "ACCEPTED", "IN_PROGRESS", "COMPLETED", "DROPPED"}


class OutcomeTrackingAgent:
    @staticmethod
    def update_participation_status(
        db: Session,
        membership_id: str,
        new_status: str,
        updated_by: str = "TPO/Faculty",
        completion_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Updates project membership status and converts completed projects into verified institutional evidence.
        """
        if new_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of {sorted(VALID_STATUSES)}.")

        member = db.query(ProjectMember).filter(ProjectMember.membership_id == membership_id).first()
        if not member:
            raise ValueError(f"Membership record '{membership_id}' not found.")

        old_status = member.status
        member.status = new_status

        project = db.query(ResearchProject).filter(ResearchProject.project_id == member.project_id).first()
        project_title = project.title if project else "Research Project"

        db.add(AuditLog(
            action="outcome_status_update",
            target_type="project_member",
            target_id=member.student_id,
            performed_by=updated_by,
            details=f"Project '{project_title}' status updated from {old_status} to {new_status}."
        ))

        # Closed Feedback Loop: Convert COMPLETED project into VERIFIED institutional claim
        if new_status == "COMPLETED" and old_status != "COMPLETED":
            claim_text = f"Completed Research Assistantship: {project_title}"
            if completion_notes:
                claim_text += f" ({completion_notes})"

            claim = db.query(ResumeClaim).filter(
                ResumeClaim.student_id == member.student_id,
                ResumeClaim.claim_text == claim_text
            ).first()

            if not claim:
                claim = ResumeClaim(
                    student_id=member.student_id,
                    claim_type="RESEARCH",
                    claim_text=claim_text,
                    normalized_skill="research assistantship",
                    source_document_id=f"research_project:{member.project_id}",
                    extraction_confidence=1.0,
                    verification_status="VERIFIED",  # Verified institutional outcome!
                    verified_by=updated_by,
                    verified_at=datetime.datetime.utcnow()
                )
                db.add(claim)

            # Trigger Agent 13 Profile Recalculation
            from backend.agents.talent_discovery_agent import TalentDiscoveryAgent
            TalentDiscoveryAgent.run_discovery_for_student(db, member.student_id, updated_by)

        db.commit()

        return {
            "membership_id": membership_id,
            "student_id": member.student_id,
            "project_title": project_title,
            "old_status": old_status,
            "new_status": new_status,
            "updated_at": datetime.datetime.utcnow()
        }

    @staticmethod
    def get_student_outcomes(db: Session, student_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves all outcome tracking history for a student.
        """
        memberships = db.query(ProjectMember, ResearchProject).join(
            ResearchProject, ProjectMember.project_id == ResearchProject.project_id
        ).filter(ProjectMember.student_id == student_id).all()

        outcomes = []
        for mem, proj in memberships:
            outcomes.append({
                "membership_id": str(mem.membership_id),
                "project_id": str(proj.project_id),
                "title": proj.title,
                "role": mem.role,
                "status": mem.status,
                "assigned_at": mem.assigned_at
            })
        return outcomes
