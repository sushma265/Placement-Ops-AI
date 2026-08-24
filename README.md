# PlacementOps AI

An AI-powered Campus Placement Management Platform that streamlines the placement process for Students, Recruiters, and Training & Placement Officers (TPOs).

---

# Features

## Authentication

- Supabase Authentication
- Google OAuth
- Email/Password Login
- JWT Protected Backend APIs
- Role-based Access Control
- Secure Profile Synchronization

Roles

- Student
- Recruiter
- TPO

---

# Student Features

## Student Dashboard

- Personalized dashboard
- Placement readiness score
- Upcoming interviews
- Eligible drives
- Applied drives
- Notifications
- Activity timeline

---

## Student Profile

Students can manage:

- Profile Photo
- Resume Upload
- GitHub
- LinkedIn
- Portfolio
- Coding Profiles
  - LeetCode
  - HackerRank
  - Codeforces
- Languages
- Projects
- Certifications
- Internship History
- Hackathons
- Skills
- Preferred Roles
- Expected Salary
- Location Preference

Automatic Profile Completion Percentage

---

## Resume AI

AI-powered resume analysis.

Features

- ATS Score
- Resume Skill Extraction
- Missing Skills Detection
- Resume Improvement Suggestions
- Job Description Matching
- Resume Bullet Generator
- Cover Letter Generator
- Cold Email Generator

Supports

- Hugging Face LLM
- Deterministic fallback when AI is unavailable

---

# Recruiter Features

- Create Placement Drives
- Manage Drives
- View Eligible Students
- Shortlist Candidates
- Schedule Interviews
- Candidate Ranking
- AI Match Scores

---

# TPO Features

- Dashboard
- Placement Analytics
- Placement Readiness
- Skill Gap Analytics
- Student Management
- Drive Management
- Reports
- CSV Export
- Exception Management
- Notifications
- Audit Logs

---

# AI Features

- AI Chat Assistant
- Resume AI
- Resume ATS Analysis
- Skill Gap Detection
- Candidate Matching
- Eligibility Explanation
- Career Assistant

---

# Security

- Supabase Authentication
- JWT Verification
- Role-based Authorization
- Protected Backend APIs
- Ownership Validation
- Server-side Role Resolution

---

# Tech Stack

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS

## Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- Supabase

## AI

- Hugging Face Inference API
- PyPDF
- Scikit-learn
- XGBoost

---

# Project Structure

```
frontend/
│
├── app/
│   ├── profile/
│   ├── resume-ai/
│   └── page.tsx
│
├── components/
│   ├── dashboards/
│   ├── cards/
│   ├── jobs/
│   ├── timeline/
│   └── ai/
│
└── lib/
    ├── api.ts
    ├── auth.ts
    ├── student-api.ts
    └── format.ts

backend/
│
├── agents/
│   ├── resume_agent.py
│   ├── notification_agent.py
│   ├── matching_agent.py
│   └── context_router.py
│
├── deps/
│   └── supabase_auth.py
│
├── utils/
│   ├── llm_client.py
│   └── profile_completion.py
│
├── uploads/
│   └── resumes/
│
├── models.py
├── database.py
├── seed.py
└── main.py
```

---

# Current Status

✅ Milestone 0 — Authentication Complete

- Supabase Auth
- JWT Verification
- Role-based Access
- Profile Sync

---

✅ Milestone 1 — Student Profile Complete

- Full Profile
- Resume Upload
- Profile Completion

---

✅ Student Dashboard Complete

- Dashboard
- Notifications
- Applications
- Interviews
- Analytics

---

✅ Resume AI Complete

- ATS Analysis
- Skill Extraction
- JD Matching
- Bullet Generator
- Cover Letter Generator
- Cold Email Generator

---

# Current Known Issue

Authentication currently throws:

```
Invalid session token: The specified alg value is not allowed
```

This is being fixed by updating JWT verification to correctly support modern Supabase JWT signing (HS256 and asymmetric JWKS-based verification where applicable).

---

# Next Milestone

Recruiter AI

- AI Candidate Ranking
- AI Resume Comparison
- Smart Shortlisting
- Interview Recommendations
- Candidate Insights
- Recruiter Copilot

---

# License

MIT License