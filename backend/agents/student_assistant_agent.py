"""
Student Assistant Agent: Provides profile-aware AI co-pilot capabilities for students.
Handles 5 quick action career agents:
1. Improve Resume Agent
2. Find Matching Jobs Agent
3. Interview Preparation Agent
4. Skill Roadmap Agent
5. Career Advice Agent
"""

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.models import Student, Drive, MatchScore, Interview, EligibilityResult

logger = logging.getLogger(__name__)


class StudentAssistantAgent:
    @staticmethod
    def build_student_context_prompt(student_data: Dict[str, Any], db_drives: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Builds a comprehensive system prompt injected into LLM calls for student users.
        """
        skills_str = ", ".join([f"{s.get('skill')} ({s.get('level', 'Beginner')})" for s in student_data.get("skills", [])]) or "None specified"
        projects_str = ", ".join([p.get("title", "") for p in student_data.get("projects", [])]) or "None listed"
        certs_str = ", ".join([c.get("name", "") for c in student_data.get("certifications", [])]) or "None"
        
        prompt = f"""
Student Profile Context:
- Name: {student_data.get('name', 'Student')}
- Branch: {student_data.get('branch', 'Engineering')}
- CGPA: {student_data.get('cgpa', 0.0)}
- 10th %: {student_data.get('tenth_pct', 0.0)}% | 12th %: {student_data.get('twelfth_pct', 0.0)}%
- Active Backlogs: {student_data.get('backlog_count', 0)}
- Skills: {skills_str}
- Projects: {projects_str}
- Certifications: {certs_str}
- Placement Readiness Score (PRS): {student_data.get('prs_score', 75.0)}
- Resume ATS Score: {student_data.get('resume_ats_score', 'Not evaluated yet')}
"""
        if db_drives:
            drives_str = "\n".join([
                f"- {d.get('company_name')} ({d.get('role_title')}): Min CGPA {d.get('cgpa_cutoff', 0)}, Package {d.get('package_min')}-{d.get('package_max')} LPA, Required: {', '.join(d.get('required_skills', {}).get('required', [])) if isinstance(d.get('required_skills'), dict) else ''}"
                for d in db_drives
            ])
            prompt += f"\nActive Open Placement Drives:\n{drives_str}\n"

        return prompt

    @staticmethod
    def generate_agent_reply(query: str, student_data: Dict[str, Any], db: Optional[Session] = None) -> str:
        """
        Generates domain-aware, personalized offline fallback response for student career agents.
        """
        q = query.lower()
        name = student_data.get("name", "Student")
        branch = student_data.get("branch", "Computer Science")
        cgpa = student_data.get("cgpa", 8.0)
        skills = [s.get("skill") for s in student_data.get("skills", []) if s.get("skill")]
        skills_str = ", ".join(skills) if skills else "Python, Java, Web Development"
        ats_score = student_data.get("resume_ats_score")
        projects = student_data.get("projects", [])
        
        # 1. IMPROVE RESUME AGENT
        if "resume" in q or "improve my resume" in q or "ats" in q:
            reply = f"### 📄 AI Resume Optimizer for {name}\n\n"
            if ats_score:
                reply += f"**Current Resume ATS Score:** `{ats_score}/100`\n\n"
            else:
                reply += f"**Current Status:** Your resume has not been ATS-scored yet. Head to **Resume AI** tab to upload and scan your PDF.\n\n"
                
            reply += f"**Personalized Action Items for {branch} (CGPA: {cgpa}):**\n"
            reply += f"1. **Quantify Accomplishments:** Ensure every project bullet includes measurable impact (e.g. *'Optimized database queries reducing latency by 35%'*).\n"
            
            if not skills or len(skills) < 4:
                reply += f"2. **Expand Skill Section:** You currently have {len(skills)} skills listed ({skills_str}). Add target keywords like Cloud (AWS/Azure), Docker, and REST APIs.\n"
            else:
                reply += f"2. **Highlight Key Stack:** Highlight top proficiencies: **{skills_str}** prominently in the top third of your resume.\n"
                
            if not projects:
                reply += f"3. **Add Technical Projects:** Add at least 2 full-stack or system projects with GitHub links to boost recruiter match rates.\n"
            else:
                reply += f"3. **Project Action Verbs:** For your project *'{projects[0].get('title', 'Portfolio Project')}'*, use strong action verbs (Engineered, Architected, Deployed).\n"
                
            reply += f"4. **Formatting Check:** Keep your layout single-column, standard PDF text (no scanned images), and ensure contact links (LinkedIn & GitHub) are clickable.\n"
            return reply

        # 2. FIND MATCHING JOBS AGENT
        elif "match" in q or "job" in q or "good fit" in q or "drives" in q:
            reply = f"### 🔍 AI Job Match Finder for {name}\n\n"
            reply += f"Based on your profile (**{branch}**, **CGPA: {cgpa}**, **Skills: {skills_str}**):\n\n"
            
            active_drives = []
            if db:
                try:
                    drives = db.query(Drive).filter(Drive.status == "published").all()
                    for d in drives:
                        req_sk = d.required_skills.get("required", []) if isinstance(d.required_skills, dict) else []
                        overlap = [s for s in skills if any(s.lower() in r.lower() for r in req_sk)]
                        match_score = min(98, 60 + len(overlap) * 12 + (5 if cgpa >= (d.cgpa_cutoff or 0) else -15))
                        active_drives.append({
                            "company": d.company_name,
                            "role": d.role_title,
                            "package": f"{d.package_min}-{d.package_max} LPA",
                            "cutoff": d.cgpa_cutoff,
                            "match": match_score,
                            "eligible": cgpa >= (d.cgpa_cutoff or 0),
                            "overlap": overlap
                        })
                except Exception as e:
                    logger.error(f"Error fetching drives for job match agent: {e}")

            if active_drives:
                reply += "#### 🎯 Open Campus Recruitment Drives:\n"
                for d in active_drives:
                    status_badge = "✅ Eligible" if d["eligible"] else f"⚠️ Below Cutoff ({d['cutoff']})"
                    reply += f"- **{d['company']}** — *{d['role']}* ({d['package']})\n"
                    reply += f"  - **AI Match Score:** `{d['match']}%` | **Status:** {status_badge}\n"
                    if d["overlap"]:
                        reply += f"  - **Matching Skills:** {', '.join(d['overlap'])}\n"
                    reply += "\n"
            else:
                reply += f"#### Recommended Roles for {branch}:\n"
                reply += f"1. **Software Development Engineer (SDE - I)** — Strong match with your programming skillset in {skills_str}.\n"
                reply += f"2. **Backend/API Developer** — Ideal fit for candidates with Python/Java & Database experience.\n"
                reply += f"3. **Data Analyst / Systems Engineer** — Excellent match for {branch} students with CGPA >= {cgpa}.\n\n"
                
            reply += "💡 *Tip: Keep your profile CGPA and skills updated to automatically unlock direct applications when new campus drives launch!*"
            return reply

        # 3. INTERVIEW PREPARATION AGENT
        elif "interview" in q or "prepare" in q or "prep" in q:
            reply = f"### 🎙️ AI Interview Coach for {name}\n\n"
            reply += f"Tailored prep strategy for **{branch}** candidates:\n\n"
            reply += f"#### 1. Core Technical Focus Areas:\n"
            reply += f"- **Data Structures & Algorithms:** Focus on Arrays, HashMaps, Trees, and Dynamic Programming (LeetCode Medium).\n"
            reply += f"- **Database Management (DBMS):** Be ready for SQL queries (JOINs, GROUP BY, Indexing) and ACID properties.\n"
            reply += f"- **System Design Basics:** Practice REST API design, caching strategies, and database indexing.\n\n"
            
            reply += f"#### 2. Project Deep Dive:\n"
            if projects:
                reply += f"Be prepared to explain *'{projects[0].get('title', 'your main project')}'* using the **STAR Method** (Situation, Task, Action, Result):\n"
                reply += f"- Why did you choose the tech stack (`{', '.join(projects[0].get('tech_stack', ['React', 'Node']))}`)?\n"
                reply += f"- What was the biggest technical challenge and how did you resolve it?\n\n"
            else:
                reply += f"Be prepared to explain your core academic projects, key trade-offs, and architecture decisions using the STAR framework.\n\n"
                
            reply += f"#### 3. Top Behavioral & HR Questions:\n"
            reply += f"- *'Tell me about yourself and your journey in {branch}.'*\n"
            reply += f"- *'Describe a project where you faced a tough bug or deadline.'*\n"
            reply += f"- *'Why do you want to join our company?'*\n"
            return reply

        # 4. SKILL ROADMAP AGENT
        elif "skill" in q or "roadmap" in q or "learn" in q or "readiness" in q:
            reply = f"### 📈 Placement Skill Roadmap for {name}\n\n"
            reply += f"Current Skills: **{skills_str}** | Branch: **{branch}**\n\n"
            reply += f"#### 🚀 4-Week Skill Enhancement Plan:\n\n"
            reply += f"**Week 1: Advanced Problem Solving & DSA**\n"
            reply += f"- Master Graph Traversal (BFS/DFS), Dynamic Programming, and Binary Search.\n"
            reply += f"- Target: Solve 30 curated LeetCode Medium problems.\n\n"
            
            reply += f"**Week 2: Backend & System Integration**\n"
            reply += f"- Learn Docker containerization and CI/CD pipelines.\n"
            reply += f"- Build and deploy a secure REST API with JWT authentication.\n\n"
            
            reply += f"**Week 3: Cloud & Databases**\n"
            reply += f"- Gain hands-on exposure with AWS (EC2, S3, RDS) or GCP.\n"
            reply += f"- Learn PostgreSQL query optimization and Redis caching.\n\n"
            
            reply += f"**Week 4: Mock Tests & Resume Refinement**\n"
            reply += f"- Complete 3 timed mock coding assessments.\n"
            reply += f"- Conduct 2 peer mock interviews focusing on system design and HR responses.\n"
            return reply

        # 5. CAREER ADVICE AGENT
        elif "career" in q or "advice" in q or "interests" in q or "path" in q:
            reply = f"### 🧭 Career Guidance & Advisory for {name}\n\n"
            reply += f"Given your academic background in **{branch}** (CGPA: **{cgpa}**):\n\n"
            reply += f"#### 🌟 Top Career Trajectories:\n"
            reply += f"1. **Software Engineering (Full-Stack / Backend):** High demand across product companies and startups. Focus on CS fundamentals, System Design, and Cloud.\n"
            reply += f"2. **Data Science & AI / ML Engineering:** If you enjoy mathematics and statistics, combine Python, Pandas, PyTorch, and SQL.\n"
            reply += f"3. **Cloud Architecture & DevOps:** Fast-growing domain focusing on Kubernetes, Terraform, and cloud platforms.\n\n"
            
            reply += f"#### 🎯 Placement Strategy Advice:\n"
            if cgpa >= 8.5:
                reply += f"- **Tier-1 Placement Eligibility:** Your CGPA ({cgpa}) qualifies you for top-tier product company campus drives. Aim for high CTC roles by sharpening DSA and System Design.\n"
            else:
                reply += f"- **High-Growth Mid-Market & Startups:** Combine your CGPA ({cgpa}) with strong practical projects to stand out in technical interviews.\n"
                
            reply += f"\nNeed specific guidance on higher studies (GATE/GRE) vs placements? Ask me anytime!"
            return reply

        # GENERAL STUDENT ASSISTANT
        else:
            return f"Hello **{name}**! 👋 I am your **AI Career Co-Pilot**.\n\nI can assist you with your placement journey:\n- **Improve Resume**: ATS score feedback & bullet point generation\n- **Find Matching Jobs**: AI placement drive compatibility\n- **Interview Preparation**: Technical & behavioral mock prep\n- **Skill Roadmap**: Step-by-step 4-week learning plan\n- **Career Advice**: Tailored career guidance for {branch}\n\nHow can I help you today?"
