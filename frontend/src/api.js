/**
 * API client for KnowWhere backend.
 * Uses relative URL '/api' (proxied via Vite dev server, or direct).
 */

const API_BASE = import.meta.env.VITE_API_URL || '/api';

async function handleResponse(res) {
  if (!res.ok) {
    let errorDetail = 'API request failed';
    try {
      const err = await res.json();
      errorDetail = err.detail || err.message || JSON.stringify(err);
    } catch {
      errorDetail = `${res.status} ${res.statusText}`;
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export async function fetchHealth() {
  return fetch(`${API_BASE}/health`).then(handleResponse);
}

export async function fetchDocuments() {
  return fetch(`${API_BASE}/documents`).then(handleResponse);
}

export async function fetchDocument(docId) {
  return fetch(`${API_BASE}/documents/${docId}`).then(handleResponse);
}

export async function fetchDocumentFacts(docId) {
  return fetch(`${API_BASE}/documents/${docId}/facts`).then(handleResponse);
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/documents`, {
    method: 'POST',
    body: formData,
  });
  return handleResponse(res);
}

export async function triggerReconcile(docId) {
  const res = await fetch(`${API_BASE}/documents/${docId}/reconcile`, {
    method: 'POST',
  });
  return handleResponse(res);
}

export async function fetchRelationships(relationshipType = null, limit = 200) {
  const params = new URLSearchParams();
  if (relationshipType) params.set('relationship', relationshipType);
  params.set('limit', String(limit));
  return fetch(`${API_BASE}/relationships?${params.toString()}`).then(handleResponse);
}

export async function fetchEntities() {
  return fetch(`${API_BASE}/entities`).then(handleResponse);
}

export async function fetchEntity(entityId) {
  return fetch(`${API_BASE}/entities/${entityId}`).then(handleResponse);
}

export async function searchFacts(query, limit = 30) {
  return fetch(`${API_BASE}/facts/search?q=${encodeURIComponent(query)}&limit=${limit}`).then(handleResponse);
}

export async function synthesizeAnswer(query) {
  return fetch(`${API_BASE}/facts/synthesize?q=${encodeURIComponent(query)}`).then(handleResponse);
}

export function getDocumentFileUrl(docId) {
  return `${API_BASE}/documents/${docId}/file`;
}
