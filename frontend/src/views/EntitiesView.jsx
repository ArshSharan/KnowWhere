import React, { useState, useEffect, useRef } from 'react';
import { Building2, Tag, RefreshCw, ChevronRight, X, ExternalLink, FileText } from 'lucide-react';
import { fetchEntities, fetchEntity } from '../api';
import EvidenceDrawer from '../components/EvidenceDrawer';

function SkeletonEntityList() {
  return Array.from({ length: 4 }).map((_, i) => (
    <div key={i} className="skeleton-entity-item">
      <div className="skeleton skeleton-text" style={{ width: '65%' }} />
      <div className="skeleton skeleton-text sm" style={{ width: '40%' }} />
    </div>
  ));
}

function SkeletonEntityPanel() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="skeleton skeleton-text sm" style={{ width: 100, height: 22, borderRadius: 9999 }} />
      <div className="skeleton skeleton-text xl" style={{ width: '60%' }} />
      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        {[60, 80, 55].map((w, i) => <div key={i} className="skeleton skeleton-text sm" style={{ width: w, borderRadius: 9999 }} />)}
      </div>
      <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} style={{ display: 'flex', gap: 16 }}>
            <div className="skeleton skeleton-text" style={{ width: '25%' }} />
            <div className="skeleton skeleton-text lg" style={{ width: '20%' }} />
            <div className="skeleton skeleton-text sm" style={{ width: '10%', borderRadius: 9999 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Inline cell-expand modal for a fact row */
function FactDetailModal({ fact, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  useEffect(() => {
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onClose]);

  if (!fact) return null;

  return (
    <div className="fact-detail-overlay">
      <div className="fact-detail-modal" ref={ref}>
        <div className="fact-detail-header">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--text-muted)', fontWeight: 600 }}>Fact detail</span>
            <h4 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>{fact.attribute}</h4>
          </div>
          <button className="fact-detail-close" onClick={onClose}><X size={15} /></button>
        </div>

        <div className="fact-detail-body">
          {/* Value */}
          <div className="fact-detail-row">
            <span className="fact-detail-label">Value</span>
            <span className="fact-detail-value-text">
              {fact.value}
              {fact.unit && <span className="fact-detail-unit"> {fact.unit}</span>}
            </span>
          </div>

          {/* Period */}
          {(fact.fiscal_year || fact.period_start || fact.period_end) && (
            <div className="fact-detail-row">
              <span className="fact-detail-label">Period</span>
              <span className="fact-detail-value-text">
                {fact.fiscal_year || `${fact.period_start || ''} – ${fact.period_end || ''}`}
              </span>
            </div>
          )}

          {/* Confidence */}
          <div className="fact-detail-row">
            <span className="fact-detail-label">Confidence</span>
            <span className="fact-detail-value-text">{((fact.confidence || 1) * 100).toFixed(0)}%</span>
          </div>

          {/* Evidence quote */}
          {fact.evidence?.verbatim_quote && (
            <div className="fact-detail-evidence-box">
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                <FileText size={11} /> Source quote · p.{fact.evidence?.page_number}
              </div>
              <blockquote className="fact-detail-quote">
                "{fact.evidence.verbatim_quote}"
              </blockquote>
            </div>
          )}

          {/* Qualifiers */}
          {fact.qualifiers && Object.keys(fact.qualifiers).length > 0 && (
            <div className="fact-detail-row" style={{ flexDirection: 'column', gap: 6 }}>
              <span className="fact-detail-label">Qualifiers</span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 2 }}>
                {Object.entries(fact.qualifiers).map(([k, v]) => (
                  <span key={k} className="badge-tag" style={{ fontFamily: 'var(--font-mono)' }}>
                    {k}: {v}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function EntitiesView() {
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEntityId, setSelectedEntityId] = useState(null);
  const [entityDetails, setEntityDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [expandedFact, setExpandedFact] = useState(null);

  const loadEntities = async () => {
    setLoading(true);
    try {
      const data = await fetchEntities();
      setEntities(data);
      if (data.length > 0 && !selectedEntityId) {
        handleSelectEntity(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load entities:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectEntity = async (entityId) => {
    setSelectedEntityId(entityId);
    setLoadingDetails(true);
    setExpandedFact(null);
    try {
      const data = await fetchEntity(entityId);
      setEntityDetails(data);
    } catch (err) {
      console.error('Failed to load entity details:', err);
    } finally {
      setLoadingDetails(false);
    }
  };

  useEffect(() => { loadEntities(); }, []);

  return (
    <div>
      {/* Header */}
      <div className="section-header">
        <div className="section-title">
          <h2>Entities</h2>
          <p>Canonical entities resolved across documents, with merged aliases and cross-document facts</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadEntities} id="btn-refresh-entities">
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="entities-layout">
          <div className="entity-list"><SkeletonEntityList /></div>
          <div className="entity-detail-panel"><SkeletonEntityPanel /></div>
        </div>
      ) : entities.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><Building2 size={22} /></div>
          <h3>No entities detected yet</h3>
          <p>Entities are automatically resolved when PDF documents are ingested.</p>
        </div>
      ) : (
        <div className="entities-layout">
          {/* Left pane — entity list */}
          <div className="entity-list">
            {entities.map((ent) => {
              const isSelected = ent.id === selectedEntityId;
              return (
                <div
                  key={ent.id}
                  className={`entity-list-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleSelectEntity(ent.id)}
                  id={`entity-item-${ent.id}`}
                >
                  <div>
                    <div className="entity-list-item-name">{ent.canonical_name}</div>
                    <div className="entity-list-item-meta">
                      {ent.fact_count} facts · {ent.alias_count} aliases
                    </div>
                  </div>
                  <ChevronRight size={15} color={isSelected ? 'var(--brand-green)' : 'var(--text-muted)'} />
                </div>
              );
            })}
          </div>

          {/* Right pane — entity details */}
          <div className="entity-detail-panel">
            {loadingDetails ? (
              <SkeletonEntityPanel />
            ) : !entityDetails ? (
              <div className="loading-state">Select an entity to view cross-document knowledge.</div>
            ) : (
              <div>
                {/* Entity header */}
                <div style={{ paddingBottom: 20, marginBottom: 20, borderBottom: '1px solid var(--border-subtle)' }}>
                  <span className="badge-tag" style={{ color: 'var(--brand-green)', borderColor: 'rgba(30,142,90,0.25)', background: 'var(--brand-green-bg)', marginBottom: 6, display: 'inline-flex' }}>
                    Canonical entity
                  </span>
                  <h3 style={{ fontSize: '1.375rem', fontWeight: 700, letterSpacing: '-0.01em', color: 'var(--text-primary)', marginTop: 6 }}>
                    {entityDetails.canonical_name}
                  </h3>

                  {entityDetails.aliases && entityDetails.aliases.length > 0 && (
                    <div style={{ marginTop: 10, display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap', gap: 6 }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4, marginTop: 2, flexShrink: 0 }}>
                        <Tag size={11} /> Aliases:
                      </span>
                      {entityDetails.aliases.map((alias) => (
                        <span
                          key={alias}
                          className="badge-tag entity-alias-pill"
                          title={alias}
                        >
                          {alias.length > 40 ? alias.slice(0, 38) + '…' : alias}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Facts table */}
                <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, marginBottom: 12, color: 'var(--text-primary)' }}>
                  Cross-document facts ({entityDetails.facts?.length || 0})
                </h4>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 14, marginTop: -8 }}>
                  Click any row to inspect the full value and evidence quote.
                </p>

                <div className="facts-table-wrap">
                  <table className="facts-table">
                    <thead>
                      <tr>
                        <th style={{ width: '28%' }}>Attribute</th>
                        <th style={{ width: '30%' }}>Value</th>
                        <th style={{ width: '14%' }}>Period</th>
                        <th style={{ width: '8%' }}>Page</th>
                        <th style={{ width: '20%' }}>Quote preview</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entityDetails.facts?.map((fact) => (
                        <tr
                          key={fact.id}
                          onClick={() => setExpandedFact(fact)}
                          style={{ cursor: 'pointer' }}
                          className="fact-row-clickable"
                          title="Click to inspect full detail"
                        >
                          {/* Attribute — truncated */}
                          <td style={{ fontWeight: 600 }}>
                            <div className="cell-clamp-1">{fact.attribute}</div>
                          </td>

                          {/* Value — truncated with unit */}
                          <td>
                            <div className="cell-clamp-2" style={{ fontWeight: 700 }}>
                              {fact.value}
                            </div>
                            {fact.unit && (
                              <span style={{ fontWeight: 400, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                {fact.unit}
                              </span>
                            )}
                          </td>

                          {/* Period */}
                          <td>
                            {fact.fiscal_year
                              ? <span className="badge-tag" style={{ whiteSpace: 'nowrap' }}>{fact.fiscal_year}</span>
                              : <span style={{ color: 'var(--text-muted)' }}>—</span>
                            }
                          </td>

                          {/* Page */}
                          <td>
                            <span className="badge-tag">p.{fact.evidence?.page_number || '—'}</span>
                          </td>

                          {/* Quote preview — single truncated line */}
                          <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                            <div className="cell-clamp-1">"{fact.evidence?.verbatim_quote}"</div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fact detail modal (click-to-expand) */}
      {expandedFact && (
        <FactDetailModal fact={expandedFact} onClose={() => setExpandedFact(null)} />
      )}
    </div>
  );
}
