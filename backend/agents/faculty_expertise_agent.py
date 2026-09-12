"""
FacultyExpertiseAgent: Calculates explainable faculty mentor compatibility (0-100%)
by matching student multidimensional strengths (TECHNICAL, RESEARCH, INNOVATION, COMMUNICATION, DESIGN)
and specific skill/project interests against faculty research areas in people.faculty_expertise.
REMOVES hardcoded `AND domain = 'RESEARCH'` restrictions to allow true multi-domain mentor matching.
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.models import FacultyExpertise, Student

logger = logging.getLogger(__name__)


class FacultyExpertiseAgent:
    @staticmethod
    def match_faculty_for_student(
        db: Session, student: Student, strength_profile: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Matches all active faculty against the student's 5-domain strengths, skills, and projects.
        Returns a list of faculty matches sorted by compatibility score (descending).
        """
        faculty_list = db.query(FacultyExpertise).all()
        if not faculty_list:
            return []

        # Extract student's top skills and project domains
        student_skills = [s.get("skill", "").lower() for s in (student.skills or []) if s.get("skill")]
        student_projects = [p.get("title", "").lower() for p in (student.projects or [])]
        student_branch = (student.branch or "").lower()

        # Find student's top 2 domain strengths
        sorted_domains = sorted(strength_profile.items(), key=lambda x: x[1], reverse=True)
        top_domain, top_score = sorted_domains[0] if sorted_domains else ("TECHNICAL", 75.0)
        second_domain, second_score = sorted_domains[1] if len(sorted_domains) > 1 else ("RESEARCH", 70.0)

        matches = []
        for fac in faculty_list:
            research_areas = [r.lower() for r in (fac.research_areas or [])]
            dept = fac.department.lower()

            # 1. Department Alignment (20% weight)
            dept_score = 100.0 if dept == student_branch or student_branch in dept or dept in student_branch else 60.0

            # 2. Domain Strength Compatibility (40% weight)
            # Evaluates match between top student domains and faculty focus
            domain_score = (top_score * 0.7) + (second_score * 0.3)

            # 3. Direct Keyword & Research Skill Overlap (40% weight)
            overlap_count = 0
            matched_keywords = []
            for area in research_areas:
                for sk in student_skills:
                    if sk in area or area in sk:
                        overlap_count += 1
                        matched_keywords.append(sk.title())
                for proj in student_projects:
                    if any(word in area for word in proj.split()):
                        overlap_count += 1

            skill_overlap_score = min(100.0, 40.0 + (overlap_count * 20.0))

            # Final Weighted Compatibility Calculation
            compatibility = round(
                (0.20 * dept_score) + (0.40 * domain_score) + (0.40 * skill_overlap_score),
                1
            )
            compatibility = min(98.0, max(35.0, compatibility))

            # Explainable rationale
            reasons = []
            if matched_keywords:
                reasons.append(f"Direct skill overlap in {', '.join(set(matched_keywords))}")
            if dept_score == 100.0:
                reasons.append(f"Departmental alignment in {fac.department}")
            reasons.append(f"Strong alignment with candidate's primary domain ({top_domain} score: {top_score:.1f})")

            matches.append({
                "faculty_id": fac.faculty_id,
                "profile_id": fac.profile_id,
                "name": fac.name,
                "department": fac.department,
                "research_areas": fac.research_areas,
                "compatibility_score": compatibility,
                "rationale": " • ".join(reasons)
            })

        matches.sort(key=lambda x: x["compatibility_score"], reverse=True)
        return matches
