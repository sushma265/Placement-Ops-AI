"""
AchievementVerificationAgent: Handles institutional verification workflow for student
achievements and resume claims. Faculty/TPO review provisional claims and mark them
VERIFIED or REJECTED with full audit tracking. Triggers Agent 13 recalculation upon status change.
"""

import logging
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.models import ResumeClaim, Student, AuditLog

logger = logging.getLogger(__name__)


class AchievementVerificationAgent:
    @staticmethod
    def get_pending_verification_queue(db: Session, branch_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all PROVISIONAL claims awaiting institutional verification by Faculty/TPO.
        """
        query = db.query(ResumeClaim, Student).join(Student, ResumeClaim.student_id == Student.id).filter(
            ResumeClaim.verification_status == "PROVISIONAL"
        )
        if branch_filter:
            query = query.filter(Student.branch == branch_filter)

        claims = query.order_by(ResumeClaim.created_at.desc()).all()

        queue = []
        for claim, student in claims:
            queue.append({
                "claim_id": str(claim.resume_claim_id),
                "student_id": student.id,
                "student_name": student.name,
                "branch": student.branch,
                "cgpa": student.cgpa,
                "claim_type": claim.claim_type,
                "claim_text": claim.claim_text,
                "normalized_skill": claim.normalized_skill,
                "extraction_confidence": claim.extraction_confidence,
                "verification_status": claim.verification_status,
                "created_at": claim.created_at
            })
        return queue

    @staticmethod
    def verify_or_reject_claim(
        db: Session,
        claim_id: str,
        decision: str,  # VERIFIED or REJECTED
        reviewer_profile_id: str,
        reviewer_email: str = "Faculty/TPO"
    ) -> Dict[str, Any]:
        """
        Updates claim verification status, records reviewer audit log, and triggers Agent 13 recalculation.
        """
        if decision not in ["VERIFIED", "REJECTED"]:
            raise ValueError("Decision must be either VERIFIED or REJECTED")

        claim = db.query(ResumeClaim).filter(ResumeClaim.resume_claim_id == claim_id).first()
        if not claim:
            raise ValueError(f"Resume claim {claim_id} not found.")

        old_status = claim.verification_status
        claim.verification_status = decision
        claim.verified_by = reviewer_profile_id
        claim.verified_at = datetime.datetime.utcnow()

        db.add(AuditLog(
            action="achievement_verification",
            target_type="resume_claim",
            target_id=claim.student_id,
            performed_by=reviewer_email,
            details=f"Claim '{claim.claim_text}' changed from {old_status} to {decision} by {reviewer_email}."
        ))
        db.commit()

        # Recalculate Agent 13 strength profile and recommendations for this student
        from backend.agents.talent_discovery_agent import TalentDiscoveryAgent
        TalentDiscoveryAgent.run_discovery_for_student(db, claim.student_id, reviewer_profile_id)

        return {
            "claim_id": claim_id,
            "student_id": claim.student_id,
            "new_status": decision,
            "verified_by": reviewer_email,
            "verified_at": claim.verified_at
        }
