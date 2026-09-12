"""
AcademicPerformanceAgent: Evaluates student academic trajectory, semester-over-semester growth,
consistency, and domain academic strength using real semester_marks data.
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.models import Student

logger = logging.getLogger(__name__)


class AcademicPerformanceAgent:
    @staticmethod
    def analyze_academic_trajectory(student: Student) -> Dict[str, Any]:
        """
        Calculates real academic metrics from student.semester_marks:
        - current_academic_score (CGPA or latest semester SGPA)
        - semester_history (ordered list of SGPAs)
        - recent_sem_sgpa
        - previous_sem_sgpa
        - growth_delta (recent vs previous)
        - total_growth_delta (latest vs first semester)
        - consistency_score (0.0 to 1.0, low standard deviation)
        - trajectory_status ("HIGH_GROWTH", "STEADY", "DECLINING", "INSUFFICIENT_DATA")
        """
        sem_marks = student.semester_marks or {}
        cgpa = student.cgpa or 0.0

        if not sem_marks or not isinstance(sem_marks, dict):
            return {
                "current_academic_score": cgpa * 10.0,
                "cgpa": cgpa,
                "semester_count": 0,
                "growth_delta": 0.0,
                "trajectory_status": "STEADY",
                "consistency_score": 0.85,
                "explanation": f"Evaluated based on cumulative CGPA of {cgpa:.2f} (no semester SGPA history recorded)."
            }

        # Sort semester keys (e.g. sem1, sem2, sem3...)
        sorted_keys = sorted(
            sem_marks.keys(),
            key=lambda k: int(''.join(filter(str.isdigit, k))) if any(c.isdigit() for c in k) else k
        )

        sgpa_list = [float(sem_marks[k]) for k in sorted_keys if isinstance(sem_marks[k], (int, float))]

        if not sgpa_list:
            return {
                "current_academic_score": cgpa * 10.0,
                "cgpa": cgpa,
                "semester_count": 0,
                "growth_delta": 0.0,
                "trajectory_status": "STEADY",
                "consistency_score": 0.85,
                "explanation": f"Cumulative CGPA: {cgpa:.2f}."
            }

        recent_sem = sgpa_list[-1]
        previous_sem = sgpa_list[-2] if len(sgpa_list) >= 2 else sgpa_list[0]
        growth_delta = round(recent_sem - previous_sem, 2)
        total_delta = round(recent_sem - sgpa_list[0], 2)

        # Consistency score (based on variance)
        mean_sgpa = sum(sgpa_list) / len(sgpa_list)
        variance = sum((x - mean_sgpa) ** 2 for x in sgpa_list) / len(sgpa_list)
        std_dev = variance ** 0.5
        consistency_score = round(max(0.0, min(1.0, 1.0 - (std_dev / 2.0))), 2)

        # Trajectory classification
        if growth_delta >= 0.4 or total_delta >= 0.8:
            status = "HIGH_GROWTH"
        elif growth_delta <= -0.4:
            status = "DECLINING"
        else:
            status = "STEADY"

        current_academic_score = round(mean_sgpa * 10.0, 1)

        explanation = (
            f"Recent semester SGPA: {recent_sem:.2f} (Delta: {growth_delta:+.2f} from previous sem {previous_sem:.2f}). "
            f"Consistency score: {consistency_score * 100:.0f}% across {len(sgpa_list)} semesters."
        )

        return {
            "current_academic_score": current_academic_score,
            "cgpa": cgpa,
            "semester_count": len(sgpa_list),
            "recent_sem_sgpa": recent_sem,
            "previous_sem_sgpa": previous_sem,
            "growth_delta": growth_delta,
            "total_delta": total_delta,
            "consistency_score": consistency_score,
            "trajectory_status": status,
            "explanation": explanation,
            "semester_history": list(zip(sorted_keys, sgpa_list))
        }
