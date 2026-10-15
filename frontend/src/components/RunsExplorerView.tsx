import React, { useState, useEffect } from 'react';
import { BenchmarkRunSummaryItem, BenchmarkSummaryReport } from '../types';
import { getRunReport } from '../api';

interface RunsExplorerViewProps {
  runs: BenchmarkRunSummaryItem[];
  selectedRunId: string | null;
  onSelectRun: (runId: string) => void;
  onInspectTrial: (runId: string, trialIndex: number) => void;
}

export const RunsExplorerView: React.FC<RunsExplorerViewProps> = ({
  runs,
  selectedRunId,
  onSelectRun,
  onInspectTrial,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [strategyFilter, setStrategyFilter] = useState<'all' | 'closed_loop' | 'baseline'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'clean' | 'has_failures'>('all');

  const [activeReport, setActiveReport] = useState<BenchmarkSummaryReport | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedRunId) {
      setLoadingReport(true);
      setReportError(null);
      getRunReport(selectedRunId)
        .then((rep) => {
          setActiveReport(rep);
          setLoadingReport(false);
        })
        .catch((err) => {
          setReportError(err.message);
          setLoadingReport(false);
        });
    } else {
      setActiveReport(null);
    }
  }, [selectedRunId]);

  const filteredRuns = runs.filter((r) => {
    const matchesSearch =
      r.run_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStrategy =
      strategyFilter === 'all' || r.strategy === strategyFilter;
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'clean' && r.trials_failed === 0 && r.safety_invariant_violations_count === 0) ||
      (statusFilter === 'has_failures' && (r.trials_failed > 0 || r.safety_invariant_violations_count > 0));

    return matchesSearch && matchesStrategy && matchesStatus;
  });

  return (
    <div className="container">
      <div className="page-header">
        <h1 className="page-title">Benchmark Run Explorer</h1>
        <p className="page-desc">
          Search, filter, and inspect detailed trial traces and latency metrics from saved benchmark runs.
        </p>
      </div>

      {/* Filter Toolbar */}
      <div
        style={{
          display: 'flex',
          gap: '12px',
          alignItems: 'center',
          flexWrap: 'wrap',
          marginBottom: '20px',
        }}
      >
        <input
          type="text"
          className="input-box"
          placeholder="Search by run ID or name..."
          style={{ width: '280px' }}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />

        <select
          className="input-box"
          value={strategyFilter}
          onChange={(e) => setStrategyFilter(e.target.value as any)}
        >
          <option value="all">All Strategies</option>
          <option value="closed_loop">closed_loop</option>
          <option value="baseline">baseline</option>
        </select>

        <select
          className="input-box"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as any)}
        >
          <option value="all">All Outcomes</option>
          <option value="clean">Clean (100% Pass, 0 Violations)</option>
          <option value="has_failures">Has Failures / Violations</option>
        </select>

        <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: 'auto' }}>
          Showing {filteredRuns.length} of {runs.length} runs
        </span>
      </div>

      {/* Runs Table */}
      <div className="table-container" style={{ marginBottom: '28px' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Config Name</th>
              <th>Strategy</th>
              <th>Trials</th>
              <th>Completion Rate</th>
              <th>Target Acc.</th>
              <th>Safety Violations</th>
              <th>Date</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredRuns.map((r) => {
              const isSelected = r.run_id === selectedRunId;
              const compPct = (r.task_completion_rate * 100).toFixed(1);
              const targetPct = r.target_selection_accuracy !== null
                ? `${(r.target_selection_accuracy * 100).toFixed(1)}%`
                : 'N/A';
              return (
                <tr
                  key={r.run_id}
                  style={{
                    backgroundColor: isSelected ? 'var(--accent-cyan-dim)' : undefined,
                  }}
                >
                  <td>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent-cyan)' }}>
                      {r.run_id}
                    </span>
                  </td>
                  <td>{r.name}</td>
                  <td>
                    <span className="badge badge-muted">{r.strategy}</span>
                  </td>
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
                      <span className="badge badge-success">0</span>
                    )}
                  </td>
                  <td style={{ fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                    {new Date(r.timestamp_utc).toLocaleDateString()}
                  </td>
                  <td>
                    <button
                      className={`btn btn-sm ${isSelected ? 'btn-primary' : 'btn-secondary'}`}
                      onClick={() => onSelectRun(r.run_id)}
                    >
                      {isSelected ? 'Viewing' : 'Inspect'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Selected Run Detail Pane */}
      {selectedRunId && (
        <div style={{ marginTop: '24px', borderTop: '1px solid var(--border)', paddingTop: '24px' }}>
          {loadingReport && (
            <p style={{ color: 'var(--text-muted)' }}>Loading run report {selectedRunId}...</p>
          )}

          {reportError && (
            <div className="alert-box alert-danger">
              Failed to load run details: {reportError}
            </div>
          )}

          {activeReport && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 700 }}>
                    Run Detail: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>{activeReport.run_id}</span>
                  </h2>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Executed at {new Date(activeReport.timestamp_utc).toUTCString()} | Schema {activeReport.schema_version}
                  </p>
                </div>
              </div>

              {/* Run Config Bar */}
              <div className="metric-card" style={{ marginBottom: '20px' }}>
                <div className="metric-header">
                  <span className="metric-label">Configuration & Seed</span>
                  <span className="badge badge-muted">Deterministic Replay</span>
                </div>
                <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', fontSize: '13px' }}>
                  <div>Strategy: <strong>{activeReport.config.strategy}</strong></div>
                  <div>Trials per Scenario: <strong>{activeReport.config.trials_per_scenario}</strong></div>
                  <div>Step Budget: <strong>{activeReport.config.max_budget}</strong></div>
                  <div>Seed: <code className="code-inline">{activeReport.config.seed}</code></div>
                  <div>Fault Injection: <strong>{activeReport.config.fault_injection || 'None'}</strong></div>
                </div>
              </div>

              {/* Trials Table */}
              <h3 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '10px' }}>
                Evaluated Trials ({activeReport.trial_results.length})
              </h3>
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Trial #</th>
                      <th>Scenario</th>
                      <th>Execution Status</th>
                      <th>Evaluator GT</th>
                      <th>Agent Verdict</th>
                      <th>Target Decisions</th>
                      <th>Duration</th>
                      <th>Safety Violations</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeReport.trial_results.map((t) => {
                      const isGtPass = t.ground_truth_passed;
                      const durationMs = t.durations.total_trial_ms.toFixed(1);
                      return (
                        <tr key={t.trial_index}>
                          <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                            #{t.trial_index}
                          </td>
                          <td>
                            <code className="code-inline">{t.scenario_id}</code>
                          </td>
                          <td>
                            <span className={`badge ${t.execution_status === 'completed' ? 'badge-success' : 'badge-warning'}`}>
                              {t.execution_status}
                            </span>
                          </td>
                          <td>
                            <span className={`badge ${isGtPass ? 'badge-success' : 'badge-danger'}`}>
                              {isGtPass ? 'Passed' : 'Failed'}
                            </span>
                          </td>
                          <td>
                            <span className="badge badge-muted">
                              {t.agent_final_verdict || 'N/A'}
                            </span>
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>
                            {t.target_selections.correct_selections} / {t.target_selections.decisions_count}
                          </td>
                          <td style={{ fontFamily: 'var(--font-mono)' }}>
                            {durationMs} ms
                          </td>
                          <td>
                            {t.safety_violations_count > 0 ? (
                              <span className="badge badge-danger">
                                {t.safety_violations_count} VIOLATION
                              </span>
                            ) : (
                              <span className="badge badge-success">0</span>
                            )}
                          </td>
                          <td>
                            <button
                              className="btn btn-primary btn-sm"
                              onClick={() => onInspectTrial(activeReport.run_id, t.trial_index)}
                            >
                              Inspect Trace & Images
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
