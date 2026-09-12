"""
FairnessAuditAgent: Evaluates Agent 13 recommendation distribution across student branches
and academic cohorts to ensure equitable opportunity allocation without inventing sensitive demographic fields.
Calculates group distributions, selection rates, and disparity alerts.
"""

import logging
import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.models import Student, Agent13Recommendation

logger = logging.getLogger(__name__)


class FairnessAuditAgent:
    @staticmethod
    def run_fairness_audit(db: Session) -> Dict[str, Any]:
        """
        Computes fairness metrics across department branches using database records.
        """
        total_students = db.query(Student).count()
        total_recommendations = db.query(Agent13Recommendation).count()

        # Branch student counts
        students_by_branch = dict(
            db.query(Student.branch, func.count(Student.id)).group_by(Student.branch).all()
        )

        # Branch recommendation counts
        recs_by_branch = dict(
            db.query(Student.branch, func.count(Agent13Recommendation.recommendation_id))
            .join(Student, Agent13Recommendation.student_id == Student.id)
            .group_by(Student.branch)
            .all()
        )

        # Recommendation status counts
        status_counts = dict(
            db.query(Agent13Recommendation.status, func.count(Agent13Recommendation.recommendation_id))
            .group_by(Agent13Recommendation.status)
            .all()
        )

        # Hidden talent distribution
        hidden_talent_counts = dict(
            db.query(Student.branch, func.count(Agent13Recommendation.recommendation_id))
            .join(Student, Agent13Recommendation.student_id == Student.id)
            .filter(Agent13Recommendation.hidden_talent == True)
            .group_by(Student.branch)
            .all()
        )

        branch_breakdown = []
        selection_rates = []

        for branch, student_cnt in students_by_branch.items():
            rec_cnt = recs_by_branch.get(branch, 0)
            rate = round((rec_cnt / student_cnt) * 100, 1) if student_cnt > 0 else 0.0
            selection_rates.append(rate)

            branch_breakdown.append({
                "branch": branch,
                "total_students": student_cnt,
                "recommended_students": rec_cnt,
                "recommendation_rate_pct": rate,
                "hidden_talent_count": hidden_talent_counts.get(branch, 0)
            })

        # Disparity Warning check (if max rate > 2.5x min rate)
        disparity_warning = False
        disparity_message = "Opportunity distribution across branches is balanced within acceptable thresholds."

        if selection_rates:
            max_rate = max(selection_rates)
            min_rate = min(selection_rates)
            if min_rate > 0 and (max_rate / min_rate) > 2.5:
                disparity_warning = True
                disparity_message = f"Disparity alert: Recommendation rate varies significantly between branches (Highest: {max_rate}%, Lowest: {min_rate}%)."

        return {
            "timestamp": datetime.datetime.utcnow(),
            "total_students": total_students,
            "total_recommendations": total_recommendations,
            "decision_distribution": status_counts,
            "branch_breakdown": branch_breakdown,
            "disparity_warning": disparity_warning,
            "disparity_message": disparity_message
        }
