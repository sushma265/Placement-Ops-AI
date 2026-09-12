"""
ResumeClaimExtractionAgent: Extracts structured claims (projects, technical skills,
research, hackathons, publications, certifications, leadership) from resume text
and student profile entries, categorizing them into the 5 core domains and storing
them as PROVISIONAL claims in studentlife.resume_claim.
"""

import logging
import uuid
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.models import Student, ResumeClaim

logger = logging.getLogger(__name__)

# Keywords mapped to the 5 core domains
DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "TECHNICAL": [
        "python", "java", "c++", "javascript", "typescript", "react", "fastapi", "django",
        "sql", "postgresql", "mongodb", "docker", "kubernetes", "aws", "gcp", "azure",
        "system design", "dsa", "algorithms", "rest api", "backend", "frontend", "fullstack",
        "devops", "cloud", "git", "linux", "ci/cd", "redis", "microservices"
    ],
    "RESEARCH": [
        "research", "paper", "publication", "ieee", "arxiv", "journal", "conference",
        "literature review", "experiment", "hypothesis", "dataset", "deep learning",
        "machine learning", "nlp", "computer vision", "neural network", "transformer",
        "model training", "accuracy", "benchmarking", "patent"
    ],
    "INNOVATION": [
        "hackathon", "smart india hackathon", "prototype", "patent", "startup",
        "first place", "winner", "finalist", "incubation", "solution", "architecture",
        "novel", "automation", "disruptive", "proof of concept", "poc"
    ],
    "COMMUNICATION": [
        "presentation", "speaker", "workshop", "mentorship", "lead", "organized",
        "documentation", "technical writer", "club lead", "community", "outreach",
        "event manager", "host", "moderator", "agile scrum master"
    ],
    "DESIGN": [
        "ui/ux", "figma", "wireframe", "user experience", "interface design", "css",
        "tailwindcss", "user research", "prototyping", "accessibility", "a11y",
        "design system", "graphic design", "canvas"
    ]
}


class ResumeClaimExtractionAgent:
    @staticmethod
    def classify_domain(text_snippet: str) -> tuple[str, float]:
        """
        Classifies a snippet into one of the 5 domains using rule-based keyword match.
        Returns (domain, confidence).
        """
        snippet = text_snippet.lower()
        scores: Dict[str, int] = {domain: 0 for domain in DOMAIN_KEYWORDS}
        
        for domain, keywords in DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in snippet:
                    scores[domain] += 1

        best_domain = max(scores, key=scores.get)
        max_score = scores[best_domain]

        if max_score == 0:
            return ("TECHNICAL", 0.5)

        confidence = min(0.95, 0.60 + (max_score * 0.10))
        return (best_domain, round(confidence, 2))

    @staticmethod
    def extract_and_store_claims(
        db: Session, student_id: int, resume_text: str = "", source_doc: str = "profile"
    ) -> List[ResumeClaim]:
        """
        Extracts claims from student profile (projects, hackathons, certs, skills) and resume text,
        then persists them into studentlife.resume_claim with status PROVISIONAL.
        """
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return []

        existing_claims = {
            c.claim_text.lower().strip(): c for c in db.query(ResumeClaim).filter(ResumeClaim.student_id == student_id).all()
        }

        new_claims: List[ResumeClaim] = []

        # 1. Process Projects
        for proj in (student.projects or []):
            title = proj.get("title", "").strip()
            desc = proj.get("description", "").strip()
            tech = ", ".join(proj.get("tech_stack", []))
            claim_str = f"Project: {title} ({tech}). {desc}".strip()
            
            if claim_str and claim_str.lower() not in existing_claims:
                domain, confidence = ResumeClaimExtractionAgent.classify_domain(f"{title} {tech} {desc}")
                claim = ResumeClaim(
                    student_id=student_id,
                    claim_type="PROJECT",
                    claim_text=claim_str,
                    normalized_skill=tech.split(",")[0].strip().lower() if tech else title.lower(),
                    source_document_id=source_doc,
                    extraction_confidence=confidence,
                    verification_status="PROVISIONAL"
                )
                db.add(claim)
                new_claims.append(claim)

        # 2. Process Hackathons
        for hack in (student.hackathons or []):
            name = hack.get("name", "").strip()
            res = hack.get("result", "Participant").strip()
            claim_str = f"Hackathon: {name} - {res}".strip()

            if claim_str and claim_str.lower() not in existing_claims:
                domain, confidence = ResumeClaimExtractionAgent.classify_domain(f"{name} {res} hackathon")
                claim = ResumeClaim(
                    student_id=student_id,
                    claim_type="HACKATHON",
                    claim_text=claim_str,
                    normalized_skill=name.lower(),
                    source_document_id=source_doc,
                    extraction_confidence=max(0.85, confidence),
                    verification_status="PROVISIONAL"
                )
                db.add(claim)
                new_claims.append(claim)

        # 3. Process Certifications
        for cert in (student.certifications or []):
            c_name = cert.get("name", "").strip()
            issuer = cert.get("issuer", "").strip()
            claim_str = f"Certification: {c_name} by {issuer}".strip()

            if claim_str and claim_str.lower() not in existing_claims:
                domain, confidence = ResumeClaimExtractionAgent.classify_domain(f"{c_name} {issuer}")
                claim = ResumeClaim(
                    student_id=student_id,
                    claim_type="CERTIFICATION",
                    claim_text=claim_str,
                    normalized_skill=c_name.lower(),
                    source_document_id=source_doc,
                    extraction_confidence=confidence,
                    verification_status="PROVISIONAL"
                )
                db.add(claim)
                new_claims.append(claim)

        # 4. Process Skills
        for sk in (student.skills or []):
            skill_name = sk.get("skill", "").strip()
            level = sk.get("level", "Intermediate").strip()
            claim_str = f"Proficiency in {skill_name} ({level})"

            if skill_name and claim_str.lower() not in existing_claims:
                domain, confidence = ResumeClaimExtractionAgent.classify_domain(skill_name)
                claim = ResumeClaim(
                    student_id=student_id,
                    claim_type="SKILL",
                    claim_text=claim_str,
                    normalized_skill=skill_name.lower(),
                    source_document_id=source_doc,
                    extraction_confidence=0.75,
                    verification_status="PROVISIONAL"
                )
                db.add(claim)
                new_claims.append(claim)

        db.commit()
        return new_claims
