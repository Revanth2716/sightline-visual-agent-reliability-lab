import React, { useState, useEffect } from 'react';
import { BenchmarkRunSummaryItem, BenchmarkTrialResult } from '../types';
import { getRunReport } from '../api';

interface SafetyFailureViewProps {
  runs: BenchmarkRunSummaryItem[];
  onInspectTrial: (runId: string, trialIndex: number) => void;
}

interface IncidentItem {
  run_id: string;
  trial_index: number;
  scenario_id: string;
  type: 'executed_prohibited' | 'false_positive_verif' | 'safety_violation' | 'failed_trial' | 'errored_trial' | 'uncertain_verif';
  severity: 'critical' | 'high' | 'medium';
  title: string;
  detail: string;
  trial: BenchmarkTrialResult;
}

export const SafetyFailureView: React.FC<SafetyFailureViewProps> = ({
  runs,
  onInspectTrial,
}) => {
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Totals
  const [totalAttempted, setTotalAttempted] = useState(0);
  const [totalBlocked, setTotalBlocked] = useState(0);
  const [totalExecuted, setTotalExecuted] = useState(0);
  const [totalAuthorized, setTotalAuthorized] = useState(0);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.all(runs.map((r) => getRunReport(r.run_id).catch(() => null)))
      .then((reports) => {
        const foundIncidents: IncidentItem[] = [];
        let att = 0;
        let blk = 0;
        let exc = 0;
        let auth = 0;

        for (const rep of reports) {
          if (!rep) continue;

          att += rep.prohibited_actions_attempted;
          blk += rep.prohibited_actions_blocked;
          exc += rep.prohibited_actions_executed;
          auth += rep.authorized_actions_executed ?? 0;

          for (const t of rep.trial_results) {
            // 1. Critical: Prohibited Action Executed
            if (t.safety_actions.prohibited_executed > 0) {
              foundIncidents.push({
                run_id: t.run_id,
                trial_index: t.trial_index,
                scenario_id: t.scenario_id,
                type: 'executed_prohibited',
                severity: 'critical',
                title: 'CRITICAL: Prohibited Action Executed',
                detail: `Destructive action executed without authorization in trial #${t.trial_index}.`,
                trial: t,
              });
            }

            // 2. Critical: False Positive Verification
            if (t.verification_evaluation.confusion_class === 'false_positive') {
              foundIncidents.push({
                run_id: t.run_id,
                trial_index: t.trial_index,
                scenario_id: t.scenario_id,
                type: 'false_positive_verif',
                severity: 'critical',
                title: 'CRITICAL: False-Positive Verification',
                detail: `Agent reported action verified, but independent ground truth check detected failure.`,
                trial: t,
              });
            }

            // 3. High: Safety Violations Recorded
            for (const v of t.safety_violations) {
              if (!v.includes('False-positive')) {
                foundIncidents.push({
                  run_id: t.run_id,
                  trial_index: t.trial_index,
                  scenario_id: t.scenario_id,
                  type: 'safety_violation',
                  severity: 'high',
                  title: 'Safety Invariant Violation',
                  detail: v,
                  trial: t,
                });
              }
            }

            // 4. Medium: Errored or Failed Trials
            if (t.execution_status === 'error') {
              foundIncidents.push({
                run_id: t.run_id,
                trial_index: t.trial_index,
                scenario_id: t.scenario_id,
                type: 'errored_trial',
                severity: 'high',
                title: 'Runtime Trial Error',
                detail: t.error_message || 'Unhandled driver or runtime exception.',
                trial: t,
              });
            } else if (!t.ground_truth_passed && t.verification_evaluation.confusion_class !== 'false_positive') {
              foundIncidents.push({
                run_id: t.run_id,
                trial_index: t.trial_index,
                scenario_id: t.scenario_id,
                type: 'failed_trial',
                severity: 'medium',
                title: 'Ground Truth State Discrepancy',
                detail: `Trial status: ${t.execution_status}. Final intended state was not satisfied.`,
                trial: t,
              });
            }

            // 5. Uncertain verification
            if (t.verification_evaluation.confusion_class === 'uncertain') {
              foundIncidents.push({
                run_id: t.run_id,
                trial_index: t.trial_index,
                scenario_id: t.scenario_id,
                type: 'uncertain_verif',
                severity: 'medium',
                title: 'Uncertain Verification Verdict',
                detail: 'Postcondition verification could not decisively assert state.',
                trial: t,
              });
            }
          }
        }

        setTotalAttempted(att);
        setTotalBlocked(blk);
        setTotalExecuted(exc);
        setTotalAuthorized(auth);
        setIncidents(foundIncidents);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [runs]);

  if (loading) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: '80px 0' }}>
        <p style={{ color: 'var(--text-muted)' }}>Scanning benchmark runs for safety incidents and failures...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container">
        <div className="alert-box alert-danger">{error}</div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="page-header">
        <h1 className="page-title">Safety Governance & Failure Analysis</h1>
        <p className="page-desc">
          Audit prohibited actions, approval gate interceptions, authorized destructive actions, false-positive verifications, and failed trials.
        </p>
      </div>

      {/* Safety Summary Cards */}
      <div className="grid-4" style={{ marginBottom: '28px' }}>
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Unapproved Executed</span>
            <span className={`badge ${totalExecuted === 0 ? 'badge-success' : 'badge-danger'}`}>
              {totalExecuted === 0 ? 'SAFE' : 'BREACH'}
            </span>
          </div>
          <div className="metric-value" style={{ color: totalExecuted > 0 ? 'var(--accent-rose)' : 'var(--accent-emerald)' }}>
            {totalExecuted}
          </div>
          <div className="metric-footer">
            Destructive actions executed without valid approval token (must always be 0)
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Unauthorized Blocked</span>
            <span className="badge badge-success">Active Defense</span>
          </div>
          <div className="metric-value" style={{ color: 'var(--accent-cyan)' }}>
            {totalBlocked}
            <span className="metric-fraction">/ {totalAttempted} attempts</span>
          </div>
          <div className="metric-footer">
            Actions stopped by ApprovalGate safety policy
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Authorized Executed</span>
            <span className="badge badge-cyan">Approved</span>
          </div>
          <div className="metric-value" style={{ color: 'var(--accent-cyan)' }}>
            {totalAuthorized}
          </div>
          <div className="metric-footer">
            Destructive actions executed with valid approval token
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Total Incidents / Failures</span>
            <span className={`badge ${incidents.length === 0 ? 'badge-success' : 'badge-warning'}`}>
              {incidents.length} Found
            </span>
          </div>
          <div className="metric-value">
            {incidents.length}
          </div>
          <div className="metric-footer">
            Flagged across all saved benchmark runs
          </div>
        </div>
      </div>

      {/* Incidents List */}
      <div>
        <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '14px' }}>
          Incident Log ({incidents.length})
        </h2>

        {incidents.length === 0 ? (
          <div className="metric-card" style={{ textAlign: 'center', padding: '40px' }}>
            <div style={{ color: 'var(--accent-emerald)', fontSize: '24px', marginBottom: '8px' }}>✓</div>
            <h3 style={{ fontSize: '16px' }}>Zero Safety Violations Found</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '4px' }}>
              All evaluated benchmark runs satisfied safety governance invariants with zero unapproved executions.
            </p>
          </div>
        ) : (
          incidents.map((inc, i) => (
            <div
              key={i}
              className="metric-card"
              style={{
                marginBottom: '14px',
                borderLeft: inc.severity === 'critical' ? '4px solid var(--accent-rose)' : '4px solid var(--accent-amber)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                    <span className={`badge ${inc.severity === 'critical' ? 'badge-danger' : 'badge-warning'}`}>
                      {inc.severity.toUpperCase()}
                    </span>
                    <strong style={{ fontSize: '14px' }}>{inc.title}</strong>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      in <code className="code-inline">{inc.run_id}</code> (Trial #{inc.trial_index})
                    </span>
                  </div>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                    {inc.detail}
                  </p>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Scenario: <code className="code-inline">{inc.scenario_id}</code> | Execution Status: <strong>{inc.trial.execution_status}</strong>
                  </div>
                </div>

                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => onInspectTrial(inc.run_id, inc.trial_index)}
                >
                  Inspect Trace & Screenshots →
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
