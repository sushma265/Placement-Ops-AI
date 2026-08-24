import os
import sys
from dotenv import load_dotenv

# Ensure the parent directory of backend/ is in sys.path so 'backend' imports resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Loads backend/.env into the process environment. Nothing in this codebase
# did this before -- .env values (SUPABASE_JWT_SECRET, HUGGINGFACE_API_KEY,
# etc.) were silently ignored no matter what the file contained. Must run
# before any of the backend.* imports below, since supabase_auth.py and
# llm_client.py read these via os.environ.get(...) at call time.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from fastapi import FastAPI, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import datetime
import uuid
import io
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from backend.database import get_db
from backend.models import Student, Drive, EligibilityResult, MatchScore, Interview, ExceptionItem, Notification, AuditLog, ProfileRole
from backend.deps.supabase_auth import (
    CurrentUser,
    get_current_user,
    get_verified_claims,
    require_role,
)
from backend.utils.profile_completion import compute_profile_completion_pct
from backend.utils.llm_client import get_hf_token, call_llm, DEFAULT_MODEL
from backend.agents.context_router import ContextRouter, ContextObject
from backend.agents.resume_agent import ResumeAgent
from backend.agents.jd_intake_agent import JDIntakeAgent
from backend.agents.eligibility_agent import EligibilityAgent
from backend.agents.matching_agent import MatchingAgent
from backend.agents.scheduling_agent import SchedulingAgent
from backend.agents.coordination_agent import CoordinationAgent
from backend.agents.notification_agent import NotificationAgent
from backend.agents.exception_agent import ExceptionAgent
from backend.agents.analytics_agent import AnalyticsAgent
from backend.agents.reporting_agent import ReportingAgent

app = FastAPI(title="Placement Ops - AI Recruiter Agent Backend")

# Enable CORS for frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "resumes"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")), name="uploads")

@app.get("/")
def read_root():
    return {"message": "Placement Ops Core Multi-Agent API is running."}

class SyncProfileRequest(BaseModel):
    """Sent once after Supabase login/signup. `role` is only honored the
    FIRST time this is called for a given profile_id -- it locks in the
    role in profile_roles and is ignored on every subsequent call, so a
    later request can't silently change someone's role."""
    role: str  # student, recruiter, tpo

ALLOWED_ROLES = {"student", "recruiter", "tpo"}

@app.post("/auth/sync-profile")
def sync_profile(req: SyncProfileRequest, request: Request, db: Session = Depends(get_db)):
    """
    Single entrypoint for turning a verified Supabase session into an
    application identity. Idempotent: safe to call on every login.

    NOTE (hackathon scope): any authenticated Supabase user may currently
    self-select role="tpo" on their first sync. Before a real deployment,
    gate the "tpo" role behind an admin invite/allowlist so a student
    account can't claim to be a placement officer -- that's the one
    remaining privilege-escalation gap in this milestone, called out
    explicitly rather than silently shipped.
    """
    payload = get_verified_claims(request)
    profile_id = payload.get("sub")
    email = payload.get("email")
    if not profile_id or not email:
        raise HTTPException(status_code=401, detail="Token payload missing sub/email.")

    if req.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(ALLOWED_ROLES)}.")

    record = db.query(ProfileRole).filter(ProfileRole.profile_id == profile_id).first()
    if not record:
        record = ProfileRole(profile_id=profile_id, email=email, role=req.role)
        db.add(record)
        db.commit()
        db.refresh(record)

    role = record.role  # locked to first-sync value; req.role is ignored after that

    if role == "student":
        student = db.query(Student).filter(Student.profile_id == profile_id).first()
        if not student:
            # Claim a pre-existing seeded/demo row with a matching email that
            # hasn't been claimed by any account yet, instead of creating a
            # second, blank row for the same person.
            student = db.query(Student).filter(
                Student.email == email, Student.profile_id.is_(None)
            ).first()
            if student:
                student.profile_id = profile_id
                db.commit()
                db.refresh(student)
        if not student:
            user_metadata = payload.get("user_metadata", {}) or {}
            student = Student(
                profile_id=profile_id,
                name=user_metadata.get("full_name") or user_metadata.get("name") or email.split("@")[0],
                email=email,
                branch="",
                cgpa=0.0,
                tenth_pct=0.0,
                twelfth_pct=0.0,
                backlog_count=0,
                api_score=0.0,
                ssi_score=0.0,
                prs_score=0.0,
            )
            db.add(student)
            db.commit()
            db.refresh(student)
        return {
            "role": "student",
            "profile_id": profile_id,
            "student_id": student.id,
            "email": student.email,
            "name": student.name,
            # Frontend uses this to route first-time users into onboarding
            # instead of showing fabricated demo stats.
            "profile_complete": bool(student.branch and student.cgpa),
        }

    if role == "recruiter":
        # No dedicated recruiter/company table yet -- that's Milestone 1+
        # (Recruiter Dashboard) scope. Identity is confirmed; profile
        # completion (company name, etc.) happens there.
        return {"role": "recruiter", "profile_id": profile_id, "email": email}

    # role == "tpo"
    return {"role": "tpo", "profile_id": profile_id, "email": email}


# ==========================================
# STUDENTS ENDPOINTS
# ==========================================
@app.get("/students")
def get_students(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("recruiter", "tpo")),
):
    return db.query(Student).order_by(Student.name).all()


class StudentProfileUpdate(BaseModel):
    """All fields optional -- PATCH semantics, only sent fields are updated."""
    name: Optional[str] = None
    branch: Optional[str] = None
    cgpa: Optional[float] = None
    tenth_pct: Optional[float] = None
    twelfth_pct: Optional[float] = None
    semester_marks: Optional[Dict[str, float]] = None
    backlog_count: Optional[int] = None
    skills: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    internship_history: Optional[List[Dict[str, Any]]] = None
    hackathons: Optional[List[Dict[str, Any]]] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    coding_profiles: Optional[Dict[str, str]] = None
    preferred_roles: Optional[List[str]] = None
    expected_salary: Optional[float] = None
    location_preference: Optional[List[str]] = None
    languages: Optional[List[str]] = None


def _get_own_student(db: Session, user: CurrentUser) -> Student:
    student = db.query(Student).filter(Student.profile_id == user.profile_id).first()
    if not student:
        raise HTTPException(
            status_code=404,
            detail="No student record linked to this account yet. Call /auth/sync-profile first.",
        )
    return student


@app.get("/students/me")
def get_my_student_profile(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("student")),
):
    student = _get_own_student(db, user)
    payload = {c.name: getattr(student, c.name) for c in Student.__table__.columns}
    payload["profile_completion_pct"] = compute_profile_completion_pct(student)
    return payload


NON_NEGATIVE_FIELDS = {"cgpa", "tenth_pct", "twelfth_pct", "backlog_count", "expected_salary"}

@app.patch("/students/me")
def update_my_student_profile(
    req: StudentProfileUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("student")),
):
    student = _get_own_student(db, user)

    updates = req.dict(exclude_unset=True)
    for field, value in updates.items():
        if field in NON_NEGATIVE_FIELDS and value is not None and value < 0:
            raise HTTPException(status_code=400, detail=f"{field} cannot be negative.")
        if field == "cgpa" and value is not None and value > 10:
            raise HTTPException(status_code=400, detail="cgpa must be between 0 and 10.")
        setattr(student, field, value)

    db.commit()
    db.refresh(student)

    db.add(AuditLog(
        action="profile_updated",
        target_type="student",
        target_id=student.id,
        performed_by=student.email,
        details=f"Updated fields: {', '.join(updates.keys())}",
    ))
    db.commit()

    payload = {c.name: getattr(student, c.name) for c in Student.__table__.columns}
    payload["profile_completion_pct"] = compute_profile_completion_pct(student)
    return payload


RESUME_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "resumes")
ALLOWED_RESUME_TYPES = {"application/pdf"}
MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024  # 5MB

@app.post("/students/me/resume")
async def upload_my_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("student")),
):
    student = _get_own_student(db, user)

    if file.content_type not in ALLOWED_RESUME_TYPES:
        raise HTTPException(status_code=400, detail="Resume must be a PDF.")

    contents = await file.read()
    if len(contents) > MAX_RESUME_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="Resume must be under 5MB.")

    os.makedirs(RESUME_UPLOAD_DIR, exist_ok=True)
    # profile_id-based filename: deterministic, avoids collisions across
    # students, and overwrites cleanly on re-upload.
    safe_name = f"{user.profile_id}.pdf"
    dest_path = os.path.join(RESUME_UPLOAD_DIR, safe_name)
    with open(dest_path, "wb") as f:
        f.write(contents)

    # NOTE (hackathon scope): this writes to local disk, which does not
    # survive a redeploy on most hosting platforms (Render/Railway/Fly all
    # use ephemeral filesystems on the free/starter tiers). Fine for a demo;
    # swap for Supabase Storage before a real deployment.
    student.resume_url = f"/uploads/resumes/{safe_name}"
    student.resume_filename = file.filename
    db.commit()
    db.refresh(student)

    db.add(AuditLog(
        action="resume_uploaded",
        target_type="student",
        target_id=student.id,
        performed_by=student.email,
        details=file.filename,
    ))
    db.commit()

    return {"resume_url": student.resume_url, "resume_filename": student.resume_filename}


@app.post("/students/me/resume/analyze")
def analyze_my_resume(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("student")),
):
    student = _get_own_student(db, user)
    if not student.resume_url:
        raise HTTPException(status_code=400, detail="Upload a resume before running analysis.")

    resume_path = os.path.join(RESUME_UPLOAD_DIR, os.path.basename(student.resume_url))
    resume_text = ResumeAgent.extract_text_from_pdf(resume_path)
    target_skills = [s.get("skill") for s in (student.skills or []) if s.get("skill")]

    result = ResumeAgent.analyze(resume_text, target_skills=target_skills, hf_token=get_hf_token())

    student.resume_ats_score = result.get("ats_score")
    student.resume_analysis = result
    student.resume_analyzed_at = datetime.datetime.utcnow()
    db.commit()

    db.add(AuditLog(
        action="resume_analyzed",
        target_type="student",
        target_id=student.id,
        performed_by=student.email,
        details=f"source={result.get('source')}",
    ))
    db.commit()

    return result


@app.get("/students/me/resume/analysis")
def get_my_resume_analysis(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("student")),
):
    student = _get_own_student(db, user)
    if not student.resume_analysis:
        raise HTTPException(status_code=404, detail="No resume analysis yet. Run analysis first.")
    return {**student.resume_analysis, "analyzed_at": student.resume_analyzed_at}


class GenerateBulletsRequest(BaseModel):
    project_title: str
    description: str

@app.post("/students/me/resume/bullets")
def generate_resume_bullets(
    req: GenerateBulletsRequest,
    user: CurrentUser = Depends(require_role("student")),
):
    if not req.project_title.strip() or not req.description.strip():
        raise HTTPException(status_code=400, detail="project_title and description are required.")
    return ResumeAgent.generate_bullets(req.project_title, req.description, hf_token=get_hf_token())


class GenerateForDriveRequest(BaseModel):
    drive_id: int

@app.post("/students/me/resume/cover-letter")
def generate_cover_letter(
    req: GenerateForDriveRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("student")),
):
    student = _get_own_student(db, user)
    drive = db.query(Drive).filter(Drive.id == req.drive_id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found.")

    skills = [s.get("skill") for s in (student.skills or []) if s.get("skill")]
    result = ResumeAgent.generate_cover_letter(
        student.name, student.branch, skills, drive.company_name, drive.role_title,
        drive.jd_raw_text or "", hf_token=get_hf_token(),
    )
    return result


@app.post("/students/me/resume/cold-email")
def generate_cold_email(
    req: GenerateForDriveRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("student")),
):
    student = _get_own_student(db, user)
    drive = db.query(Drive).filter(Drive.id == req.drive_id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found.")

    skills = [s.get("skill") for s in (student.skills or []) if s.get("skill")]
    result = ResumeAgent.generate_cold_email(
        student.name, student.branch, skills, drive.company_name, drive.role_title,
        hf_token=get_hf_token(),
    )
    return result


@app.post("/students/me/resume/match-drive")
def match_resume_to_drive(
    req: GenerateForDriveRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("student")),
):
    """Self-service 'how well does my resume match this specific job' check.
    Distinct from the TPO/recruiter-facing AI Matching Engine (which ranks
    students for a drive cohort-wide) -- this is a Resume AI tool for the
    student's own use."""
    student = _get_own_student(db, user)
    if not student.resume_url:
        raise HTTPException(status_code=400, detail="Upload a resume before checking a match.")

    drive = db.query(Drive).filter(Drive.id == req.drive_id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found.")

    resume_path = os.path.join(RESUME_UPLOAD_DIR, os.path.basename(student.resume_url))
    resume_text = ResumeAgent.extract_text_from_pdf(resume_path)

    required_skills_field = drive.required_skills or {}
    if isinstance(required_skills_field, dict):
        target_skills = list(required_skills_field.get("required", [])) + list(required_skills_field.get("preferred", []))
    elif isinstance(required_skills_field, list):
        target_skills = required_skills_field
    else:
        target_skills = []

    result = ResumeAgent.compare_to_jd(
        resume_text, target_skills, drive.jd_raw_text or "",
        hf_token=get_hf_token(),
    )
    return result


def _derive_application_status(student: Student, drive: Drive, match: Optional[MatchScore], interviews: List[Interview]) -> str:
    """Single source of truth for a student's status on a drive they've
    applied to. Only ever returns Rejected/Offer if MatchScore.outcome was
    actually set by a recruiter -- never inferred/guessed."""
    if match and match.outcome == "offer":
        return "Offer"
    if match and match.outcome == "rejected":
        return "Rejected"
    if any(i.status == "completed" for i in interviews):
        return "Interview Completed"
    if any(i.status == "scheduled" for i in interviews):
        return "Interview Scheduled"
    if match and match.approved:
        return "Shortlisted"
    return "Applied"


@app.get("/students/me/dashboard")
def get_my_dashboard(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("student")),
):
    student = _get_own_student(db, user)

    # --- Applied jobs (real -- driven by student.applied_drives) ---
    applied_jobs = []
    if student.applied_drives:
        drives_by_id = {d.id: d for d in db.query(Drive).filter(Drive.id.in_(student.applied_drives)).all()}
        matches_by_drive = {
            m.drive_id: m for m in db.query(MatchScore).filter(
                MatchScore.student_id == student.id, MatchScore.drive_id.in_(student.applied_drives)
            ).all()
        }
        interviews_by_drive: Dict[int, List[Interview]] = {}
        for iv in db.query(Interview).filter(
            Interview.student_id == student.id, Interview.drive_id.in_(student.applied_drives)
        ).all():
            interviews_by_drive.setdefault(iv.drive_id, []).append(iv)

        for drive_id in student.applied_drives:
            drive = drives_by_id.get(drive_id)
            if not drive:
                continue
            match = matches_by_drive.get(drive_id)
            interviews = interviews_by_drive.get(drive_id, [])
            applied_jobs.append({
                "drive_id": drive.id,
                "company_name": drive.company_name,
                "role_title": drive.role_title,
                "package_min": drive.package_min,
                "package_max": drive.package_max,
                "location": drive.location,
                "status": _derive_application_status(student, drive, match, interviews),
            })

    # --- Eligible jobs (published drives the student is eligible for and hasn't applied to) ---
    eligible_drive_ids = {
        r.drive_id for r in db.query(EligibilityResult).filter(
            EligibilityResult.student_id == student.id, EligibilityResult.eligible == True
        ).all()
    }
    applied_ids = set(student.applied_drives or [])
    eligible_jobs = []
    if eligible_drive_ids - applied_ids:
        for drive in db.query(Drive).filter(
            Drive.id.in_(eligible_drive_ids - applied_ids), Drive.status == "published"
        ).all():
            eligible_jobs.append({
                "drive_id": drive.id,
                "company_name": drive.company_name,
                "role_title": drive.role_title,
                "package_min": drive.package_min,
                "package_max": drive.package_max,
                "location": drive.location,
                # Real matching (Milestone 3 - AI Matching Engine) isn't wired
                # up to this view yet -- no match % shown until it is.
                "match_pct": None,
            })

    # --- Upcoming interviews ---
    # NOTE: time_slot is a free-text string (e.g. "2026-08-22 10:00 - 10:30"),
    # not a real datetime column, so we can't reliably filter to "future"
    # server-side -- we return all non-terminal interviews and let the
    # client sort. Flagged as technical debt below.
    interviews = db.query(Interview).filter(
        Interview.student_id == student.id, Interview.status == "scheduled"
    ).order_by(Interview.time_slot.asc()).all()
    upcoming_interviews = [{
        "interview_id": iv.id,
        "drive_id": iv.drive_id,
        "company_name": (db.query(Drive.company_name).filter(Drive.id == iv.drive_id).scalar()),
        "time_slot": iv.time_slot,
        "room_or_link": iv.room_or_link,
        "panel_members": iv.panel_members,
    } for iv in interviews]

    # --- Notifications ---
    notifications = db.query(Notification).filter(
        Notification.recipient_type == "student", Notification.recipient_id == student.id
    ).order_by(Notification.sent_at.desc()).limit(10).all()
    notification_payload = [{
        "id": n.id,
        "message": n.message_template,
        "sent_at": n.sent_at,
        "delivery_status": n.delivery_status,
    } for n in notifications]

    # --- Recent activity (reuses AuditLog -- only reflects events from
    # this milestone onward, since nothing wrote to it before) ---
    activity = db.query(AuditLog).filter(
        AuditLog.performed_by == student.email
    ).order_by(AuditLog.timestamp.desc()).limit(10).all()
    activity_payload = [{
        "action": a.action,
        "target_type": a.target_type,
        "details": a.details,
        "timestamp": a.timestamp,
    } for a in activity]

    return {
        "profile": {
            "name": student.name,
            "branch": student.branch,
            "cgpa": student.cgpa,
            "placement_readiness_score": student.prs_score,
            "profile_completion_pct": compute_profile_completion_pct(student),
            "resume_ats_score": student.resume_ats_score,
        },
        "stats": {
            "profile_completion_pct": compute_profile_completion_pct(student),
            "placement_readiness_score": student.prs_score,
            "resume_ats_score": student.resume_ats_score,
            "applied_jobs_count": len(applied_jobs),
            "eligible_jobs_count": len(eligible_jobs),
            "upcoming_interviews_count": len(upcoming_interviews),
            "notifications_count": len(notification_payload),
        },
        "eligible_jobs": eligible_jobs,
        "applied_jobs": applied_jobs,
        "upcoming_interviews": upcoming_interviews,
        "notifications": notification_payload,
        "recent_activity": activity_payload,
        # Skill gap analysis is real elsewhere (AnalyticsAgent, TPO-facing,
        # cohort-level) but not yet wired to a per-student view. Placeholder
        # per this milestone's brief -- no fabricated missing-skills/
        # recommendations data.
        "skill_gap": {
            "current_skills": student.skills,
            "missing_skills": [],
            "recommendations": [],
        },
    }


@app.post("/students/me/apply/{drive_id}")
def apply_to_drive(
    drive_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("student")),
):
    student = _get_own_student(db, user)

    drive = db.query(Drive).filter(Drive.id == drive_id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found.")
    if drive.status != "published":
        raise HTTPException(status_code=400, detail="This drive is not open for applications.")

    applied = list(student.applied_drives or [])
    if drive_id in applied:
        raise HTTPException(status_code=400, detail="You've already applied to this drive.")

    eligibility = db.query(EligibilityResult).filter(
        EligibilityResult.student_id == student.id, EligibilityResult.drive_id == drive_id
    ).first()
    if eligibility is not None and not eligibility.eligible:
        raise HTTPException(status_code=403, detail="You are not eligible for this drive.")

    applied.append(drive_id)
    student.applied_drives = applied
    db.commit()

    db.add(AuditLog(
        action="applied",
        target_type="drive",
        target_id=drive_id,
        performed_by=student.email,
        details=f"Applied to {drive.company_name} - {drive.role_title}",
    ))
    db.commit()

    return {"drive_id": drive_id, "status": "Applied"}


@app.get("/students/{id}")
def get_student_details(
    id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    student = db.query(Student).filter(Student.id == id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if user.role == "student" and student.profile_id != user.profile_id:
        raise HTTPException(status_code=403, detail="You can only view your own profile.")
    return student

# ==========================================
# DRIVES (JD INTAKE) ENDPOINTS
# ==========================================
@app.get("/drives")
def get_drives(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return db.query(Drive).order_by(Drive.created_at.desc()).all()

@app.get("/drives/{id}")
def get_drive(
    id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    drive = db.query(Drive).filter(Drive.id == id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found")
    return drive

class CreateDriveRequest(BaseModel):
    company_name: str
    jd_raw_text: str

class JDRequest(BaseModel):
    company_name: str
    jd_raw_text: str

@app.post("/drives")
def create_drive(
    req: JDRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("recruiter")),
):
    # 1. Start intake session
    session_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    
    # Run JDIntakeAgent to parse raw text
    parsed = JDIntakeAgent.parse_jd(req.jd_raw_text)
    
    # Save parsed draft into Drive
    drive = Drive(
        recruiter_profile_id=user.profile_id,
        company_name=req.company_name or parsed.get("company_name", "Unknown"),
        role_title=parsed.get("role_title"),
        jd_raw_text=req.jd_raw_text,
        required_skills=parsed.get("required_skills"),
        cgpa_cutoff=parsed.get("cgpa_cutoff"),
        eligible_branches=parsed.get("eligible_branches"),
        package_min=parsed.get("package_min"),
        package_max=parsed.get("package_max"),
        headcount=parsed.get("headcount"),
        status="draft",
        stage="intake"
    )
    db.add(drive)
    db.commit()
    db.refresh(drive)
    
    # Return draft drive + explanations for review
    return {
        "drive": drive,
        "session_id": session_id,
        "task_id": task_id,
        "explanations": parsed.get("explanations")
    }

class ConfirmDriveRequest(BaseModel):
    company_name: str
    role_title: str
    cgpa_cutoff: float
    eligible_branches: List[str]
    package_min: float
    package_max: float
    headcount: int
    required_skills: Dict[str, List[str]]

@app.patch("/drives/{id}/confirm")
def confirm_drive(
    id: int,
    req: ConfirmDriveRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("recruiter", "tpo")),
):
    drive = db.query(Drive).filter(Drive.id == id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found")
    if user.role == "recruiter" and drive.recruiter_profile_id != user.profile_id:
        raise HTTPException(status_code=403, detail="You can only confirm your own drives.")

    # Apply human-approved/modified fields
    drive.company_name = req.company_name
    drive.role_title = req.role_title
    drive.cgpa_cutoff = req.cgpa_cutoff
    drive.eligible_branches = req.eligible_branches
    drive.package_min = req.package_min
    drive.package_max = req.package_max
    drive.headcount = req.headcount
    drive.required_skills = req.required_skills
    drive.status = "published"
    
    db.commit()
    
    # Trigger EligibilityAgent in background via context object router
    context = ContextObject(
        drive_id=drive.id,
        task_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        payload={},
        routing=["EligibilityAgent"]
    )
    
    updated_context = ContextRouter.execute_next(context, db)
    
    # Log Audit
    audit = AuditLog(
        action="confirm_jd",
        target_type="drive",
        target_id=drive.id,
        performed_by="TPO",
        details=f"TPO confirmed JD extraction parameters. Drive status is now Published."
    )
    db.add(audit)
    db.commit()
    
    return {
        "drive": drive,
        "context_payload": updated_context.payload
    }

# ==========================================
# ELIGIBILITY ENDPOINTS
# ==========================================
@app.get("/drives/{id}/eligibility")
def get_drive_eligibility(
    id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("recruiter", "tpo")),
):
    results = db.query(EligibilityResult).filter(EligibilityResult.drive_id == id).all()
    
    output = []
    for r in results:
        student = db.query(Student).filter(Student.id == r.student_id).first()
        if student:
            output.append({
                "eligibility_id": r.id,
                "student_id": student.id,
                "student_name": student.name,
                "branch": student.branch,
                "cgpa": student.cgpa,
                "backlog_count": student.backlog_count,
                "current_best_offer": student.current_best_offer,
                "eligible": r.eligible,
                "reason": r.reason,
                "overridden_by_tpo": r.overridden_by_tpo,
                "flagged_for_review": r.flagged_for_review
            })
            
    return output

class OverrideEligibilityRequest(BaseModel):
    eligible: bool
    reason: str
    tpo_name: str = "TPO"

@app.patch("/eligibility/{id}/override")
def override_eligibility(
    id: int,
    req: OverrideEligibilityRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    result = db.query(EligibilityResult).filter(EligibilityResult.id == id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Eligibility record not found")
        
    student = db.query(Student).filter(Student.id == result.student_id).first()
    drive = db.query(Drive).filter(Drive.id == result.drive_id).first()
    
    old_status = result.eligible
    result.eligible = req.eligible
    result.overridden_by_tpo = True
    result.reason = f"[TPO Override] {req.reason} (Originally: {result.reason})"
    
    # Audit log
    audit = AuditLog(
        action="eligibility_override",
        target_type="eligibility",
        target_id=id,
        performed_by=req.tpo_name,
        details=f"Overrode eligibility for student '{student.name if student else 'ID '+str(result.student_id)}' in drive '{drive.company_name if drive else 'ID '+str(result.drive_id)}'. Changed from {old_status} to {req.eligible}."
    )
    db.add(audit)
    db.commit()
    
    return {"message": "Eligibility override applied successfully", "result": result}

# ==========================================
# SHORTLIST / MATCHING ENDPOINTS
# ==========================================
@app.get("/drives/{id}/shortlist")
def get_drive_shortlist(
    id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("recruiter", "tpo")),
):
    # If shortlist doesn't exist, we run matching agent.
    # Note: Shortlist is calculated based on eligible candidates.
    scores = db.query(MatchScore).filter(MatchScore.drive_id == id).order_by(MatchScore.rank).all()
    
    if not scores:
        # Run matching
        MatchingAgent.match_and_rank_students(id, db)
        scores = db.query(MatchScore).filter(MatchScore.drive_id == id).order_by(MatchScore.rank).all()

    output = []
    for s in scores:
        student = db.query(Student).filter(Student.id == s.student_id).first()
        if student:
            output.append({
                "match_id": s.id,
                "student_id": student.id,
                "student_name": student.name,
                "branch": student.branch,
                "cgpa": student.cgpa,
                "overall_score": s.overall_score,
                "skill_score": s.skill_score,
                "academic_score": s.academic_score,
                "project_score": s.project_score,
                "readiness_score": s.readiness_score,
                "feature_importance": s.feature_importance,
                "rank": s.rank,
                "approved": s.approved
            })
    return output

class ApproveShortlistRequest(BaseModel):
    approved_candidate_ids: List[int] # List of Student IDs approved
    tpo_name: str = "TPO"

@app.patch("/drives/{id}/shortlist/approve")
def approve_shortlist(
    id: int,
    req: ApproveShortlistRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    drive = db.query(Drive).filter(Drive.id == id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found")
        
    # Reset all approved flags for this drive
    db.query(MatchScore).filter(MatchScore.drive_id == id).update({"approved": False})
    
    # Set approved flags for selected
    db.query(MatchScore).filter(
        MatchScore.drive_id == id,
        MatchScore.student_id.in_(req.approved_candidate_ids)
    ).update({"approved": True})
    
    drive.stage = "scheduling"
    db.commit()
    
    # Audit log
    audit = AuditLog(
        action="approve_shortlist",
        target_type="shortlist",
        target_id=id,
        performed_by=req.tpo_name,
        details=f"TPO approved shortlist of {len(req.approved_candidate_ids)} candidates: {req.approved_candidate_ids}."
    )
    db.add(audit)
    db.commit()
    
    return {"message": f"Shortlist of {len(req.approved_candidate_ids)} candidates approved and ready for scheduling."}

# ==========================================
# SCHEDULING & COORDINATION ENDPOINTS
# ==========================================
class ProposeScheduleRequest(BaseModel):
    panel_members: List[str]
    available_slots: List[str]
    rooms: List[str]

@app.post("/drives/{id}/schedule/propose")
def propose_schedule(
    id: int,
    req: ProposeScheduleRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    proposed = SchedulingAgent.propose_schedule(
        id, req.panel_members, req.available_slots, req.rooms, db
    )
    
    # Perform coordination validation check immediately
    CoordinationAgent.validate_all_interviews(db)
    
    return proposed

@app.get("/drives/{id}/interviews")
def get_drive_interviews(
    id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    query = db.query(Interview).filter(Interview.drive_id == id)
    if user.role == "student":
        # Without this filter, any student could see every other student's
        # name and interview schedule for this drive just by knowing the
        # drive ID -- recruiters/TPO legitimately see the full list for
        # coordination, but a student may only see their own record.
        own_student = db.query(Student).filter(Student.profile_id == user.profile_id).first()
        query = query.filter(Interview.student_id == (own_student.id if own_student else -1))
    interviews = query.all()

    output = []
    for intr in interviews:
        student = db.query(Student).filter(Student.id == intr.student_id).first()
        output.append({
            "interview_id": intr.id,
            "student_id": intr.student_id,
            "student_name": student.name if student else "Unknown",
            "panel_members": intr.panel_members,
            "room_or_link": intr.room_or_link,
            "time_slot": intr.time_slot,
            "status": intr.status,
            "conflict_flag": intr.conflict_flag
        })
    return output

class ConfirmScheduleRequest(BaseModel):
    tpo_name: str = "TPO"

@app.patch("/schedule/{id}/confirm")
def confirm_schedule(
    id: int,
    req: ConfirmScheduleRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    # 'id' is drive_id
    drive = db.query(Drive).filter(Drive.id == id).first()
    if not drive:
        raise HTTPException(status_code=404, detail="Drive not found")
        
    drive.stage = "coordination"
    db.commit()
    
    # Run Coordination check
    CoordinationAgent.validate_all_interviews(db)
    
    # Trigger notifications if no conflicts
    conflicts = db.query(Interview).filter(
        Interview.drive_id == id,
        Interview.conflict_flag == True
    ).count()
    
    audit = AuditLog(
        action="confirm_schedule",
        target_type="schedule",
        target_id=id,
        performed_by=req.tpo_name,
        details=f"TPO confirmed proposed schedule for drive ID {id}. Checked coordination anomalies: {conflicts} conflicts remaining."
    )
    db.add(audit)
    db.commit()
    
    if conflicts == 0:
        # Move drive stage to notified and send notifications
        context = ContextObject(
            drive_id=id,
            task_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            payload={},
            routing=["NotificationAgent"]
        )
        ContextRouter.execute_next(context, db)
        return {"message": "Schedule confirmed and notifications dispatched successfully. Stage set to notified."}
    else:
        return {"message": f"Schedule locked. However, {conflicts} coordination conflicts remain. Please resolve in the exceptions screen before dispatching.", "conflicts_found": True}

class ResolveInterviewRequest(BaseModel):
    time_slot: str
    room_or_link: str
    panel_members: List[str]
    tpo_name: str = "TPO"

@app.patch("/interviews/{id}/resolve")
def resolve_interview(
    id: int,
    req: ResolveInterviewRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    res = CoordinationAgent.resolve_conflict(
        id, req.time_slot, req.room_or_link, req.panel_members, db, req.tpo_name
    )
    if not res:
        raise HTTPException(status_code=404, detail="Interview not found")
    return {"message": "Interview slot resolved and updated successfully."}

# ==========================================
# EXCEPTIONS ENDPOINTS
# ==========================================
@app.get("/exceptions")
def get_exceptions(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    exceptions = db.query(ExceptionItem).order_by(ExceptionItem.resolved, ExceptionItem.severity.desc()).all()
    output = []
    for exc in exceptions:
        drive = db.query(Drive).filter(Drive.id == exc.drive_id).first()
        output.append({
            "exception_id": exc.id,
            "drive_id": exc.drive_id,
            "company_name": drive.company_name if drive else "System Wide",
            "type": exc.type,
            "severity": exc.severity,
            "description": exc.description,
            "resolved": exc.resolved,
            "resolved_by": exc.resolved_by,
            "resolved_at": exc.resolved_at
        })
    return output

class ResolveExceptionRequest(BaseModel):
    resolved_by: str = "TPO"

@app.patch("/exceptions/{id}/resolve")
def resolve_exception(
    id: int,
    req: ResolveExceptionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    res = ExceptionAgent.resolve_exception(id, req.resolved_by, db)
    if not res:
        raise HTTPException(status_code=404, detail="Exception item not found")
    return {"message": "Exception marked as resolved."}

# ==========================================
# ANALYTICS ENDPOINTS
# ==========================================
@app.get("/analytics/skill-gap")
def get_skill_gap(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    return AnalyticsAgent.get_skill_gap_analysis(db)

@app.get("/analytics/readiness-trend")
def get_readiness_trend(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    return AnalyticsAgent.get_readiness_trends(db)

# ==========================================
# REPORTS ENDPOINTS
# ==========================================
@app.get("/reports/{drive_id}")
def get_drive_report(
    drive_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    # To support completed reports, let's mark the drive stage as completed if it was in notified stage
    drive = db.query(Drive).filter(Drive.id == drive_id).first()
    if drive and drive.stage in ["notified", "coordination", "scheduling"]:
        # Simulate drive completion
        drive.stage = "completed"
        drive.status = "closed"
        db.commit()

        # Update some interview statuses to 'completed' and 'no_show' for realistic stats
        interviews = db.query(Interview).filter(Interview.drive_id == drive_id).all()
        for idx, intr in enumerate(interviews):
            if idx % 5 == 0:
                intr.status = "no_show"
            else:
                intr.status = "completed"
        db.commit()

    return ReportingAgent.generate_drive_report(drive_id, db)

@app.get("/reports/{drive_id}/csv")
def get_drive_report_csv(
    drive_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    csv_str = ReportingAgent.export_report_csv(drive_id, db)
    drive = db.query(Drive).filter(Drive.id == drive_id).first()
    filename = f"{drive.company_name.lower().replace(' ', '_')}_placement_report.csv" if drive else "report.csv"
    
    return StreamingResponse(
        io.BytesIO(csv_str.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ==========================================
# AUDIT LOGS ENDPOINTS
# ==========================================
@app.get("/audit-logs")
def get_audit_logs(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()

# ==========================================
# NOTIFICATIONS FEED ENDPOINT
# ==========================================
@app.get("/notifications")
def get_notifications(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_role("tpo")),
):
    notifications = db.query(Notification).order_by(Notification.sent_at.desc()).all()
    output = []
    for n in notifications:
        student = db.query(Student).filter(Student.id == n.recipient_id).first()
        output.append({
            "notification_id": n.id,
            "drive_id": n.drive_id,
            "recipient_name": student.name if student else "Panelist",
            "recipient_type": n.recipient_type,
            "channel": n.channel,
            "message_template": n.message_template,
            "sent_at": n.sent_at,
            "delivery_status": n.delivery_status
        })
    return output

# ==========================================
# HUGGING FACE AI CHATBOT ENDPOINT
# ==========================================
class AIChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []
    model: Optional[str] = "mistralai/Mistral-7B-Instruct-v0.3"
    api_key: Optional[str] = None

def _resolve_chat_role(request: Request, db: Session) -> str:
    """Best-effort role resolution for the chat assistant's persona.
    Falls back to "guest" for signed-out visitors rather than trusting a
    client-supplied role field -- role_context used to be an arbitrary
    request field, which meant any caller could claim role_context="tpo"."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return "guest"
    try:
        payload = get_verified_claims(request)
        profile_id = payload.get("sub")
        record = db.query(ProfileRole).filter(ProfileRole.profile_id == profile_id).first()
        return record.role if record else "guest"
    except HTTPException:
        return "guest"

def generate_placement_ops_reply(query: str, role: str) -> str:
    q = query.lower()
    if "jd" in q or "intake" in q or "job description" in q:
        return "### 📄 JD Intake Agent Advice\nTo draft or parse a new Job Description:\n1. Navigate to **Recruitment Drives** -> **Upload / Paste JD**.\n2. The JD Intake Agent will parse role title, required skills, package, branch criteria, and CGPA cutoff automatically.\n3. Review and confirm the extracted metadata before publishing to candidates."
    elif "eligibility" in q or "criteria" in q or "cutoff" in q:
        return "### 🎯 Eligibility Engine Guidance\nEligibility is evaluated deterministically against criteria like:\n- **CGPA Cutoff** (e.g. 8.0/10)\n- **Eligible Branches** (e.g. CSE, ECE)\n- **Backlogs & Offer Limits**\n\nIf a student is flagged as ineligible due to a borderline metric, TPOs can apply a manual **TPO Override** with an auditable justification."
    elif "match" in q or "shap" in q or "shortlist" in q or "rank" in q:
        return "### ⚡ Matching Agent & SHAP Scoring\nCandidates are ranked based on a multi-vector match score combining:\n- **Skill Vector Match** (40% weight)\n- **Academic Performance** (30% weight)\n- **Project Score & Placement Readiness (PRS)** (30% weight)\n\nClick on any candidate card to view their **SHAP Feature Importance Breakdown** explaining why they were recommended."
    elif "schedule" in q or "interview" in q or "panel" in q:
        return "### 📅 Interview Scheduler & Coordination\nThe Scheduling Agent automatically matches candidates to interviewer panels and rooms to eliminate timing overlaps.\n- If a panelist or candidate double-books, the **Coordination Agent** flags an exception in your Exception Queue for resolution."
    elif "skill" in q or "gap" in q or "curriculum" in q:
        return "### 📊 Skill Gap & Analytics\nOur Analytics engine compares incoming company JD skill demands against current student skill profiles.\n- Common gap areas identified include Cloud Architecture (AWS/GCP), System Design, and Kubernetes.\n- TPOs can export these insights to update semester electives."
    else:
        return f"Hello! I am your **Placement Ops AI Assistant** powered by Hugging Face.\n\nI can help you with:\n- **JD Intake & Requirement Parsing**\n- **Student Eligibility & TPO Overrides**\n- **SHAP-based Candidate Matching**\n- **Interview Panel Scheduling & Conflict Resolution**\n- **Curriculum Skill Gap Analytics**\n\nHow can I assist you with your recruitment drive today?"

@app.post("/ai/chat")
def ai_chat(req: AIChatRequest, request: Request, db: Session = Depends(get_db)):
    role_context = _resolve_chat_role(request, db)
    hf_token = get_hf_token(req.api_key)

    system_prompt = f"""You are Placement Ops AI Assistant, an expert AI co-pilot for college placement operations, job drive management, candidate eligibility evaluation, interview scheduling, and curriculum skill gap analysis. 
You are currently assisting a user logged in as role: {role_context.upper()}. 
Provide clear, actionable, concise, and professional responses tailored to placement officers, recruiters, and students. Use markdown formatting with bullet points where appropriate."""

    messages = [{"role": "system", "content": system_prompt}]
    if req.history:
        for msg in req.history[-6:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": req.message})

    reply = call_llm(messages, hf_token, model=req.model or DEFAULT_MODEL)
    if reply is not None:
        return {"reply": reply, "source": "huggingface", "model": req.model or DEFAULT_MODEL}

    # Fallback domain-aware intelligent responder when offline or without HF key
    reply = generate_placement_ops_reply(req.message, role_context)
    return {
        "reply": reply, 
        "source": "placement_ops_local_ai", 
        "note": "Using Placement Ops built-in domain AI engine. Add a valid Hugging Face API key in settings or .env to connect directly to Hugging Face models."
    }