import React from 'react';

export type TabType = 'overview' | 'runs' | 'compare' | 'safety' | 'trace';

interface NavbarProps {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
  selectedRunId: string | null;
  selectedTrialIndex: number | null;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onSelectTab,
  selectedRunId,
  selectedTrialIndex,
}) => {
  return (
    <header className="navbar">
      <div className="brand">
        <div className="brand-icon">S</div>
        <div>
          <div className="brand-title">Sightline</div>
          <div className="brand-sub">Visual Agent Reliability Lab</div>
        </div>
      </div>

      <nav className="nav-links">
        <button
          className={`nav-btn ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => onSelectTab('overview')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="7" />
            <rect x="14" y="3" width="7" height="7" />
            <rect x="14" y="14" width="7" height="7" />
            <rect x="3" y="14" width="7" height="7" />
          </svg>
          Overview
        </button>

        <button
          className={`nav-btn ${activeTab === 'runs' ? 'active' : ''}`}
          onClick={() => onSelectTab('runs')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="8" y1="6" x2="21" y2="6" />
            <line x1="8" y1="12" x2="21" y2="12" />
            <line x1="8" y1="18" x2="21" y2="18" />
            <line x1="3" y1="6" x2="3.01" y2="6" />
            <line x1="3" y1="12" x2="3.01" y2="12" />
            <line x1="3" y1="18" x2="3.01" y2="18" />
          </svg>
          Run Explorer
        </button>

        <button
          className={`nav-btn ${activeTab === 'compare' ? 'active' : ''}`}
          onClick={() => onSelectTab('compare')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="16 3 21 3 21 8" />
            <line x1="4" y1="20" x2="21" y2="3" />
            <polyline points="21 16 21 21 16 21" />
            <line x1="15" y1="15" x2="21" y2="21" />
            <line x1="4" y1="4" x2="9" y2="9" />
          </svg>
          Compare Runs
        </button>

        <button
          className={`nav-btn ${activeTab === 'safety' ? 'active' : ''}`}
          onClick={() => onSelectTab('safety')}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
          Safety & Failures
        </button>

        {selectedRunId && selectedTrialIndex && (
          <button
            className={`nav-btn ${activeTab === 'trace' ? 'active' : ''}`}
            onClick={() => onSelectTab('trace')}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 14 14" />
            </svg>
            Trace ({selectedRunId.slice(0, 8)}: T{selectedTrialIndex})
          </button>
        )}
      </nav>

      <div className="system-badge">
        <span className="pulse-dot"></span>
        <span>Local-Only Evaluation Lab</span>
      </div>
    </header>
  );
};
