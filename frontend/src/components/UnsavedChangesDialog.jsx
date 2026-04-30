/**
 * UnsavedChangesDialog
 *
 * Standard "you have unsaved changes" prompt shown before New / Open.
 * Offers three choices: Save, Don't Save (discard), Cancel.
 */

import { AlertTriangle } from 'lucide-react';

const BTN = {
  padding: '6px 16px',
  borderRadius: 6,
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  border: '1px solid transparent',
};

export default function UnsavedChangesDialog({ filename, onSave, onDiscard, onCancel }) {
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
    >
      <div
        style={{
          background: '#0f172a',
          border: '1px solid #334155',
          borderRadius: 10,
          width: 380,
          padding: '24px 24px 20px',
          boxShadow: '0 25px 60px rgba(0,0,0,0.65)',
        }}
      >
        {/* Icon + title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <AlertTriangle size={18} style={{ color: '#f59e0b', flexShrink: 0 }} />
          <span style={{ fontWeight: 700, fontSize: 15, color: '#e2e8f0' }}>Unsaved Changes</span>
        </div>

        {/* Message */}
        <p style={{ color: '#94a3b8', fontSize: 13, margin: '0 0 22px 0', lineHeight: 1.6 }}>
          {filename ? (
            <>
              Do you want to save changes to{' '}
              <strong style={{ color: '#e2e8f0' }}>{filename}</strong>?
            </>
          ) : (
            'Do you want to save your changes before continuing?'
          )}
        </p>

        {/* Buttons — right-aligned, matching standard OS ordering */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            style={{
              ...BTN,
              background: 'rgba(255,255,255,0.04)',
              borderColor: '#334155',
              color: '#94a3b8',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onDiscard}
            style={{
              ...BTN,
              background: 'rgba(239,68,68,0.12)',
              borderColor: '#7f1d1d',
              color: '#f87171',
            }}
          >
            Don&apos;t Save
          </button>
          <button
            onClick={onSave}
            style={{
              ...BTN,
              background: 'rgba(124,58,237,0.2)',
              borderColor: '#7c3aed',
              color: '#a78bfa',
            }}
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
