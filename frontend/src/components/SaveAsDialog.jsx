/**
 * SaveAsDialog
 *
 * Minimal modal for naming a canvas before saving.
 * Shown when the user clicks "Save As" or "Save" on an untitled canvas.
 */

import { useEffect, useRef, useState } from 'react';
import { Save, X } from 'lucide-react';

export default function SaveAsDialog({ initialName, onConfirm, onClose }) {
  const [name, setName] = useState(initialName || '');
  const inputRef = useRef(null);

  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 50);
  }, []);

  const handleConfirm = () => {
    const n = name.trim();
    if (!n) return;
    onConfirm(n);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter')  handleConfirm();
    if (e.key === 'Escape') onClose();
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 2000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.72)',
        backdropFilter: 'blur(4px)',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: 10,
          width: 360,
          boxShadow: '0 25px 60px rgba(0,0,0,0.65)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '12px 16px',
            borderBottom: '1px solid #1e293b',
          }}
        >
          <Save size={14} style={{ color: '#7c3aed' }} />
          <span style={{ fontWeight: 700, fontSize: 14, color: '#e2e8f0', flex: 1 }}>Save As</span>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#475569', cursor: 'pointer', padding: 2, display: 'flex' }}
          >
            <X size={15} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: '18px 16px 16px' }}>
          <label
            style={{
              display: 'block',
              fontSize: 11,
              color: '#64748b',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.07em',
              marginBottom: 6,
            }}
          >
            Canvas name
          </label>
          <input
            ref={inputRef}
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. my-alchemist-subgraph"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              background: 'rgba(0,0,0,0.35)',
              border: '1px solid #334155',
              borderRadius: 5,
              padding: '6px 10px',
              color: '#e2e8f0',
              fontSize: 13,
              outline: 'none',
            }}
          />
          <div
            style={{
              display: 'flex',
              gap: 8,
              justifyContent: 'flex-end',
              marginTop: 16,
            }}
          >
            <button
              onClick={onClose}
              style={{
                padding: '6px 14px',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid #334155',
                color: '#94a3b8',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={!name.trim()}
              style={{
                padding: '6px 18px',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 600,
                cursor: name.trim() ? 'pointer' : 'not-allowed',
                background: name.trim() ? 'rgba(124,58,237,0.2)' : 'rgba(255,255,255,0.03)',
                border: `1px solid ${name.trim() ? '#7c3aed' : '#334155'}`,
                color: name.trim() ? '#a78bfa' : '#475569',
                opacity: name.trim() ? 1 : 0.6,
              }}
            >
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
