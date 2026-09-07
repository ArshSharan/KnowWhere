import React from 'react';
import { X, Quote, FileText, CheckCircle, AlertTriangle, ExternalLink } from 'lucide-react';
import { getDocumentFileUrl } from '../api';

export default function EvidenceDrawer({ fact, onClose }) {
  if (!fact) return null;

  const quote = fact.evidence?.verbatim_quote || fact.verbatim_quote || 'No quote available';
  const pageNum = fact.evidence?.page_number || fact.page_number || 1;
  const isHighConf = (fact.evidence?.evidence_confidence || fact.evidence_confidence) === 'high';
  const docId = fact.document_id || fact.doc_id;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="evidence-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div>
            <span className="badge-tag" style={{ color: 'var(--accent-cyan)', marginBottom: '0.25rem' }}>
              Fact Grounding & Evidence
            </span>
            <h3>{fact.attribute}</h3>
          </div>
          <button className="drawer-close-btn" onClick={onClose} id="btn-close-drawer">
            <X size={20} />
          </button>
        </div>

        <div className="drawer-body">
          {/* Main Value Callout */}
          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1rem 1.25rem', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
              {fact.entity}
            </div>
            <div style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'var(--font-heading)', color: '#fff' }}>
              {fact.value} {fact.unit && <span style={{ fontSize: '1rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{fact.unit}</span>}
            </div>
            {fact.fiscal_year && (
              <span className="badge-tag" style={{ marginTop: '0.5rem', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
                {fact.fiscal_year}
              </span>
            )}
          </div>

          {/* Verbatim Quote Box */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Quote size={16} color="var(--accent-cyan)" /> Verbatim Source Quote
              </span>
              <span className={`confidence-chip ${isHighConf ? 'high' : 'low'}`}>
                {isHighConf ? <CheckCircle size={13} /> : <AlertTriangle size={13} />}
                {isHighConf ? 'Exact Match (Verified)' : 'Fuzzy / Low Confidence'}
              </span>
            </div>

            <div className="evidence-quote-box">
              <blockquote>"{quote}"</blockquote>
              <div className="evidence-quote-meta">
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                  <FileText size={14} color="var(--text-muted)" /> Page {pageNum} in document
                </span>
                {docId && (
                  <a
                    href={getDocumentFileUrl(docId)}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-secondary btn-sm"
                    style={{ textDecoration: 'none', padding: '0.2rem 0.6rem' }}
                  >
                    View Source PDF <ExternalLink size={12} style={{ marginLeft: '4px' }} />
                  </a>
                )}
              </div>
            </div>
          </div>

          {/* Fact Metadata & Qualifiers */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Fact Specification
            </span>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>FACT TYPE</div>
                <div style={{ fontSize: '0.875rem', fontWeight: 500, marginTop: '2px' }}>{fact.fact_type || 'General'}</div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>VALUE TYPE</div>
                <div style={{ fontSize: '0.875rem', fontWeight: 500, marginTop: '2px' }}>{fact.value_type || 'string'}</div>
              </div>
            </div>

            {fact.qualifiers && Object.keys(fact.qualifiers).length > 0 && (
              <div style={{ background: 'rgba(255,255,255,0.02)', padding: '0.85rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>QUALIFIERS</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                  {Object.entries(fact.qualifiers).map(([k, v]) => (
                    <span key={k} className="badge-tag">
                      <strong>{k}:</strong> {String(v)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
