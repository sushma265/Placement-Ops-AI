'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Loader2, Save, Upload, FileText, CheckCircle2, ArrowLeft, Plus, X, FolderGit2, Link2, Globe,
} from 'lucide-react'
import { supabase } from '@/lib/supabase'
import {
  getMyProfile, updateMyProfile, uploadMyResume, type StudentProfile, type StudentProfileUpdate,
} from '@/lib/student-api'

// ── small reusable bits (kept local -- page.tsx's helpers aren't exported) ──

function Field({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-[11px] font-mono uppercase tracking-wide text-muted-foreground">{label}</label>
      {children}
    </div>
  )
}

const inputClass =
  'w-full bg-input border border-border rounded-lg p-2.5 text-foreground text-xs font-semibold focus:border-primary focus:outline-none input-focus'

function TagListInput({ values, onChange, placeholder }: { values: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const v = draft.trim()
    if (v && !values.includes(v)) onChange([...values, v])
    setDraft('')
  }
  return (
    <div>
      <div className="flex gap-2">
        <input
          className={inputClass}
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }}
        />
        <button type="button" onClick={add} className="btn btn-outline"><Plus size={14} /></button>
      </div>
      {values.length > 0 && (
        <div className="skill-tags mt-2 flex-wrap">
          {values.map((v) => (
            <span key={v} className="inline-flex items-center gap-1">
              {v}
              <button type="button" onClick={() => onChange(values.filter((x) => x !== v))}><X size={10} /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ProfilePage() {
  const router = useRouter()
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [resumeUploading, setResumeUploading] = useState(false)

  useEffect(() => {
    let active = true
    supabase.auth.getSession().then(async ({ data }) => {
      if (!active) return
      if (!data.session) {
        router.push('/')
        return
      }
      try {
        const prof = await getMyProfile()
        if (active) setProfile(prof)
      } catch (e: any) {
        // Backend enforces role -- a non-student session gets a 403 here,
        // which is the real authorization boundary, not just client-side UI.
        if (active) setError(e.message || 'Could not load your profile.')
      } finally {
        if (active) setLoading(false)
      }
    })
    return () => { active = false }
  }, [router])

  const patch = (updates: StudentProfileUpdate) => {
    if (!profile) return
    setProfile({ ...profile, ...updates } as StudentProfile)
  }

  const handleSave = async () => {
    if (!profile) return
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const updated = await updateMyProfile({
        name: profile.name,
        branch: profile.branch,
        cgpa: profile.cgpa,
        tenth_pct: profile.tenth_pct,
        twelfth_pct: profile.twelfth_pct,
        backlog_count: profile.backlog_count,
        skills: profile.skills,
        certifications: profile.certifications,
        projects: profile.projects,
        internship_history: profile.internship_history,
        hackathons: profile.hackathons,
        github_url: profile.github_url,
        linkedin_url: profile.linkedin_url,
        portfolio_url: profile.portfolio_url,
        coding_profiles: profile.coding_profiles,
        preferred_roles: profile.preferred_roles,
        expected_salary: profile.expected_salary,
        location_preference: profile.location_preference,
        languages: profile.languages,
      })
      setProfile(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e: any) {
      setError(e.message || 'Failed to save profile.')
    } finally {
      setSaving(false)
    }
  }

  const handleResumeChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !profile) return
    setResumeUploading(true)
    setError('')
    try {
      const { resume_url, resume_filename } = await uploadMyResume(file)
      setProfile({ ...profile, resume_url, resume_filename })
    } catch (e: any) {
      setError(e.message || 'Resume upload failed.')
    } finally {
      setResumeUploading(false)
      e.target.value = ''
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="animate-spin text-primary" size={28} />
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center text-center p-6">
        <p className="text-sm text-muted-foreground">{error || 'Could not load your profile.'}</p>
      </div>
    )
  }

  const completion = profile.profile_completion_pct

  return (
    <div className="min-h-screen bg-background">
      <div className="dashboard-main motion-page">
        <div className="section-title">
          <div>
            <button onClick={() => router.push('/')} className="quiet-link mb-3">
              <ArrowLeft size={13} /> Back to dashboard
            </button>
            <div className="eyebrow">Student Profile</div>
            <h1>Complete your placement profile</h1>
            <p>Recruiters and the matching engine use this to find and rank you for drives.</p>
          </div>
          <button onClick={handleSave} disabled={saving} className="btn btn-primary">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>

        {saved && (
          <div className="status-badge good mb-4"><CheckCircle2 size={12} /> Profile saved</div>
        )}
        {error && (
          <div className="status-badge danger mb-4">{error}</div>
        )}

        {/* Completion */}
        <div className="metric-card mb-6">
          <div className="metric-top">
            <span>Profile Completion</span>
          </div>
          <div className="metric-value">{completion}%</div>
          <div className="bar mt-2"><i style={{ width: `${completion}%` }} /></div>
          <div className="metric-detail mt-2">
            {completion < 100 ? 'Fill in more sections below to improve your visibility to recruiters.' : 'Your profile is complete.'}
          </div>
        </div>

        <div className="dashboard-grid" style={{ gridTemplateColumns: '1fr' }}>
          {/* Basics */}
          <div className="panel">
            <div className="panel-head"><div><h2>Basics & Academics</h2></div></div>
            <div className="field-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
              <div className="data-field">
                <Field label="Full Name">
                  <input className={inputClass} value={profile.name} onChange={(e) => patch({ name: e.target.value })} />
                </Field>
              </div>
              <div className="data-field">
                <Field label="Branch">
                  <input className={inputClass} value={profile.branch} onChange={(e) => patch({ branch: e.target.value })} placeholder="e.g. CSE" />
                </Field>
              </div>
              <div className="data-field">
                <Field label="CGPA (out of 10)">
                  <input type="number" step="0.01" min={0} max={10} className={inputClass} value={profile.cgpa} onChange={(e) => patch({ cgpa: parseFloat(e.target.value) || 0 })} />
                </Field>
              </div>
              <div className="data-field">
                <Field label="10th %">
                  <input type="number" step="0.1" className={inputClass} value={profile.tenth_pct} onChange={(e) => patch({ tenth_pct: parseFloat(e.target.value) || 0 })} />
                </Field>
              </div>
              <div className="data-field">
                <Field label="12th %">
                  <input type="number" step="0.1" className={inputClass} value={profile.twelfth_pct} onChange={(e) => patch({ twelfth_pct: parseFloat(e.target.value) || 0 })} />
                </Field>
              </div>
              <div className="data-field">
                <Field label="Active Backlogs">
                  <input type="number" min={0} className={inputClass} value={profile.backlog_count} onChange={(e) => patch({ backlog_count: parseInt(e.target.value) || 0 })} />
                </Field>
              </div>
            </div>
          </div>

          {/* Skills */}
          <div className="panel mt-4">
            <div className="panel-head"><div><h2>Skills</h2><p>Used by the matching engine to compute your skill match score.</p></div></div>
            <SkillsEditor
              skills={profile.skills}
              onChange={(skills) => patch({ skills })}
            />
          </div>

          {/* Projects */}
          <div className="panel mt-4">
            <div className="panel-head"><div><h2>Projects</h2></div></div>
            <ProjectsEditor projects={profile.projects} onChange={(projects) => patch({ projects })} />
          </div>

          {/* Certifications & Hackathons */}
          <div className="panel mt-4">
            <div className="panel-head"><div><h2>Certifications</h2></div></div>
            <SimplePairListEditor
              items={profile.certifications}
              onChange={(certifications) => patch({ certifications })}
              fieldA={{ key: 'name', label: 'Certification name' }}
              fieldB={{ key: 'issuer', label: 'Issuer' }}
            />
          </div>

          <div className="panel mt-4">
            <div className="panel-head"><div><h2>Hackathons</h2></div></div>
            <SimplePairListEditor
              items={profile.hackathons}
              onChange={(hackathons) => patch({ hackathons })}
              fieldA={{ key: 'name', label: 'Hackathon name' }}
              fieldB={{ key: 'result', label: 'Result' }}
            />
          </div>

          {/* Internships */}
          <div className="panel mt-4">
            <div className="panel-head"><div><h2>Internships</h2></div></div>
            <InternshipsEditor
              items={profile.internship_history}
              onChange={(internship_history) => patch({ internship_history })}
            />
          </div>

          {/* Links & Coding Profiles */}
          <div className="panel mt-4">
            <div className="panel-head"><div><h2>Links & Coding Profiles</h2></div></div>
            <div className="field-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
              <div className="data-field">
                <Field label={<span className="flex items-center gap-1"><FolderGit2 size={11} /> GitHub</span>}>
                  <input className={inputClass} value={profile.github_url || ''} onChange={(e) => patch({ github_url: e.target.value })} placeholder="https://github.com/you" />
                </Field>
              </div>
              <div className="data-field">
                <Field label={<span className="flex items-center gap-1"><Link2 size={11} /> LinkedIn</span>}>
                  <input className={inputClass} value={profile.linkedin_url || ''} onChange={(e) => patch({ linkedin_url: e.target.value })} placeholder="https://linkedin.com/in/you" />
                </Field>
              </div>
              <div className="data-field">
                <Field label={<span className="flex items-center gap-1"><Globe size={11} /> Portfolio</span>}>
                  <input className={inputClass} value={profile.portfolio_url || ''} onChange={(e) => patch({ portfolio_url: e.target.value })} placeholder="https://you.dev" />
                </Field>
              </div>
              <div className="data-field">
                <Field label="LeetCode">
                  <input className={inputClass} value={profile.coding_profiles?.leetcode || ''} onChange={(e) => patch({ coding_profiles: { ...profile.coding_profiles, leetcode: e.target.value } })} />
                </Field>
              </div>
              <div className="data-field">
                <Field label="Codeforces">
                  <input className={inputClass} value={profile.coding_profiles?.codeforces || ''} onChange={(e) => patch({ coding_profiles: { ...profile.coding_profiles, codeforces: e.target.value } })} />
                </Field>
              </div>
              <div className="data-field">
                <Field label="HackerRank">
                  <input className={inputClass} value={profile.coding_profiles?.hackerrank || ''} onChange={(e) => patch({ coding_profiles: { ...profile.coding_profiles, hackerrank: e.target.value } })} />
                </Field>
              </div>
            </div>
          </div>

          {/* Preferences */}
          <div className="panel mt-4">
            <div className="panel-head"><div><h2>Job Preferences</h2></div></div>
            <div className="field-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
              <div className="data-field">
                <Field label="Preferred Roles">
                  <TagListInput values={profile.preferred_roles} onChange={(preferred_roles) => patch({ preferred_roles })} placeholder="e.g. Backend Engineer" />
                </Field>
              </div>
              <div className="data-field">
                <Field label="Expected Salary (LPA)">
                  <input type="number" step="0.5" min={0} className={inputClass} value={profile.expected_salary ?? ''} onChange={(e) => patch({ expected_salary: e.target.value ? parseFloat(e.target.value) : null })} />
                </Field>
              </div>
              <div className="data-field">
                <Field label="Location Preference">
                  <TagListInput values={profile.location_preference} onChange={(location_preference) => patch({ location_preference })} placeholder="e.g. Bangalore" />
                </Field>
              </div>
              <div className="data-field">
                <Field label="Languages">
                  <TagListInput values={profile.languages} onChange={(languages) => patch({ languages })} placeholder="e.g. English" />
                </Field>
              </div>
            </div>
          </div>

          {/* Resume */}
          <div className="panel mt-4">
            <div className="panel-head"><div><h2>Resume</h2></div></div>
            <div className="upload-panel">
              <div className="upload-zone">
                <div className="upload-icon"><Upload size={22} /></div>
                <p>PDF only, up to 5MB.</p>
                <label className="btn btn-outline" style={{ cursor: 'pointer', display: 'inline-flex' }}>
                  {resumeUploading ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                  {resumeUploading ? 'Uploading…' : 'Choose file'}
                  <input type="file" accept="application/pdf" onChange={handleResumeChange} className="hidden" style={{ display: 'none' }} disabled={resumeUploading} />
                </label>
              </div>
              {profile.resume_filename && (
                <div className="file-row">
                  <FileText size={18} className="text-success" />
                  <div>
                    <strong>{profile.resume_filename}</strong>
                    <span>Uploaded and visible to recruiters on drives you're eligible for.</span>
                  </div>
                </div>
              )}
              {profile.resume_ats_score != null && (
                <div className="text-xs text-muted-foreground">ATS Score: <strong className="text-foreground">{profile.resume_ats_score}</strong></div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── list editors ─────────────────────────────────────────────────────────

function SkillsEditor({ skills, onChange }: { skills: StudentProfile['skills']; onChange: (v: StudentProfile['skills']) => void }) {
  const [name, setName] = useState('')
  const [level, setLevel] = useState('Intermediate')
  const add = () => {
    if (!name.trim()) return
    onChange([...skills, { skill: name.trim(), level }])
    setName('')
  }
  return (
    <div>
      <div className="flex gap-2">
        <input className={inputClass} value={name} placeholder="e.g. Python" onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); add() } }} />
        <select className={inputClass} style={{ width: 140 }} value={level} onChange={(e) => setLevel(e.target.value)}>
          <option>Beginner</option>
          <option>Intermediate</option>
          <option>Advanced</option>
        </select>
        <button type="button" onClick={add} className="btn btn-outline"><Plus size={14} /></button>
      </div>
      {skills.length > 0 && (
        <div className="skill-tags mt-3 flex-wrap">
          {skills.map((s, i) => (
            <span key={`${s.skill}-${i}`} className="inline-flex items-center gap-1">
              {s.skill} · {s.level}
              <button type="button" onClick={() => onChange(skills.filter((_, idx) => idx !== i))}><X size={10} /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function ProjectsEditor({ projects, onChange }: { projects: StudentProfile['projects']; onChange: (v: StudentProfile['projects']) => void }) {
  const [title, setTitle] = useState('')
  const [tech, setTech] = useState('')
  const [link, setLink] = useState('')
  const add = () => {
    if (!title.trim()) return
    onChange([...projects, { title: title.trim(), tech_stack: tech.split(',').map((t) => t.trim()).filter(Boolean), link: link.trim() || undefined }])
    setTitle(''); setTech(''); setLink('')
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input className={inputClass} value={title} placeholder="Project title" onChange={(e) => setTitle(e.target.value)} />
        <input className={inputClass} value={tech} placeholder="Tech stack (comma separated)" onChange={(e) => setTech(e.target.value)} />
        <input className={inputClass} value={link} placeholder="Link (optional)" onChange={(e) => setLink(e.target.value)} />
        <button type="button" onClick={add} className="btn btn-outline"><Plus size={14} /></button>
      </div>
      {projects.map((p, i) => (
        <div key={i} className="file-row">
          <div>
            <strong>{p.title}</strong>
            <span>{p.tech_stack.join(', ')}{p.link ? ` · ${p.link}` : ''}</span>
          </div>
          <button type="button" onClick={() => onChange(projects.filter((_, idx) => idx !== i))} className="dismiss"><X size={14} /></button>
        </div>
      ))}
    </div>
  )
}

function InternshipsEditor({ items, onChange }: { items: StudentProfile['internship_history']; onChange: (v: StudentProfile['internship_history']) => void }) {
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [months, setMonths] = useState('')
  const add = () => {
    if (!company.trim()) return
    onChange([...items, { company: company.trim(), role: role.trim() || undefined, duration_months: parseInt(months) || 0 }])
    setCompany(''); setRole(''); setMonths('')
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input className={inputClass} value={company} placeholder="Company" onChange={(e) => setCompany(e.target.value)} />
        <input className={inputClass} value={role} placeholder="Role" onChange={(e) => setRole(e.target.value)} />
        <input className={inputClass} style={{ width: 140 }} type="number" min={0} value={months} placeholder="Months" onChange={(e) => setMonths(e.target.value)} />
        <button type="button" onClick={add} className="btn btn-outline"><Plus size={14} /></button>
      </div>
      {items.map((it, i) => (
        <div key={i} className="file-row">
          <div>
            <strong>{it.company}{it.role ? ` · ${it.role}` : ''}</strong>
            <span>{it.duration_months} month(s)</span>
          </div>
          <button type="button" onClick={() => onChange(items.filter((_, idx) => idx !== i))} className="dismiss"><X size={14} /></button>
        </div>
      ))}
    </div>
  )
}

function SimplePairListEditor<T extends Record<string, any>>({
  items, onChange, fieldA, fieldB,
}: {
  items: T[]
  onChange: (v: T[]) => void
  fieldA: { key: keyof T & string; label: string }
  fieldB: { key: keyof T & string; label: string }
}) {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const add = () => {
    if (!a.trim()) return
    onChange([...items, { [fieldA.key]: a.trim(), [fieldB.key]: b.trim() } as unknown as T])
    setA(''); setB('')
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input className={inputClass} value={a} placeholder={fieldA.label} onChange={(e) => setA(e.target.value)} />
        <input className={inputClass} value={b} placeholder={fieldB.label} onChange={(e) => setB(e.target.value)} />
        <button type="button" onClick={add} className="btn btn-outline"><Plus size={14} /></button>
      </div>
      {items.map((it, i) => (
        <div key={i} className="file-row">
          <div>
            <strong>{it[fieldA.key]}</strong>
            <span>{it[fieldB.key]}</span>
          </div>
          <button type="button" onClick={() => onChange(items.filter((_, idx) => idx !== i))} className="dismiss"><X size={14} /></button>
        </div>
      ))}
    </div>
  )
}
