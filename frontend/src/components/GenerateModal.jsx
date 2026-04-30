/**
 * GenerateModal
 *
 * A directory-picker modal for the Generate action.
 * Features:
 *   - Text input for typing a path directly
 *   - Browse panel showing the server filesystem (via /api/fs/browse)
 *   - Navigate into subdirectories with a click
 *   - Go Up button
 *   - New Folder button to create a directory in the current location
 *   - Select button to confirm the browsed-to directory
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Folder, FolderOpen, FolderPlus, ChevronUp, ChevronRight, Zap } from 'lucide-react';

const PANEL_BG   = '#0f172a';   // solid dark — no transparency bleeding through
const BORDER_CLR = '#1e293b';
const ACCENT     = '#7c3aed';
const ACCENT_LT  = '#c4b5fd';
const TEXT       = '#e2e8f0';
const TEXT_MUTED = '#64748b';
const INPUT_BG   = '#1e293b';

export default function GenerateModal({ initialDir, onConfirm, onClose }) {
  const [typedDir, setTypedDir]     = useState(initialDir || '');
  const [browsePath, setBrowsePath] = useState(null);   // null = browser not loaded yet
  const [listing, setListing]       = useState(null);   // { path, parent, dirs }
  const [loading, setLoading]       = useState(false);
  const [browseOpen, setBrowseOpen] = useState(false);
  const [newFolderMode, setNewFolderMode] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [newFolderErr, setNewFolderErr]   = useState('');
  const newFolderRef = useRef(null);

  // Fetch directory listing from the server
  const fetchListing = useCallback(async (path) => {
    setLoading(true);
    setNewFolderMode(false);
    setNewFolderName('');
    setNewFolderErr('');
    try {
      const url = path ? `/api/fs/browse?path=${encodeURIComponent(path)}` : '/api/fs/browse';
      const res = await fetch(url);
      if (!res.ok) throw new Error('browse error');
      const data = await res.json();
      setListing(data);
      setBrowsePath(data.path);
      // Sync text input to browsed path
      setTypedDir(data.path);
    } catch {
      // ignore — leave existing listing
    } finally {
      setLoading(false);
    }
  }, []);

  // Open browse panel starting from the current typed path (or home)
  const openBrowse = useCallback(() => {
    setBrowseOpen(true);
    fetchListing(typedDir.trim() || null);
  }, [fetchListing, typedDir]);

  // Focus new-folder input when it appears
  useEffect(() => {
    if (newFolderMode && newFolderRef.current) newFolderRef.current.focus();
  }, [newFolderMode]);

  const handleCreateFolder = useCallback(async () => {
    const name = newFolderName.trim();
    if (!name) return;
    const fullPath = `${browsePath}/${name}`;
    try {
      const res = await fetch('/api/fs/mkdir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: fullPath }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setNewFolderErr(d.detail ?? 'Could not create folder');
        return;
      }
      // Navigate into the new folder
      await fetchListing(fullPath);
      setNewFolderMode(false);
      setNewFolderName('');
    } catch (e) {
      setNewFolderErr(String(e));
    }
  }, [browsePath, newFolderName, fetchListing]);

  const handleConfirm = useCallback(() => {
    const dir = (browseOpen ? browsePath : typedDir).trim();
    if (dir) onConfirm(dir);
  }, [browseOpen, browsePath, typedDir, onConfirm]);

  const confirmDir = browseOpen ? browsePath : typedDir.trim();

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9000,
        background: 'rgba(0,0,0,0.75)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: PANEL_BG,
        border: `1px solid ${BORDER_CLR}`,
        borderRadius: 12,
        padding: 24,
        width: 540,
        maxWidth: '92vw',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 24px 80px rgba(0,0,0,0.8)',
      }}>
        {/* ── Header ── */}
        <div style={{ fontSize: 15, fontWeight: 700, color: TEXT, marginBottom: 6 }}>
          Generate Subgraph Files
        </div>
        <div style={{ fontSize: 12, color: TEXT_MUTED, marginBottom: 18, lineHeight: 1.6 }}>
          Choose where to write the generated files. A{' '}
          <code style={{ fontSize: 11, background: '#1e293b', padding: '1px 5px', borderRadius: 3, color: ACCENT_LT }}>howto.md</code>{' '}
          deployment guide and{' '}
          <code style={{ fontSize: 11, background: '#1e293b', padding: '1px 5px', borderRadius: 3, color: ACCENT_LT }}>package.json</code>{' '}
          will be included. The directory is created if it doesn't exist.
        </div>

        {/* ── Path input row ── */}
        <label style={{ fontSize: 10, color: TEXT_MUTED, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', marginBottom: 5 }}>
          Output directory
        </label>
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          <input
            autoFocus={!browseOpen}
            value={browseOpen ? (browsePath ?? '') : typedDir}
            onChange={(e) => { if (!browseOpen) setTypedDir(e.target.value); }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && confirmDir) handleConfirm();
              if (e.key === 'Escape') onClose();
            }}
            readOnly={browseOpen}
            placeholder="/home/you/my-subgraph"
            style={{
              flex: 1,
              background: INPUT_BG,
              border: `1px solid ${BORDER_CLR}`,
              borderRadius: 6,
              padding: '7px 10px',
              color: browseOpen ? TEXT_MUTED : TEXT,
              fontSize: 12,
              fontFamily: 'ui-monospace, monospace',
              outline: 'none',
              minWidth: 0,
            }}
          />
          <button
            type="button"
            onClick={browseOpen ? () => { setBrowseOpen(false); } : openBrowse}
            style={{
              padding: '7px 13px', borderRadius: 6, fontSize: 12, fontWeight: 600,
              background: browseOpen ? '#1e293b' : '#1e293b',
              border: `1px solid ${browseOpen ? ACCENT : BORDER_CLR}`,
              color: browseOpen ? ACCENT_LT : TEXT_MUTED,
              cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
              display: 'flex', alignItems: 'center', gap: 5,
            }}
          >
            <FolderOpen size={13} />
            {browseOpen ? 'Type path' : 'Browse…'}
          </button>
        </div>

        {/* ── File browser panel ── */}
        {browseOpen && (
          <div style={{
            flex: 1,
            border: `1px solid ${BORDER_CLR}`,
            borderRadius: 8,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            marginBottom: 14,
            minHeight: 0,
          }}>
            {/* Browser toolbar */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '7px 10px',
              background: '#1a2744',
              borderBottom: `1px solid ${BORDER_CLR}`,
              flexShrink: 0,
            }}>
              <button
                type="button"
                onClick={() => listing?.parent && fetchListing(listing.parent)}
                disabled={!listing?.parent || loading}
                title="Go up"
                style={{
                  background: 'none', border: 'none', cursor: listing?.parent ? 'pointer' : 'default',
                  color: listing?.parent ? TEXT : TEXT_MUTED, display: 'flex', alignItems: 'center', padding: 2,
                  opacity: listing?.parent ? 1 : 0.3,
                }}
              >
                <ChevronUp size={14} />
              </button>
              <span style={{ flex: 1, fontSize: 11, color: TEXT_MUTED, fontFamily: 'ui-monospace, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {listing?.path ?? '…'}
              </span>
              <button
                type="button"
                onClick={() => { setNewFolderMode(true); setNewFolderErr(''); setNewFolderName(''); }}
                title="New folder here"
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: TEXT_MUTED, display: 'flex', alignItems: 'center', padding: 2,
                }}
              >
                <FolderPlus size={14} />
              </button>
            </div>

            {/* New folder input */}
            {newFolderMode && (
              <div style={{ padding: '6px 10px', background: '#111827', borderBottom: `1px solid ${BORDER_CLR}`, flexShrink: 0 }}>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <Folder size={13} style={{ color: TEXT_MUTED, flexShrink: 0 }} />
                  <input
                    ref={newFolderRef}
                    value={newFolderName}
                    onChange={(e) => { setNewFolderName(e.target.value); setNewFolderErr(''); }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCreateFolder();
                      if (e.key === 'Escape') setNewFolderMode(false);
                    }}
                    placeholder="New folder name"
                    style={{
                      flex: 1, background: INPUT_BG, border: `1px solid ${BORDER_CLR}`,
                      borderRadius: 4, padding: '4px 7px', color: TEXT, fontSize: 12,
                      fontFamily: 'ui-monospace, monospace', outline: 'none',
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleCreateFolder}
                    disabled={!newFolderName.trim()}
                    style={{
                      padding: '4px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                      background: newFolderName.trim() ? 'rgba(124,58,237,0.2)' : 'rgba(255,255,255,0.03)',
                      border: `1px solid ${newFolderName.trim() ? ACCENT : BORDER_CLR}`,
                      color: newFolderName.trim() ? ACCENT_LT : TEXT_MUTED,
                      cursor: newFolderName.trim() ? 'pointer' : 'not-allowed',
                    }}
                  >Create</button>
                  <button
                    type="button"
                    onClick={() => setNewFolderMode(false)}
                    style={{ background: 'none', border: 'none', color: TEXT_MUTED, cursor: 'pointer', fontSize: 16, lineHeight: 1 }}
                  >×</button>
                </div>
                {newFolderErr && (
                  <div style={{ fontSize: 11, color: '#f87171', marginTop: 4 }}>{newFolderErr}</div>
                )}
              </div>
            )}

            {/* Directory listing */}
            <div style={{ flex: 1, overflowY: 'auto', minHeight: 120, maxHeight: 260 }}>
              {loading && (
                <div style={{ padding: 16, color: TEXT_MUTED, fontSize: 12, textAlign: 'center' }}>Loading…</div>
              )}
              {!loading && listing && listing.dirs.length === 0 && (
                <div style={{ padding: 16, color: TEXT_MUTED, fontSize: 12, fontStyle: 'italic', textAlign: 'center' }}>
                  No subdirectories — use the folder icon above to create one
                </div>
              )}
              {!loading && listing && listing.dirs.map((d) => (
                <button
                  type="button"
                  key={d.path}
                  onClick={() => fetchListing(d.path)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    width: '100%', padding: '7px 12px',
                    background: 'none', border: 'none', borderBottom: `1px solid ${BORDER_CLR}`,
                    color: TEXT, fontSize: 12, cursor: 'pointer', textAlign: 'left',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#1e293b'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'none'}
                >
                  <Folder size={13} style={{ color: '#fbbf24', flexShrink: 0 }} />
                  <span style={{ flex: 1, fontFamily: 'ui-monospace, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.name}</span>
                  <ChevronRight size={11} style={{ color: TEXT_MUTED, flexShrink: 0 }} />
                </button>
              ))}
            </div>

            {/* "Select this folder" footer */}
            <div style={{
              padding: '8px 12px', background: '#111827',
              borderTop: `1px solid ${BORDER_CLR}`, flexShrink: 0,
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <span style={{ fontSize: 11, color: TEXT_MUTED, flex: 1 }}>
                Selected: <span style={{ color: TEXT, fontFamily: 'ui-monospace, monospace' }}>{browsePath ?? '—'}</span>
              </span>
            </div>
          </div>
        )}

        {/* ── Action buttons ── */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexShrink: 0 }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '7px 18px', borderRadius: 7, fontSize: 12, fontWeight: 600,
              background: '#1e293b', border: `1px solid ${BORDER_CLR}`,
              color: TEXT_MUTED, cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!confirmDir}
            style={{
              padding: '7px 18px', borderRadius: 7, fontSize: 12, fontWeight: 600,
              background: confirmDir ? 'rgba(124,58,237,0.28)' : 'rgba(255,255,255,0.03)',
              border: `1px solid ${confirmDir ? ACCENT : BORDER_CLR}`,
              color: confirmDir ? ACCENT_LT : TEXT_MUTED,
              cursor: confirmDir ? 'pointer' : 'not-allowed',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <Zap size={12} />
            Generate
          </button>
        </div>
      </div>
    </div>
  );
}
