import React, { useState } from 'react';
import { Search, Sparkles, FileText, CheckCircle, Loader2 } from 'lucide-react';
import { searchFacts, synthesizeAnswer } from '../api';
import EvidenceDrawer from '../components/EvidenceDrawer';

// Skeleton result card
function SkeletonResult() {
  return (
    <div className="surface-card" style={{ padding: '16px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div className="skeleton skeleton-text sm" style={{ width: '40%' }} />
          <div className="skeleton skeleton-text lg" style={{ width: '75%' }} />
          <div className="skeleton skeleton-text xl" style={{ width: '30%' }} />
        </div>
        <div className="skeleton skeleton-text sm" style={{ width: 72, height: 22, borderRadius: 9999 }} />
      </div>
      <div style={{ marginTop: 10, borderLeft: '2px solid var(--border-subtle)', paddingLeft: 12 }}>
        <div className="skeleton skeleton-text sm" style={{ width: '90%', marginBottom: 6 }} />
        <div className="skeleton skeleton-text sm" style={{ width: '60%' }} />
      </div>
    </div>
  );
}

// Skeleton synthesis card
function SkeletonSynthesis() {
  return (
    <div className="synthesis-card">
      <div className="synthesis-header">
        <Loader2 size={14} className="animate-spin" />
        Generating answer from facts…
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div className="skeleton skeleton-text" style={{ width: '100%' }} />
        <div className="skeleton skeleton-text" style={{ width: '90%' }} />
        <div className="skeleton skeleton-text" style={{ width: '75%' }} />
      </div>
    </div>
  );
}

export default function SearchView() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [synthesis, setSynthesis] = useState(null);
  const [searching, setSearching] = useState(false);
  const [synthesizing, setSynthesizing] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedFact, setSelectedFact] = useState(null);

  const suggestedQueries = [
    'FY24 total revenue',
    'Express parcel shipment volume',
    'EBITDA margin',
    'Registered office address',
    'Active customers',
  ];

  const handleSearch = async (searchQuery) => {
    const q = searchQuery || query;
    if (!q.trim()) return;

    setSearching(true);
    setSynthesizing(true);
    setSynthesis(null);
    setHasSearched(true);

    // Fire search + synthesis in parallel
    const [factsResult] = await Promise.allSettled([
      searchFacts(q.trim()),
    ]);

    if (factsResult.status === 'fulfilled') {
      setResults(factsResult.value);
    } else {
      console.error('Search failed:', factsResult.reason);
    }
    setSearching(false);

    // Synthesis runs a bit after search returns (non-blocking for UX)
    try {
      const synthResult = await synthesizeAnswer(q.trim());
      setSynthesis(synthResult);
    } catch (err) {
      console.error('Synthesis failed:', err);
      setSynthesis(null);
    } finally {
      setSynthesizing(false);
    }
  };

  return (
    <div>
      <div style={{ maxWidth: 600, marginBottom: 28 }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.01em', color: 'var(--text-primary)', marginBottom: 4 }}>
          Semantic search
        </h2>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Ask a question in plain English — AI synthesises an answer from grounded facts, with sources
        </p>
      </div>

      {/* Search bar */}
      <form
        onSubmit={(e) => { e.preventDefault(); handleSearch(); }}
        className="search-input-group"
        style={{ marginBottom: 12 }}
      >
        <Search className="search-icon-pos" size={18} />
        <input
          type="text" className="search-input"
          placeholder="Ask a question (e.g. 'What was FY24 revenue?')…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          id="input-semantic-search"
        />
        <button
          type="submit" className="btn btn-primary btn-sm"
          style={{ position: 'absolute', right: 8 }}
          disabled={searching}
          id="btn-run-search"
        >
          {searching ? 'Searching…' : 'Search'}
        </button>
      </form>

      {/* Suggested queries */}
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 32 }}>
        <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
          <Sparkles size={13} /> Suggested:
        </span>
        {suggestedQueries.map((sq) => (
          <button
            key={sq} className="badge-tag"
            style={{ cursor: 'pointer' }}
            onClick={() => { setQuery(sq); handleSearch(sq); }}
          >
            {sq}
          </button>
        ))}
      </div>

      {/* AI Synthesis card */}
      {synthesizing && <SkeletonSynthesis />}
      {!synthesizing && synthesis && (
        <div className="synthesis-card">
          <div className="synthesis-header">
            <Sparkles size={14} />
            AI answer · {synthesis.facts_used} facts used
            {synthesis.model_used && synthesis.model_used !== 'none' && synthesis.model_used !== 'error' && (
              <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6 }}>
                · {synthesis.model_used}
              </span>
            )}
          </div>
          <div className="synthesis-answer">{synthesis.answer}</div>
          <div className="synthesis-meta">
            Raw grounded facts shown below — click any to inspect the verbatim quote
          </div>
        </div>
      )}

      {/* Results */}
      {searching ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <SkeletonResult /><SkeletonResult /><SkeletonResult />
        </div>
      ) : hasSearched && results.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><Search size={22} /></div>
          <h3>No matching facts found</h3>
          <p>Try broadening your search, or upload more documents to expand the knowledge base.</p>
        </div>
      ) : results.length > 0 ? (
        <div>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: 16 }}>
            <strong style={{ color: 'var(--text-primary)' }}>{results.length}</strong> grounded facts, ordered by semantic similarity
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {results.map((fact, idx) => {
              const simPct = (fact.similarity * 100).toFixed(0);
              return (
                <div
                  key={fact.id}
                  className="surface-card fade-up visible"
                  onClick={() => setSelectedFact(fact)}
                  style={{ padding: '16px 20px', cursor: 'pointer', transitionDelay: `${Math.min(idx * 40, 240)}ms` }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                        <FileText size={12} />
                        <span>{fact.document_title || 'Document'}</span>
                        <span>· p.{fact.evidence?.page_number || '—'}</span>
                        {fact.fiscal_year && <span className="badge-tag">{fact.fiscal_year}</span>}
                      </div>
                      <div style={{ fontSize: '0.9375rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                        <span style={{ color: 'var(--brand)' }}>{fact.entity}</span>
                        {' — '}{fact.attribute}
                      </div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 700, letterSpacing: '-0.01em', color: 'var(--text-primary)' }}>
                        {fact.value}
                        {fact.unit && <span style={{ fontSize: '0.875rem', fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6 }}>{fact.unit}</span>}
                      </div>
                    </div>

                    <span className="badge-tag" style={{ background: 'var(--brand-bg)', color: 'var(--brand)', borderColor: 'var(--brand-border)', flexShrink: 0 }}>
                      <CheckCircle size={11} /> {simPct}% match
                    </span>
                  </div>

                  {fact.evidence?.verbatim_quote && (
                    <div style={{ marginTop: 10, paddingLeft: 12, borderLeft: '2px solid var(--border-subtle)', fontSize: '0.8125rem', color: 'var(--text-muted)', fontStyle: 'italic', lineHeight: 1.6 }}>
                      "{fact.evidence.verbatim_quote}"
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      <EvidenceDrawer fact={selectedFact} onClose={() => setSelectedFact(null)} />
    </div>
  );
}
