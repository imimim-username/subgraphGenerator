/**
 * CanvasLibraryPanel — "Open" dialog
 *
 * Shows a list of saved canvases and lets the user:
 *   - Open (load) a canvas
 *   - Delete a canvas
 *   - Import a canvas from a local .json file
 *   - Export the current canvas as a .json file
 *
 * Save / Save As are handled by the top toolbar, not here.
 * Callers should check for unsaved changes BEFORE opening this dialog.
 */

import { useCallback, useEffect, useState } from 'react';
import { FolderOpen, Trash2, RefreshCw, Download, Upload, X } from 'lucide-react';

function relativeDate(unixTs) {
  const diff = Date.now() / 1000 - unixTs;
  if (diff < 60)        return 'just now';
  if (diff < 3600)      return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)     return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(unixTs * 1000).toLocaleDateString();
}

export default function CanvasLibraryPanel({
  isOpen,
  onClose,
  onLoad,           // (canvasData, name) => void  — load + set currentFile
  buildPayload,     // () => object                — serialize current canvas
  currentFile,      // string | null               — name of currently open file
  subgraphName,     // string                      — used as default export filename
}) {
  const [canvases, setCanvases]         = useState([]);
  const [loadStatus, setLoadStatus]     = useState(null);   // name being loaded
  const [deleteStatus, setDeleteStatus] = useState(null);
  const [loading, setLoading]           = useState(false);
  const [importError, setImportError]   = useState(null);

  const refreshList = useCallback(() => {
    setLoading(true);
    fetch('/api/canvases')
      .then((r) => r.json())
      .then((list) => { setCanvases(list); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (isOpen) refreshList();
  }, [isOpen, refreshList]);

  // ── Load ──────────────────────────────────────────────────────────────────
  const handleLoad = useCallback(async (name) => {
    setLoadStatus(name);
    try {
      const res = await fetch(`/api/canvases/${encodeURIComponent(name)}`);
      if (!res.ok) throw new Error('Not found');
      const data = await res.json();
      onLoad(data, name);
      onClose();
    } catch (e) {
      console.error('Load failed', e);
    } finally {
      setLoadStatus(null);
    }
  }, [onLoad, onClose]);

  // ── Delete ────────────────────────────────────────────────────────────────
  const handleDelete = useCallback(async (name) => {
    if (!window.confirm(`Delete canvas "${name}"?`)) return;
    setDeleteStatus(name);
    try {
      await fetch(`/api/canvases/${encodeURIComponent(name)}`, { method: 'DELETE' });
      refreshList();
    } catch (e) {
      console.error('Delete failed', e);
    } finally {
      setDeleteStatus(null);
    }
  }, [refreshList]);

  // ── Export — download current canvas as .json ─────────────────────────────
  const handleExport = useCallback(() => {
    const payload = buildPayload();
    const filename = `${(currentFile || subgraphName || 'canvas').replace(/\s+/g, '-')}.json`;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }, [buildPayload, currentFile, subgraphName]);

  // ── Import — load a .json file from disk ──────────────────────────────────
  const [fileInputEl, setFileInputEl] = useState(null);

  const handleImportFile = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportError(null);
    file.text().then((text) => {
      try {
        const data = JSON.parse(text);
        if (!data.nodes && !data.edges) throw new Error('Not a valid canvas file');
        // Derive a name from the filename (strip .json extension)
        const name = file.name.replace(/\.json$/i, '');
        onLoad(data, name || null);
        onClose();
      } catch (err) {
        setImportError(err.message);
      }
    });
    e.target.value = '';
  }, [onLoad, onClose]);

  if (!isOpen) return null;

  return (
    /* Backdrop */
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.6)',
        backdropFilter: 'blur(4px)',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Modal */}
      <div style={{
        background: '#0f172a',
        border: '1px solid #334155',
        borderRadius: 10,
        width: 480,
        maxWidth: '95vw',
        maxHeight: '80vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 60px rgba(0,0,0,0.6)',
      }}>

        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '12px 16px',
          borderBottom: '1px solid #1e293b',
        }}>
          <FolderOpen size={15} style={{ color: '#7c3aed' }} />
          <span style={{ fontWeight: 700, fontSize: 14, color: '#e2e8f0', flex: 1 }}>Open Canvas</span>

          {/* Export current canvas */}
          <button
            onClick={handleExport}
            title="Export current canvas as a .json file"
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '4px 10px',
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid #334155',
              borderRadius: 5,
              color: '#94a3b8',
              fontSize: 11, fontWeight: 600, cursor: 'pointer',
            }}
          >
            <Download size={11} /> Export
          </button>

          {/* Import from disk */}
          <button
            onClick={() => fileInputEl?.click()}
            title="Import a canvas from a .json file"
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '4px 10px',
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid #334155',
              borderRadius: 5,
              color: '#94a3b8',
              fontSize: 11, fontWeight: 600, cursor: 'pointer',
            }}
          >
            <Upload size={11} /> Import
          </button>
          <input
            ref={setFileInputEl}
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={handleImportFile}
          />

          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#475569', cursor: 'pointer', padding: 4, display: 'flex' }}
          >
            <X size={15} />
          </button>
        </div>

        {/* Import error */}
        {importError && (
          <div style={{ padding: '6px 16px', color: '#f87171', fontSize: 12, background: 'rgba(239,68,68,0.1)', borderBottom: '1px solid #1e293b' }}>
            ✗ Import failed: {importError}
          </div>
        )}

        {/* Canvas list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {loading && (
            <div style={{ padding: '20px 16px', color: '#475569', fontSize: 13, textAlign: 'center' }}>
              <RefreshCw size={14} style={{ display: 'inline', marginRight: 6 }} />
              Loading…
            </div>
          )}

          {!loading && canvases.length === 0 && (
            <div style={{ padding: '28px 16px', color: '#475569', fontSize: 13, textAlign: 'center' }}>
              No saved canvases yet — use Save As to create one.
            </div>
          )}

          {canvases.map((c) => {
            const isActive = c.name === currentFile;
            return (
              <div
                key={c.name}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '9px 16px',
                  borderBottom: '1px solid #0f172a',
                  background: isActive ? 'rgba(124,58,237,0.08)' : 'transparent',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = '#1e293b'; }}
                onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
              >
                {/* Active indicator */}
                {isActive && (
                  <div style={{ width: 3, height: 3, borderRadius: '50%', background: '#7c3aed', flexShrink: 0 }} />
                )}

                {/* Info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontWeight: 600, fontSize: 13,
                    color: isActive ? '#a78bfa' : '#e2e8f0',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {c.name}
                    {isActive && <span style={{ fontSize: 10, color: '#7c3aed', marginLeft: 6 }}>current</span>}
                  </div>
                  <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>
                    {c.subgraph_name && c.subgraph_name !== c.name && (
                      <span style={{ marginRight: 8, color: '#64748b' }}>{c.subgraph_name}</span>
                    )}
                    {c.node_count} node{c.node_count !== 1 ? 's' : ''}
                    {' · '}
                    {relativeDate(c.updated_at)}
                  </div>
                </div>

                {/* Open button */}
                <button
                  onClick={() => handleLoad(c.name)}
                  disabled={loadStatus === c.name || isActive}
                  style={{
                    padding: '4px 12px',
                    background: isActive ? 'transparent' : 'rgba(124,58,237,0.15)',
                    border: `1px solid ${isActive ? '#334155' : '#7c3aed'}`,
                    borderRadius: 5,
                    color: isActive ? '#475569' : '#a78bfa',
                    fontSize: 11, fontWeight: 600,
                    cursor: isActive ? 'default' : 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {loadStatus === c.name ? 'Opening…' : isActive ? 'Open' : 'Open'}
                </button>

                {/* Delete button */}
                <button
                  onClick={() => handleDelete(c.name)}
                  disabled={deleteStatus === c.name}
                  title="Delete canvas"
                  style={{
                    padding: '4px 7px',
                    background: 'none',
                    border: '1px solid #7f1d1d',
                    borderRadius: 5,
                    color: '#f87171',
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center',
                  }}
                >
                  <Trash2 size={11} />
                </button>
              </div>
            );
          })}
        </div>

      </div>
    </div>
  );
}
