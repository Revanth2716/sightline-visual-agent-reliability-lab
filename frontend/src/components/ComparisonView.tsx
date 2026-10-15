import React, { useState, useEffect } from 'react';
import { BenchmarkRunSummaryItem, BenchmarkSummaryReport } from '../types';
import { getRunReport } from '../api';

interface ComparisonViewProps {
  runs: BenchmarkRunSummaryItem[];
}

export const ComparisonView: React.FC<ComparisonViewProps> = ({ runs }) => {
  const [runAId, setRunAId] = useState<string>(runs[0]?.run_id || '');
  const [runBId, setRunBId] = useState<string>(runs[1]?.run_id || runs[0]?.run_id || '');

  const [reportA, setReportA] = useState<BenchmarkSummaryReport | null>(null);
  const [reportB, setReportB] = useState<BenchmarkSummaryReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runAId || !runBId) return;

    setLoading(true);
    setError(null);

    Promise.all([getRunReport(runAId), getRunReport(runBId)])
      .then(([a, b]) => {
        setReportA(a);
        setReportB(b);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [runAId, runBId]);

  if (runs.length < 2) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: '60px 0' }}>
        <h2>At Least 2 Runs Required</h2>
        <p style={{ color: 'var(--text-secondary)', marginTop: '8px' }}>
          Execute and save at least two benchmark runs to enable comparative analysis.
        </p>
      </div>
    );
  }

  const isConfigMismatch =
    reportA &&
    reportB &&
    (reportA.strategy !== reportB.strategy ||
      reportA.config.fault_injection !== reportB.config.fault_injection);

  return (
    <div className="container">
      <div className="page-header">
        <h1 className="page-title">Run Comparison & Differential Analysis</h1>
        <p className="page-desc">
          Compare reliability metrics, target selection, safety enforcement, and latency across evaluation runs.
        </p>
      </div>

      {/* Selector Toolbar */}
      <div
        className="metric-card"
        style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          gap: '24px',
          flexWrap: 'wrap',
          marginBottom: '24px',
        }}
      >
        <div style={{ flex: 1, minWidth: '220px' }}>
          <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
            BASELINE RUN (A)
          </label>
          <select
            className="input-box"
            style={{ width: '100%' }}
            value={runAId}
            onChange={(e) => setRunAId(e.target.value)}
          >
            {runs.map((r) => (
              <option key={`a-${r.run_id}`} value={r.run_id}>
                {r.run_id} ({r.strategy}, {r.trials_attempted} trials)
              </option>
            ))}
          </select>
        </div>

        <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-muted)' }}>VS</div>

        <div style={{ flex: 1, minWidth: '220px' }}>
          <label style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
            COMPARISON RUN (B)
          </label>
          <select
            className="input-box"
            style={{ width: '100%' }}
            value={runBId}
            onChange={(e) => setRunBId(e.target.value)}
          >
            {runs.map((r) => (
              <option key={`b-${r.run_id}`} value={r.run_id}>
                {r.run_id} ({r.strategy}, {r.trials_attempted} trials)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Statistical Caveat Notice */}
      <div className="alert-box alert-warning">
        <div>
          <strong>Statistical Significance Warning:</strong> Sample sizes reflect recorded deterministic benchmark trials ($N_A = {reportA?.trials_attempted || '?'}, N_B = {reportB?.trials_attempted || '?'}$). Small samples do not imply broad generalization across all arbitrary web applications.
        </div>
      </div>

      {isConfigMismatch && (
        <div className="alert-box alert-danger">
          <div>
            <strong>Configuration Discrepancy:</strong> Run A ({reportA?.strategy}, fault: {reportA?.config.fault_injection || 'none'}) and Run B ({reportB?.strategy}, fault: {reportB?.config.fault_injection || 'none'}) evaluate different strategies or fault injection modes. Comparisons reflect configuration changes.
          </div>
        </div>
      )}

      {loading && <p style={{ color: 'var(--text-muted)' }}>Comparing runs...</p>}
      {error && <div className="alert-box alert-danger">{error}</div>}

      {reportA && reportB && (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Reliability Metric</th>
                <th>Run A: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>{reportA.run_id}</span></th>
                <th>Run B: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-purple)' }}>{reportB.run_id}</span></th>
                <th>Delta (B − A)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Strategy & Fault Injection</strong></td>
                <td>
                  <span className="badge badge-muted">{reportA.strategy}</span>{' '}
                  {reportA.config.fault_injection && (
                    <span className="badge badge-warning">{reportA.config.fault_injection}</span>
                  )}
                </td>
                <td>
                  <span className="badge badge-muted">{reportB.strategy}</span>{' '}
                  {reportB.config.fault_injection && (
                    <span className="badge badge-warning">{reportB.config.fault_injection}</span>
                  )}
                </td>
                <td style={{ color: 'var(--text-muted)' }}>—</td>
              </tr>

              <tr>
                <td><strong>Sample Size ($N$ Trials)</strong></td>
                <td><strong>{reportA.trials_attempted}</strong> trials ({reportA.config.scenario_ids.length} scenarios)</td>
                <td><strong>{reportB.trials_attempted}</strong> trials ({reportB.config.scenario_ids.length} scenarios)</td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {reportB.trials_attempted - reportA.trials_attempted >= 0 ? '+' : ''}
                  {reportB.trials_attempted - reportA.trials_attempted}
                </td>
              </tr>

              <tr>
                <td><strong>Task Completion Rate</strong></td>
                <td>
                  <span className="badge badge-cyan">
                    {(reportA.task_completion_rate * 100).toFixed(1)}% ({reportA.trials_completed}/{reportA.trials_attempted})
                  </span>
                </td>
                <td>
                  <span className="badge badge-cyan">
                    {(reportB.task_completion_rate * 100).toFixed(1)}% ({reportB.trials_completed}/{reportB.trials_attempted})
                  </span>
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {((reportB.task_completion_rate - reportA.task_completion_rate) * 100).toFixed(1)}%
                </td>
              </tr>

              <tr>
                <td><strong>Target Selection Accuracy</strong></td>
                <td>
                  {reportA.target_selection_accuracy !== null
                    ? `${(reportA.target_selection_accuracy * 100).toFixed(1)}% (${reportA.target_decisions_count} targets)`
                    : 'N/A'}
                </td>
                <td>
                  {reportB.target_selection_accuracy !== null
                    ? `${(reportB.target_selection_accuracy * 100).toFixed(1)}% (${reportB.target_decisions_count} targets)`
                    : 'N/A'}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {reportA.target_selection_accuracy !== null && reportB.target_selection_accuracy !== null
                    ? `${((reportB.target_selection_accuracy - reportA.target_selection_accuracy) * 100).toFixed(1)}%`
                    : 'N/A'}
                </td>
              </tr>

              <tr>
                <td><strong>Unsafe Action Rate</strong></td>
                <td>
                  <span className={reportA.unsafe_action_rate === 0 ? 'badge badge-success' : 'badge badge-danger'}>
                    {(reportA.unsafe_action_rate * 100).toFixed(1)}% ({reportA.prohibited_actions_executed} unapproved)
                  </span>
                </td>
                <td>
                  <span className={reportB.unsafe_action_rate === 0 ? 'badge badge-success' : 'badge badge-danger'}>
                    {(reportB.unsafe_action_rate * 100).toFixed(1)}% ({reportB.prohibited_actions_executed} unapproved)
                  </span>
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {((reportB.unsafe_action_rate - reportA.unsafe_action_rate) * 100).toFixed(1)}%
                </td>
              </tr>

              <tr>
                <td><strong>Unauthorized Actions Blocked</strong></td>
                <td>
                  {reportA.prohibited_actions_attempted > 0
                    ? `${reportA.prohibited_actions_blocked} / ${reportA.prohibited_actions_attempted} attempts`
                    : 'N/A — 0 attempts'}
                </td>
                <td>
                  {reportB.prohibited_actions_attempted > 0
                    ? `${reportB.prohibited_actions_blocked} / ${reportB.prohibited_actions_attempted} attempts`
                    : 'N/A — 0 attempts'}
                </td>
                <td style={{ color: 'var(--text-muted)' }}>—</td>
              </tr>

              <tr>
                <td><strong>Authorized Destructive Executions</strong></td>
                <td>
                  <span className="badge badge-muted">
                    {reportA.authorized_actions_executed || 0}
                  </span>
                </td>
                <td>
                  <span className="badge badge-muted">
                    {reportB.authorized_actions_executed || 0}
                  </span>
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {((reportB.authorized_actions_executed || 0) - (reportA.authorized_actions_executed || 0) >= 0 ? '+' : '')}
                  {(reportB.authorized_actions_executed || 0) - (reportA.authorized_actions_executed || 0)}
                </td>
              </tr>

              <tr>
                <td><strong>Verification Accuracy</strong></td>
                <td>
                  {reportA.verification_accuracy !== null
                    ? `${(reportA.verification_accuracy * 100).toFixed(1)}%`
                    : 'N/A'}
                </td>
                <td>
                  {reportB.verification_accuracy !== null
                    ? `${(reportB.verification_accuracy * 100).toFixed(1)}%`
                    : 'N/A'}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {reportA.verification_accuracy !== null && reportB.verification_accuracy !== null
                    ? `${((reportB.verification_accuracy - reportA.verification_accuracy) * 100).toFixed(1)}%`
                    : 'N/A'}
                </td>
              </tr>

              <tr>
                <td><strong>Safety Invariant Violations</strong></td>
                <td>
                  <span className={reportA.safety_invariant_violations_count > 0 ? 'badge badge-danger' : 'badge badge-success'}>
                    {reportA.safety_invariant_violations_count}
                  </span>
                </td>
                <td>
                  <span className={reportB.safety_invariant_violations_count > 0 ? 'badge badge-danger' : 'badge badge-success'}>
                    {reportB.safety_invariant_violations_count}
                  </span>
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {reportB.safety_invariant_violations_count - reportA.safety_invariant_violations_count}
                </td>
              </tr>

              <tr>
                <td><strong>Trial Latency (Mean / P95)</strong></td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {reportA.latency_summary.trial_duration_ms?.mean_ms ?? 'N/A'} ms / {reportA.latency_summary.trial_duration_ms?.p95_ms ?? 'N/A'} ms
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {reportB.latency_summary.trial_duration_ms?.mean_ms ?? 'N/A'} ms / {reportB.latency_summary.trial_duration_ms?.p95_ms ?? 'N/A'} ms
                </td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {reportA.latency_summary.trial_duration_ms && reportB.latency_summary.trial_duration_ms
                    ? `${(reportB.latency_summary.trial_duration_ms.mean_ms - reportA.latency_summary.trial_duration_ms.mean_ms).toFixed(1)} ms`
                    : 'N/A'}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
