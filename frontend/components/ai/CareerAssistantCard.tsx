'use client'

import { Sparkles, FileText, Search, Mic, TrendingUp, Compass, BookOpen } from 'lucide-react'

const QUICK_ACTIONS = [
  { label: 'Improve Resume', icon: FileText, prompt: 'How can I improve my resume for placements?' },
  { label: 'Find Opportunities', icon: Search, prompt: 'What research projects, hackathons, and jobs am I matched with?' },
  { label: 'Interview Preparation', icon: Mic, prompt: 'How should I prepare for upcoming placement interviews?' },
  { label: 'Advanced Skill Roadmap', icon: TrendingUp, prompt: 'What skills should I learn next to improve my placement readiness?' },
  { label: 'Research Pathway', icon: BookOpen, prompt: 'Show my 6-month personalized research and publication pathway' },
  { label: 'Career Guidance', icon: Compass, prompt: 'What career path should I consider given my branch and interests?' },
]

function askAI(prompt: string) {
  window.dispatchEvent(new CustomEvent('placement-ops:ask-ai', { detail: prompt }))
}

export function CareerAssistantCard() {
  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold"><Sparkles size={16} className="text-blue-500" /> Agent 13 Career Co-Pilot</h2>
          <p className="text-xs text-muted-foreground">AI-powered career & advanced learner guidance</p>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {QUICK_ACTIONS.map(({ label, icon: Icon, prompt }) => (
          <button
            key={label}
            onClick={() => askAI(prompt)}
            className="action-card hover:bg-muted/50 p-2 rounded-lg transition-colors flex items-center gap-2.5"
            style={{ width: '100%', textAlign: 'left', cursor: 'pointer', border: 0, background: 'transparent' }}
          >
            <div className="action-icon text-blue-500 bg-blue-500/10 p-1.5 rounded-md"><Icon size={15} /></div>
            <div className="action-copy text-xs font-medium"><strong>{label}</strong></div>
          </button>
        ))}
      </div>
    </div>
  )
}
