import React, { useState } from 'react';
import { Search, Sparkles, FileText, CheckCircle, Quote, ArrowRight } from 'lucide-react';
import { searchFacts } from '../api';
import EvidenceDrawer from '../components/EvidenceDrawer';

export default function SearchView() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [selectedFact, setSelectedFact] = useState(null);

  const suggestedQueries = [
    'FY24 total revenue',
    'Express parcel shipment volume',
    'EBITDA and profitability margin',
    'Registered office address',
    'Active customers and PIN codes covered',
  ];

  const handleSearch = async (searchQuery) => {
    const q = searchQuery || query;
    if (!q.trim()) return;

    setSearching(true);
    setHasSearched(true);
    try {
      const data = await searchFacts(q.trim());
      setResults(data);
    } catch (err) {
      console.error('Semantic search failed:', err);
      alert(`Search error: ${err.message}`);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div>
      {/* Title */}
      <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.85rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
          Semantic Knowledge Search
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginTop: '0.35rem', maxWidth: '600px', margin: '0.35rem auto 0' }}>
          Query across all ingested facts using OpenAI vector embeddings + pgvector cosine similarity
        </p>
      </div>

      {/* Search Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSearch();
        }}
        className="search-input-group"
      >
        <Search className="search-icon-pos" size={20} />
        <input
          type="text"
          className="search-input"
          placeholder="Ask a question or enter keywords (e.g. 'What was the FY24 revenue?')..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          id="input-semantic-search"
        />
        <button
          type="submit"
          className="btn btn-primary"
          style={{ position: 'absolute', right: '8px', padding: '0.5rem 1.15rem' }}
          disabled={searching}
          id="btn-run-search"
        >
          {searching ? 'Searching...' : 'Search'}
        </button>
      </form>

      {/* Suggested Query Chips */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '2.5rem' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <Sparkles size={13} color="var(--accent-cyan)" /> Suggested:
        </span>
        {suggestedQueries.map((sq) => (
          <button
            key={sq}
            className="badge-tag"
            style={{ cursor: 'pointer', background: 'rgba(255,255,255,0.04)' }}
            onClick={() => {
              setQuery(sq);
              handleSearch(sq);
            }}
          >
            {sq}
          </button>
        ))}
      </div>

      {/* Search Results */}
      {searching ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
          Computing embeddings and searching vector index...
        </div>
      ) : hasSearched && results.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem', background: 'var(--bg-card)', borderRadius: '16px', border: '1px solid var(--border-subtle)' }}>
          <h3>No matching facts found</h3>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
            Try broadening your search or uploading more documents.
          </p>
        </div>
      ) : results.length > 0 ? (
        <div>
          <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            Found <strong>{results.length}</strong> matching facts ordered by semantic similarity:
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {results.map((fact) => {
              const simPct = (fact.similarity * 100).toFixed(0);
              return (
                <div
                  key={fact.id}
                  className="glass-card"
                  onClick={() => setSelectedFact(fact)}
                  style={{ cursor: 'pointer', padding: '1.25rem 1.5rem' }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
                    <div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                        <FileText size={13} />
                        <span>{fact.document_title || 'Document'}</span>
                        <span>• P. {fact.evidence?.page_number || '—'}</span>
                        {fact.fiscal_year && <span className="badge-tag">{fact.fiscal_year}</span>}
                      </div>

                      <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
                        <span style={{ color: 'var(--accent-cyan)' }}>{fact.entity}</span> — {fact.attribute}
                      </div>

                      <div style={{ fontSize: '1.35rem', fontWeight: 700, fontFamily: 'var(--font-heading)', marginTop: '0.25rem' }}>
                        {fact.value} {fact.unit}
                      </div>
                    </div>

                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <span className="badge-tag" style={{ background: 'rgba(6, 182, 212, 0.15)', color: 'var(--accent-cyan)', borderColor: 'var(--border-accent)', fontWeight: 600 }}>
                        {simPct}% Similarity
                      </span>
                    </div>
                  </div>

                  {fact.evidence?.verbatim_quote && (
                    <div style={{ marginTop: '0.75rem', padding: '0.65rem 0.85rem', background: 'rgba(0,0,0,0.25)', borderRadius: '8px', borderLeft: '3px solid var(--accent-cyan)', fontSize: '0.85rem', color: '#cbd5e1', fontStyle: 'italic' }}>
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
