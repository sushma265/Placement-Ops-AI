"""
Resume AI agent: PDF text extraction, weighted ATS-style analysis,
categorized skill extraction with alias resolution, JD comparison, and
generation tools (bullet points, cover letters, cold emails) on top of the
shared LLM client.

When no Hugging Face key is configured (or the call fails or returns
something unparseable), every method falls back to a deterministic,
non-LLM path -- this never silently fabricates an "AI-generated" result;
every response carries a `source` field so the caller (and the UI) can be
truthful about what actually produced it.
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional

from pypdf import PdfReader

from backend.utils.llm_client import call_llm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skill taxonomy: canonical name -> category, plus alias resolution so
# "JS" / "Node" / "Postgres" etc. all normalize to one canonical entry
# instead of showing up as separate, duplicate-looking skills.
# ---------------------------------------------------------------------------
SKILL_TAXONOMY: Dict[str, Dict[str, List[str]]] = {
    "Programming Languages": {
        "Python": ["python"],
        "Java": ["java"],
        "JavaScript": ["javascript", "js"],
        "TypeScript": ["typescript", "ts"],
        "C++": ["c++", "cpp"],
        "C": ["c"],
        "C#": ["c#", "csharp"],
        "Go": ["go", "golang"],
        "Ruby": ["ruby"],
        "PHP": ["php"],
        "Swift": ["swift"],
        "Kotlin": ["kotlin"],
        "SQL": ["sql"],
    },
    "Frameworks": {
        "React": ["react", "reactjs", "react.js"],
        "Angular": ["angular", "angularjs"],
        "Vue": ["vue", "vuejs", "vue.js"],
        "Django": ["django"],
        "Flask": ["flask"],
        "FastAPI": ["fastapi"],
        "Spring": ["spring", "spring boot", "springboot"],
        "Express": ["express", "expressjs", "express.js"],
        "Node.js": ["node.js", "nodejs", "node"],
        ".NET": [".net", "dotnet"],
        "Next.js": ["next.js", "nextjs"],
    },
    "Databases": {
        "MySQL": ["mysql"],
        "PostgreSQL": ["postgresql", "postgres"],
        "MongoDB": ["mongodb", "mongo"],
        "Redis": ["redis"],
        "SQLite": ["sqlite"],
        "Oracle DB": ["oracle db", "oracle database"],
        "DynamoDB": ["dynamodb"],
    },
    "Cloud & DevOps": {
        "AWS": ["aws", "amazon web services"],
        "GCP": ["gcp", "google cloud"],
        "Azure": ["azure"],
        "Docker": ["docker"],
        "Kubernetes": ["kubernetes", "k8s"],
        "Terraform": ["terraform"],
        "CI/CD": ["ci/cd", "cicd", "continuous integration"],
    },
    "Tools": {
        "Git": ["git"],
        "GitHub": ["github"],
        "Jira": ["jira"],
        "Jenkins": ["jenkins"],
        "Linux": ["linux"],
        "Postman": ["postman"],
        "REST APIs": ["rest api", "rest apis", "restful api"],
        "GraphQL": ["graphql"],
        "Kafka": ["kafka"],
    },
    "Soft Skills": {
        "Communication": ["communication"],
        "Leadership": ["leadership"],
        "Teamwork": ["teamwork", "collaboration"],
        "Problem Solving": ["problem solving", "problem-solving"],
        "Time Management": ["time management"],
        "Agile": ["agile", "scrum"],
    },
}

# Flatten into alias -> (canonical, category) for fast lookup, longest-alias
# first so "node.js" matches before the (nonexistent but illustrative) "node"
# substring ambiguity is avoided by word-boundary matching anyway.
_ALIAS_TO_CANONICAL: Dict[str, tuple] = {}
for _category, _skills in SKILL_TAXONOMY.items():
    for _canonical, _aliases in _skills.items():
        for _alias in _aliases:
            _ALIAS_TO_CANONICAL[_alias] = (_canonical, _category)
# Sort aliases longest-first so multi-word aliases are checked before their
# shorter substrings (e.g. "spring boot" before "spring").
_SORTED_ALIASES = sorted(_ALIAS_TO_CANONICAL.keys(), key=len, reverse=True)


def _extract_categorized_skills(text: str) -> Dict[str, List[str]]:
    """Returns {category: [canonical skill names]}, deduplicated, using
    word-boundary alias matching so 'c' doesn't match inside 'Docker' and
    'JS' correctly resolves to 'JavaScript' rather than showing as a
    separate entry."""
    text_lower = text.lower()
    found: Dict[str, set] = {cat: set() for cat in SKILL_TAXONOMY}

    for alias in _SORTED_ALIASES:
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(pattern, text_lower):
            canonical, category = _ALIAS_TO_CANONICAL[alias]
            found[category].add(canonical)

    return {cat: sorted(skills) for cat, skills in found.items() if skills}


def _flatten_skills(categorized: Dict[str, List[str]]) -> List[str]:
    seen = []
    for skills in categorized.values():
        for s in skills:
            if s not in seen:
                seen.append(s)
    return sorted(seen)


def _canonicalize_skill(skill: str) -> str:
    """Resolves a skill name to its taxonomy canonical form if known (e.g.
    'K8s' -> 'Kubernetes'), otherwise returns it unchanged."""
    key = skill.strip().lower()
    if key in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[key][0]
    return skill.strip()


def _find_missing_target_skills(text_lower: str, found_canonical: List[str], target_skills: List[str]) -> List[str]:
    """Checks each target skill against the resume, using alias resolution
    first (so 'Kubernetes' as a target correctly matches 'K8s' in the
    resume) and falling back to a direct word-boundary check for skills
    outside the known taxonomy."""
    missing = []
    for skill in target_skills:
        canonical = _canonicalize_skill(skill)
        if canonical in found_canonical:
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])", text_lower):
            continue
        missing.append(skill)
    return sorted(set(missing))


class ResumeAgent:
    @staticmethod
    def extract_text_from_pdf(path: str) -> str:
        try:
            reader = PdfReader(path)
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as e:
            logger.warning(f"Resume PDF extraction failed for {path}: {e}")
            return ""

    @staticmethod
    def _try_parse_json(text: str):
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(json)?", "", text).rstrip("`").strip()
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"[\{\[].*[\}\]]", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    return None
            return None

    # -----------------------------------------------------------------
    # ATS analysis -- weighted breakdown across 7 categories, summing to
    # 100. Every sub-score has a `detail` string explaining why it landed
    # where it did, so "why was I scored this way" always has an answer.
    # -----------------------------------------------------------------
    @staticmethod
    def _heuristic_analysis(resume_text: str, target_skills: List[str]) -> Dict[str, Any]:
        text_lower = resume_text.lower()
        categorized_skills = _extract_categorized_skills(resume_text)
        found_skills = _flatten_skills(categorized_skills)

        missing_from_target = _find_missing_target_skills(text_lower, found_skills, target_skills) if target_skills else []

        word_count = len(resume_text.split())

        # --- Skills (25 pts): breadth of recognized skills found ---
        skills_score = round(min(len(found_skills) * 2.2, 25), 1)
        skills_detail = f"{len(found_skills)} recognized skill(s) found across {len(categorized_skills)} categor{'y' if len(categorized_skills)==1 else 'ies'}."

        # --- Education (10 pts): degree/institution/CGPA-style mentions ---
        has_degree = bool(re.search(r"\b(b\.?tech|b\.?e\.?|bachelor|m\.?tech|master|b\.?sc|m\.?sc|be\b|btech)\b", text_lower))
        has_cgpa = bool(re.search(r"\bcgpa\b|\bgpa\b|\b\d\.\d{1,2}\s*/\s*10\b", text_lower))
        education_score = (6 if has_degree else 0) + (4 if has_cgpa else 0)
        education_detail = "Degree and CGPA/GPA mentioned." if has_degree and has_cgpa else (
            "Degree mentioned, but no CGPA/GPA found." if has_degree else "No clear education section detected."
        )

        # --- Projects (15 pts): presence of a projects section + count ---
        project_mentions = len(re.findall(r"\bproject[s]?\b", text_lower))
        has_projects_section = bool(re.search(r"\bprojects?\b\s*[:\n]", text_lower)) or project_mentions >= 2
        projects_score = 15.0 if has_projects_section else (7.0 if project_mentions == 1 else 0.0)
        projects_detail = "Clear projects section detected." if has_projects_section else (
            "Projects mentioned but no distinct section found." if project_mentions == 1 else "No projects section detected."
        )

        # --- Certifications (10 pts) ---
        has_certs = bool(re.search(r"\bcertificat(e|ion|ions)\b|\bcertified\b", text_lower))
        certifications_score = 10.0 if has_certs else 0.0
        certifications_detail = "Certifications mentioned." if has_certs else "No certifications detected."

        # --- Experience (15 pts): internships/work experience signals ---
        has_experience = bool(re.search(r"\bintern(ship)?\b|\bwork experience\b|\bexperience\b", text_lower))
        has_dates = bool(re.search(r"\b(19|20)\d{2}\b", text_lower))
        experience_score = (10 if has_experience else 0) + (5 if has_dates else 0)
        experience_detail = "Experience section with dates found." if has_experience and has_dates else (
            "Experience mentioned, but no clear dates found." if has_experience else "No internship/work experience detected."
        )

        # --- Formatting (15 pts): bullets, contact info, quantified impact, length ---
        has_email = bool(re.search(r"[\w\.-]+@[\w\.-]+\.\w+", resume_text))
        has_phone = bool(re.search(r"\b\d{10}\b|\+\d{1,3}[\s-]?\d{10}\b", resume_text))
        has_bullets = "•" in resume_text or resume_text.count("\n-") > 3
        has_quant = bool(re.search(r"\d+%|\d+x\b|\$\d+", resume_text))
        reasonable_length = 150 <= word_count <= 1200
        formatting_score = (
            (4 if has_email else 0) + (3 if has_phone else 0) + (4 if has_bullets else 0)
            + (2 if has_quant else 0) + (2 if reasonable_length else 0)
        )
        formatting_detail = f"{'Bulleted, ' if has_bullets else 'Not bulleted, '}{'quantified impact present, ' if has_quant else 'no quantified impact, '}{word_count} words."

        # --- Keyword match vs target skills (10 pts) ---
        if target_skills:
            matched_target = len(target_skills) - len(missing_from_target)
            keyword_score = round((matched_target / len(target_skills)) * 10, 1)
            keyword_detail = f"Matched {matched_target}/{len(target_skills)} of your profile's target skills."
        else:
            keyword_score = 5.0  # neutral -- no target skills to compare against
            keyword_detail = "No target skills set on your profile to compare against."

        breakdown = {
            "skills": {"score": skills_score, "max": 25, "detail": skills_detail},
            "education": {"score": education_score, "max": 10, "detail": education_detail},
            "projects": {"score": projects_score, "max": 15, "detail": projects_detail},
            "certifications": {"score": certifications_score, "max": 10, "detail": certifications_detail},
            "experience": {"score": experience_score, "max": 15, "detail": experience_detail},
            "formatting": {"score": formatting_score, "max": 15, "detail": formatting_detail},
            "keyword_match": {"score": keyword_score, "max": 10, "detail": keyword_detail},
        }
        total_score = round(sum(v["score"] for v in breakdown.values()), 1)

        suggestions = []
        if not has_quant:
            suggestions.append("Add measurable impact to your bullet points (e.g. 'reduced load time by 30%').")
        if not has_bullets:
            suggestions.append("Use bullet points instead of paragraphs for experience and projects.")
        if not has_projects_section:
            suggestions.append("Add a clearly labeled Projects section.")
        if not has_certs:
            suggestions.append("List relevant certifications if you have any.")
        if word_count < 150:
            suggestions.append("Your resume looks short -- consider adding more detail on projects and skills.")
        if not has_email or not has_phone:
            suggestions.append("Make sure your contact info (email and phone) is clearly visible.")
        if not suggestions:
            suggestions.append("Structure looks solid. Consider tailoring skills and keywords to each job you apply to.")

        return {
            "ats_score": total_score,
            "score_breakdown": breakdown,
            "extracted_skills": categorized_skills,
            "missing_skills": missing_from_target,
            "suggestions": suggestions[:5],
            "missing_keywords": missing_from_target,
            "source": "heuristic",
        }

    @classmethod
    def analyze(cls, resume_text: str, target_skills: Optional[List[str]] = None, hf_token: Optional[str] = None) -> Dict[str, Any]:
        target_skills = target_skills or []
        if not resume_text.strip():
            return {
                "ats_score": None,
                "score_breakdown": {},
                "extracted_skills": {},
                "missing_skills": target_skills,
                "suggestions": ["Couldn't extract any text from your resume PDF. Make sure it isn't a scanned image."],
                "missing_keywords": target_skills,
                "source": "extraction_failed",
            }

        if hf_token:
            system_prompt = (
                "You are an ATS (Applicant Tracking System) resume analyzer. "
                "Given resume text, respond ONLY with a JSON object (no markdown, no prose) with exactly this shape: "
                '{"ats_score": <0-100 integer, weighted sum of the breakdown below>, '
                '"score_breakdown": {'
                '"skills": {"score": <0-25>, "max": 25, "detail": "<one sentence>"}, '
                '"education": {"score": <0-10>, "max": 10, "detail": "<one sentence>"}, '
                '"projects": {"score": <0-15>, "max": 15, "detail": "<one sentence>"}, '
                '"certifications": {"score": <0-10>, "max": 10, "detail": "<one sentence>"}, '
                '"experience": {"score": <0-15>, "max": 15, "detail": "<one sentence>"}, '
                '"formatting": {"score": <0-15>, "max": 15, "detail": "<one sentence>"}, '
                '"keyword_match": {"score": <0-10>, "max": 10, "detail": "<one sentence>"}}, '
                '"extracted_skills": {"Programming Languages": [<strings>], "Frameworks": [<strings>], '
                '"Databases": [<strings>], "Cloud & DevOps": [<strings>], "Tools": [<strings>], "Soft Skills": [<strings>]}, '
                '"missing_skills": [<strings>], "suggestions": [<3-5 short actionable strings>], "missing_keywords": [<strings>]}. '
                "Only include categories in extracted_skills that have at least one skill. "
                "Normalize skill names (e.g. 'JS' to 'JavaScript', 'Node' to 'Node.js') and never list the same skill twice."
            )
            user_prompt = f"Resume text:\n{resume_text[:6000]}"
            if target_skills:
                user_prompt += f"\n\nTarget role skills to check for: {', '.join(target_skills)}"

            reply = call_llm(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                hf_token, max_tokens=900, temperature=0.3,
            )
            if reply:
                parsed = cls._try_parse_json(reply)
                if isinstance(parsed, dict) and "ats_score" in parsed and "score_breakdown" in parsed:
                    parsed["source"] = "huggingface"
                    return parsed
                logger.warning("LLM resume analysis returned unparseable/incomplete JSON, falling back to heuristic.")

        return cls._heuristic_analysis(resume_text, target_skills)

    # -----------------------------------------------------------------
    # JD comparison -- how well does this resume match a specific drive's
    # required skills, with matched/missing breakdown and an explanation.
    # -----------------------------------------------------------------
    @classmethod
    def compare_to_jd(
        cls, resume_text: str, jd_required_skills: List[str], jd_text: str, hf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not resume_text.strip():
            return {
                "match_pct": None, "matched_skills": [], "missing_skills": jd_required_skills,
                "explanation": "Couldn't read your resume -- upload a text-based PDF (not a scanned image).",
                "source": "extraction_failed",
            }

        if hf_token:
            system_prompt = (
                "Compare a resume against a job description. Respond ONLY with a JSON object: "
                '{"match_pct": <0-100 integer>, "matched_skills": [<strings from resume that match the JD>], '
                '"missing_skills": [<strings the JD wants but the resume lacks>], '
                '"explanation": "<2-3 sentences on why this match percentage was given>"}.'
            )
            user_prompt = f"Resume:\n{resume_text[:4000]}\n\nJob description:\n{jd_text[:2000]}"
            if jd_required_skills:
                user_prompt += f"\n\nRequired skills list: {', '.join(jd_required_skills)}"
            reply = call_llm(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                hf_token, max_tokens=500, temperature=0.3,
            )
            if reply:
                parsed = cls._try_parse_json(reply)
                if isinstance(parsed, dict) and "match_pct" in parsed:
                    parsed["source"] = "huggingface"
                    return parsed
                logger.warning("LLM JD comparison returned unparseable JSON, falling back to heuristic.")

        # Heuristic fallback: word-boundary match against required skills list
        # (if given) or against skills extracted from the JD text itself,
        # using the same alias resolution as analyze() so a JD asking for
        # "Kubernetes" correctly matches a resume that says "K8s".
        text_lower = resume_text.lower()
        required = jd_required_skills or _flatten_skills(_extract_categorized_skills(jd_text))
        if not required:
            return {
                "match_pct": None, "matched_skills": [], "missing_skills": [],
                "explanation": "This drive has no listed required skills to compare against.",
                "source": "heuristic",
            }
        found_canonical = _flatten_skills(_extract_categorized_skills(resume_text))
        missing = _find_missing_target_skills(text_lower, found_canonical, required)
        matched = sorted(set(required) - set(missing))
        match_pct = round((len(matched) / len(required)) * 100, 1)
        explanation = (
            f"Your resume matches {len(matched)} of {len(required)} required skill(s) "
            f"({match_pct}%). " + (f"Missing: {', '.join(missing[:6])}." if missing else "You cover every listed skill.")
        )
        return {
            "match_pct": match_pct, "matched_skills": matched, "missing_skills": missing,
            "explanation": explanation, "source": "heuristic",
        }

    # -----------------------------------------------------------------
    # Generation tools
    # -----------------------------------------------------------------
    @classmethod
    def generate_bullets(cls, project_title: str, description: str, hf_token: Optional[str] = None) -> Dict[str, Any]:
        if hf_token:
            system_prompt = (
                "You write concise, impact-driven resume bullet points (each under 20 "
                "words, start with a strong action verb, quantify impact where plausible). "
                "Given a project title and rough description, return exactly 3 improved "
                "bullet points as a JSON array of strings, nothing else."
            )
            user_prompt = f"Project: {project_title}\nDescription: {description}"
            reply = call_llm(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                hf_token, max_tokens=250, temperature=0.6,
            )
            if reply:
                parsed = cls._try_parse_json(reply)
                if isinstance(parsed, list) and parsed:
                    return {"bullets": [str(b) for b in parsed[:3]], "source": "huggingface"}
                lines = [l.strip("-• ").strip() for l in reply.splitlines() if l.strip()]
                if lines:
                    return {"bullets": lines[:3], "source": "huggingface"}

        clean_desc = description.strip().rstrip(".")
        return {
            "bullets": [
                f"Built {project_title}, {clean_desc}.",
                f"Contributed to {project_title} with a focus on core functionality and reliability.",
                f"Delivered {project_title} independently, applying relevant tools and best practices.",
            ],
            "source": "template_fallback",
        }

    @classmethod
    def generate_cover_letter(
        cls, student_name: str, branch: str, skills: List[str],
        company_name: str, role_title: str, jd_text: str, hf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        if hf_token:
            system_prompt = (
                "You write concise, professional, honest cover letters (strictly under 200 "
                "words, 3 short paragraphs) for campus placement applications. No "
                "placeholders like [Your Name] -- use the real details given. No cliches "
                "like 'I am writing to express my interest'. Return plain text only, no markdown."
            )
            user_prompt = (
                f"Candidate: {student_name}, {branch} student. "
                f"Key skills: {', '.join(skills[:8]) or 'not specified'}.\n"
                f"Company: {company_name}\nRole: {role_title}\n"
                f"Job description: {jd_text[:1500]}"
            )
            reply = call_llm(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                hf_token, max_tokens=400, temperature=0.6,
            )
            if reply:
                return {"cover_letter": reply.strip(), "source": "huggingface"}

        skills_line = ", ".join(skills[:5]) if skills else "a strong technical foundation"
        letter = (
            f"Dear Hiring Team at {company_name},\n\n"
            f"I am {student_name}, a {branch} student, applying for the {role_title} role. "
            f"I bring hands-on experience in {skills_line}, which lines up well with what "
            f"this position needs.\n\n"
            f"I'd welcome the chance to talk through how my background could contribute to "
            f"your team.\n\nSincerely,\n{student_name}"
        )
        return {"cover_letter": letter, "source": "template_fallback"}

    @classmethod
    def generate_cold_email(
        cls, student_name: str, branch: str, skills: List[str],
        company_name: str, role_title: Optional[str], hf_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        target_role = role_title or "opportunities matching my background"
        if hf_token:
            system_prompt = (
                "You write short, polite, professional cold outreach emails (strictly under "
                "120 words) from students to recruiters, expressing interest and asking about "
                "opportunities. No placeholders, no cliches. Return plain text only, "
                "including a Subject: line."
            )
            user_prompt = (
                f"Candidate: {student_name}, {branch} student. "
                f"Key skills: {', '.join(skills[:8]) or 'not specified'}.\n"
                f"Company: {company_name}\nTarget: {target_role}"
            )
            reply = call_llm(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                hf_token, max_tokens=250, temperature=0.6,
            )
            if reply:
                return {"cold_email": reply.strip(), "source": "huggingface"}

        skills_line = ", ".join(skills[:5]) if skills else "software development"
        email = (
            f"Subject: Interest in Opportunities at {company_name}\n\n"
            f"Hi,\n\nI'm {student_name}, a {branch} student with experience in {skills_line}. "
            f"I'm reaching out about {target_role} at {company_name} and would appreciate "
            f"the chance to share my resume.\n\nThank you for your time.\n\nBest,\n{student_name}"
        )
        return {"cold_email": email, "source": "template_fallback"}
