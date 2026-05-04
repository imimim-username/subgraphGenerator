/**
 * ValidationPanel — collapsible sidebar showing validation issues.
 *
 * Props:
 *   issues       Array of issue objects {level, code, message, node_id, edge_id}
 *   hasErrors    bool
 *   isValidating bool
 *   onIssueClick (issue) => void  — called when user clicks an issue row
 */

import React, { useState } from 'react';

const LEVEL_STYLES = {
  error: {
    dot: '#ef4444',
    bg: 'rgba(239,68,68,0.08)',
    border: 'rgba(239,68,68,0.25)',
    label: 'ERR',
    labelColor: '#fca5a5',
  },
  warning: {
    dot: '#f59e0b',
    bg: 'rgba(245,158,11,0.08)',
    border: 'rgba(245,158,11,0.25)',
    label: 'WRN',
    labelColor: '#fcd34d',
  },
};

export function ValidationPanel({ issues = [], hasErrors, isValidating, onIssueClick }) {
  const [collapsed, setCollapsed] = useState(false);

  const errors = issues.filter((i) => i.level === 'error');
  const warnings = issues.filter((i) => i.level === 'warning');

  // Header badge
  const badgeText = issues.length === 0
    ? (isValidating ? '…' : '✓')
    : `${errors.length > 0 ? `${errors.length}E` : ''}${errors.length > 0 && warnings.length > 0 ? ' ' : ''}${warnings.length > 0 ? `${warnings.length}W` : ''}`;
  const badgeColor = errors.length > 0 ? '#ef4444' : warnings.length > 0 ? '#f59e0b' : '#22c55e';

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 16,
        left: 56,
        zIndex: 20,
        width: collapsed ? 'auto' : 320,
        background: '#0f172a',
        border: '1px solid #1e293b',
        borderRadius: 8,
        boxShadow: '0 4px 24px rgba(0,0,0,0.5)',
        fontFamily: 'ui-monospace, "Cascadia Code", monospace',
        fontSize: 12,
        color: '#e2e8f0',
        overflow: 'hidden',
        transition: 'width 0.15s',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          width: '100%',
          padding: '6px 10px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: '#94a3b8',
          textAlign: 'left',
        }}
      >
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          minWidth: 22,
          height: 18,
          borderRadius: 10,
          background: badgeColor,
          color: '#fff',
          fontSize: 10,
          fontWeight: 700,
          padding: '0 5px',
        }}>
          {badgeText}
        </span>
        {!collapsed && (
          <span style={{ flex: 1, fontSize: 11, color: '#64748b' }}>
            Validation {isValidating ? '(checking…)' : ''}
          </span>
        )}
        <span style={{ fontSize: 10, color: '#475569' }}>{collapsed ? '▲' : '▼'}</span>
      </button>

      {/* Issue list */}
      {!collapsed && (
        <div style={{ maxHeight: 260, overflowY: 'auto' }}>
          {issues.length === 0 && !isValidating && (
            <div style={{ padding: '8px 12px', color: '#22c55e', fontSize: 11 }}>
              No issues found
            </div>
          )}
          {issues.map((issue, idx) => {
            const s = LEVEL_STYLES[issue.level] ?? LEVEL_STYLES.warning;
            return (
              <div
                key={idx}
                onClick={() => onIssueClick?.(issue)}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 8,
                  padding: '5px 10px',
                  background: s.bg,
                  borderTop: `1px solid ${s.border}`,
                  cursor: onIssueClick ? 'pointer' : 'default',
                }}
              >
                <span style={{
                  marginTop: 2,
                  flexShrink: 0,
                  fontSize: 9,
                  fontWeight: 700,
                  color: s.labelColor,
                  letterSpacing: '0.05em',
                }}>
                  {s.label}
                </span>
                <div style={{ flex: 1, lineHeight: 1.4 }}>
                  <div style={{ color: '#cbd5e1', fontSize: 11 }}>{issue.message}</div>
                  <div style={{ color: '#475569', fontSize: 10, marginTop: 1 }}>{issue.code}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
