'use client';

import React, { useEffect, useState } from 'react';
import { Loader2, CheckCircle, XCircle, BrainCircuit, PlayCircle, AlertTriangle } from 'lucide-react';
import { 
  getAgent13Recommendations, 
  reviewAgent13Recommendation, 
  executeAgent13Recommendation,
  getAgent13FairnessAudit,
  Agent13Recommendation 
} from '../../lib/student-api';

export default function FacultyDiscoveryDashboard() {
  const [recommendations, setRecommendations] = useState<Agent13Recommendation[]>([]);
  const [auditData, setAuditData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('pending');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [recsRes, auditRes] = await Promise.all([
        getAgent13Recommendations(),
        getAgent13FairnessAudit()
      ]);
      setRecommendations(recsRes.recommendations || []);
      setAuditData(auditRes);
    } catch (err: any) {
      setError(err.message || "Failed to load Agent 13 data");
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (id: string, decision: 'APPROVED' | 'REJECTED') => {
    try {
      await reviewAgent13Recommendation(id, decision);
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to review recommendation");
    }
  };

  const handleExecute = async (id: string) => {
    try {
      await executeAgent13Recommendation(id);
      loadData();
    } catch (err: any) {
      alert(err.message || "Failed to execute recommendation");
    }
  };

  if (loading) return <div className="p-8 flex justify-center"><Loader2 className="animate-spin h-8 w-8" /></div>;
  
  if (error) return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="border border-red-500 bg-red-500/10 p-6 rounded-lg text-red-400 font-semibold">{error}</div>
      <button className="px-4 py-2 bg-gray-800 text-white rounded" onClick={() => loadData()}>Retry</button>
    </div>
  );

  const pendingRecs = recommendations.filter(r => r.status === 'DISCOVERED' || r.status === 'MATCHED' || r.status === 'RECOMMENDED' || r.status === 'PENDING_APPROVAL');
  const approvedRecs = recommendations.filter(r => r.status === 'APPROVED');
  const executedRecs = recommendations.filter(r => r.status === 'EXECUTED');
  const rejectedRecs = recommendations.filter(r => r.status === 'REJECTED');

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 min-h-screen">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-3 mb-2">
          <BrainCircuit className="h-8 w-8 text-purple-500" />
          Agent 13 — Talent Discovery
        </h1>
        <p className="text-gray-500 max-w-2xl">
          Discovers hidden student potential and matches them with evidence-backed non-placement opportunities (Research, Hackathons, Mentorship). Every action requires human approval.
        </p>
      </div>

      <div className="w-full">
        <div className="grid w-full grid-cols-4 max-w-3xl mb-8 bg-gray-100 dark:bg-zinc-900 border border-gray-200 dark:border-white/10 rounded-lg p-1">
          {['pending', 'approved', 'history', 'audit'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                activeTab === tab ? 'bg-white dark:bg-zinc-800 shadow' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              {tab === 'pending' ? `Pending (${pendingRecs.length})` :
               tab === 'approved' ? `Ready (${approvedRecs.length})` :
               tab === 'history' ? `History (${executedRecs.length + rejectedRecs.length})` :
               'Fairness Audit'}
            </button>
          ))}
        </div>

        {activeTab === 'pending' && (
          <div className="space-y-4">
            {pendingRecs.length === 0 ? (
              <div className="text-center p-12 border border-dashed rounded-xl border-gray-300 dark:border-white/20 text-gray-500">
                No pending recommendations.
              </div>
            ) : (
              pendingRecs.map(rec => (
                <RecommendationCard key={rec.id} rec={rec} onApprove={() => handleReview(rec.id, 'APPROVED')} onReject={() => handleReview(rec.id, 'REJECTED')} />
              ))
            )}
          </div>
        )}

        {activeTab === 'approved' && (
          <div className="space-y-4">
            {approvedRecs.length === 0 ? (
              <div className="text-center p-12 border border-dashed rounded-xl border-gray-300 dark:border-white/20 text-gray-500">
                No approved recommendations waiting for execution.
              </div>
            ) : (
              approvedRecs.map(rec => (
                <RecommendationCard key={rec.id} rec={rec} onExecute={() => handleExecute(rec.id)} showExecute />
              ))
            )}
          </div>
        )}

        {activeTab === 'history' && (
          <div className="space-y-4">
            {[...executedRecs, ...rejectedRecs].map(rec => (
              <RecommendationCard key={rec.id} rec={rec} readonly />
            ))}
          </div>
        )}

        {activeTab === 'audit' && (
          <div className="space-y-4">
            <div className="bg-gray-50 dark:bg-zinc-900/50 border border-gray-200 dark:border-white/10 rounded-xl">
              <div className="p-6 border-b border-gray-200 dark:border-white/10">
                <h3 className="text-xl font-semibold">Fairness & Bias Audit</h3>
              </div>
              <div className="p-6">
                <pre className="p-4 bg-gray-100 dark:bg-black/50 rounded-lg overflow-auto text-sm text-blue-800 dark:text-blue-300 border border-gray-200 dark:border-white/5">
                  {JSON.stringify(auditData, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function RecommendationCard({ rec, onApprove, onReject, onExecute, showExecute, readonly }: any) {
  return (
    <div className="bg-white dark:bg-zinc-900/50 border border-gray-200 dark:border-white/10 rounded-xl overflow-hidden relative shadow-sm">
      {rec.hidden_talent && (
        <div className="absolute top-0 right-0 bg-gradient-to-r from-purple-600 to-blue-600 text-white text-xs font-bold px-3 py-1 rounded-bl-lg flex items-center gap-1 shadow-lg shadow-purple-500/20">
          <BrainCircuit className="h-3 w-3" /> Hidden Talent Identified
        </div>
      )}
      <div className="p-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-xl font-semibold mb-1">{rec.student_name} → {rec.opportunity_title}</h3>
            <div className="flex gap-2 text-sm text-gray-500">
              <span className="px-2 py-0.5 border rounded bg-gray-50 dark:bg-white/5">{rec.status}</span>
              <span className="flex items-center gap-1"><BrainCircuit className="h-3 w-3"/> Fit Score: {rec.fit_score.toFixed(1)}</span>
            </div>
          </div>
          {!readonly && !showExecute && (
            <div className="flex gap-2 mt-4 sm:mt-0">
              <button className="px-4 py-2 border border-red-500/50 hover:bg-red-500/20 text-red-600 dark:text-red-400 rounded-md flex items-center transition" onClick={onReject}>
                <XCircle className="h-4 w-4 mr-2" /> Reject
              </button>
              <button className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-md flex items-center transition" onClick={onApprove}>
                <CheckCircle className="h-4 w-4 mr-2" /> Approve
              </button>
            </div>
          )}
          {showExecute && (
             <button className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-md flex items-center shadow-lg shadow-blue-500/20 transition" onClick={onExecute}>
               <PlayCircle className="h-4 w-4 mr-2" /> Execute (ACT_WITH_APPROVAL)
             </button>
          )}
        </div>

        {rec.hidden_talent && rec.hidden_talent_explanation && (
          <div className="mb-6 p-4 rounded-lg bg-purple-100 dark:bg-purple-500/10 border border-purple-200 dark:border-purple-500/20 text-purple-800 dark:text-purple-200 text-sm">
            <strong>Agent 13 Reasoning:</strong> {rec.hidden_talent_explanation}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div className="space-y-2">
            <h4 className="font-semibold text-gray-800 dark:text-zinc-300 flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500 dark:text-green-400" /> Verified Evidence (Weight: 1.0)
            </h4>
            <ul className="list-disc pl-5 text-gray-600 dark:text-gray-400 space-y-1">
              {rec.evidence_breakdown?.verified?.map((ev: string, i: number) => <li key={i}>{ev}</li>)}
              {!rec.evidence_breakdown?.verified?.length && <li className="text-gray-400 dark:text-zinc-600 italic">None</li>}
            </ul>
          </div>
          <div className="space-y-2">
            <h4 className="font-semibold text-gray-800 dark:text-zinc-300 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500 dark:text-amber-400" /> Provisional Claims (Weight: 0.3)
            </h4>
            <ul className="list-disc pl-5 text-gray-600 dark:text-gray-400 space-y-1">
              {rec.evidence_breakdown?.provisional?.map((ev: string, i: number) => <li key={i}>{ev}</li>)}
              {!rec.evidence_breakdown?.provisional?.length && <li className="text-gray-400 dark:text-zinc-600 italic">None</li>}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
