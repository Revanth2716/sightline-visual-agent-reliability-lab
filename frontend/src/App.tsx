import React, { useState, useEffect } from 'react';
import { Navbar, TabType } from './components/Navbar';
import { OverviewView } from './components/OverviewView';
import { RunsExplorerView } from './components/RunsExplorerView';
import { ComparisonView } from './components/ComparisonView';
import { TraceInspectorView } from './components/TraceInspectorView';
import { SafetyFailureView } from './components/SafetyFailureView';
import { DashboardOverviewStats } from './types';
import { getOverviewStats } from './api';
import './styles.css';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [stats, setStats] = useState<DashboardOverviewStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedTrialIndex, setSelectedTrialIndex] = useState<number | null>(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    getOverviewStats()
      .then((data) => {
        setStats(data);
        if (data.runs.length > 0 && !selectedRunId) {
          setSelectedRunId(data.runs[0].run_id);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectRun = (runId: string) => {
    setSelectedRunId(runId);
    setActiveTab('runs');
  };

  const handleInspectTrial = (runId: string, trialIndex: number) => {
    setSelectedRunId(runId);
    setSelectedTrialIndex(trialIndex);
    setActiveTab('trace');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        activeTab={activeTab}
        onSelectTab={(t) => setActiveTab(t)}
        selectedRunId={selectedRunId}
        selectedTrialIndex={selectedTrialIndex}
      />

      <main style={{ flex: 1 }}>
        {activeTab === 'overview' && (
          <OverviewView
            stats={stats}
            loading={loading}
            error={error}
            onSelectRun={handleSelectRun}
            onRefresh={loadData}
          />
        )}

        {activeTab === 'runs' && (
          <RunsExplorerView
            runs={stats?.runs || []}
            selectedRunId={selectedRunId}
            onSelectRun={(id) => setSelectedRunId(id)}
            onInspectTrial={handleInspectTrial}
          />
        )}

        {activeTab === 'compare' && (
          <ComparisonView runs={stats?.runs || []} />
        )}

        {activeTab === 'safety' && (
          <SafetyFailureView
            runs={stats?.runs || []}
            onInspectTrial={handleInspectTrial}
          />
        )}

        {activeTab === 'trace' && selectedRunId && selectedTrialIndex && (
          <TraceInspectorView
            runId={selectedRunId}
            trialIndex={selectedTrialIndex}
            onBackToRun={() => setActiveTab('runs')}
          />
        )}
      </main>

      <footer
        style={{
          borderTop: '1px solid var(--border)',
          padding: '16px 28px',
          backgroundColor: 'var(--bg-surface)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '12px',
          color: 'var(--text-muted)',
        }}
      >
        <div>
          Sightline — Visual Agent Reliability Lab &copy; 2026. Local-first deterministic evaluation laboratory.
        </div>
        <div style={{ fontFamily: 'var(--font-mono)' }}>
          Local Loopback (127.0.0.1) &bull; Zero Cloud Telemetry &bull; Read-Only Audit Mode
        </div>
      </footer>
    </div>
  );
};
