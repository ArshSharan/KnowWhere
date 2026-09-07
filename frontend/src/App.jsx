import React, { useState, useEffect } from 'react';
import { 
  FileText, GitCompare, Building2, Search, Database, Layers, 
  Activity, CheckCircle2, ShieldCheck, Cpu 
} from 'lucide-react';
import { fetchHealth, fetchDocuments, fetchEntities, fetchRelationships } from './api';
import DocumentsView from './views/DocumentsView';
import DocumentDetailView from './views/DocumentDetailView';
import ReconciliationHub from './views/ReconciliationHub';
import EntitiesView from './views/EntitiesView';
import SearchView from './views/SearchView';

export default function App() {
  const [activeTab, setActiveTab] = useState('documents');
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [backendHealth, setBackendHealth] = useState(null);
  const [stats, setStats] = useState({
    documents: 0,
    facts: 0,
    entities: 0,
    relationships: 0,
  });

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
        fetchRelationships().catch(() => []),
      ]);

      const totalFacts = docs.reduce((acc, d) => acc + (d.facts_count || 0), 0);
      setStats({
        documents: docs.length,
        facts: totalFacts,
        entities: ents.length,
        relationships: rels.length,
      });
    } catch (e) {
      console.error('Stats loading error:', e);
    }
  };

  useEffect(() => {
    loadHealthAndStats();
    const interval = setInterval(loadHealthAndStats, 8000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectDoc = (docId) => {
    setSelectedDocId(docId);
    setActiveTab('document-detail');
  };

  return (
    <div className="app-container">
      {/* Navbar */}
      <header className="navbar">
        <div className="navbar-inner">
          <a href="#" className="brand" onClick={() => setActiveTab('documents')}>
            <div className="brand-icon">
              <Database size={20} />
            </div>
            <div className="brand-text">
              <h1>KnowWhere</h1>
              <span>Fact Knowledge Layer</span>
            </div>
          </a>

          {/* Navigation Tabs */}
          <nav className="nav-tabs">
            <button
              className={`nav-tab ${activeTab === 'documents' || activeTab === 'document-detail' ? 'active' : ''}`}
              onClick={() => setActiveTab('documents')}
              id="nav-tab-documents"
            >
              <FileText size={16} /> Documents
            </button>
            <button
              className={`nav-tab ${activeTab === 'reconciliation' ? 'active' : ''}`}
              onClick={() => setActiveTab('reconciliation')}
              id="nav-tab-reconciliation"
            >
              <GitCompare size={16} /> Reconciliation Hub
              {stats.relationships > 0 && (
                <span style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem', borderRadius: '6px', background: 'rgba(6, 182, 212, 0.25)', color: 'var(--accent-cyan)' }}>
                  {stats.relationships}
                </span>
              )}
            </button>
            <button
              className={`nav-tab ${activeTab === 'entities' ? 'active' : ''}`}
              onClick={() => setActiveTab('entities')}
              id="nav-tab-entities"
            >
              <Building2 size={16} /> Entities
            </button>
            <button
              className={`nav-tab ${activeTab === 'search' ? 'active' : ''}`}
              onClick={() => setActiveTab('search')}
              id="nav-tab-search"
            >
              <Search size={16} /> Semantic Search
            </button>
          </nav>

          {/* Backend Status */}
          <div className="nav-status">
            {backendHealth?.status === 'ok' ? (
              <div className="status-pill" title="Connected to FastAPI + Supabase">
                <span className="status-dot"></span>
                <span>System Online</span>
              </div>
            ) : (
              <div className="status-pill offline" title="Cannot reach backend API">
                <span className="status-dot"></span>
                <span>Connecting...</span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="main-content">
        {/* Top Metrics Banner */}
        <div className="metrics-banner">
          <div className="metric-card">
            <div className="metric-icon blue">
              <FileText size={22} />
            </div>
            <div className="metric-info">
              <div className="metric-value">{stats.documents}</div>
              <div className="metric-label">Ingested PDFs</div>
            </div>
          </div>

          <div className="metric-card">
            <div className="metric-icon green">
              <ShieldCheck size={22} />
            </div>
            <div className="metric-info">
              <div className="metric-value">{stats.facts}</div>
              <div className="metric-label">Grounded Facts</div>
            </div>
          </div>

          <div className="metric-card">
            <div className="metric-icon purple">
              <Building2 size={22} />
            </div>
            <div className="metric-info">
              <div className="metric-value">{stats.entities}</div>
              <div className="metric-label">Resolved Entities</div>
            </div>
          </div>

          <div className="metric-card">
            <div className="metric-icon amber">
              <GitCompare size={22} />
            </div>
            <div className="metric-info">
              <div className="metric-value">{stats.relationships}</div>
              <div className="metric-label">Reconciled Relations</div>
            </div>
          </div>
        </div>

        {/* View Switcher */}
        {activeTab === 'documents' && (
          <DocumentsView
            onSelectDocument={handleSelectDoc}
            onNavigateReconcile={() => setActiveTab('reconciliation')}
          />
        )}

        {activeTab === 'document-detail' && (
          <DocumentDetailView
            docId={selectedDocId}
            onBack={() => setActiveTab('documents')}
          />
        )}

        {activeTab === 'reconciliation' && <ReconciliationHub />}

        {activeTab === 'entities' && <EntitiesView />}

        {activeTab === 'search' && <SearchView />}
      </main>
    </div>
  );
}
