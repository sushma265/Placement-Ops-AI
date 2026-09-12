# 🚀 Placement Ops AI — Evaluator Presentation & Technical Architecture Guide

This document provides a comprehensive technical walkthrough, system architecture summary, tech stack breakdown, and detailed agent-by-agent explanation to help you present **Placement Ops AI** to judges and evaluators.

---

## 🏆 Project Elevator Pitch

> **Placement Ops AI** is an autonomous, multi-agent campus placement operations and career intelligence platform. It replaces fragmented spreadsheets, manual eligibility checking, and scheduling chaos with an explainable, protocol-driven multi-agent ecosystem — while ensuring strict **Human-in-the-Loop governance (`ACT_WITH_APPROVAL`)** where placement officers and faculty retain control of every decision.

---

## 💻 Tech Stack Overview

| Component | Technology | Rationale & Usage |
|---|---|---|
| **Frontend Framework** | **Next.js 14 (App Router, React 18, TypeScript)** | High-performance, server-side rendered UI with responsive dashboards for Students, Recruiters, Faculty, and TPOs. |
| **Styling & Icons** | **Vanilla CSS + Tailwind CSS + Lucide React** | Clean, minimalist, modern design system with restrained colors, accessible contrast, and micro-interactions. |
| **Backend Framework** | **FastAPI (Python 3.10+)** | Async REST API micro-services with Pydantic validation, automatic OpenAPI docs (`/docs`), and low latency. |
| **Database & ORM** | **PostgreSQL + Supabase + SQLAlchemy ORM** | Relational data integrity for students, drives, interviews, audit logs, and Agent 13 schemas (`studentlife`, `research`, `agentops`, `people`). |
| **Authentication & RBAC** | **Supabase Auth (PKCE OAuth + JWT)** | Real-time session management, social OAuth (Google, GitHub, LinkedIn), and strict server-enforced role locking (`ProfileRole`). |
| **LLM & AI Engine** | **Hugging Face Inference API (Mistral-7B, Qwen-2.5, Llama-3.2)** + **Built-in Domain AI Engine** | Dual-mode AI: uses Hugging Face models when configured, falling back to a deterministic, offline domain AI engine when offline. |
| **Agent Protocol** | **Placement Context Protocol (PCP / Context Router)** | Decoupled hub-and-agent architecture passing shared `ContextObject` state between independent agents. |
| **Explainable ML** | **Weighted Multi-Vector Scoring + SHAP (SHapley Additive exPlanations)** | Candidate-job matching with itemized feature importance breakdowns (not a black-box score). |

---

## 🤖 Detailed Agent-by-Agent Walkthrough

The platform decomposes campus placement operations and career development into specialized micro-agents:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PLACEMENT OPS MULTI-AGENT PLATFORM                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
      ┌────────────────────────────────┼──────────────────────────────┐
      ▼                                ▼                              ▼
┌───────────────────────────┐    ┌───────────────────────────┐    ┌───────────────────────────┐
│  RECRUITMENT OPS AGENTS   │    │  STUDENT CAREER CO-PILOT  │    │   AGENT 13 DISCOVERY      │
├───────────────────────────┤    ├───────────────────────────┤    ├───────────────────────────┤
│ • JDIntakeAgent           │    │ • Improve Resume Agent    │    │ • AcademicPerformanceAgent│
│ • EligibilityAgent        │    │ • Find Matching Jobs Agent│    │ • ResumeClaimAgent        │
│ • MatchingAgent (SHAP)    │    │ • Interview Prep Agent    │    │ • AchievementVerifyAgent  │
│ • SchedulingAgent         │    │ • Skill Roadmap Agent     │    │ • DomainTaggingAgent      │
│ • CoordinationAgent       │    │ • Research Pathway Agent  │    │ • FacultyExpertiseAgent   │
│ • NotificationAgent       │    │ • Career Guidance Agent   │    │ • OutcomeTrackingAgent    │
│ • ExceptionAgent          │    └───────────────────────────┘    │ • FairnessAuditAgent      │
│ • Analytics & Reporting   │                                     └───────────────────────────┘
└───────────────────────────┘
```

---

### 🏛️ Category 1: Recruitment Operations Agents

#### 1. `JDIntakeAgent` (`backend/agents/jd_intake_agent.py`)
* **How it works:** Accepts uploaded PDF or raw text Job Descriptions (JDs). Uses natural language parsing to extract key recruitment criteria: `role_title`, `required_skills`, `cgpa_cutoff`, `eligible_branches`, `package_min`, `package_max`, and `headcount`.
* **Human Checkpoint:** The TPO confirms or edits extracted draft metadata before publishing the drive.

#### 2. `EligibilityAgent` (`backend/agents/eligibility_agent.py`)
* **How it works:** Executes rule-based filtering against student database records (CGPA, active backlog counts, branch eligibility, and current best offer limits).
* **Human Checkpoint:** Generates eligibility results with auditable TPO manual override support (`overridden_by_tpo`).

#### 3. `MatchingAgent` (`backend/agents/matching_agent.py`)
* **How it works:** Scores eligible candidates against published company JDs using a multi-vector similarity model:
  $$\text{Overall Match} = (0.40 \times \text{Skill}) + (0.30 \times \text{Academic}) + (0.30 \times \text{Projects/PRS})$$
  Computes SHAP (SHapley Additive exPlanations) feature importance to explain why a candidate was ranked.
* **Human Checkpoint:** TPO approves and locks the shortlist before dispatching to recruiters.

#### 4. `SchedulingAgent` (`backend/agents/scheduling_agent.py`)
* **How it works:** Proposes conflict-free interview time slots matching candidate schedules, interviewer panel availability, and physical/virtual room capacities.
* **Human Checkpoint:** TPO confirms the final proposed calendar.

#### 5. `CoordinationAgent` (`backend/agents/coordination_agent.py`)
* **How it works:** Validates scheduled interviews in real-time to detect double-booked interviewers, room overlaps, or student schedule collisions. Flags conflicts as actionable items.

#### 6. `NotificationAgent` (`backend/agents/notification_agent.py`)
* **How it works:** Dispatches multi-channel notifications (email, SMS, in-app portal alerts) for interview invites, eligibility updates, and reminders using pre-approved templates.

#### 7. `ExceptionAgent` (`backend/agents/exception_agent.py`)
* **How it works:** Monitors the system for edge cases (missing student data, borderline eligibility, schedule double-bookings) and surfaces them in a central exception queue.

#### 8. `AnalyticsAgent` & `ReportingAgent` (`backend/agents/analytics_agent.py`, `reporting_agent.py`)
* **How it works:** Computes campus-wide skill gaps (industry demand vs. student supply), placement readiness trends across departments, and exports CSV reports for institutional accreditation.

---

### 🎓 Category 2: Student AI Career Co-Pilot Agents

Located on the **Student Dashboard**, this module connects the student directly to personalized AI guidance:

1. **📄 Improve Resume Agent**: Scans resume text, evaluates ATS scores (0–100), detects missing keywords, and rewrites project bullets into quantifiable STAR-format achievements.
2. **🔍 Find Matching Jobs Agent**: Scans open campus placement drives, matches candidate CGPA/branch/skills, and displays fit percentages and eligibility cutoffs.
3. **🎙️ Interview Preparation Agent**: Formulates technical focus areas (DSA, System Design, SQL), STAR project deep-dive questions, and behavioral HR prep.
4. **📈 Advanced Skill Roadmap Agent**: Compares student current skills against in-demand tech stacks across company JDs to build a step-by-step 4-week learning roadmap.
5. **📖 Research Pathway Agent**: Builds a 6-month customized trajectory for literature review, experimental design, and paper publication.
6. **🧭 Career Guidance Agent**: Advises on tier-1 product company CTC target strategies, higher studies (GATE/GRE), and domain specialization.

---

### 🔬 Category 3: Agent 13 — Fast Learner & Advanced Learner Ecosystem

**Agent 13** addresses a critical institutional problem: *universities often focus heavily on remedial students while neglecting high-potential advanced learners.* Agent 13 operates via a 7-stage pipeline: **DETECT → PROFILE → MATCH → RECOMMEND → ACT → TRACK → LEARN**.

#### Sub-Agents inside Agent 13:
1. **`ResumeClaimExtractionAgent`** (`backend/agents/resume_claim_agent.py`):
   * Extracts structured claims (projects, research, hackathons, publications, certs) from resumes/profiles into `studentlife.resume_claim` as **`PROVISIONAL`** claims across 5 domains.
2. **`AchievementVerificationAgent`** (`backend/agents/achievement_verification_agent.py`):
   * Institution-facing verification queue where Faculty/TPO review provisional claims.
   * Distinguishes **`VERIFIED` evidence (weight: 1.0)** from **`PROVISIONAL` claims (weight: 0.3)** and **`REJECTED` claims (weight: 0.0)**.
3. **`AcademicPerformanceAgent`** (`backend/agents/academic_performance_agent.py`):
   * Evaluates true academic performance, semester-over-semester SGPA growth deltas (e.g. `+0.6` SGPA delta), consistency scores, and trajectory statuses (`HIGH_GROWTH`, `STEADY`, `DECLINING`) from `semester_marks`.
4. **`DomainTaggingAgent`** (`backend/agents/domain_tagging_agent.py`):
   * Classifies achievements and projects into 5 core domains: **TECHNICAL, RESEARCH, INNOVATION, COMMUNICATION, DESIGN**.
5. **`FacultyExpertiseAgent`** (`backend/agents/faculty_expertise_agent.py`):
   * Matches candidates with faculty research areas in `people.faculty_expertise` based on multidimensional domain scores and skill overlaps (without hardcoded `domain = 'RESEARCH'` restrictions!).
6. **`OutcomeTrackingAgent`** (`backend/agents/outcome_tracking_agent.py`):
   * Tracks participation lifecycle: `RECOMMENDED` → `ASSIGNED` → `ACCEPTED` → `IN_PROGRESS` → `COMPLETED` → `DROPPED`.
   * **Closed Feedback Loop:** Converts completed research assistantships into verified institutional evidence and recalculates student profiles.
7. **`FairnessAuditAgent`** (`backend/agents/fairness_audit_agent.py`):
   * Audits non-placement opportunity distribution across departments/branches to ensure equitable access without fabricating demographic data.

---

## 🎙️ Key Talking Points for Evaluator Q&A

### Q1: "How is this different from a simple job board or placement portal?"
* **Answer:** Traditional portals are static forms with manual filtering. Placement Ops AI is a **protocol-driven multi-agent ecosystem**. It parses raw JDs automatically, runs explainable ML matching with SHAP feature breakdowns, auto-proposes conflict-free interview schedules, and features Agent 13 to discover hidden student talent.

### Q2: "What is your Human-in-the-Loop strategy? Do AI agents make autonomous decisions?"
* **Answer:** Agents handle **operations and recommendations**, not final human decisions. Through strict **`ACT_WITH_APPROVAL` constraints**, every major action (confirming a JD, approving a shortlist, locking an interview schedule, or assigning a student to a research project) requires explicit TPO or Faculty authorization. All actions are tracked in `audit_logs`.

### Q3: "How does Agent 13 evaluate student potential without falling for self-reported resume fluff?"
* **Answer:** Agent 13 uses a **Weighted Evidence Verification Model**. Self-reported claims are marked `PROVISIONAL` and carry a reduced weight (0.3). Only when a Faculty member or TPO verifies the achievement through the verification queue does it become `VERIFIED` evidence (weight 1.0).

### Q4: "How does the AI matching work? Is it a black box?"
* **Answer:** No. Candidate matching uses weighted vector scoring across skills, academics, and projects, combined with **SHAP (SHapley Additive exPlanations)**. Recruiter and TPO cards explicitly display feature importance metrics (e.g. *"+40% Skill Match in Python/SQL, +30% Academic CGPA 9.2"*).

### Q5: "What LLM architecture are you using?"
* **Answer:** We use a **Hybrid AI Strategy**. The platform integrates directly with Hugging Face Inference models (`Mistral-7B-Instruct`, `Qwen-2.5`, `Llama-3.2`). If the network is offline or no API key is provided, the backend seamlessly routes queries through our built-in domain AI engine so the platform remains 100% operational.

---

## 🧪 Verification & Build Status

* **Backend Compilation**: `python -c "import backend.main"` passed with code 0.
* **Agent 13 End-to-End Test**: `python backend/test_agent13_e2e.py` passed cleanly (`ALL AGENT 13 END-TO-END TESTS PASSED`).
* **Frontend Production Build**: `npx next build` compiled successfully (0 errors).
* **Git Repository**: Pushed to `main` branch at [`github.com/sushma265/Placement-Ops-AI`](https://github.com/sushma265/Placement-Ops-AI.git).
