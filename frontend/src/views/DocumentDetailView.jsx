import React, { useState, useEffect } from 'react';
import { ArrowLeft, Search, FileText, CheckCircle, AlertTriangle, ExternalLink, TrendingUp, DollarSign, Users, Building } from 'lucide-react';
import { fetchDocumentFacts, getDocumentFileUrl } from '../api';
import EvidenceDrawer from '../components/EvidenceDrawer';

function getTileColor(factType) {
  if (!factType) return 'sky';
  const ft = factType.toLowerCase();
  if (ft.includes('financial') || ft.includes('revenue') || ft.includes('profit')) return 'mint';
  if (ft.includes('operational') || ft.includes('volume') || ft.includes('shipment')) return 'sky';
  if (ft.includes('corporate') || ft.includes('governance') || ft.includes('director')) return 'lavender';
  if (ft.includes('legal') || ft.includes('address') || ft.includes('registration')) return 'peach';
  return 'amber';
}

function getTileIcon(factType) {
  if (!factType) return <FileText size={15} />;
  const ft = factType.toLowerCase();
  if (ft.includes('financial') || ft.includes('revenue')) return <DollarSign size={15} />;
  if (ft.includes('operational') || ft.includes('volume')) return <TrendingUp size={15} />;
  if (ft.includes('corporate') || ft.includes('governance')) return <Building size={15} />;
  if (ft.includes('customer') || ft.includes('employee')) return <Users size={15} />;
  return <FileText size={15} />;
}

// Skeleton table rows
function SkeletonRows({ count = 6 }) {
  return Array.from({ length: count }).map((_, i) => (
    <tr key={i} className="skeleton-row">
      <td><div className="skeleton skeleton-tile" /></td>
      <td><div className="skeleton skeleton-text" style={{ width: '80%' }} /></td>
      <td><div className="skeleton skeleton-text" style={{ width: '60%' }} /></td>
      <td><div className="skeleton skeleton-text lg" style={{ width: '50%' }} /></td>
      <td><div className="skeleton skeleton-text sm" style={{ width: 40, borderRadius: 9999 }} /></td>
      <td><div className="skeleton skeleton-text sm" style={{ width: 36, borderRadius: 9999 }} /></td>
      <td><div className="skeleton skeleton-text sm" style={{ width: 60, borderRadius: 9999 }} /></td>
      <td><div className="skeleton skeleton-text sm" style={{ width: 80, borderRadius: 8 }} /></td>
    </tr>
  ));
}

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

  if (!loading && !docData) {
    return (
      <div className="empty-state" style={{ marginTop: 32 }}>
        <h3>Document not found</h3>
        <p>This document may have been removed or failed to ingest.</p>
        <button className="btn btn-secondary" onClick={onBack} style={{ marginTop: 16 }}>
          <ArrowLeft size={15} /> Back to documents
        </button>
      </div>
    );
  }

  const allFacts = docData?.facts || [];
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
      {/* Back + title */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, gap: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-secondary btn-sm" onClick={onBack} id="btn-back-docs">
            <ArrowLeft size={15} /> Documents
          </button>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.01em', color: 'var(--text-primary)' }}>
              {loading ? <div className="skeleton skeleton-text xl" style={{ width: 240 }} /> : (docData?.title || 'Document facts')}
            </h2>
            {!loading && (
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', display: 'flex', gap: 12, marginTop: 2 }}>
                <span>{docData?.page_count || '?'} pages</span>
                <span>•</span>
                <span><strong style={{ color: 'var(--text-primary)' }}>{allFacts.length}</strong> facts extracted</span>
              </div>
            )}
          </div>
        </div>

        {!loading && (
          <a href={getDocumentFileUrl(docId)} target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm" id="btn-view-pdf">
            <ExternalLink size={13} /> Open source PDF
          </a>
        )}
      </div>

      {/* Filter & search */}
      {!loading && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 220, maxWidth: 400 }}>
            <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', pointerEvents: 'none' }} />
            <input
              type="text" className="input-field" placeholder="Search facts…"
              value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
              style={{ paddingLeft: '2.25rem' }}
            />
          </div>
          <div className="filter-row" style={{ marginBottom: 0 }}>
            {factTypes.map((ft) => (
              <button key={ft} className={`filter-pill ${typeFilter === ft ? 'active' : ''}`} onClick={() => setTypeFilter(ft)}>
                {ft === 'all' ? 'All types' : ft}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="facts-table-wrap">
        <table className="facts-table">
          <thead>
            <tr>
              <th style={{ width: 40 }}></th>
              <th>Entity</th>
              <th>Attribute</th>
              <th>Value</th>
              <th>Period</th>
              <th>Page</th>
              <th>Grounding</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <SkeletonRows count={6} />
            ) : filteredFacts.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-muted)' }}>
                  No facts match the selected filters.
                </td>
              </tr>
            ) : (
              filteredFacts.map((fact) => {
                const isHighConf = fact.evidence?.evidence_confidence === 'high';
                const tileColor = getTileColor(fact.fact_type);
                return (
                  <tr key={fact.id} onClick={() => setSelectedFact({ ...fact, document_id: docId })} title="Click to view evidence">
                    <td>
                      <div className={`fact-type-tile ${tileColor}`}>{getTileIcon(fact.fact_type)}</div>
                    </td>
                    <td style={{ fontWeight: 600 }}>{fact.entity}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{fact.attribute}</td>
                    <td style={{ fontWeight: 700 }}>
                      {fact.value}
                      {fact.unit && <span style={{ fontSize: '0.8rem', fontWeight: 400, color: 'var(--text-muted)', marginLeft: 4 }}>{fact.unit}</span>}
                    </td>
                    <td>
                      {fact.fiscal_year ? <span className="badge-tag">{fact.fiscal_year}</span> : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                    </td>
                    <td><span className="badge-tag">p.{fact.evidence?.page_number || '—'}</span></td>
                    <td>
                      <span className={`confidence-chip ${isHighConf ? 'high' : 'low'}`}>
                        {isHighConf ? <CheckCircle size={11} /> : <AlertTriangle size={11} />}
                        {isHighConf ? 'Verified' : 'Fuzzy'}
                      </span>
                    </td>
                    <td>
                      <button className="btn btn-secondary btn-sm" onClick={(e) => { e.stopPropagation(); setSelectedFact({ ...fact, document_id: docId }); }}>
                        Evidence
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <EvidenceDrawer fact={selectedFact} onClose={() => setSelectedFact(null)} />
    </div>
  );
}
