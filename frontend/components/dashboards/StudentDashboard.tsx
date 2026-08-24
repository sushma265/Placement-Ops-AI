'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Zap, LayoutDashboard, User as UserIcon, Briefcase, ClipboardList, CalendarDays,
  Sparkles, Bell, Settings, LogOut, Moon, Menu, ChevronDown, Loader2, Gauge,
  Target, FileCheck2, Send,
} from 'lucide-react'
import { getMyDashboard, type StudentDashboardData } from '@/lib/student-api'
import { StatsCard } from '@/components/cards/StatsCard'
import { ProfileCompletionCard } from '@/components/cards/ProfileCompletionCard'
import { InterviewCard } from '@/components/cards/InterviewCard'
import { NotificationCard } from '@/components/cards/NotificationCard'
import { ActivityTimeline } from '@/components/timeline/ActivityTimeline'
import { EligibleJobs } from '@/components/jobs/EligibleJobs'
import { AppliedJobs } from '@/components/jobs/AppliedJobs'
import { CareerAssistantCard } from '@/components/ai/CareerAssistantCard'
import { getMyProfile, type StudentProfile } from '@/lib/student-api'

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'profile', label: 'Profile', icon: UserIcon },
  { id: 'jobs', label: 'Jobs', icon: Briefcase },
  { id: 'applications', label: 'Applications', icon: ClipboardList },
  { id: 'interviews', label: 'Interviews', icon: CalendarDays },
  { id: 'resume-ai', label: 'Resume AI', icon: Sparkles },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'settings', label: 'Settings', icon: Settings, comingSoon: true },
]

export function StudentDashboard({ user, onLogout }: { user: any; onLogout: () => void }) {
  const router = useRouter()
  const [active, setActive] = useState('dashboard')
  const [dark, setDark] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const [data, setData] = useState<StudentDashboardData | null>(null)
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const reload = () => {
    setLoading(true)
    Promise.all([getMyDashboard(), getMyProfile()])
      .then(([dashboard, prof]) => {
        setData(dashboard)
        setProfile(prof)
      })
      .catch((e) => setError(e.message || 'Failed to load dashboard.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { reload() }, [])

  const handleNavClick = (id: string, comingSoon?: boolean) => {
    if (comingSoon) return
    if (id === 'profile') { router.push('/profile'); return }
    if (id === 'resume-ai') { router.push('/resume-ai'); return }
    setActive(id)
    setMobileNav(false)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="animate-spin text-primary" size={28} />
          {user?.user?.name && (
            <span className="text-xs font-mono uppercase tracking-wide text-muted-foreground">
              Loading dashboard for {user.user.name}…
            </span>
          )}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center text-center p-6">
        <p className="text-sm text-muted-foreground">{error || 'Could not load your dashboard.'}</p>
      </div>
    )
  }

  const { profile: p, stats } = data

  return (
    <div className={`${dark ? 'app-shell dark' : 'app-shell'} motion-page`}>
      <aside className={mobileNav ? 'sidebar mobile-open' : 'sidebar'}>
        <div className="sidebar-brand" onClick={() => setActive('dashboard')}>
          <span className="brand-mark"><Zap size={15} /></span>
          <span>placement ops</span>
        </div>

        <div className="workspace-switch">
          <span className="avatar teal-bg">{p.name ? p.name.slice(0, 2).toUpperCase() : 'ST'}</span>
          <div>
            <strong className="truncate max-w-[120px] block">{p.name}</strong>
            <span>Student</span>
          </div>
          <ChevronDown size={14} />
        </div>

        <nav className="flex-1 space-y-1">
          {NAV_ITEMS.map(({ id, label, icon: Icon, comingSoon }) => (
            <button
              key={id}
              className={active === id ? 'nav-active w-full' : 'w-full'}
              onClick={() => handleNavClick(id, comingSoon)}
              style={comingSoon ? { opacity: 0.5, cursor: 'default' } : undefined}
            >
              <Icon size={17} />
              <span className="flex-1 text-left">{label}</span>
              {comingSoon && <span className="nav-count">Soon</span>}
              {id === 'notifications' && stats.notifications_count > 0 && (
                <span className="nav-count">{stats.notifications_count}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <button onClick={() => setDark(!dark)} className="hover:bg-muted/40 font-semibold">
            <Moon size={16} /> {dark ? 'Light mode' : 'Dark mode'}
          </button>
          <button onClick={onLogout} className="hover:bg-red-500/10 text-red-500 font-bold">
            <LogOut size={16} /> Log Out
          </button>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(!mobileNav)}>
            <Menu size={20} />
          </button>
          <div />
          <div className="top-actions">
            <button className="icon-button" onClick={onLogout}>
              <LogOut size={18} />
            </button>
          </div>
        </header>

        <main className="dashboard-main">
          {/* Welcome header */}
          <div className="section-title">
            <div>
              <div className="eyebrow">Welcome back</div>
              <h1>{p.name}</h1>
              <p>{p.branch} · CGPA {p.cgpa}</p>
            </div>
          </div>

          {/* Quick stats */}
          <div className="metric-grid">
            <StatsCard label="Profile Completion" value={`${stats.profile_completion_pct}%`} icon={Gauge} />
            <StatsCard label="Placement Readiness" value={stats.placement_readiness_score} icon={Target} />
            <StatsCard label="Resume ATS Score" value={stats.resume_ats_score ?? 'Not scored yet'} icon={FileCheck2} />
            <StatsCard label="Applied Jobs" value={stats.applied_jobs_count} icon={Send} />
            <StatsCard label="Eligible Jobs" value={stats.eligible_jobs_count} icon={Briefcase} />
            <StatsCard label="Upcoming Interviews" value={stats.upcoming_interviews_count} icon={CalendarDays} />
            <StatsCard label="Notifications" value={stats.notifications_count} icon={Bell} tone="coral" />
          </div>

          {profile && <ProfileCompletionCard profile={profile} />}

          <div className="dashboard-grid mt-4">
            <div>
              <div className="panel">
                <div className="panel-head"><div><h2>Eligible Jobs</h2><p>Match % arrives with the AI Matching Engine (next milestone).</p></div></div>
                <EligibleJobs jobs={data.eligible_jobs} onApplied={reload} />
              </div>

              <div className="panel mt-4">
                <div className="panel-head"><div><h2>Applied Jobs</h2></div></div>
                <AppliedJobs jobs={data.applied_jobs} />
              </div>

              <div className="panel mt-4">
                <div className="panel-head"><div><h2>Recent Activity</h2></div></div>
                <ActivityTimeline activity={data.recent_activity} />
              </div>
            </div>

            <div>
              <div className="panel">
                <div className="panel-head"><div><h2>Upcoming Interviews</h2></div></div>
                {data.upcoming_interviews.length === 0 ? (
                  <div className="text-xs text-muted-foreground">No interviews scheduled yet.</div>
                ) : (
                  <div className="action-list">
                    {data.upcoming_interviews.map((iv) => <InterviewCard key={iv.interview_id} interview={iv} />)}
                  </div>
                )}
              </div>

              <div className="panel mt-4">
                <div className="panel-head"><div><h2>Notifications</h2></div></div>
                {data.notifications.length === 0 ? (
                  <div className="text-xs text-muted-foreground">No notifications yet.</div>
                ) : (
                  <div className="action-list">
                    {data.notifications.map((n) => <NotificationCard key={n.id} notification={n} />)}
                  </div>
                )}
              </div>

              <div className="mt-4">
                <CareerAssistantCard />
              </div>

              <div className="panel mt-4">
                <div className="panel-head"><div><h2>Skill Gap</h2><p>Full analysis arrives in a future milestone.</p></div></div>
                {data.skill_gap.current_skills.length > 0 ? (
                  <div className="skill-tags flex-wrap">
                    {data.skill_gap.current_skills.map((s, i) => <span key={i}>{s.skill}</span>)}
                  </div>
                ) : (
                  <div className="text-xs text-muted-foreground">Add skills to your profile to see this here.</div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
