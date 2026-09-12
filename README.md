# ⚡ Placement Ops AI — Autonomous Multi-Agent Placement & Career Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14+-000000.svg?style=flat&logo=next.js)](https://nextjs.org/)
[![Supabase](https://img.shields.io/badge/Supabase-Auth%20%26%20DB-3ECF8E.svg?style=flat&logo=supabase)](https://supabase.com/)
[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Inference-FFD21E.svg?style=flat&logo=huggingface)](https://huggingface.co/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1.svg?style=flat&logo=postgresql)](https://www.postgresql.org/)

---

## 📖 Executive Summary

Campus recruitment operations involve a high-stakes, multi-step pipeline: job description parsing, eligibility verification, candidate matching, interview panel scheduling, room coordination, notification dispatch, and reporting.

**Placement Ops AI** is an autonomous multi-agent platform designed to automate this end-to-end recruitment lifecycle while ensuring human-in-the-loop governance (TPO & Recruiter approvals). It features specialized AI agents for placement cell operations, faculty research discovery, and student career coaching.

---

## 🌟 Key Platform Modules & AI Agents

### 1. 🎓 AI Career Assistant (Student Profile Agents)
Interactive AI Co-Pilot on the Student Dashboard equipped with 5 specialized career sub-agents:
* 📄 **Improve Resume Agent**: Analyzes ATS scores, missing keywords, and section formatting; generates quantifiable STAR bullet points.
* 🔍 **Find Matching Jobs Agent**: Scans active campus recruitment drives, matches candidate CGPA/branch/skills, and highlights eligibility fit.
* 🎙️ **Interview Preparation Agent**: Prepares customized technical focus areas (DSA, System Design, SQL) and STAR project deep-dive questions.
* 📈 **Skill Roadmap Agent**: Evaluates skill gaps against company JDs to build a step-by-step 4-week learning roadmap.
* 🧭 **Career Advice Agent**: Delivers personalized career trajectory recommendations (SDE, Data Science, DevOps) tailored to branch & CGPA.

### 2. 🏛️ Core Multi-Agent Placement Pipeline
* 📄 **JDIntakeAgent**: Parses job descriptions (PDF/text) to extract role titles, required skills, package, CGPA cutoffs, and eligible branches.
* 🎯 **EligibilityAgent**: Filters candidate cohorts against academic cutoffs, backlog rules, and prior offer status.
* ⚡ **MatchingAgent**: Ranks eligible candidates using weighted multi-vector similarity scores and SHAP feature importance explanations.
* 📅 **SchedulingAgent**: Proposes interview slots matching panel availability, room capacities, and student schedules.
* 🤝 **CoordinationAgent**: Detects and resolves panelist/room double-bookings and scheduling anomalies.
* 🔔 **NotificationAgent**: Dispatches multi-channel email, SMS, and in-app alerts with automated templates.
* 📊 **AnalyticsAgent & ReportingAgent**: Computes cohort skill gaps, placement readiness trends, and exports accreditation compliance reports.
* 🛡️ **ExceptionAgent**: Surfaces pipeline anomalies into a centralized TPO action queue.

### 3. 🔬 Agent 13 — Talent Discovery & Non-Placement Opportunity Engine
Identifies high-performing students with capacity beyond standard placement curricula and channels them into faculty research projects and competitive technical tracks under strict `ACT_WITH_APPROVAL` human review controls.

---

## 🏗️ System Architecture

```
                          ┌─────────────────────────────┐
                          │   TPO / Student Dashboard   │
                          │   (Next.js 14 + Tailwind)   │
                          └───────────────┬─────────────┘
                                          │
                          ┌───────────────▼─────────────┐
                          │   FastAPI Context Router    │
                          │  (Shared Context Protocol)  │
                          └───────────────┬─────────────┘
                                          │
        ┌────────────┬────────────┬───────┴─────┬─────────────┬────────────┐
        ▼            ▼            ▼             ▼             ▼            ▼
   JDIntake     Eligibility   Matching     Scheduling     Coordination  Notification
    Agent          Agent        Agent        Agent           Agent        Agent
        │            │            │             │             │            │
        └────────────┴─────┬──────┴─────────────┴─────────────┴────────────┘
                           ▼
                  ┌───────────────────┐
                  │ Student AI Agents │──▶ Resume, Matching, Prep, Roadmap, Advice
                  │ Agent 13 Engine   │──▶ Talent Discovery & Research Projects
                  └────────┬──────────┘
                           ▼
                  ┌───────────────────┐
                  │ PostgreSQL & Supa │──▶ Auth, Profiles, Audit Logs, Drives
                  └───────────────────┘
```

---

## 🚀 Getting Started

### 1. Prerequisites
* **Python**: 3.10+
* **Node.js**: 18+
* **Database**: PostgreSQL (or Supabase connection string)

### 2. Backend Setup (FastAPI)
```bash
# Clone the repository
git clone https://github.com/sushma265/Placement-Ops-AI.git
cd Placement-Ops-AI

# Create environment and install dependencies
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# Start the FastAPI server
$env:PYTHONPATH="." ; .venv\Scripts\python -m uvicorn backend.main:app --port 8000 --reload
```
* **Interactive API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Frontend Setup (Next.js)
```bash
cd frontend
npm install
npm run dev
```
* **Application Interface**: [http://localhost:3000](http://localhost:3000)

---

## 🔐 Environment Variables

Create `backend/.env`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/placement_ops
HUGGINGFACE_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxxxxxxx
SUPABASE_JWT_SECRET=your_supabase_jwt_secret
```

Create `frontend/.env.local`:
```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-supabase-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
```

---

## 🛡️ Security & Governance
* **Human-in-the-loop**: Final candidate selections, eligibility overrides, and schedule locks require explicit TPO/Recruiter approval.
* **Audit Trail**: Full audit logging (`AuditLog` table) for every policy override and recommendation execution.
* **Role-Based Access Control (RBAC)**: Strict role boundaries for `student`, `recruiter`, `tpo`, `faculty`, `hod`, and `principal`.

---

## 📄 License
This project is licensed under the MIT License — see the LICENSE file for details.