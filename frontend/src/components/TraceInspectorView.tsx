import React, { useState, useEffect } from 'react';
import { TrialTraceDetail } from '../types';
import { getTrialTrace, getScreenshotUrl } from '../api';

interface TraceInspectorViewProps {
  runId: string;
  trialIndex: number;
  onBackToRun: () => void;
}

interface ScreenshotViewerProps {
  screenshotId?: string | null;
  alt: string;
  missingMessage?: string;
  onZoom: (screenshotId: string) => void;
}

const ScreenshotViewer: React.FC<ScreenshotViewerProps> = ({
  screenshotId,
  alt,
  missingMessage = 'No screenshot recorded',
  onZoom,
}) => {
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    setHasError(false);
  }, [screenshotId]);

  if (!screenshotId) {
    return <div className="screenshot-missing">{missingMessage}</div>;
  }

  if (hasError) {
    return (
      <div className="screenshot-missing">
        Screenshot artifact '{screenshotId}' missing or detached
      </div>
    );
  }

  return (
    <img
      src={getScreenshotUrl(screenshotId)}
      alt={alt}
      className="screenshot-img"
      onClick={() => onZoom(screenshotId)}
      onError={() => setHasError(true)}
    />
  );
};

export const TraceInspectorView: React.FC<TraceInspectorViewProps> = ({
  runId,
  trialIndex,
  onBackToRun,
}) => {
  const [trace, setTrace] = useState<TrialTraceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoomedScreenshot, setZoomedScreenshot] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getTrialTrace(runId, trialIndex)
      .then((data) => {
        setTrace(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [runId, trialIndex]);

  if (loading) {
    return (
      <div className="container" style={{ textAlign: 'center', padding: '80px 0' }}>
        <p style={{ color: 'var(--text-muted)' }}>Loading visual execution trace for Trial #{trialIndex}...</p>
      </div>
    );
  }

  if (error || !trace) {
    return (
      <div className="container">
        <div className="alert-box alert-danger">
          <strong>Failed to load trace:</strong> {error || 'Trace not found'}
        </div>
        <button className="btn btn-secondary" onClick={onBackToRun}>
          Back to Run
        </button>
      </div>
    );
  }

  const isGtPassed = trace.ground_truth_passed;

  return (
    <div className="container">
      {/* Header & Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
        <div>
          <button className="btn btn-secondary btn-sm" onClick={onBackToRun} style={{ marginBottom: '10px' }}>
            ← Back to Run Explorer
          </button>
          <h1 className="page-title">
            Visual Trace Inspector: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>Trial #{trace.trial_index}</span>
          </h1>
          <p className="page-desc">
            Scenario: <strong>{trace.scenario_title}</strong> (<code className="code-inline">{trace.scenario_id}</code>) | Strategy: <strong>{trace.strategy}</strong>
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <span className={`badge ${isGtPassed ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '13px', padding: '6px 12px' }}>
            {isGtPassed ? 'Ground Truth: PASSED' : 'Ground Truth: FAILED'}
          </span>
          <span className="badge badge-muted" style={{ fontSize: '13px', padding: '6px 12px' }}>
            Agent Verdict: {trace.agent_final_verdict || 'N/A'}
          </span>
        </div>
      </div>

      {/* User Instruction Banner */}
      <div className="metric-card" style={{ marginBottom: '24px' }}>
        <div className="metric-header">
          <span className="metric-label">Goal-Oriented User Instruction</span>
          <span className="badge badge-cyan">{trace.total_steps} Steps Planned</span>
        </div>
        <div style={{ fontSize: '14px', color: 'var(--text-primary)', fontStyle: 'italic', marginBottom: '8px' }}>
          "{trace.user_instruction}"
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Total Trial Duration: <strong>{trace.durations.total_trial_ms?.toFixed(1)} ms</strong> | Recorded Screenshots: <strong>{trace.artifact_screenshot_ids.length}</strong>
        </div>
      </div>

      {/* Safety Violations Alert if any */}
      {trace.safety_violations.length > 0 && (
        <div className="alert-box alert-danger">
          <div>
            <strong>Safety Invariant Violations in this Trial:</strong>
            <ul style={{ marginLeft: '20px', marginTop: '6px' }}>
              {trace.safety_violations.map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Step by Step Sequence */}
      <div>
        <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '16px' }}>
          Execution Step Sequence ({trace.steps.length} Steps)
        </h2>

        {trace.steps.map((st) => (
          <div key={st.step_index} className="trace-step-card">
            <div className="trace-step-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                  STEP {st.step_index}
                </span>
                <span className="badge badge-muted">{st.action_type.toUpperCase()}</span>
                <span style={{ fontSize: '13px', fontWeight: 600 }}>
                  Target Query: <code className="code-inline">{st.target_query}</code>
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {st.action_duration_ms !== null && (
                  <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                    {st.action_duration_ms.toFixed(1)} ms
                  </span>
                )}
                <span className={`badge ${st.action_status === 'success' ? 'badge-success' : 'badge-danger'}`}>
                  Action: {st.action_status}
                </span>
              </div>
            </div>

            <div className="trace-step-body">
              {/* Evidence & Verification Metadata */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px', marginBottom: '14px', fontSize: '12px' }}>
                <div style={{ background: 'var(--bg-surface)', padding: '10px 14px', borderRadius: '6px' }}>
                  <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>Grounding Target & Evidence</div>
                  <div>Selector: <code className="code-inline">{st.target_selector || st.target_id}</code></div>
                  <div>Source: <span className="badge badge-muted">{st.evidence_source}</span></div>
                </div>

                <div style={{ background: 'var(--bg-surface)', padding: '10px 14px', borderRadius: '6px' }}>
                  <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>Asserted Postcondition</div>
                  <div>Expectation: <code className="code-inline">{st.expected_postcondition || 'None'}</code></div>
                  <div>Status: <span className={`badge ${st.verification_status === 'verified' ? 'badge-success' : 'badge-warning'}`}>{st.verification_status || 'N/A'}</span></div>
                </div>
              </div>

              {/* Error message if step failed */}
              {st.error_message && (
                <div className="alert-box alert-danger" style={{ marginBottom: '14px' }}>
                  <strong>Step Error:</strong> {st.error_message}
                </div>
              )}

              {/* Screenshot Pair */}
              <div className="screenshot-pair">
                {/* Pre-Action Screenshot */}
                <div className="screenshot-frame">
                  <div className="screenshot-header">
                    <span>1. PRE-ACTION OBSERVATION</span>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>{st.pre_screenshot_id || 'None'}</span>
                  </div>
                  <ScreenshotViewer
                    screenshotId={st.pre_screenshot_id}
                    alt={`Pre-action observation for step ${st.step_index}`}
                    missingMessage="No pre-action screenshot recorded"
                    onZoom={setZoomedScreenshot}
                  />
                </div>

                {/* Post-Action Screenshot */}
                <div className="screenshot-frame">
                  <div className="screenshot-header">
                    <span>2. POST-ACTION VERIFICATION</span>
                    <span style={{ fontFamily: 'var(--font-mono)' }}>{st.post_screenshot_id || 'None'}</span>
                  </div>
                  <ScreenshotViewer
                    screenshotId={st.post_screenshot_id}
                    alt={`Post-action observation for step ${st.step_index}`}
                    missingMessage="No post-action screenshot recorded"
                    onZoom={setZoomedScreenshot}
                  />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Screenshot Zoom Modal */}
      {zoomedScreenshot && (
        <div className="modal-overlay" onClick={() => setZoomedScreenshot(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close-btn" onClick={() => setZoomedScreenshot(null)}>
              ✕
            </button>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', fontSize: '13px', fontFamily: 'var(--font-mono)' }}>
              Screenshot Artifact: {zoomedScreenshot}
            </div>
            <img
              src={getScreenshotUrl(zoomedScreenshot)}
              alt="Zoomed observation"
              style={{ maxWidth: '100%', height: 'auto', display: 'block' }}
            />
          </div>
        </div>
      )}
    </div>
  );
};
