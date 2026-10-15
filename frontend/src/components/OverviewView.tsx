import React from 'react';
import { DashboardOverviewStats } from '../types';

interface OverviewViewProps {
  stats: DashboardOverviewStats | null;
  loading: boolean;
  error: string | null;
  onSelectRun: (runId: string) => void;
  onRefresh: () => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  stats,
  loading,
  error,
  onSelectRun,
  onRefresh,
}) => {
  if (loading) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: '80px 0' }}>
        <p style={{ color: 'var(--text-muted)' }}>Loading benchmark portfolio metrics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container">
        <div className="alert-box alert-danger">
          <strong>Failed to load dashboard metrics:</strong> {error}
        </div>
        <button className="btn btn-secondary" onClick={onRefresh}>
          Retry
        </button>
      </div>
    );
  }

  if (!stats || stats.total_runs === 0) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: '80px 0' }}>
        <h2 style={{ marginBottom: '12px' }}>No Benchmark Runs Found</h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '20px', maxWidth: '500px', margin: '0 auto 20px auto' }}>
          No benchmark JSON reports were discovered in <code className="code-inline">artifacts/benchmarks/</code>. Execute a benchmark trial to populate this dashboard.
        </p>
        <button className="btn btn-primary" onClick={onRefresh}>
          Refresh Dashboard
        </button>
      </div>
    );
  }

  const completionPct = (stats.overall_completion_rate * 100).toFixed(1);
  const targetAccText = stats.overall_target_selection_accuracy !== null
    ? `${(stats.overall_target_selection_accuracy * 100).toFixed(1)}%`
    : 'N/A';
  const verifAccText = stats.verification_accuracy !== null
    ? `${(stats.verification_accuracy * 100).toFixed(1)}%`
    : 'N/A';
  const recoveryRateText = stats.recovery_success_rate !== null
    ? `${(stats.recovery_success_rate * 100).toFixed(1)}%`
    : 'N/A — no eligible trials';

  return (
    <div className="container">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Reliability Portfolio Overview</h1>
          <p className="page-desc">
            Aggregated interaction reliability across {stats.total_runs} saved benchmark runs ({stats.total_trials_attempted} trials total).
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={onRefresh}>
          Refresh Artifacts
        </button>
      </div>

      {stats.safety_invariant_violations_count > 0 && (
        <div className="alert-box alert-danger">
          <div>
            <strong>Safety Invariant Violations Detected:</strong> {stats.safety_invariant_violations_count} critical issue(s) recorded in saved reports (e.g. false-positive verification or destructive policy violations).
          </div>
        </div>
      )}

      {/* Primary 4-Metric Grid */}
      <div className="grid-4">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Task Completion Rate</span>
            <span className={`badge ${stats.overall_completion_rate >= 0.9 ? 'badge-success' : 'badge-warning'}`}>
              {stats.total_trials_completed} / {stats.total_trials_attempted}
            </span>
          </div>
          <div className="metric-value">
            {completionPct}%
            <span className="metric-fraction">
              ({stats.completion_numerator} / {stats.completion_denominator} trials)
            </span>
          </div>
          <div className="metric-footer">
            Evaluator-verified final DOM state
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Target Selection Acc.</span>
            <span className="badge badge-cyan">
              {stats.target_decisions_numerator} / {stats.target_decisions_denominator}
            </span>
          </div>
          <div className="metric-value">
            {targetAccText}
            {stats.overall_target_selection_accuracy !== null && (
              <span className="metric-fraction">
                ({stats.target_decisions_numerator} / {stats.target_decisions_denominator} targets)
              </span>
            )}
          </div>
          <div className="metric-footer">
            DOM-assisted bounding-box grounding
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Verification Accuracy</span>
            <span className="badge badge-cyan">
              {stats.verification_numerator} / {stats.verification_denominator}
            </span>
          </div>
          <div className="metric-value">
            {verifAccText}
            {stats.verification_accuracy !== null && (
              <span className="metric-fraction">
                ({stats.verification_numerator} / {stats.verification_denominator} evaluations)
              </span>
            )}
          </div>
          <div className="metric-footer">
            Agent verdict vs live DOM ground truth
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Safety Actions Governance</span>
            <span className={`badge ${stats.prohibited_executed === 0 ? 'badge-success' : 'badge-danger'}`}>
              {stats.prohibited_executed === 0 ? '0 Unapproved Executions' : `${stats.prohibited_executed} BREACHES`}
            </span>
          </div>
          <div className="metric-value">
            {stats.prohibited_executed === 0 ? '0.0%' : `${(stats.overall_unsafe_action_rate * 100).toFixed(1)}%`}
            <span className="metric-fraction">
              {stats.prohibited_attempted > 0
                ? `(Blocked: ${stats.prohibited_blocked} / ${stats.prohibited_attempted} unauthorized attempts)`
                : `(0 unauthorized attempts)`}
            </span>
          </div>
          <div className="metric-footer">
            Strict approval gate &bull; {stats.authorized_executed || 0} authorized execution{(stats.authorized_executed || 0) === 1 ? '' : 's'}
          </div>
        </div>
      </div>

      {/* Secondary 3-Card Grid */}
      <div className="grid-3">
        {/* Verification Confusion Matrix */}
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Verification Confusion Matrix</span>
            <span className="badge badge-muted">Aggregate</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', margin: '10px 0' }}>
            <div style={{ padding: '8px 12px', background: 'var(--bg-surface)', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>True Positives (TP)</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>
                {stats.verification_confusion.true_positive}
              </div>
            </div>
            <div style={{ padding: '8px 12px', background: 'var(--bg-surface)', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>False Positives (FP)</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: stats.verification_confusion.false_positive > 0 ? 'var(--accent-rose)' : 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                {stats.verification_confusion.false_positive}
              </div>
            </div>
            <div style={{ padding: '8px 12px', background: 'var(--bg-surface)', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>True Negatives (TN)</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                {stats.verification_confusion.true_negative}
              </div>
            </div>
            <div style={{ padding: '8px 12px', background: 'var(--bg-surface)', borderRadius: '6px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>False Negatives (FN)</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)' }}>
                {stats.verification_confusion.false_negative}
              </div>
            </div>
          </div>
          <div className="metric-footer">
            Uncertain verdicts: {stats.verification_confusion.uncertain} (never counted as success)
          </div>
        </div>

        {/* Recovery Metrics */}
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Bounded Error Recovery</span>
            <span className="badge badge-muted">Prerequisite</span>
          </div>
          <div className="metric-value" style={{ fontSize: '20px' }}>
            {recoveryRateText}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '8px 0' }}>
            Eligible recoverable faults: <strong>{stats.recovery_eligible_count}</strong>
            <br />
            Successful recoveries: <strong>{stats.recovery_successful_count}</strong>
          </div>
          <div className="metric-footer">
            At most 1 retry for benign actions, 0 for destructive actions
          </div>
        </div>

        {/* Portfolio Hygiene & Integrity */}
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-label">Audit Data Integrity</span>
            <span className="badge badge-success">Verified</span>
          </div>
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '8px 0' }}>
            <div>Total Valid Runs: <strong>{stats.total_runs}</strong></div>
            <div>Trials Completed: <strong>{stats.total_trials_completed}</strong></div>
            <div>Trials Failed / Errored: <strong>{stats.total_trials_failed} / {stats.total_trials_errored}</strong></div>
            <div>Safety Violations: <strong>{stats.safety_invariant_violations_count}</strong></div>
          </div>
          <div className="metric-footer">
            All reports serialized to JSON Schema v1.0.0
          </div>
        </div>
      </div>

      {/* Saved Benchmark Runs Table */}
      <div style={{ marginTop: '32px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '14px' }}>
          Saved Benchmark Reports ({stats.runs.length})
        </h2>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Strategy</th>
                <th>Scenarios</th>
                <th>Trials</th>
                <th>Completion Rate</th>
                <th>Target Acc.</th>
                <th>Safety</th>
                <th>Timestamp (UTC)</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {stats.runs.map((r) => {
                const compPct = (r.task_completion_rate * 100).toFixed(1);
                const targetPct = r.target_selection_accuracy !== null
                  ? `${(r.target_selection_accuracy * 100).toFixed(1)}%`
                  : 'N/A';
                return (
                  <tr key={r.run_id}>
                    <td>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent-cyan)' }}>
                        {r.run_id}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-muted">{r.strategy}</span>
                    </td>
                    <td>{r.scenario_count} scenarios</td>
                    <td>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>
                        {r.trials_completed} / {r.trials_attempted}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${r.task_completion_rate === 1.0 ? 'badge-success' : 'badge-warning'}`}>
                        {compPct}% ({r.trials_completed}/{r.trials_attempted})
                      </span>
                    </td>
                    <td>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{targetPct}</span>
                    </td>
                    <td>
                      {r.safety_invariant_violations_count > 0 ? (
                        <span className="badge badge-danger">
                          {r.safety_invariant_violations_count} VIOLATION
                        </span>
                      ) : (
                        <span className="badge badge-success">0 Violations</span>
                      )}
                    </td>
                    <td style={{ fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                      {new Date(r.timestamp_utc).toLocaleString()}
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => onSelectRun(r.run_id)}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
