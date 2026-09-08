import React from 'react';
import { X, FileText, CheckCircle, AlertTriangle, ExternalLink } from 'lucide-react';
import { getDocumentFileUrl } from '../api';

export default function EvidenceDrawer({ fact, onClose }) {
  if (!fact) return null;

  const quote = fact.evidence?.verbatim_quote || fact.verbatim_quote || '';
  const pageNum = fact.evidence?.page_number || fact.page_number || 1;
  const isHighConf = (fact.evidence?.evidence_confidence || fact.evidence_confidence) === 'high';
  const docId = fact.document_id || fact.doc_id;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="evidence-drawer" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="drawer-header">
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Evidence
            </div>
            <h3>{fact.attribute}</h3>
          </div>
          <button className="drawer-close-btn" onClick={onClose} id="btn-close-drawer">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="drawer-body">
          {/* Value callout */}
          <div className="drawer-value-callout">
            <div className="drawer-value-entity">{fact.entity}</div>
            <div className="drawer-value-main">
              {fact.value}
              {fact.unit && (
                <span className="drawer-value-unit"> {fact.unit}</span>
              )}
            </div>
            {fact.fiscal_year && (
              <span className="badge-tag" style={{ marginTop: 8, display: 'inline-flex' }}>
                {fact.fiscal_year}
              </span>
            )}
          </div>

          {/* Verbatim quote */}
          <div className="evidence-quote-section">
            <div className="evidence-quote-label">
              <span>
                Verbatim quote
              </span>
              <span className={`confidence-chip ${isHighConf ? 'high' : 'low'}`}>
                {isHighConf ? <CheckCircle size={11} /> : <AlertTriangle size={11} />}
                {isHighConf ? 'Verified' : 'Fuzzy match'}
              </span>
            </div>

            {/* Left-border blockquote treatment per design brief */}
            <div className="evidence-quote-box">
              {quote ? (
                <blockquote>"{quote}"</blockquote>
              ) : (
                <p style={{ color: 'var(--text-muted)', fontStyle: 'normal', fontSize: '0.875rem' }}>
                  Quote could not be verified against source text
                </p>
              )}
            </div>

            {/* Caption line below the quote */}
            <div className="evidence-quote-meta">
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <FileText size={13} color="var(--text-muted)" />
                Page {pageNum}
              </span>
              {docId && (
                <a
                  href={getDocumentFileUrl(docId)}
                  target="_blank"
                  rel="noreferrer"
                  className="btn btn-secondary btn-sm"
                  style={{ textDecoration: 'none' }}
                >
                  Open source PDF <ExternalLink size={11} style={{ marginLeft: 4 }} />
                </a>
              )}
            </div>
          </div>

          {/* Fact specification */}
          <div>
            <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10 }}>
              Fact details
            </div>
            <div className="fact-spec-grid">
              <div className="fact-spec-cell">
                <div className="fact-spec-label">Fact type</div>
                <div className="fact-spec-value">{fact.fact_type || 'General'}</div>
              </div>
              <div className="fact-spec-cell">
                <div className="fact-spec-label">Value type</div>
                <div className="fact-spec-value">{fact.value_type || 'string'}</div>
              </div>
            </div>

            {fact.qualifiers && Object.keys(fact.qualifiers).length > 0 && (
              <div className="fact-spec-cell" style={{ marginTop: 8 }}>
                <div className="fact-spec-label">Qualifiers</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
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
