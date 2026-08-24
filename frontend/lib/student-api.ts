import { apiFetch } from './api'

export interface StudentProfile {
  id: number
  profile_id: string | null
  name: string
  email: string
  branch: string
  cgpa: number
  tenth_pct: number
  twelfth_pct: number
  semester_marks: Record<string, number>
  backlog_count: number
  skills: { skill: string; level: string }[]
  certifications: { name: string; issuer: string }[]
  projects: { title: string; tech_stack: string[]; description?: string; link?: string }[]
  internship_history: { company: string; duration_months: number; role?: string }[]
  hackathons: { name: string; result?: string }[]
  current_best_offer: number | null
  applied_drives: number[]
  profile_photo_url: string | null
  resume_url: string | null
  resume_filename: string | null
  github_url: string | null
  linkedin_url: string | null
  portfolio_url: string | null
  coding_profiles: { leetcode?: string; codeforces?: string; hackerrank?: string }
  preferred_roles: string[]
  expected_salary: number | null
  location_preference: string[]
  languages: string[]
  resume_ats_score: number | null
  api_score: number
  ssi_score: number
  prs_score: number
  profile_completion_pct: number
}

export type StudentProfileUpdate = Partial<
  Omit<
    StudentProfile,
    | 'id'
    | 'profile_id'
    | 'email'
    | 'current_best_offer'
    | 'applied_drives'
    | 'profile_photo_url'
    | 'resume_url'
    | 'resume_filename'
    | 'resume_ats_score'
    | 'api_score'
    | 'ssi_score'
    | 'prs_score'
    | 'profile_completion_pct'
  >
>

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export async function getMyProfile(): Promise<StudentProfile> {
  return handle(await apiFetch('/students/me'))
}

export async function updateMyProfile(updates: StudentProfileUpdate): Promise<StudentProfile> {
  return handle(
    await apiFetch('/students/me', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
  )
}

export async function uploadMyResume(file: File): Promise<{ resume_url: string; resume_filename: string }> {
  const formData = new FormData()
  formData.append('file', file)
  // Note: don't set Content-Type manually -- the browser needs to set the
  // multipart boundary itself. apiFetch only adds the Authorization header.
  return handle(await apiFetch('/students/me/resume', { method: 'POST', body: formData }))
}

export interface DashboardJob {
  drive_id: number
  company_name: string
  role_title: string
  package_min: number
  package_max: number
  location: string | null
  status?: string
  match_pct?: number | null
}

export interface DashboardInterview {
  interview_id: number
  drive_id: number
  company_name: string | null
  time_slot: string
  room_or_link: string | null
  panel_members: string[]
}

export interface DashboardNotification {
  id: number
  message: string
  sent_at: string
  delivery_status: string
}

export interface DashboardActivity {
  action: string
  target_type: string
  details: string | null
  timestamp: string
}

export interface StudentDashboardData {
  profile: {
    name: string
    branch: string
    cgpa: number
    placement_readiness_score: number
    profile_completion_pct: number
    resume_ats_score: number | null
  }
  stats: {
    profile_completion_pct: number
    placement_readiness_score: number
    resume_ats_score: number | null
    applied_jobs_count: number
    eligible_jobs_count: number
    upcoming_interviews_count: number
    notifications_count: number
  }
  eligible_jobs: DashboardJob[]
  applied_jobs: DashboardJob[]
  upcoming_interviews: DashboardInterview[]
  notifications: DashboardNotification[]
  recent_activity: DashboardActivity[]
  skill_gap: {
    current_skills: { skill: string; level: string }[]
    missing_skills: string[]
    recommendations: string[]
  }
}

export async function getMyDashboard(): Promise<StudentDashboardData> {
  return handle(await apiFetch('/students/me/dashboard'))
}

export async function applyToDrive(driveId: number): Promise<{ drive_id: number; status: string }> {
  return handle(await apiFetch(`/students/me/apply/${driveId}`, { method: 'POST' }))
}

export interface ScoreBreakdownEntry {
  score: number
  max: number
  detail: string
}

export interface ResumeAnalysis {
  ats_score: number | null
  score_breakdown: Record<string, ScoreBreakdownEntry>
  extracted_skills: Record<string, string[]>
  missing_skills: string[]
  suggestions: string[]
  missing_keywords: string[]
  source: 'huggingface' | 'heuristic' | 'extraction_failed'
  analyzed_at?: string
}

export async function analyzeMyResume(): Promise<ResumeAnalysis> {
  return handle(await apiFetch('/students/me/resume/analyze', { method: 'POST' }))
}

export async function getMyResumeAnalysis(): Promise<ResumeAnalysis | null> {
  try {
    return await handle(await apiFetch('/students/me/resume/analysis'))
  } catch {
    return null
  }
}

export async function generateResumeBullets(
  projectTitle: string, description: string
): Promise<{ bullets: string[]; source: string }> {
  return handle(await apiFetch('/students/me/resume/bullets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_title: projectTitle, description }),
  }))
}

export async function generateCoverLetter(driveId: number): Promise<{ cover_letter: string; source: string }> {
  return handle(await apiFetch('/students/me/resume/cover-letter', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drive_id: driveId }),
  }))
}

export async function generateColdEmail(driveId: number): Promise<{ cold_email: string; source: string }> {
  return handle(await apiFetch('/students/me/resume/cold-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drive_id: driveId }),
  }))
}

export interface JDMatchResult {
  match_pct: number | null
  matched_skills: string[]
  missing_skills: string[]
  explanation: string
  source: 'huggingface' | 'heuristic' | 'extraction_failed'
}

export async function matchResumeToDrive(driveId: number): Promise<JDMatchResult> {
  return handle(await apiFetch('/students/me/resume/match-drive', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ drive_id: driveId }),
  }))
}
