import React, { useState, useEffect, useRef } from 'react';
import { FileText, GitCompare, Building2, Search, Map, RefreshCw } from 'lucide-react';
import { fetchHealth, fetchDocuments, fetchEntities, fetchRelationships } from './api';
import DocumentsView from './views/DocumentsView';
import DocumentDetailView from './views/DocumentDetailView';
import ReconciliationHub from './views/ReconciliationHub';
import EntitiesView from './views/EntitiesView';
import SearchView from './views/SearchView';

/** IntersectionObserver hook — adds 'visible' class to trigger CSS fade-up */
function useScrollReveal(ref, threshold = 0.1) {
  useEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const items = el.querySelectorAll('.fade-up');
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('visible');
            observer.unobserve(e.target);
          }
        });
      },
      { threshold }
    );
    items.forEach((item) => observer.observe(item));
    return () => observer.disconnect();
  }, [ref, threshold]);
}

export default function App() {
  const [activeTab, setActiveTab] = useState('documents');
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [backendHealth, setBackendHealth] = useState(null);
  const [stats, setStats] = useState({ documents: 0, facts: 0, entities: 0, relationships: 0 });
  const [activeIngestionDoc, setActiveIngestionDoc] = useState(null);
  const metricsRef = useRef(null);

  useScrollReveal(metricsRef);

  const loadHealthAndStats = async () => {
    try {
      const health = await fetchHealth();
      setBackendHealth(health);
    } catch {
      setBackendHealth({ status: 'offline' });
    }

    try {
      const [docs, ents, rels] = await Promise.all([
        fetchDocuments().catch(() => []),
        fetchEntities().catch(() => []),
        fetchRelationships(null, 200).catch(() => []),
      ]);
      const totalFacts = (docs || []).reduce((acc, d) => acc + (d.facts_count || 0), 0);
      setStats({
        documents: (docs || []).length,
        facts: totalFacts,
        entities: (ents || []).length,
        relationships: (rels || []).length,
      });

      // Find if any document is currently in active ingestion / reconciliation
      const processing = (docs || []).find((d) => d.status !== 'done' && d.status !== 'failed');
      setActiveIngestionDoc(processing || null);
    } catch (e) {
      console.error('Stats loading error:', e);
    }
  };

  useEffect(() => {
    loadHealthAndStats();
    const interval = setInterval(loadHealthAndStats, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectDoc = (docId) => {
    setSelectedDocId(docId);
    setActiveTab('document-detail');
  };

  const METRICS = [
    { label: 'Ingested PDFs',         value: stats.documents,     icon: <FileText size={20} />,    color: 'peach' },
    { label: 'Grounded facts',         value: stats.facts,         icon: <Search size={20} />,      color: 'sky' },
    { label: 'Resolved entities',      value: stats.entities,      icon: <Building2 size={20} />,   color: 'lavender' },
    { label: 'Cross-doc relationships',value: stats.relationships,  icon: <GitCompare size={20} />,  color: 'amber' },
  ];

  return (
    <div className="app-container">
      {/* ── Top Nav ── */}
      <header className="navbar">
        <div className="navbar-inner">
          <a href="#" className="brand" onClick={(e) => { e.preventDefault(); setActiveTab('documents'); }}>
            <div className="brand-icon"><Map size={18} /></div>
            <div className="brand-text"><h1>KnowWhere</h1></div>
          </a>

          <nav className="nav-tabs">
            <button
              className={`nav-tab ${activeTab === 'documents' || activeTab === 'document-detail' ? 'active' : ''}`}
              onClick={() => setActiveTab('documents')}
              id="nav-tab-documents"
            >
              <FileText size={15} /> Documents
            </button>
            <button
              className={`nav-tab ${activeTab === 'reconciliation' ? 'active' : ''}`}
              onClick={() => setActiveTab('reconciliation')}
              id="nav-tab-reconciliation"
            >
              <GitCompare size={15} /> Reconciliation
              {stats.relationships > 0 && (
                <span className="tab-badge">{stats.relationships}</span>
              )}
            </button>
            <button
              className={`nav-tab ${activeTab === 'entities' ? 'active' : ''}`}
              onClick={() => setActiveTab('entities')}
              id="nav-tab-entities"
            >
              <Building2 size={15} /> Entities
            </button>
            <button
              className={`nav-tab ${activeTab === 'search' ? 'active' : ''}`}
              onClick={() => setActiveTab('search')}
              id="nav-tab-search"
            >
              <Search size={15} /> Search
            </button>
          </nav>

          <div className="nav-status">
            {backendHealth?.status === 'ok' ? (
              <div className="status-pill" title="Connected to FastAPI + Supabase">
                <span className="status-dot" /> System online
              </div>
            ) : (
              <div className="status-pill offline" title="Cannot reach backend API">
                <span className="status-dot" /> Connecting…
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="main-content">
        {/* Global Active Task Banner if document is processing */}
        {activeIngestionDoc && (
          <div className="global-task-banner">
            <div className="global-task-left">
              <span className="global-task-badge">
                <RefreshCw size={13} className="animate-spin" />
                Background Ingestion Active
              </span>
              <span className="global-task-title">
                {activeIngestionDoc.title || 'Document'}
              </span>
              <span className="global-task-status-text">
                • {activeIngestionDoc.status}
              </span>
            </div>

            <div className="global-task-right">
              <span className="global-task-hint">
                Running asynchronously • Facts committed in real-time
              </span>
              {activeTab !== 'reconciliation' && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setActiveTab('reconciliation')}
                >
                  Explore Reconciliation &rarr;
                </button>
              )}
            </div>
          </div>
        )}

        {/* Metrics banner — fade-up on scroll */}
        <div className="metrics-banner" ref={metricsRef}>
          {METRICS.map((m) => (
            <div key={m.label} className="metric-card fade-up">
              <div className={`metric-icon ${m.color}`}>{m.icon}</div>
              <div>
                <div className="metric-value">{m.value}</div>
                <div className="metric-label">{m.label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Views */}
        {activeTab === 'documents' && (
          <DocumentsView
            onSelectDocument={handleSelectDoc}
            onNavigateReconcile={() => setActiveTab('reconciliation')}
          />
        )}
        {activeTab === 'document-detail' && (
          <DocumentDetailView docId={selectedDocId} onBack={() => setActiveTab('documents')} />
        )}
        {activeTab === 'reconciliation' && <ReconciliationHub />}
        {activeTab === 'entities'       && <EntitiesView />}
        {activeTab === 'search'         && <SearchView />}
      </main>
    </div>
  );
}
