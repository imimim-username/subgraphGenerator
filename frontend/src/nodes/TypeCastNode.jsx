/**
 * TypeCastNode
 *
 * Convert between compatible Graph/AssemblyScript types.
 *
 * Supported casts and generated code:
 *   BigInt  → Int     : value.toI32()
 *   Bytes   → String  : value.toHexString()
 *   Bytes   → Address : Address.fromBytes(value)
 *   String  → Bytes   : Bytes.fromHexString(value)
 *   BigInt  → String  : value.toString()
 *   Address → String  : value.toHexString()
 *   Address → Bytes   : value as Bytes
 *
 * Input:  value (fromType)
 * Output: result (toType)
 *
 * Click the header to collapse/expand the node body.
 */

import { useCallback, useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import { ArrowRightLeft, ChevronDown, ChevronUp } from 'lucide-react';

const HEADER_BG = '#1e3a5f'; // custom dark-blue

export const CAST_OPTIONS = [
  { from: 'BigInt',   to: 'Int',     label: 'BigInt → Int',     code: '{v}.toI32()' },
  { from: 'BigInt',   to: 'String',  label: 'BigInt → String',  code: '{v}.toString()' },
  { from: 'Bytes',    to: 'String',  label: 'Bytes → String',   code: '{v}.toHexString()' },
  { from: 'Bytes',    to: 'Address', label: 'Bytes → Address',  code: 'Address.fromBytes({v})' },
  { from: 'String',   to: 'Bytes',   label: 'String → Bytes',   code: 'Bytes.fromHexString({v})' },
  { from: 'Address',  to: 'String',  label: 'Address → String', code: '{v}.toHexString()' },
  { from: 'Address',  to: 'Bytes',   label: 'Address → Bytes',  code: '{v} as Bytes' },
];

// Port class helper
function portClass(type) {
  switch (type) {
    case 'Bytes':
    case 'Address': return 'event-port';    // amber — raw byte types
    case 'BigInt':
    case 'Int':     return 'field-port';    // blue — numeric
    case 'String':  return 'read-port';     // green — string
    default:        return 'implicit-port';
  }
}

export default function TypeCastNode({ id, data, selected }) {
  const { castIndex = 0, onChange, onDelete } = data;
  const [collapsed, setCollapsed] = useState(false);
  const cast = CAST_OPTIONS[castIndex] ?? CAST_OPTIONS[0];

  const handleChange = useCallback(
    (e) => onChange({ castIndex: Number(e.target.value) }),
    [onChange]
  );

  return (
    <div className={`sg-node${selected ? ' sg-node--selected' : ''}`} style={{ minWidth: 200 }}>
      {/* Header (click to collapse/expand) */}
      <div
        className="sg-node__header"
        style={{ background: HEADER_BG, cursor: 'grab', userSelect: 'none' }}
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Expand node' : 'Collapse node'}
      >
        <ArrowRightLeft size={12} />
        Type Cast
        <div style={{ flex: 1 }} />
        {collapsed && (
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)' }}>
            {cast.label}
          </span>
        )}
        {selected && onDelete && (
          <button
            className="nodrag"
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            title="Delete node"
            style={{ background: 'none', border: 'none', color: 'rgba(255,100,100,0.7)', cursor: 'pointer', padding: '0 2px', fontSize: 15, lineHeight: 1, display: 'flex', alignItems: 'center' }}
          >×</button>
        )}
        {collapsed ? <ChevronDown size={11} /> : <ChevronUp size={11} />}
      </div>

      {!collapsed && (
        <div className="sg-node__body">
          {/* Cast selector */}
          <div className="sg-node__section">
            <select
              className="nodrag"
              value={castIndex}
              onChange={handleChange}
              style={{
                width: '100%',
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid var(--border)',
                borderRadius: 4,
                padding: '4px 6px',
                color: 'var(--text-primary)',
                fontSize: 12,
                outline: 'none',
              }}
            >
              {CAST_OPTIONS.map((c, i) => (
                <option key={i} value={i}>{c.label}</option>
              ))}
            </select>
          </div>

          {/* Generated code preview */}
          <div className="sg-node__section">
            <div
              style={{
                fontFamily: 'ui-monospace, monospace',
                fontSize: 10,
                color: 'var(--text-muted)',
                background: 'rgba(0,0,0,0.25)',
                borderRadius: 4,
                padding: '4px 6px',
              }}
            >
              {cast.code.replace('{v}', 'value')}
            </div>
          </div>

          <div className="sg-node__divider" />

          {/* Input port */}
          <div className="sg-node__port-row sg-node__port-row--left" style={{ position: 'relative' }}>
            <Handle
              type="target"
              position={Position.Left}
              id="value"
              className={portClass(cast.from)}
              style={{ left: -6 }}
            />
            <span className="sg-node__port-label">value</span>
            <span className="sg-node__port-type">{cast.from}</span>
          </div>

          <div className="sg-node__divider" />

          {/* Output port */}
          <div className="sg-node__port-row" style={{ position: 'relative' }}>
            <span className="sg-node__port-type">{cast.to}</span>
            <span className="sg-node__port-label">result</span>
            <Handle
              type="source"
              position={Position.Right}
              id="result"
              className={portClass(cast.to)}
              style={{ right: -6 }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
