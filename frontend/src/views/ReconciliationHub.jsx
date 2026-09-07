import React, { useState, useEffect } from 'react';
import { GitCompare, CheckCircle2, XCircle, HelpCircle, FileText, Info, RefreshCw, Quote, ArrowRight } from 'lucide-react';
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

  useEffect(() => {
    loadRelationships();
  }, []);

  const counts = {
    all: relationships.length,
    corroborates: relationships.filter((r) => r.relationship === 'corroborates').length,
    contradicts: relationships.filter((r) => r.relationship === 'contradicts').length,
    reconciled_by_context: relationships.filter((r) => r.relationship === 'reconciled_by_context').length,
  };

  const filtered = relationships.filter((r) => {
    if (filter === 'all') return true;
    return r.relationship === filter;
  });

  const getBadgeIcon = (type) => {
    switch (type) {
      case 'corroborates':
        return <CheckCircle2 size={16} />;
      case 'contradicts':
        return <XCircle size={16} />;
      case 'reconciled_by_context':
        return <HelpCircle size={16} />;
      default:
        return <Info size={16} />;
    }
  };

  const getBadgeLabel = (type) => {
    switch (type) {
      case 'corroborates':
        return 'Corroborates (Agreement)';
      case 'contradicts':
        return 'Contradiction (Conflict)';
      case 'reconciled_by_context':
        return 'Reconciled by Context';
      default:
        return type;
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="section-header">
        <div className="section-title">
          <h2>Reconciliation Hub — The 4 Demo Cases</h2>
          <p>
            Cross-document LLM reconciliation evaluating candidate fact pairs with explainable reasoning traces
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadRelationships} id="btn-refresh-rel">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Filter Tabs & Counts */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', marginBottom: '1.75rem' }}>
        <button
          className={`btn btn-sm ${filter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setFilter('all')}
        >
          All Relationships ({counts.all})
        </button>
        <button
          className={`btn btn-sm ${filter === 'corroborates' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setFilter('corroborates')}
          style={{ borderColor: filter === 'corroborates' ? 'transparent' : 'rgba(16, 185, 129, 0.4)' }}
        >
          <CheckCircle2 size={14} color="#10b981" /> Corroborates ({counts.corroborates})
        </button>
        <button
          className={`btn btn-sm ${filter === 'contradicts' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setFilter('contradicts')}
          style={{ borderColor: filter === 'contradicts' ? 'transparent' : 'rgba(244, 63, 94, 0.4)' }}
        >
          <XCircle size={14} color="#f43f5e" /> Contradictions ({counts.contradicts})
        </button>
        <button
          className={`btn btn-sm ${filter === 'reconciled_by_context' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setFilter('reconciled_by_context')}
          style={{ borderColor: filter === 'reconciled_by_context' ? 'transparent' : 'rgba(245, 158, 11, 0.4)' }}
        >
          <HelpCircle size={14} color="#f59e0b" /> Reconciled by Context ({counts.reconciled_by_context})
        </button>
      </div>

      {/* Relationships Feed */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
          Loading cross-document reconciliation edges...
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3.5rem', background: 'var(--bg-card)', borderRadius: '16px', border: '1px solid var(--border-subtle)' }}>
          <GitCompare size={40} color="var(--text-muted)" style={{ margin: '0 auto 1rem' }} />
          <h3>No {filter !== 'all' ? filter.replace(/_/g, ' ') : ''} relationships found yet</h3>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem', maxWidth: '500px', margin: '0.5rem auto 0' }}>
            Reconciliation executes automatically across documents after two or more PDFs are ingested.
            You can also trigger manual reconciliation on the Documents page.
          </p>
        </div>
      ) : (
        <div className="reconciliation-grid">
          {filtered.map((rel) => (
            <div key={rel.id} className={`rel-card ${rel.relationship}`} id={`rel-card-${rel.id}`}>
              {/* Header Badge */}
              <div className="rel-header">
                <span className={`rel-badge ${rel.relationship}`}>
                  {getBadgeIcon(rel.relationship)}
                  {getBadgeLabel(rel.relationship)}
                </span>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  {rel.basis && rel.basis !== 'none' && (
                    <span className="badge-tag" style={{ color: 'var(--accent-cyan)', borderColor: 'var(--border-accent)' }}>
                      Basis: {rel.basis.replace(/_/g, ' ')}
                    </span>
                  )}
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Confidence: {(rel.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* Side-by-Side Comparison Box */}
              <div className="rel-comparison-box">
                {/* Fact A */}
                <div className="rel-fact-pane">
                  <div className="rel-fact-doc">
                    <FileText size={13} />
                    <span>{rel.fact_a_doc_title || 'Document A'}</span>
                    <span>• P. {rel.fact_a_page || '?'}</span>
                  </div>
                  <div className="rel-fact-entity">{rel.fact_a_entity}</div>
                  <div className="rel-fact-attr">{rel.fact_a_attribute}</div>
                  <div className="rel-fact-val">
                    {rel.fact_a_value} {rel.fact_a_unit}
                  </div>
                  {rel.fact_a_quote && (
                    <div
                      style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '0.25rem', cursor: 'pointer', textDecoration: 'underline' }}
                      onClick={() => setSelectedEvidenceFact({
                        attribute: rel.fact_a_attribute,
                        entity: rel.fact_a_entity,
                        value: rel.fact_a_value,
                        unit: rel.fact_a_unit,
                        verbatim_quote: rel.fact_a_quote,
                        page_number: rel.fact_a_page,
                        evidence_confidence: 'high',
                        document_id: rel.fact_a_doc_id,
                      })}
                    >
                      "{rel.fact_a_quote.slice(0, 75)}..."
                    </div>
                  )}
                </div>

                {/* VS Divider */}
                <div className="rel-divider-icon">
                  <GitCompare size={18} />
                </div>

                {/* Fact B */}
                <div className="rel-fact-pane">
                  <div className="rel-fact-doc">
                    <FileText size={13} />
                    <span>{rel.fact_b_doc_title || 'Document B'}</span>
                    <span>• P. {rel.fact_b_page || '?'}</span>
                  </div>
                  <div className="rel-fact-entity">{rel.fact_b_entity}</div>
                  <div className="rel-fact-attr">{rel.fact_b_attribute}</div>
                  <div className="rel-fact-val">
                    {rel.fact_b_value} {rel.fact_b_unit}
                  </div>
                  {rel.fact_b_quote && (
                    <div
                      style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '0.25rem', cursor: 'pointer', textDecoration: 'underline' }}
                      onClick={() => setSelectedEvidenceFact({
                        attribute: rel.fact_b_attribute,
                        entity: rel.fact_b_entity,
                        value: rel.fact_b_value,
                        unit: rel.fact_b_unit,
                        verbatim_quote: rel.fact_b_quote,
                        page_number: rel.fact_b_page,
                        evidence_confidence: 'high',
                        document_id: rel.fact_b_doc_id,
                      })}
                    >
                      "{rel.fact_b_quote.slice(0, 75)}..."
                    </div>
                  )}
                </div>
              </div>

              {/* Natural Language Explanation Trace */}
              <div className="rel-explanation">
                <strong>Reconciliation Reasoning: </strong>
                {rel.explanation}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Evidence Drawer for quote inspect */}
      <EvidenceDrawer fact={selectedEvidenceFact} onClose={() => setSelectedEvidenceFact(null)} />
    </div>
  );
}
