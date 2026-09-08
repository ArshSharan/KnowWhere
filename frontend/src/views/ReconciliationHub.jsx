import React, { useState, useEffect } from 'react';
import {
  GitCompare, CheckCircle2, XCircle, HelpCircle,
  FileText, RefreshCw,
} from 'lucide-react';

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
import { fetchRelationships } from '../api';
import EvidenceDrawer from '../components/EvidenceDrawer';

export default function ReconciliationHub() {
  const [relationships, setRelationships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [selectedEvidenceFact, setSelectedEvidenceFact] = useState(null);

  const loadRelationships = async () => {
    setLoading(true);
    try {
      const data = await fetchRelationships();
      setRelationships(data);
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

  const filtered = relationships.filter((r) =>
    filter === 'all' ? true : r.relationship === filter
  );

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

      {/* Filter pills */}
      <div className="filter-row">
        <button
          className={`filter-pill ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All ({counts.all})
        </button>
        <button
          className={`filter-pill ${filter === 'corroborates' ? 'active' : ''}`}
          onClick={() => setFilter('corroborates')}
          style={filter !== 'corroborates' ? { borderColor: 'rgba(30,142,90,0.3)', color: 'var(--rel-corroborates-fg)' } : {}}
        >
          <CheckCircle2 size={13} /> Corroborates ({counts.corroborates})
        </button>
        <button
          className={`filter-pill ${filter === 'contradicts' ? 'active' : ''}`}
          onClick={() => setFilter('contradicts')}
          style={filter !== 'contradicts' ? { borderColor: 'rgba(217,96,62,0.3)', color: 'var(--rel-contradicts-fg)' } : {}}
        >
          <XCircle size={13} /> Contradicts ({counts.contradicts})
        </button>
        <button
          className={`filter-pill ${filter === 'reconciled_by_context' ? 'active' : ''}`}
          onClick={() => setFilter('reconciled_by_context')}
          style={filter !== 'reconciled_by_context' ? { borderColor: 'rgba(184,132,42,0.3)', color: 'var(--rel-reconciled-fg)' } : {}}
        >
          <HelpCircle size={13} /> Reconciled by context ({counts.reconciled_by_context})
        </button>
      </div>

      {/* Feed */}
      {loading ? (
        <div className="reconciliation-grid">
          <SkeletonRelCard /><SkeletonRelCard />
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><GitCompare size={22} /></div>
          <h3>No {filter !== 'all' ? `"${getBadgeLabel(filter)}"` : ''} relationships yet</h3>
          <p>
            Reconciliation runs automatically after two or more PDFs are ingested.
            You can also trigger it manually from the Documents page.
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
