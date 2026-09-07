import React, { useState, useRef, useEffect } from 'react';
import { UploadCloud, FileText, Layers, RefreshCw, Eye, ArrowRight, AlertCircle, CheckCircle2 } from 'lucide-react';
import { fetchDocuments, uploadDocument, triggerReconcile } from '../api';

export default function DocumentsView({ onSelectDocument, onNavigateReconcile }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const loadDocs = async () => {
    try {
      const data = await fetchDocuments();
      setDocuments(data);
    } catch (err) {
      console.error('Error fetching docs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocs();
    // Poll every 4 seconds if any document is processing
    const interval = setInterval(() => {
      setDocuments((prevDocs) => {
        const hasProcessing = prevDocs.some(
          (d) => d.status !== 'done' && d.status !== 'failed'
        );
        if (hasProcessing) {
          loadDocs();
        }
        return prevDocs;
      });
    }, 4000);

    return () => clearInterval(interval);
  }, []);

  const handleFileUpload = async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please select a valid PDF file.');
      return;
    }

    setUploading(true);
    setUploadStatus({ stage: 'uploading', message: `Uploading ${file.name}...` });

    try {
      const res = await uploadDocument(file);
      if (res.duplicate) {
        setUploadStatus({ stage: 'done', message: `Document already ingested (${res.doc_id.slice(0, 8)}).` });
      } else {
        setUploadStatus({ stage: 'processing', message: 'PDF uploaded! Background ingestion started...' });
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
      alert('Reconciliation triggered in background! Refreshing in a moment...');
      loadDocs();
    } catch (err) {
      alert(`Reconciliation error: ${err.message}`);
    }
  };

  return (
    <div>
      {/* Upload Box */}
      <div
        className={`upload-dropzone ${isDragOver ? 'dragover' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragOver(false);
          if (e.dataTransfer.files?.[0]) handleFileUpload(e.dataTransfer.files[0]);
        }}
        onClick={() => fileInputRef.current?.click()}
        id="pdf-upload-dropzone"
      >
        <input
          type="file"
          accept=".pdf"
          ref={fileInputRef}
          style={{ display: 'none' }}
          onChange={(e) => {
            if (e.target.files?.[0]) handleFileUpload(e.target.files[0]);
          }}
        />
        <div className="dropzone-icon">
          <UploadCloud size={28} />
        </div>
        <div className="dropzone-text">
          <h3>Drop PDF documents here to ingest</h3>
          <p>Extracts structured facts with verbatim quotes & cross-document reconciliation</p>
        </div>

        {uploadStatus && (
          <div style={{ marginTop: '1rem', fontSize: '0.875rem', color: uploadStatus.stage === 'error' ? '#fb7185' : 'var(--accent-cyan)' }}>
            {uploadStatus.message}
          </div>
        )}
      </div>

      {/* Documents Section Header */}
      <div className="section-header">
        <div className="section-title">
          <h2>Ingested Documents</h2>
          <p>Click any document to inspect its extracted facts & verifiable citations</p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={loadDocs} id="btn-refresh-docs">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Documents Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
          Loading ingested documents...
        </div>
      ) : documents.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem', background: 'var(--bg-card)', borderRadius: '14px', border: '1px solid var(--border-subtle)' }}>
          <FileText size={40} color="var(--text-muted)" style={{ margin: '0 auto 1rem' }} />
          <h3>No documents ingested yet</h3>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
            Upload a PDF using the dropzone above to begin extraction!
          </p>
        </div>
      ) : (
        <div className="card-grid">
          {documents.map((doc) => {
            const isDone = doc.status === 'done';
            const isFailed = doc.status === 'failed';
            const isProcessing = !isDone && !isFailed;

            return (
              <div
                key={doc.id}
                className="glass-card"
                onClick={() => isDone && onSelectDocument(doc.id)}
                style={{ cursor: isDone ? 'pointer' : 'default' }}
                id={`doc-card-${doc.id}`}
              >
                <div className="doc-card-header">
                  <div className="doc-title">{doc.title || 'Untitled Document'}</div>
                  <span className={`status-badge ${doc.status.startsWith('extract') ? 'extracting' : doc.status}`}>
                    {doc.status}
                  </span>
                </div>

                <div className="doc-meta">
                  <div className="doc-meta-item">
                    <Layers size={14} />
                    <span>{doc.page_count ? `${doc.page_count} Pages` : 'Pages pending'}</span>
                  </div>
                  <div className="doc-meta-item">
                    <FileText size={14} />
                    <span><strong>{doc.facts_count}</strong> Grounded Facts</span>
                  </div>
                </div>

                <div className="doc-actions">
                  {isDone && (
                    <>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectDocument(doc.id);
                        }}
                      >
                        <Eye size={14} /> View Facts
                      </button>
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => handleReconcile(e, doc.id)}
                        title="Re-run cross-document candidate reconciliation"
                      >
                        <RefreshCw size={13} /> Reconcile
                      </button>
                    </>
                  )}
                  {isProcessing && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <RefreshCw size={12} className="animate-spin" /> Ingesting & Grounding facts...
                    </div>
                  )}
                  {isFailed && (
                    <div style={{ fontSize: '0.8rem', color: '#fb7185', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <AlertCircle size={12} /> Extraction failed
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
