'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from '@/components/ui/badge';
import { Loader2, CheckCircle, XCircle, BrainCircuit, PlayCircle, AlertTriangle } from 'lucide-react';
import { 
  getAgent13Recommendations, 
  reviewAgent13Recommendation, 
  executeAgent13Recommendation,
  getAgent13FairnessAudit,
  Agent13Recommendation 
} from '@/lib/student-api';

export default function FacultyDiscoveryDashboard() {
  const [recommendations, setRecommendations] = useState<Agent13Recommendation[]>([]);
  const [auditData, setAuditData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      <Card className="border-red-500 bg-red-500/10">
        <CardContent className="p-6 text-red-400 font-semibold">{error}</CardContent>
      </Card>
      <Button onClick={() => loadData()}>Retry</Button>
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
        <p className="text-muted-foreground max-w-2xl">
          Discovers hidden student potential and matches them with evidence-backed non-placement opportunities (Research, Hackathons, Mentorship). Every action requires human approval.
        </p>
      </div>

      <Tabs defaultValue="pending" className="w-full">
        <TabsList className="grid w-full grid-cols-4 max-w-3xl mb-8 bg-zinc-900 border border-white/10">
          <TabsTrigger value="pending">Pending ({pendingRecs.length})</TabsTrigger>
          <TabsTrigger value="approved">Ready ({approvedRecs.length})</TabsTrigger>
          <TabsTrigger value="history">History ({executedRecs.length + rejectedRecs.length})</TabsTrigger>
          <TabsTrigger value="audit">Fairness Audit</TabsTrigger>
        </TabsList>

        <TabsContent value="pending" className="space-y-4">
          {pendingRecs.length === 0 ? (
            <div className="text-center p-12 border border-dashed rounded-xl border-white/20 text-muted-foreground">
              No pending recommendations.
            </div>
          ) : (
            pendingRecs.map(rec => (
              <RecommendationCard key={rec.id} rec={rec} onApprove={() => handleReview(rec.id, 'APPROVED')} onReject={() => handleReview(rec.id, 'REJECTED')} />
            ))
          )}
        </TabsContent>

        <TabsContent value="approved" className="space-y-4">
          {approvedRecs.length === 0 ? (
            <div className="text-center p-12 border border-dashed rounded-xl border-white/20 text-muted-foreground">
              No approved recommendations waiting for execution.
            </div>
          ) : (
            approvedRecs.map(rec => (
              <RecommendationCard key={rec.id} rec={rec} onExecute={() => handleExecute(rec.id)} showExecute />
            ))
          )}
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          {[...executedRecs, ...rejectedRecs].map(rec => (
            <RecommendationCard key={rec.id} rec={rec} readonly />
          ))}
        </TabsContent>

        <TabsContent value="audit" className="space-y-4">
          <Card className="bg-zinc-900/50 border-white/10">
            <CardHeader>
              <CardTitle>Fairness & Bias Audit</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="p-4 bg-black/50 rounded-lg overflow-auto text-sm text-blue-300 border border-white/5">
                {JSON.stringify(auditData, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function RecommendationCard({ rec, onApprove, onReject, onExecute, showExecute, readonly }: any) {
  return (
    <Card className="bg-zinc-900/50 border-white/10 overflow-hidden relative">
      {rec.hidden_talent && (
        <div className="absolute top-0 right-0 bg-gradient-to-r from-purple-600 to-blue-600 text-white text-xs font-bold px-3 py-1 rounded-bl-lg flex items-center gap-1 shadow-lg shadow-purple-500/20">
          <BrainCircuit className="h-3 w-3" /> Hidden Talent Identified
        </div>
      )}
      <div className="p-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-xl font-semibold mb-1">{rec.student_name} → {rec.opportunity_title}</h3>
            <div className="flex gap-2 text-sm text-muted-foreground">
              <Badge variant="outline" className="bg-white/5">{rec.status}</Badge>
              <span className="flex items-center gap-1"><BrainCircuit className="h-3 w-3"/> Fit Score: {rec.fit_score.toFixed(1)}</span>
            </div>
          </div>
          {!readonly && !showExecute && (
            <div className="flex gap-2 mt-4 sm:mt-0">
              <Button variant="outline" className="border-red-500/50 hover:bg-red-500/20 text-red-400" onClick={onReject}>
                <XCircle className="h-4 w-4 mr-2" /> Reject
              </Button>
              <Button variant="default" className="bg-green-600 hover:bg-green-500 text-white" onClick={onApprove}>
                <CheckCircle className="h-4 w-4 mr-2" /> Approve
              </Button>
            </div>
          )}
          {showExecute && (
             <Button variant="default" className="bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20" onClick={onExecute}>
               <PlayCircle className="h-4 w-4 mr-2" /> Execute (ACT_WITH_APPROVAL)
             </Button>
          )}
        </div>

        {rec.hidden_talent && rec.hidden_talent_explanation && (
          <div className="mb-6 p-4 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-200 text-sm">
            <strong>Agent 13 Reasoning:</strong> {rec.hidden_talent_explanation}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <div className="space-y-2">
            <h4 className="font-semibold text-zinc-300 flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-400" /> Verified Evidence (Weight: 1.0)
            </h4>
            <ul className="list-disc pl-5 text-muted-foreground space-y-1">
              {rec.evidence_breakdown?.verified?.map((ev: string, i: number) => <li key={i}>{ev}</li>)}
              {!rec.evidence_breakdown?.verified?.length && <li className="text-zinc-600 italic">None</li>}
            </ul>
          </div>
          <div className="space-y-2">
            <h4 className="font-semibold text-zinc-300 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" /> Provisional Claims (Weight: 0.3)
            </h4>
            <ul className="list-disc pl-5 text-muted-foreground space-y-1">
              {rec.evidence_breakdown?.provisional?.map((ev: string, i: number) => <li key={i}>{ev}</li>)}
              {!rec.evidence_breakdown?.provisional?.length && <li className="text-zinc-600 italic">None</li>}
            </ul>
          </div>
        </div>
      </div>
    </Card>
  );
}
