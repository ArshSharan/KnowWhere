import React, { useState, useEffect } from 'react';
import { Building2, Tag, RefreshCw, ChevronRight } from 'lucide-react';
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

export default function EntitiesView() {
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEntityId, setSelectedEntityId] = useState(null);
  const [entityDetails, setEntityDetails] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [selectedFact, setSelectedFact] = useState(null);

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
              <div className="loading-state">Loading entity details…</div>
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
                    <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Tag size={11} /> Merged aliases:
                      </span>
                      {entityDetails.aliases.map((alias) => (
                        <span key={alias} className="badge-tag">{alias}</span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Facts table */}
                <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, marginBottom: 12, color: 'var(--text-primary)' }}>
                  Cross-document facts ({entityDetails.facts?.length || 0})
                </h4>

                <div className="facts-table-wrap">
                  <table className="facts-table">
                    <thead>
                      <tr>
                        <th>Attribute</th>
                        <th>Value</th>
                        <th>Period</th>
                        <th>Page</th>
                        <th>Quote</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entityDetails.facts?.map((fact) => (
                        <tr
                          key={fact.id}
                          onClick={() => setSelectedFact(fact)}
                          style={{ cursor: 'pointer' }}
                          title="Click to inspect evidence"
                        >
                          <td style={{ fontWeight: 600 }}>{fact.attribute}</td>
                          <td style={{ fontWeight: 700 }}>
                            {fact.value}
                            {fact.unit && (
                              <span style={{ fontWeight: 400, fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: 4 }}>
                                {fact.unit}
                              </span>
                            )}
                          </td>
                          <td>
                            {fact.fiscal_year ? <span className="badge-tag">{fact.fiscal_year}</span> : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                          </td>
                          <td>
                            <span className="badge-tag">p.{fact.evidence?.page_number || '—'}</span>
                          </td>
                          <td style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontStyle: 'italic' }}>
                            "{fact.evidence?.verbatim_quote}"
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

      <EvidenceDrawer fact={selectedFact} onClose={() => setSelectedFact(null)} />
    </div>
  );
}
