'use client';

import React, { useEffect, useState } from 'react';
import { Loader2, CheckCircle, XCircle, BrainCircuit, PlayCircle, ShieldAlert, Award, UserCheck, BarChart3, ChevronRight, Activity } from 'lucide-react';
import { 
  getAgent13Recommendations, 
  reviewAgent13Recommendation, 
  executeAgent13Recommendation,
  getAgent13FairnessAudit,
  Agent13Recommendation 
} from '../../lib/student-api';
import { apiFetch } from '../../lib/api';

export default function FacultyDiscoveryDashboard() {
  const [recommendations, setRecommendations] = useState<Agent13Recommendation[]>([]);
  const [auditData, setAuditData] = useState<any>(null);
  const [verificationQueue, setVerificationQueue] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('pending');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [recsRes, auditRes, queueRes] = await Promise.all([
        getAgent13Recommendations(),
        getAgent13FairnessAudit(),
        apiFetch('/api/agent13/verification-queue').then(r => r.ok ? r.json() : { queue: [] }).catch(() => ({ queue: [] }))
      ]);
      setRecommendations(recsRes.recommendations || []);
      setAuditData(auditRes);
      setVerificationQueue(queueRes.queue || []);
    } catch (err: any) {
      setError(err.message || "Failed to load Agent 13 data");
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (id: string, decision: 'APPROVED' | 'REJECTED') => {
    setActionLoading(id);
    try {
      await reviewAgent13Recommendation(id, decision);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to review recommendation");
    } finally {
      setActionLoading(null);
    }
  };

  const handleExecute = async (id: string) => {
    setActionLoading(id);
    try {
      await executeAgent13Recommendation(id);
      await loadData();
    } catch (err: any) {
      alert(err.message || "Failed to execute recommendation");
    } finally {
      setActionLoading(null);
    }
  };

  const handleVerifyClaim = async (claimId: string, decision: 'VERIFIED' | 'REJECTED') => {
    setActionLoading(claimId);
    try {
      const res = await apiFetch(`/api/agent13/resume-claims/${claimId}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision })
      });
      if (!res.ok) throw new Error("Failed to verify claim");
      await loadData();
    } catch (err: any) {
      alert(err.message || "Verification failed");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) return <div className="p-12 flex flex-col items-center justify-center gap-3"><Loader2 className="animate-spin h-7 w-7 text-blue-500" /><span className="text-xs font-mono text-muted-foreground">Loading Agent 13 Intelligence...</span></div>;
  
  if (error) return (
    <div className="p-8 max-w-5xl mx-auto space-y-4">
      <div className="border border-red-500/30 bg-red-500/10 p-4 rounded-xl text-red-400 text-sm font-semibold flex items-center gap-3">
        <ShieldAlert size={20} /> {error}
      </div>
      <button className="px-4 py-2 bg-gray-800 text-white text-xs rounded-lg font-medium" onClick={() => loadData()}>Retry Connection</button>
    </div>
  );

  const pendingRecs = recommendations.filter(r => r.status === 'DISCOVERED' || r.status === 'MATCHED' || r.status === 'RECOMMENDED' || r.status === 'PENDING_APPROVAL');
  const approvedRecs = recommendations.filter(r => r.status === 'APPROVED');
  const executedRecs = recommendations.filter(r => r.status === 'EXECUTED');
  const rejectedRecs = recommendations.filter(r => r.status === 'REJECTED');

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 min-h-screen font-sans">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-500">
              <BrainCircuit className="h-5 w-5" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight">Agent 13 — Advanced Learner Intelligence</h1>
          </div>
          <p className="text-xs text-muted-foreground max-w-3xl">
            Identifies high-potential students beyond standard course grades, verifies institutional evidence, and matches candidates with faculty research projects under human-in-the-loop controls.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-border pb-3">
        {[
          { id: 'pending', label: `Pending Approval (${pendingRecs.length})` },
          { id: 'verification', label: `Evidence Verification Queue (${verificationQueue.length})` },
          { id: 'approved', label: `Ready for Execution (${approvedRecs.length})` },
          { id: 'history', label: `History (${executedRecs.length + rejectedRecs.length})` },
          { id: 'audit', label: 'Fairness & Bias Audit' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-colors border ${
              activeTab === tab.id
                ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                : 'bg-background hover:bg-muted text-muted-foreground border-border'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Pending Recommendations */}
      {activeTab === 'pending' && (
        <div className="space-y-4">
          {pendingRecs.length === 0 ? (
            <div className="text-center p-12 border border-dashed rounded-2xl border-border text-muted-foreground text-xs">
              No pending recommendations requiring review.
            </div>
          ) : (
            pendingRecs.map(rec => (
              <RecommendationCard
                key={rec.id}
                rec={rec}
                actionLoading={actionLoading === rec.id}
                onApprove={() => handleReview(rec.id, 'APPROVED')}
                onReject={() => handleReview(rec.id, 'REJECTED')}
              />
            ))
          )}
        </div>
      )}

      {/* Tab 2: Evidence Verification Queue */}
      {activeTab === 'verification' && (
        <div className="space-y-4">
          <div className="p-4 bg-muted/30 border border-border rounded-xl flex items-center justify-between text-xs">
            <div>
              <strong className="block text-foreground font-semibold">Institutional Achievement Verification Queue</strong>
              <span className="text-muted-foreground">Faculty/TPO verification converts provisional self-reported claims into 1.0-weighted institutional evidence.</span>
            </div>
          </div>

          {verificationQueue.length === 0 ? (
            <div className="text-center p-12 border border-dashed rounded-2xl border-border text-muted-foreground text-xs">
              All student claims verified! No provisional items in the verification queue.
            </div>
          ) : (
            <div className="grid gap-3">
              {verificationQueue.map((item: any) => (
                <div key={item.claim_id} className="p-4 bg-background border border-border rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-foreground">{item.student_name}</span>
                      <span className="text-muted-foreground">• {item.branch} (CGPA: {item.cgpa})</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-600 border border-amber-500/20">{item.claim_type}</span>
                    </div>
                    <p className="text-foreground font-medium">{item.claim_text}</p>
                    <div className="text-muted-foreground text-[11px]">Skill: <code className="bg-muted px-1 py-0.5 rounded">{item.normalized_skill}</code> | Confidence: {item.extraction_confidence}</div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      disabled={actionLoading === item.claim_id}
                      onClick={() => handleVerifyClaim(item.claim_id, 'REJECTED')}
                      className="px-3 py-1.5 text-xs border border-red-500/30 text-red-500 hover:bg-red-500/10 rounded-lg font-medium transition-colors"
                    >
                      Reject Claim
                    </button>
                    <button
                      disabled={actionLoading === item.claim_id}
                      onClick={() => handleVerifyClaim(item.claim_id, 'VERIFIED')}
                      className="px-3 py-1.5 text-xs bg-green-600 hover:bg-green-500 text-white rounded-lg font-semibold transition-colors flex items-center gap-1 shadow-sm"
                    >
                      <CheckCircle size={13} /> Verify Evidence
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Ready for Execution */}
      {activeTab === 'approved' && (
        <div className="space-y-4">
          {approvedRecs.length === 0 ? (
            <div className="text-center p-12 border border-dashed rounded-2xl border-border text-muted-foreground text-xs">
              No approved recommendations waiting for execution.
            </div>
          ) : (
            approvedRecs.map(rec => (
              <RecommendationCard key={rec.id} rec={rec} actionLoading={actionLoading === rec.id} onExecute={() => handleExecute(rec.id)} showExecute />
            ))
          )}
        </div>
      )}

      {/* Tab 4: History */}
      {activeTab === 'history' && (
        <div className="space-y-4">
          {[...executedRecs, ...rejectedRecs].map(rec => (
            <RecommendationCard key={rec.id} rec={rec} readonly />
          ))}
        </div>
      )}

      {/* Tab 5: Fairness Audit */}
      {activeTab === 'audit' && (
        <div className="space-y-6">
          <div className="p-6 bg-background border border-border rounded-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-4">
              <div>
                <h3 className="text-base font-bold flex items-center gap-2"><BarChart3 size={18} className="text-blue-500"/> Institutional Fairness & Disparity Audit</h3>
                <p className="text-xs text-muted-foreground">Monitors non-placement opportunity distributions across branches to prevent structural bias.</p>
              </div>
              <span className={`px-2.5 py-1 rounded-full text-xs font-mono font-semibold ${auditData?.disparity_warning ? 'bg-amber-500/20 text-amber-500 border border-amber-500/30' : 'bg-green-500/20 text-green-500 border border-green-500/30'}`}>
                {auditData?.disparity_warning ? '⚠️ Disparity Alert' : '✅ Compliant'}
              </span>
            </div>

            {auditData?.disparity_message && (
              <p className="text-xs text-muted-foreground bg-muted/40 p-3 rounded-lg border border-border">{auditData.disparity_message}</p>
            )}

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
              <div className="p-3 bg-muted/20 border border-border rounded-xl">
                <span className="text-muted-foreground block text-[11px]">TOTAL EVALUATED STUDENTS</span>
                <strong className="text-lg text-foreground font-bold">{auditData?.total_students ?? 0}</strong>
              </div>
              <div className="p-3 bg-muted/20 border border-border rounded-xl">
                <span className="text-muted-foreground block text-[11px]">RECOMMENDATIONS GENERATED</span>
                <strong className="text-lg text-foreground font-bold">{auditData?.total_recommendations ?? 0}</strong>
              </div>
              <div className="p-3 bg-muted/20 border border-border rounded-xl">
                <span className="text-muted-foreground block text-[11px]">AUDIT STATUS</span>
                <strong className="text-lg text-foreground font-bold">{auditData?.disparity_warning ? 'DISPARITY DETECTED' : 'EQUITABLE'}</strong>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function RecommendationCard({ rec, onApprove, onReject, onExecute, showExecute, readonly, actionLoading }: any) {
  return (
    <div className="bg-background border border-border rounded-2xl p-5 shadow-sm space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-base font-bold text-foreground">{rec.student_name}</h3>
            <ChevronRight size={14} className="text-muted-foreground" />
            <span className="text-sm font-semibold text-blue-500">{rec.opportunity_title}</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
            <span className="px-2 py-0.5 rounded bg-muted border border-border text-[11px] font-semibold">{rec.status}</span>
            <span>Fit Score: <strong>{rec.fit_score?.toFixed(1)}%</strong></span>
          </div>
        </div>

        {!readonly && !showExecute && (
          <div className="flex items-center gap-2">
            <button disabled={actionLoading} className="px-3.5 py-1.5 text-xs border border-red-500/30 text-red-500 hover:bg-red-500/10 rounded-lg font-semibold transition-colors" onClick={onReject}>
              Reject
            </button>
            <button disabled={actionLoading} className="px-3.5 py-1.5 text-xs bg-green-600 hover:bg-green-500 text-white rounded-lg font-semibold transition-colors shadow-sm flex items-center gap-1" onClick={onApprove}>
              <CheckCircle size={13} /> Approve Recommendation
            </button>
          </div>
        )}

        {showExecute && (
          <button disabled={actionLoading} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 shadow-sm" onClick={onExecute}>
            <PlayCircle size={14} /> Assign Student to Project (ACT_WITH_APPROVAL)
          </button>
        )}
      </div>

      {rec.hidden_talent && rec.hidden_talent_explanation && (
        <div className="p-3.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs">
          <strong>Agent 13 Reasoning:</strong> {rec.hidden_talent_explanation}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs pt-2 border-t border-border">
        <div className="space-y-1.5">
          <strong className="text-foreground font-semibold flex items-center gap-1.5 text-[11px]">
            <CheckCircle size={13} className="text-green-500" /> Verified Institutional Evidence (Weight: 1.0)
          </strong>
          <ul className="list-disc pl-4 text-muted-foreground space-y-0.5">
            {rec.evidence_breakdown?.verified?.map((ev: string, i: number) => <li key={i}>{ev}</li>)}
            {!rec.evidence_breakdown?.verified?.length && <li className="italic text-muted-foreground/60">None recorded</li>}
          </ul>
        </div>
        <div className="space-y-1.5">
          <strong className="text-foreground font-semibold flex items-center gap-1.5 text-[11px]">
            <Activity size={13} className="text-amber-500" /> Provisional Self-Reported Claims (Weight: 0.3)
          </strong>
          <ul className="list-disc pl-4 text-muted-foreground space-y-0.5">
            {rec.evidence_breakdown?.provisional?.map((ev: string, i: number) => <li key={i}>{ev}</li>)}
            {!rec.evidence_breakdown?.provisional?.length && <li className="italic text-muted-foreground/60">None recorded</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}
