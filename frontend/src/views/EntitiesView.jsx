import React, { useState, useEffect } from 'react';
import { Building2, Tag, Layers, RefreshCw, ChevronRight, FileText, Quote } from 'lucide-react';
import { fetchEntities, fetchEntity } from '../api';
import EvidenceDrawer from '../components/EvidenceDrawer';

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

  useEffect(() => {
    loadEntities();
  }, []);

  return (
    <div>
      {/* Header */}
      <div className="section-header">
        <div className="section-title">
          <h2>Canonical Entities Explorer</h2>
          <p>Multi-pass entity resolution merging alternate surface forms and tracking cross-document facts</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadEntities} id="btn-refresh-entities">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
          Loading canonical entities...
        </div>
      ) : entities.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem', background: 'var(--bg-card)', borderRadius: '16px', border: '1px solid var(--border-subtle)' }}>
          <Building2 size={40} color="var(--text-muted)" style={{ margin: '0 auto 1rem' }} />
          <h3>No entities detected yet</h3>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
            Entities are automatically canonicalized when PDF documents are ingested.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.5rem', alignItems: 'start' }}>
          {/* Entity List (Left Pane) */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            {entities.map((ent) => {
              const isSelected = ent.id === selectedEntityId;
              return (
                <div
                  key={ent.id}
                  className="glass-card"
                  onClick={() => handleSelectEntity(ent.id)}
                  style={{
                    cursor: 'pointer',
                    padding: '1rem 1.25rem',
                    borderColor: isSelected ? 'var(--accent-cyan)' : 'var(--border-subtle)',
                    background: isSelected ? 'rgba(6, 182, 212, 0.1)' : 'var(--bg-card)',
                    boxShadow: isSelected ? '0 0 16px rgba(6, 182, 212, 0.2)' : 'none',
                  }}
                  id={`entity-item-${ent.id}`}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', color: isSelected ? '#fff' : 'var(--text-primary)' }}>
                      {ent.canonical_name}
                    </div>
                    <ChevronRight size={16} color={isSelected ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
                  </div>

                  <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', fontSize: '0.785rem', color: 'var(--text-secondary)' }}>
                    <span><strong>{ent.fact_count}</strong> facts</span>
                    <span>•</span>
                    <span>{ent.alias_count} aliases</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Entity Details (Right Pane) */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '16px', padding: '1.5rem' }}>
            {loadingDetails ? (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                Loading entity details...
              </div>
            ) : !entityDetails ? (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                Select an entity on the left to view cross-document knowledge.
              </div>
            ) : (
              <div>
                {/* Header */}
                <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '1.25rem', marginBottom: '1.25rem' }}>
                  <span className="badge-tag" style={{ color: 'var(--accent-cyan)', marginBottom: '0.4rem' }}>
                    Canonical Entity
                  </span>
                  <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.5rem', fontWeight: 700 }}>
                    {entityDetails.canonical_name}
                  </h3>

                  {/* Surface Aliases */}
                  {entityDetails.aliases && entityDetails.aliases.length > 0 && (
                    <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.4rem' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <Tag size={12} /> Merged Aliases:
                      </span>
                      {entityDetails.aliases.map((alias) => (
                        <span key={alias} className="badge-tag" style={{ background: 'rgba(255,255,255,0.03)' }}>
                          {alias}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Facts Table */}
                <h4 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.75rem' }}>
                  Cross-Document Facts ({entityDetails.facts?.length || 0})
                </h4>

                <div className="facts-table-wrap">
                  <table className="facts-table">
                    <thead>
                      <tr>
                        <th>Attribute</th>
                        <th>Value</th>
                        <th>Fiscal Year</th>
                        <th>Page</th>
                        <th>Evidence Quote</th>
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
                          <td style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>{fact.attribute}</td>
                          <td style={{ fontWeight: 700 }}>{fact.value} {fact.unit}</td>
                          <td>
                            {fact.fiscal_year ? <span className="badge-tag">{fact.fiscal_year}</span> : '—'}
                          </td>
                          <td>
                            <span className="badge-tag">P. {fact.evidence?.page_number || '—'}</span>
                          </td>
                          <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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
