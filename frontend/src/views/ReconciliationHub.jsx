import React, { useState, useEffect } from 'react';
import {
  GitCompare, CheckCircle2, XCircle, HelpCircle,
  FileText, RefreshCw, ExternalLink, Search, Filter,
} from 'lucide-react';
import { fetchRelationships, getDocumentFileUrl } from '../api';
import EvidenceDrawer from '../components/EvidenceDrawer';

function SkeletonRelCard() {
  return (
    <div className="skeleton-rel-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="skeleton skeleton-text" style={{ width: 100, height: 22, borderRadius: 9999 }} />
        <div className="skeleton skeleton-text sm" style={{ width: 80 }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 16, padding: '12px', background: 'var(--bg-surface)', borderRadius: 8 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div className="skeleton skeleton-text sm" style={{ width: '60%' }} />
          <div className="skeleton skeleton-text" style={{ width: '80%' }} />
          <div className="skeleton skeleton-text lg" style={{ width: '40%' }} />
        </div>
        <div className="skeleton" style={{ width: 32, height: 32, borderRadius: '50%', flexShrink: 0 }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div className="skeleton skeleton-text sm" style={{ width: '60%' }} />
          <div className="skeleton skeleton-text" style={{ width: '80%' }} />
          <div className="skeleton skeleton-text lg" style={{ width: '40%' }} />
        </div>
      </div>
      <div style={{ borderLeft: '2px solid var(--border-subtle)', paddingLeft: 12 }}>
        <div className="skeleton skeleton-text sm" style={{ width: '85%', marginBottom: 6 }} />
        <div className="skeleton skeleton-text sm" style={{ width: '60%' }} />
      </div>
    </div>
  );
}

export default function ReconciliationHub() {
  const [relationships, setRelationships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEvidenceFact, setSelectedEvidenceFact] = useState(null);

  const loadRelationships = async () => {
    setLoading(true);
    try {
      // Fetch global feed (limit 200) + specifically fetch contradicts and corroborates to guarantee no truncations
      const [allData, corrobData, contraData] = await Promise.all([
        fetchRelationships(null, 200).catch(() => []),
        fetchRelationships('corroborates', 200).catch(() => []),
        fetchRelationships('contradicts', 200).catch(() => []),
      ]);

      const map = new Map();
      allData.forEach((r) => map.set(r.id, r));
      corrobData.forEach((r) => map.set(r.id, r));
      contraData.forEach((r) => map.set(r.id, r));

      setRelationships(Array.from(map.values()));
    } catch (err) {
      console.error('Failed to load relationships:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadRelationships(); }, []);

  const counts = {
    all: relationships.length,
    corroborates: relationships.filter((r) => r.relationship === 'corroborates').length,
    contradicts: relationships.filter((r) => r.relationship === 'contradicts').length,
    reconciled_by_context: relationships.filter((r) => r.relationship === 'reconciled_by_context').length,
  };

  const filtered = relationships.filter((r) => {
    const matchesCategory = filter === 'all' ? true : r.relationship === filter;
    if (!matchesCategory) return false;

    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      (r.fact_a_entity && r.fact_a_entity.toLowerCase().includes(q)) ||
      (r.fact_b_entity && r.fact_b_entity.toLowerCase().includes(q)) ||
      (r.fact_a_attribute && r.fact_a_attribute.toLowerCase().includes(q)) ||
      (r.fact_b_attribute && r.fact_b_attribute.toLowerCase().includes(q)) ||
      (r.fact_a_value && String(r.fact_a_value).toLowerCase().includes(q)) ||
      (r.fact_b_value && String(r.fact_b_value).toLowerCase().includes(q)) ||
      (r.explanation && r.explanation.toLowerCase().includes(q))
    );
  });

  const getBadgeIcon = (type) => {
    switch (type) {
      case 'corroborates':        return <CheckCircle2 size={14} />;
      case 'contradicts':         return <XCircle size={14} />;
      case 'reconciled_by_context': return <HelpCircle size={14} />;
      default:                    return <GitCompare size={14} />;
    }
  };

  const getBadgeLabel = (type) => {
    switch (type) {
      case 'corroborates':          return 'Corroborates';
      case 'contradicts':           return 'Contradicts';
      case 'reconciled_by_context': return 'Reconciled by context';
      default:                      return type;
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="section-header">
        <div className="section-title">
          <h2>Reconciliation hub</h2>
          <p>Cross-document fact pairs evaluated with explainable reasoning</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadRelationships} id="btn-refresh-rel">
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        {/* Filter pills */}
        <div className="filter-row" style={{ marginBottom: 0 }}>
          <button
            className={`filter-pill ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
            id="filter-all"
          >
            All ({counts.all})
          </button>
          <button
            className={`filter-pill ${filter === 'corroborates' ? 'active' : ''}`}
            onClick={() => setFilter('corroborates')}
            style={filter !== 'corroborates' ? { borderColor: 'rgba(30,142,90,0.3)', color: 'var(--rel-corroborates-fg)' } : {}}
            id="filter-corroborates"
          >
            <CheckCircle2 size={13} /> Corroborates ({counts.corroborates})
          </button>
          <button
            className={`filter-pill ${filter === 'contradicts' ? 'active' : ''}`}
            onClick={() => setFilter('contradicts')}
            style={filter !== 'contradicts' ? { borderColor: 'rgba(217,96,62,0.3)', color: 'var(--rel-contradicts-fg)' } : {}}
            id="filter-contradicts"
          >
            <XCircle size={13} /> Contradicts ({counts.contradicts})
          </button>
          <button
            className={`filter-pill ${filter === 'reconciled_by_context' ? 'active' : ''}`}
            onClick={() => setFilter('reconciled_by_context')}
            style={filter !== 'reconciled_by_context' ? { borderColor: 'rgba(184,132,42,0.3)', color: 'var(--rel-reconciled-fg)' } : {}}
            id="filter-reconciled"
          >
            <HelpCircle size={13} /> Reconciled by context ({counts.reconciled_by_context})
          </button>
        </div>

        {/* Search inside relationships */}
        <div style={{ position: 'relative', flex: 1, minWidth: 220, maxWidth: 360 }}>
          <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
          <input
            type="text"
            className="input-field"
            placeholder="Search reconciled pairs…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: '2.25rem', height: 36, fontSize: '0.8125rem' }}
          />
        </div>
      </div>

      {/* Feed */}
      {loading ? (
        <div className="reconciliation-grid">
          <SkeletonRelCard /><SkeletonRelCard />
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><GitCompare size={22} /></div>
          <h3>No {filter !== 'all' ? `"${getBadgeLabel(filter)}"` : ''} relationships match</h3>
          <p>
            {searchQuery ? `No pairs found matching "${searchQuery}". Try clearing the search.` :
            'Reconciliation runs automatically as documents are ingested. You can also trigger it manually from the Documents page.'}
          </p>
        </div>
      ) : (
        <div className="reconciliation-grid">
          {filtered.map((rel) => (
            <div
              key={rel.id}
              className={`rel-card ${rel.relationship}`}
              id={`rel-card-${rel.id}`}
            >
              {/* Header */}
              <div className="rel-header">
                <span className={`rel-badge ${rel.relationship}`}>
                  {getBadgeIcon(rel.relationship)}
                  {getBadgeLabel(rel.relationship)}
                </span>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {rel.basis && rel.basis !== 'none' && (
                    <span className="badge-tag">{rel.basis.replace(/_/g, ' ')}</span>
                  )}
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {(rel.confidence * 100).toFixed(0)}% confidence
                  </span>
                </div>
              </div>

              {/* Side-by-side facts */}
              <div className="rel-comparison-box">
                {/* Fact A */}
                <div className="rel-fact-pane">
                  <div className="rel-fact-doc">
                    <FileText size={12} />
                    <span>{rel.fact_a_doc_title || 'Document A'}</span>
                    <span>· p.{rel.fact_a_page || '?'}</span>
                    {rel.fact_a_doc_id && (
                      <a
                        href={`${getDocumentFileUrl(rel.fact_a_doc_id)}#page=${rel.fact_a_page || 1}`}
                        target="_blank"
                        rel="noreferrer"
                        className="rel-doc-pdf-link"
                        title={`Open source PDF at page ${rel.fact_a_page || 1}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink size={11} /> PDF
                      </a>
                    )}
                  </div>
                  <div className="rel-fact-entity">{rel.fact_a_entity}</div>
                  <div className="rel-fact-attr">{rel.fact_a_attribute}</div>
                  <div className="rel-fact-val">
                    {rel.fact_a_value} {rel.fact_a_unit}
                  </div>
                  {rel.fact_a_quote && (
                    <div
                      className="rel-fact-quote"
                      onClick={() =>
                        setSelectedEvidenceFact({
                          attribute: rel.fact_a_attribute,
                          entity: rel.fact_a_entity,
                          value: rel.fact_a_value,
                          unit: rel.fact_a_unit,
                          verbatim_quote: rel.fact_a_quote,
                          page_number: rel.fact_a_page,
                          evidence_confidence: 'high',
                          document_id: rel.fact_a_doc_id,
                        })
                      }
                    >
                      "{rel.fact_a_quote.slice(0, 80)}…"
                    </div>
                  )}
                </div>

                {/* VS divider */}
                <div className="rel-divider-icon">
                  <GitCompare size={15} />
                </div>

                {/* Fact B */}
                <div className="rel-fact-pane">
                  <div className="rel-fact-doc">
                    <FileText size={12} />
                    <span>{rel.fact_b_doc_title || 'Document B'}</span>
                    <span>· p.{rel.fact_b_page || '?'}</span>
                    {rel.fact_b_doc_id && (
                      <a
                        href={`${getDocumentFileUrl(rel.fact_b_doc_id)}#page=${rel.fact_b_page || 1}`}
                        target="_blank"
                        rel="noreferrer"
                        className="rel-doc-pdf-link"
                        title={`Open source PDF at page ${rel.fact_b_page || 1}`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink size={11} /> PDF
                      </a>
                    )}
                  </div>
                  <div className="rel-fact-entity">{rel.fact_b_entity}</div>
                  <div className="rel-fact-attr">{rel.fact_b_attribute}</div>
                  <div className="rel-fact-val">
                    {rel.fact_b_value} {rel.fact_b_unit}
                  </div>
                  {rel.fact_b_quote && (
                    <div
                      className="rel-fact-quote"
                      onClick={() =>
                        setSelectedEvidenceFact({
                          attribute: rel.fact_b_attribute,
                          entity: rel.fact_b_entity,
                          value: rel.fact_b_value,
                          unit: rel.fact_b_unit,
                          verbatim_quote: rel.fact_b_quote,
                          page_number: rel.fact_b_page,
                          evidence_confidence: 'high',
                          document_id: rel.fact_b_doc_id,
                        })
                      }
                    >
                      "{rel.fact_b_quote.slice(0, 80)}…"
                    </div>
                  )}
                </div>
              </div>

              {/* Reasoning trace */}
              <div className="rel-explanation">
                <strong>Reasoning: </strong>
                {rel.explanation}
              </div>
            </div>
          ))}
        </div>
      )}

      <EvidenceDrawer
        fact={selectedEvidenceFact}
        onClose={() => setSelectedEvidenceFact(null)}
      />
    </div>
  );
}
