"""
DomainTaggingAgent: Classifies student achievements, projects, research, certifications,
and hackathons into the 5 core domains: TECHNICAL, RESEARCH, INNOVATION, COMMUNICATION, DESIGN.
Uses explicit domain selection when available, falling back to a rule-based keyword classifier.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

VALID_DOMAINS = {"TECHNICAL", "RESEARCH", "INNOVATION", "COMMUNICATION", "DESIGN"}

DOMAIN_LEXICON = {
    "RESEARCH": ["paper", "publication", "ieee", "arxiv", "journal", "conference", "literature", "experiment", "hypothesis", "thesis", "patent", "deep learning", "nlp", "computer vision"],
    "INNOVATION": ["hackathon", "sih", "smart india", "prototype", "patent", "startup", "winner", "finalist", "incubation", "solution", "disruptive", "poc", "venture"],
    "COMMUNICATION": ["presentation", "speaker", "workshop", "mentorship", "lead", "organized", "documentation", "writer", "club", "community", "event", "manager"],
    "DESIGN": ["ui/ux", "figma", "wireframe", "user experience", "interface", "css", "tailwindcss", "design system", "graphic", "usability", "a11y"],
    "TECHNICAL": ["python", "java", "c++", "javascript", "typescript", "react", "fastapi", "django", "sql", "postgresql", "docker", "kubernetes", "aws", "backend", "frontend", "system design", "dsa", "algorithm"]
}


class DomainTaggingAgent:
    @staticmethod
    def tag_item(title: str, description: str = "", user_domain: Optional[str] = None) -> Dict[str, Any]:
        """
        Classifies an item into one of the 5 core domains.
        Returns: { "domain": str, "domain_confidence": float, "domain_source": str }
        """
        # If user explicitly selected a valid domain, honor it
        if user_domain and user_domain.upper() in VALID_DOMAINS:
            return {
                "domain": user_domain.upper(),
                "domain_confidence": 1.0,
                "domain_source": "user_selection"
            }

        text = f"{title} {description}".lower()
        scores = {domain: 0 for domain in VALID_DOMAINS}

        for domain, keywords in DOMAIN_LEXICON.items():
            for kw in keywords:
                if kw in text:
                    scores[domain] += 1

        best_domain = max(scores, key=scores.get)
        max_hits = scores[best_domain]

        if max_hits == 0:
            return {
                "domain": "TECHNICAL",
                "domain_confidence": 0.50,
                "domain_source": "default_fallback"
            }

        confidence = round(min(0.98, 0.60 + (max_hits * 0.10)), 2)
        return {
            "domain": best_domain,
            "domain_confidence": confidence,
            "domain_source": "keyword_classifier"
        }
