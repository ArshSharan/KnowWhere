import React, { useState, useRef, useEffect, useCallback } from 'react';
import { UploadCloud, FileText, Layers, RefreshCw, Eye, AlertCircle, ExternalLink, X, Compass } from 'lucide-react';
import { fetchDocuments, uploadDocument, triggerReconcile, getDocumentFileUrl } from '../api';

// ── Status string parser ──────────────────────────────────────────────────
// Converts raw DB status like "extracting: 24/48 pages" → { label, phase, progress }
export function parseStatus(rawStatus = '') {
  const s = rawStatus.toLowerCase().trim();

  if (s === 'done')                 return { label: 'Done',               phase: 'done',       progress: 100 };
  if (s === 'failed')               return { label: 'Failed',             phase: 'failed',     progress: 0 };
  if (s === 'queued' || s === 'pending') return { label: 'Queued',        phase: 'queued',     progress: 5 };
  if (s === 'processing')           return { label: 'Starting…',          phase: 'processing', progress: 10 };
  if (s === 'validating quotes')    return { label: 'Verifying quotes…',  phase: 'validating', progress: 55 };
  if (s === 'computing embeddings') return { label: 'Computing vectors…', phase: 'computing',  progress: 65 };
  if (s === 'storing facts')        return { label: 'Storing facts…',     phase: 'storing',    progress: 75 };
  if (s === 'reconciling')          return { label: 'Cross-referencing…', phase: 'reconciling',progress: 88 };

  // "extracting: 24/48 pages"
  const extractMatch = s.match(/extracting:\s*(\d+)\/(\d+)/);
  if (extractMatch) {
    const [, done, total] = extractMatch;
    const pct = Math.round((parseInt(done) / parseInt(total)) * 40) + 15; // 15–55%
    return {
      label: `Reading page ${done} of ${total}…`,
      phase: 'extracting',
      progress: pct,
    };
  }

  // "storing: 12/50 facts"
  const storingMatch = s.match(/storing:\s*(\d+)\/(\d+)/);
  if (storingMatch) {
    const [, done, total] = storingMatch;
    const pct = Math.round((parseInt(done) / parseInt(total)) * 20) + 65; // 65–85%
    return {
      label: `Storing fact ${done} of ${total}…`,
      phase: 'storing',
      progress: pct,
    };
  }

  return { label: rawStatus, phase: 'processing', progress: 15 };
}

// ── Skeleton card placeholder ─────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 4 }}>
        <div className="skeleton skeleton-text lg" style={{ width: '70%' }} />
        <div className="skeleton skeleton-text" style={{ width: 56, height: 20, borderRadius: 9999 }} />
      </div>
      <div className="skeleton skeleton-text sm" style={{ width: '40%' }} />
      <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
        <div className="skeleton skeleton-text sm" style={{ width: 80 }} />
        <div className="skeleton skeleton-text sm" style={{ width: 60 }} />
      </div>
      <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: 16, paddingTop: 16, display: 'flex', gap: 8 }}>
        <div className="skeleton skeleton-text" style={{ width: 90, height: 30, borderRadius: 8 }} />
        <div className="skeleton skeleton-text" style={{ width: 80, height: 30, borderRadius: 8 }} />
      </div>
    </div>
  );
}

// ── PDF Preview Modal ─────────────────────────────────────────────────────
function PdfPreviewModal({ doc, onClose }) {
  if (!doc) return null;
  const fileUrl = getDocumentFileUrl(doc.id);

  return (
    <div className="pdf-modal-overlay" onClick={onClose}>
      <div className="pdf-modal-container" onClick={(e) => e.stopPropagation()}>
        <div className="pdf-modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <div className="fact-type-tile mint" style={{ flexShrink: 0 }}>
              <FileText size={16} />
            </div>
            <div style={{ minWidth: 0 }}>
              <h3 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {doc.title || 'Source PDF'}
              </h3>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {doc.page_count ? `${doc.page_count} pages • ` : ''}PDF Preview
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <a
              href={fileUrl}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary btn-sm"
              title="Open full PDF in browser tab"
            >
              <ExternalLink size={13} /> Full tab
            </a>
            <button
              className="fact-detail-close"
              onClick={onClose}
              title="Close viewer"
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 32, height: 32 }}
            >
              <X size={18} />
            </button>
          </div>
        </div>
        <div className="pdf-modal-body">
          <iframe
            src={fileUrl}
            title={doc.title || 'PDF Document'}
            className="pdf-iframe"
          />
        </div>
      </div>
    </div>
  );
}

export default function DocumentsView({ onSelectDocument, onNavigateReconcile }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [previewPdfDoc, setPreviewPdfDoc] = useState(null);
  const fileInputRef = useRef(null);

  const loadDocs = useCallback(async () => {
    try {
      const data = await fetchDocuments();
      setDocuments(data);
    } catch (err) {
      console.error('Error fetching docs:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocs();

    // Poll every 2.5s for live progress updates
    const interval = setInterval(() => {
      loadDocs();
    }, 2500);

    return () => clearInterval(interval);
  }, [loadDocs]);

  const handleFileUpload = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setUploadStatus({ stage: 'error', message: "That doesn't look like a PDF — please select a .pdf file." });
      return;
    }
    setUploading(true);
    setUploadStatus({ stage: 'uploading', message: `Uploading ${file.name}…` });
    try {
      const res = await uploadDocument(file);
      if (res.duplicate) {
        setUploadStatus({ stage: 'ok', message: 'Already ingested — no need to re-upload.' });
      } else {
        setUploadStatus({ stage: 'processing', message: 'PDF uploaded! Fact extraction is running asynchronously in the background.' });
      }
      await loadDocs();
    } catch (err) {
      setUploadStatus({ stage: 'error', message: `Upload failed: ${err.message}` });
    } finally {
      setUploading(false);
    }
  };

  const handleReconcile = async (e, docId) => {
    e.stopPropagation();
    try {
      await triggerReconcile(docId);
      loadDocs();
    } catch (err) {
      alert(`Reconciliation error: ${err.message}`);
    }
  };

  // Check if any document is processing
  const processingDoc = documents.find((d) => d.status !== 'done' && d.status !== 'failed');

  return (
    <div>
      {/* Upload zone */}
      <div
        className={`upload-dropzone ${isDragOver ? 'dragover' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setIsDragOver(false); if (e.dataTransfer.files?.[0]) handleFileUpload(e.dataTransfer.files[0]); }}
        onClick={() => !uploading && fileInputRef.current?.click()}
        id="pdf-upload-dropzone"
        style={{ cursor: uploading ? 'wait' : 'pointer' }}
      >
        <input
          type="file" accept=".pdf" ref={fileInputRef} style={{ display: 'none' }}
          onChange={(e) => { if (e.target.files?.[0]) handleFileUpload(e.target.files[0]); }}
        />
        <div className="dropzone-icon"><UploadCloud size={24} /></div>
        <div className="dropzone-text">
          <h3>Upload a PDF to get started</h3>
          <p>Extracts structured facts with verbatim quote grounding and cross-document reconciliation</p>
        </div>

        {uploadStatus && (
          <div className={`upload-status ${uploadStatus.stage === 'error' ? 'error' : uploadStatus.stage === 'processing' ? 'processing' : 'ok'}`} style={{ marginTop: 12 }}>
            {uploadStatus.message}
          </div>
        )}
      </div>

      {/* Background Processing Reassurance Banner */}
      <div className="status-notice-banner">
        <div className="status-notice-icon">
          <Compass size={18} />
        </div>
        <div className="status-notice-content">
          <div className="status-notice-title">
            Asynchronous &amp; State-Preserved Processing
          </div>
          <div className="status-notice-desc">
            Fact extraction, vector embeddings, and cross-document reconciliation run safely in the background on the server.
            Your facts and relationships are saved continuously to the database. You can freely switch to{' '}
            <button
              className="text-link-btn"
              onClick={onNavigateReconcile}
            >
              Reconciliation
            </button>
            {' '}or explore other views anytime without losing progress or interrupting active tasks.
          </div>
        </div>
      </div>

      {/* Section header */}
      <div className="section-header">
        <div className="section-title">
          <h2>Ingested documents</h2>
          <p>Click any document to inspect its extracted facts, or click "View PDF" to open the source document</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadDocs} id="btn-refresh-docs">
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* Grid — skeleton while first loading */}
      {loading ? (
        <div className="card-grid">
          <SkeletonCard /><SkeletonCard /><SkeletonCard />
        </div>
      ) : documents.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><FileText size={22} /></div>
          <h3>No documents yet</h3>
          <p>Upload a PDF using the dropzone above to begin extraction.</p>
        </div>
      ) : (
        <div className="card-grid">
          {documents.map((doc, idx) => {
            const { label, phase, progress } = parseStatus(doc.status);
            const isDone       = phase === 'done';
            const isFailed     = phase === 'failed';
            const isProcessing = !isDone && !isFailed;

            return (
              <div
                key={doc.id}
                className="glass-card fade-up visible"
                onClick={() => isDone && onSelectDocument(doc.id)}
                style={{
                  cursor: isDone ? 'pointer' : 'default',
                  transitionDelay: `${Math.min(idx * 60, 300)}ms`,
                }}
                id={`doc-card-${doc.id}`}
              >
                <div className="doc-card-header">
                  <div className="doc-title">{doc.title || 'Untitled document'}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <a
                      href={getDocumentFileUrl(doc.id)}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      title="Open source PDF in new tab"
                      className="doc-ext-link-icon"
                    >
                      <ExternalLink size={13} />
                    </a>
                    <span className={`status-badge ${phase}`}>{label}</span>
                  </div>
                </div>

                <div className="doc-meta">
                  <div className="doc-meta-item">
                    <Layers size={13} />
                    <span>{doc.page_count ? `${doc.page_count} pages` : 'Pages pending'}</span>
                  </div>
                  <div className="doc-meta-item">
                    <FileText size={13} />
                    <span><strong>{doc.facts_count ?? 0}</strong> facts</span>
                  </div>
                </div>

                {/* Live progress bar while processing */}
                {isProcessing && (
                  <div className="doc-progress-bar">
                    <div
                      className="doc-progress-bar-fill"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                )}

                <div className="doc-actions">
                  {isDone && (
                    <>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={(e) => { e.stopPropagation(); onSelectDocument(doc.id); }}
                      >
                        <Eye size={13} /> View facts
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => { e.stopPropagation(); setPreviewPdfDoc(doc); }}
                        title="Preview PDF document"
                      >
                        <FileText size={13} /> View PDF
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => handleReconcile(e, doc.id)}
                        title="Re-run cross-document reconciliation"
                      >
                        <RefreshCw size={13} /> Reconcile
                      </button>
                    </>
                  )}
                  {isProcessing && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: 8, flexWrap: 'wrap' }}>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--brand)', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <RefreshCw size={12} className="animate-spin" />
                        {label}
                      </div>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => { e.stopPropagation(); setPreviewPdfDoc(doc); }}
                        title="Preview uploaded PDF"
                      >
                        <FileText size={13} /> View PDF
                      </button>
                    </div>
                  )}
                  {isFailed && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: 8, flexWrap: 'wrap' }}>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--rel-contradicts-fg)', display: 'flex', alignItems: 'center', gap: 6 }}>
                        <AlertCircle size={12} /> Ingestion failed
                      </div>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => { e.stopPropagation(); setPreviewPdfDoc(doc); }}
                        title="View uploaded PDF"
                      >
                        <FileText size={13} /> View PDF
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* PDF Modal Viewer */}
      <PdfPreviewModal
        doc={previewPdfDoc}
        onClose={() => setPreviewPdfDoc(null)}
      />
    </div>
  );
}
