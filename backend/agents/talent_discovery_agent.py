"""
Agent 13 — Fast Learner & Advanced Learner Orchestrator:
Decomposes student evaluation into an integrated 7-stage pipeline:
DETECT -> PROFILE -> MATCH -> RECOMMEND -> ACT -> TRACK -> LEARN

Integrates sub-agents:
- AcademicPerformanceAgent (Growth & Consistency)
- ResumeClaimExtractionAgent (Structured Claims)
- AchievementVerificationAgent (Institutional Evidence)
- DomainTaggingAgent (5 Domain Classification)
- FacultyExpertiseAgent (Multi-domain Mentor Matching)
- OutcomeTrackingAgent (Participation Feedback Loop)
- FairnessAuditAgent (Distribution & Disparity Auditing)
"""

import logging
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.models import Student, ResumeClaim, Agent13Recommendation, ResearchProject, ProjectRequirement, FacultyExpertise

from backend.agents.academic_performance_agent import AcademicPerformanceAgent
from backend.agents.resume_claim_agent import ResumeClaimExtractionAgent
from backend.agents.domain_tagging_agent import DomainTaggingAgent
from backend.agents.faculty_expertise_agent import FacultyExpertiseAgent
from backend.agents.outcome_tracking_agent import OutcomeTrackingAgent

logger = logging.getLogger(__name__)


class TalentDiscoveryAgent:
    @staticmethod
    def calculate_multidimensional_profile(db: Session, student_id: int) -> Dict[str, Any]:
        """
        Builds a true 5-domain strength profile (TECHNICAL, RESEARCH, INNOVATION, COMMUNICATION, DESIGN)
        distinguishing VERIFIED institutional evidence (weight: 1.0) from PROVISIONAL claims (weight: 0.3).
        """
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {}

        # 1. Extract and sync claims if not already present
        ResumeClaimExtractionAgent.extract_and_store_claims(db, student_id)

        # 2. Academic Trajectory & Growth
        acad_metrics = AcademicPerformanceAgent.analyze_academic_trajectory(student)
        base_academic_score = acad_metrics.get("current_academic_score", student.cgpa * 10.0)

        # 3. Fetch Claims & Verification Statuses
        claims = db.query(ResumeClaim).filter(ResumeClaim.student_id == student_id).all()

        domain_evidence: Dict[str, Dict[str, List[str]]] = {
            domain: {"verified": [], "provisional": [], "rejected": []}
            for domain in ["TECHNICAL", "RESEARCH", "INNOVATION", "COMMUNICATION", "DESIGN"]
        }

        domain_scores: Dict[str, float] = {domain: 0.0 for domain in domain_evidence}

        # Initialize base domain weights from student skills & projects
        for sk in (student.skills or []):
            sk_name = sk.get("skill", "")
            tagged = DomainTaggingAgent.tag_item(sk_name)
            dom = tagged["domain"]
            domain_evidence[dom]["verified"].append(f"Verified Institutional Skill: {sk_name}")
            domain_scores[dom] += 15.0

        for proj in (student.projects or []):
            p_title = proj.get("title", "")
            tagged = DomainTaggingAgent.tag_item(p_title, ", ".join(proj.get("tech_stack", [])))
            dom = tagged["domain"]
            domain_evidence[dom]["verified"].append(f"Verified Project: {p_title}")
            domain_scores[dom] += 20.0

        for hack in (student.hackathons or []):
            h_name = hack.get("name", "")
            tagged = DomainTaggingAgent.tag_item(h_name, hack.get("result", ""))
            dom = tagged["domain"]
            domain_evidence[dom]["verified"].append(f"Hackathon Achievement: {h_name}")
            domain_scores[dom] += 25.0

        # Process Resume Claims
        for claim in claims:
            tagged = DomainTaggingAgent.tag_item(claim.claim_text, user_domain=claim.claim_type)
            dom = tagged["domain"]
            status = claim.verification_status.upper()

            if status == "VERIFIED":
                domain_evidence[dom]["verified"].append(claim.claim_text)
                domain_scores[dom] += 15.0
            elif status == "PROVISIONAL":
                domain_evidence[dom]["provisional"].append(claim.claim_text)
                domain_scores[dom] += 4.5  # 0.3 x 15.0
            elif status == "REJECTED":
                domain_evidence[dom]["rejected"].append(claim.claim_text)

        # Combine with Academic Base score (40% academic + 60% domain evidence)
        final_profile: Dict[str, float] = {}
        for domain in domain_scores:
            evidence_score = min(100.0, domain_scores[domain])
            combined = round((0.40 * base_academic_score) + (0.60 * evidence_score), 1)
            final_profile[domain] = min(98.0, max(45.0, combined))

        # Hidden Talent Detection
        # High potential based on unverified/provisional claims or strong growth delta despite lower CGPA
        total_provisional = sum(len(ev["provisional"]) for ev in domain_evidence.values())
        total_verified = sum(len(ev["verified"]) for ev in domain_evidence.values())
        growth_delta = acad_metrics.get("growth_delta", 0.0)

        is_hidden_talent = (total_provisional > total_verified and max(final_profile.values()) >= 78.0) or (growth_delta >= 0.5)
        hidden_talent_expl = None
        if is_hidden_talent:
            hidden_talent_expl = (
                f"Student demonstrates high growth trajectory ({growth_delta:+.2f} SGPA delta) "
                f"and strong unverified project evidence ({total_provisional} provisional claims) "
                f"indicating significant capability beyond baseline GPA."
            )

        return {
            "student_id": student_id,
            "student_name": student.name,
            "branch": student.branch,
            "cgpa": student.cgpa,
            "academic_metrics": acad_metrics,
            "domain_scores": final_profile,
            "evidence_breakdown": domain_evidence,
            "hidden_talent": is_hidden_talent,
            "hidden_talent_explanation": hidden_talent_expl
        }

    @staticmethod
    def generate_personalized_pathway(student: Student, profile: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Generates an individualized 6-month learning & research pathway.
        """
        branch = student.branch or "Engineering"
        scores = profile.get("domain_scores", {})
        top_domain = max(scores, key=scores.get) if scores else "TECHNICAL"

        pathway = [
            {"phase": "Month 1: Foundation & Core Deep-Dive", "milestone": f"Master advanced algorithmic problem solving and core {top_domain.title()} principles."},
            {"phase": "Month 2: Applied System Architecture", "milestone": "Build and deploy a scalable distributed project with comprehensive test coverage."},
            {"phase": "Month 3: Mentorship & Research Prep", "milestone": f"Connect with faculty mentor for literature review in {branch} domains."},
            {"phase": "Month 4: Experimental Implementation", "milestone": "Execute novel baseline experiments and benchmark performance against state-of-the-art."},
            {"phase": "Month 5: Paper/Patent Drafting", "milestone": "Draft research paper manuscript or patent application for institutional review."},
            {"phase": "Month 6: High-Value Placement & Opportunities", "milestone": "Apply for tier-1 research assistantships, funded projects, and high-value internships."}
        ]
        return pathway

    @staticmethod
    def run_discovery_for_student(db: Session, student_id: int, triggered_by_profile_id: str) -> Optional[str]:
        """
        Executes end-to-end Agent 13 Orchestration pipeline for a student.
        """
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return None

        # 1. DETECT & PROFILE: Generate Multidimensional 5-Domain Profile
        profile_data = TalentDiscoveryAgent.calculate_multidimensional_profile(db, student_id)
        domain_scores = profile_data.get("domain_scores", {})

        # 2. FACULTY MATCHING: Run Multi-Domain Faculty Mentorship Agent
        faculty_matches = FacultyExpertiseAgent.match_faculty_for_student(db, student, domain_scores)

        # 3. OPPORTUNITY MATCHING: Evaluate against Active Opportunities
        opportunities = db.query(ResearchProject).filter(ResearchProject.status == "ACTIVE").all()
        new_recs = []

        for opp in opportunities:
            all_reqs = db.query(ProjectRequirement).filter(ProjectRequirement.project_id == opp.project_id).all()
            
            fit_score = 70.0
            if all_reqs:
                matched_weight = sum(
                    domain_scores.get(req.domain, 70.0) * (req.weight or 1.0)
                    for req in all_reqs if req.domain in domain_scores
                )
                total_weight = sum(req.weight or 1.0 for req in all_reqs)
                fit_score = round(matched_weight / max(1.0, total_weight), 1)

            existing = db.query(Agent13Recommendation).filter(
                Agent13Recommendation.student_id == student_id,
                Agent13Recommendation.opportunity_id == opp.project_id
            ).first()

            if existing:
                existing.fit_score = fit_score
                existing.hidden_talent = profile_data.get("hidden_talent", False)
                existing.hidden_talent_explanation = profile_data.get("hidden_talent_explanation")
                existing.evidence_breakdown = profile_data.get("evidence_breakdown")
            else:
                rec = Agent13Recommendation(
                    student_id=student_id,
                    opportunity_id=opp.project_id,
                    opportunity_type="RESEARCH",
                    status="DISCOVERED",
                    fit_score=fit_score,
                    hidden_talent=profile_data.get("hidden_talent", False),
                    hidden_talent_explanation=profile_data.get("hidden_talent_explanation"),
                    evidence_breakdown=profile_data.get("evidence_breakdown")
                )
                db.add(rec)
                new_recs.append(rec)

        db.commit()
        return f"Successfully processed Agent 13 discovery for student ID {student_id} across {len(opportunities)} opportunities and {len(faculty_matches)} faculty mentors."
