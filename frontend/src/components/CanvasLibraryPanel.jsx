/**
 * CanvasLibraryPanel
 *
 * Modal overlay for saving and loading named canvas states.
 *
 * Features:
 *   - List of all saved canvases (name, subgraph name, node count, date)
 *   - Load a canvas (replaces current canvas)
 *   - Delete a canvas
 *   - Save current canvas with a custom name
 *   - New canvas (clears the current canvas)
 *   - Export: download current canvas as a .json file
 *   - Import: load any .json file from disk
 *
 * Opens as a centered modal; click backdrop or × to close.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { FolderOpen, Save, Trash2, FilePlus, X, RefreshCw, Download, Upload } from 'lucide-react';

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
  onLoad,          // (canvasData) => void  — replace canvas with loaded data
  onNew,           // () => void             — clear canvas
  buildPayload,    // () => object           — get current canvas as serialisable object
  subgraphName,    // string                 — default save name
}) {
  const [canvases, setCanvases] = useState([]);
  const [saveName, setSaveName] = useState('');
  const [saveStatus, setSaveStatus] = useState(null);  // null | 'saving' | 'saved' | {error}
  const [loadStatus, setLoadStatus] = useState(null);  // null | name being loaded
  const [deleteStatus, setDeleteStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [importError, setImportError] = useState(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);

  // Refresh list whenever the panel opens
  const refreshList = useCallback(() => {
    setLoading(true);
    fetch('/api/canvases')
      .then((r) => r.json())
      .then((list) => { setCanvases(list); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    setSaveName(subgraphName || '');
    refreshList();
    // Focus the name input after a tick
    setTimeout(() => inputRef.current?.focus(), 50);
  }, [isOpen, subgraphName, refreshList]);

  // ── Save ──────────────────────────────────────────────────────────────────
  const handleSave = useCallback(async () => {
    const name = saveName.trim();
    if (!name) return;
    setSaveStatus('saving');
    try {
      const res = await fetch(`/api/canvases/${encodeURIComponent(name)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload()),
      });
      if (res.ok) {
        setSaveStatus('saved');
        refreshList();
        setTimeout(() => setSaveStatus(null), 2000);
      } else {
        const d = await res.json().catch(() => ({}));
        setSaveStatus({ error: d.detail ?? 'Save failed' });
        setTimeout(() => setSaveStatus(null), 3000);
      }
    } catch (e) {
      setSaveStatus({ error: String(e) });
      setTimeout(() => setSaveStatus(null), 3000);
    }
  }, [saveName, buildPayload, refreshList]);

  // ── Load ──────────────────────────────────────────────────────────────────
  const handleLoad = useCallback(async (name) => {
    setLoadStatus(name);
    try {
      const res = await fetch(`/api/canvases/${encodeURIComponent(name)}`);
      if (!res.ok) throw new Error('Not found');
      const data = await res.json();
      onLoad(data);
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

  // ── Export — download current canvas as .json file ───────────────────────
  const handleExport = useCallback(() => {
    const payload = buildPayload();
    const filename = `${(saveName || subgraphName || 'canvas').trim().replace(/\s+/g, '-')}.json`;
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }, [buildPayload, saveName, subgraphName]);

  // ── Import — load any .json file from disk ────────────────────────────────
  const handleImportFile = useCallback((e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportError(null);
    file.text().then((text) => {
      try {
        const data = JSON.parse(text);
        if (!data.nodes && !data.edges) throw new Error('Does not look like a canvas file');
        onLoad(data);
        onClose();
      } catch (err) {
        setImportError(err.message);
      }
    });
    // reset so same file can be re-selected
    e.target.value = '';
  }, [onLoad, onClose]);

  // ── New canvas ────────────────────────────────────────────────────────────
  const handleNew = useCallback(() => {
    if (!window.confirm('Start a new canvas? Unsaved changes will be lost.')) return;
    onNew();
    onClose();
  }, [onNew, onClose]);

  if (!isOpen) return null;

  const saveLabel = saveStatus === 'saving' ? 'Saving…'
    : saveStatus === 'saved' ? '✓ Saved'
    : saveStatus?.error ? `✗ ${saveStatus.error}`
    : 'Save';

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
          <span style={{ fontWeight: 700, fontSize: 14, color: '#e2e8f0' }}>Canvas Library</span>
          <div style={{ flex: 1 }} />
          <button
            onClick={handleNew}
            title="New canvas"
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
            <FilePlus size={11} /> New
          </button>
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
          <button
            onClick={() => fileInputRef.current?.click()}
            title="Import a canvas from a .json file on disk"
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
            ref={fileInputRef}
            type="file"
            accept=".json"
            style={{ display: 'none' }}
            onChange={handleImportFile}
          />
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#475569', cursor: 'pointer', padding: 4 }}
          >
            <X size={15} />
          </button>
        </div>

        {/* Save-as row */}
        <div style={{
          display: 'flex', gap: 6, alignItems: 'center',
          padding: '10px 16px',
          borderBottom: '1px solid #1e293b',
        }}>
          <input
            ref={inputRef}
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleSave(); }}
            placeholder="Canvas name…"
            style={{
              flex: 1,
              background: 'rgba(0,0,0,0.35)',
              border: '1px solid #334155',
              borderRadius: 5,
              padding: '5px 10px',
              color: '#e2e8f0',
              fontSize: 13,
              outline: 'none',
            }}
          />
          <button
            onClick={handleSave}
            disabled={!saveName.trim() || saveStatus === 'saving'}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '5px 14px',
              background: saveStatus === 'saved' ? 'rgba(34,197,94,0.2)'
                : saveStatus?.error ? 'rgba(239,68,68,0.2)'
                : 'rgba(124,58,237,0.18)',
              border: `1px solid ${saveStatus === 'saved' ? '#22c55e' : saveStatus?.error ? '#ef4444' : '#7c3aed'}`,
              borderRadius: 5,
              color: saveStatus === 'saved' ? '#22c55e' : saveStatus?.error ? '#ef4444' : '#a78bfa',
              fontSize: 12, fontWeight: 600,
              cursor: !saveName.trim() || saveStatus === 'saving' ? 'not-allowed' : 'pointer',
              opacity: !saveName.trim() ? 0.5 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            <Save size={11} /> {saveLabel}
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
              <RefreshCw size={14} style={{ display: 'inline', marginRight: 6, animation: 'spin 1s linear infinite' }} />
              Loading…
            </div>
          )}
          {!loading && canvases.length === 0 && (
            <div style={{ padding: '28px 16px', color: '#475569', fontSize: 13, textAlign: 'center' }}>
              No saved canvases yet — type a name above and click Save.
            </div>
          )}
          {canvases.map((c) => (
            <div key={c.name} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '9px 16px',
              borderBottom: '1px solid #0f172a',
              transition: 'background 0.1s',
            }}
              onMouseEnter={(e) => { e.currentTarget.style.background = '#1e293b'; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
            >
              {/* Info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 13, color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.name}
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

              {/* Load button */}
              <button
                onClick={() => handleLoad(c.name)}
                disabled={loadStatus === c.name}
                style={{
                  padding: '4px 12px',
                  background: 'rgba(124,58,237,0.15)',
                  border: '1px solid #7c3aed',
                  borderRadius: 5,
                  color: '#a78bfa',
                  fontSize: 11, fontWeight: 600, cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {loadStatus === c.name ? 'Loading…' : 'Load'}
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
          ))}
        </div>

      </div>
    </div>
  );
}
