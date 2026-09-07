import React, { useState, useEffect } from 'react';
import { ArrowLeft, Search, FileText, Quote, CheckCircle, AlertTriangle, ExternalLink } from 'lucide-react';
import { fetchDocumentFacts, getDocumentFileUrl } from '../api';
import EvidenceDrawer from '../components/EvidenceDrawer';

export default function DocumentDetailView({ docId, onBack }) {
  const [docData, setDocData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [selectedFact, setSelectedFact] = useState(null);

  useEffect(() => {
    async function loadFacts() {
      try {
        const data = await fetchDocumentFacts(docId);
        setDocData(data);
      } catch (err) {
        console.error('Failed to load document facts:', err);
      } finally {
        setLoading(false);
      }
    }
    loadFacts();
  }, [docId]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-muted)' }}>
        Loading document facts and evidence...
      </div>
    );
  }

  if (!docData) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem' }}>
        <h3>Document not found</h3>
        <button className="btn btn-secondary" onClick={onBack} style={{ marginTop: '1rem' }}>
          <ArrowLeft size={16} /> Back to Documents
        </button>
      </div>
    );
  }

  const allFacts = docData.facts || [];
  const factTypes = ['all', ...Array.from(new Set(allFacts.map((f) => f.fact_type).filter(Boolean)))];

  const filteredFacts = allFacts.filter((f) => {
    const matchesType = typeFilter === 'all' || f.fact_type === typeFilter;
    const q = searchQuery.toLowerCase();
    const matchesSearch =
      !q ||
      f.entity?.toLowerCase().includes(q) ||
      f.attribute?.toLowerCase().includes(q) ||
      f.value?.toLowerCase().includes(q) ||
      f.evidence?.verbatim_quote?.toLowerCase().includes(q);
    return matchesType && matchesSearch;
  });

  return (
    <div>
      {/* Back button & Document Title */}
      <div style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button className="btn btn-secondary btn-sm" onClick={onBack} id="btn-back-docs">
            <ArrowLeft size={16} /> Documents
          </button>
          <div>
            <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.4rem', fontWeight: 700 }}>
              {docData.title || 'Document Facts'}
            </h2>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', gap: '1rem', marginTop: '0.25rem' }}>
              <span>{docData.page_count || '?'} Pages</span>
              <span>•</span>
              <span><strong>{allFacts.length}</strong> Facts Extracted</span>
            </div>
          </div>
        </div>

        <a
          href={getDocumentFileUrl(docId)}
          target="_blank"
          rel="noreferrer"
          className="btn btn-secondary btn-sm"
          id="btn-view-pdf"
        >
          <ExternalLink size={14} /> Open Source PDF
        </a>
      </div>

      {/* Filter & Search Bar */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: '240px', maxWidth: '420px' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search attributes, values, or quotes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              background: 'var(--bg-glass-input)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '10px',
              padding: '0.55rem 1rem 0.55rem 2.25rem',
              color: 'var(--text-primary)',
              fontSize: '0.875rem',
              outline: 'none',
            }}
          />
        </div>

        {/* Fact Type Pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
          {factTypes.map((ft) => (
            <button
              key={ft}
              className={`badge-tag ${typeFilter === ft ? 'active' : ''}`}
              onClick={() => setTypeFilter(ft)}
              style={{
                cursor: 'pointer',
                background: typeFilter === ft ? 'rgba(6, 182, 212, 0.2)' : 'rgba(255,255,255,0.04)',
                color: typeFilter === ft ? '#fff' : 'var(--text-secondary)',
                borderColor: typeFilter === ft ? 'var(--accent-cyan)' : 'var(--border-subtle)',
              }}
            >
              {ft}
            </button>
          ))}
        </div>
      </div>

      {/* Facts Table */}
      <div className="facts-table-wrap">
        <table className="facts-table">
          <thead>
            <tr>
              <th>Entity</th>
              <th>Attribute</th>
              <th>Value</th>
              <th>Time / FY</th>
              <th>Page</th>
              <th>Evidence Grounding</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredFacts.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                  No facts match the selected filters.
                </td>
              </tr>
            ) : (
              filteredFacts.map((fact) => {
                const isHighConf = fact.evidence?.evidence_confidence === 'high';
                return (
                  <tr
                    key={fact.id}
                    onClick={() => setSelectedFact({ ...fact, document_id: docId })}
                    title="Click to view verbatim evidence quote"
                  >
                    <td style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>{fact.entity}</td>
                    <td style={{ color: 'var(--text-primary)' }}>{fact.attribute}</td>
                    <td style={{ fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                      {fact.value} {fact.unit && <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{fact.unit}</span>}
                    </td>
                    <td>
                      {fact.fiscal_year ? (
                        <span className="badge-tag">{fact.fiscal_year}</span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td>
                      <span className="badge-tag">P. {fact.evidence?.page_number || '—'}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <span className={`confidence-chip ${isHighConf ? 'high' : 'low'}`}>
                          {isHighConf ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
                          {isHighConf ? 'High' : 'Low'}
                        </span>
                        <span style={{ fontSize: '0.785rem', color: 'var(--text-muted)', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          "{fact.evidence?.verbatim_quote}"
                        </span>
                      </div>
                    </td>
                    <td>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedFact({ ...fact, document_id: docId });
                        }}
                      >
                        <Quote size={13} /> Evidence
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Selected Fact Evidence Drawer */}
      <EvidenceDrawer fact={selectedFact} onClose={() => setSelectedFact(null)} />
    </div>
  );
}
