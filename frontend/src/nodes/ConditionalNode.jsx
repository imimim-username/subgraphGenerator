/**
 * ConditionalNode
 *
 * Guards a value behind a boolean condition.
 * If the condition is false at runtime, the event handler returns early
 * (the entity save is skipped entirely for that event).
 *
 * Inputs:  condition (Boolean)
 *          value     (any)
 * Output:  value     (passes through when condition is true)
 *
 * Generated AssemblyScript (inside a handler):
 *   if (!condition) return
 *   // ... rest of handler uses value normally
 */

import { useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import { GitBranch, ChevronDown, ChevronUp } from 'lucide-react';

const HEADER_BG = '#4c1d95'; // violet-900

export default function ConditionalNode({ id, data, selected }) {
  const { onDelete } = data;
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={`sg-node${selected ? ' sg-node--selected' : ''}`} style={{ minWidth: 190 }}>
      {/* Header (click to collapse/expand) */}
      <div
        className="sg-node__header"
        style={{ background: HEADER_BG, cursor: 'grab', userSelect: 'none' }}
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Expand node' : 'Collapse node'}
      >
        <GitBranch size={12} />
        Conditional
        <div style={{ flex: 1 }} />
        {collapsed && (
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)', fontFamily: 'ui-monospace, monospace' }}>
            if (!cond) return
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
        {/* Description */}
        <div className="sg-node__section" style={{ color: 'var(--text-muted)', fontSize: 11 }}>
          Skips the handler if condition is{' '}
          <span style={{ fontFamily: 'ui-monospace, monospace', color: '#f87171' }}>false</span>.
        </div>

        {/* Code preview */}
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
            {'if (!condition) return'}
          </div>
        </div>

        <div className="sg-node__divider" />

        {/* Input: condition */}
        <div className="sg-node__port-row sg-node__port-row--left" style={{ position: 'relative' }}>
          <Handle
            type="target"
            position={Position.Left}
            id="condition"
            className="implicit-port"
            style={{ left: -6 }}
          />
          <span className="sg-node__port-label">condition</span>
          <span className="sg-node__port-type">Boolean</span>
        </div>

        {/* Input: value */}
        <div className="sg-node__port-row sg-node__port-row--left" style={{ position: 'relative' }}>
          <Handle
            type="target"
            position={Position.Left}
            id="value"
            className="implicit-port"
            style={{ left: -6 }}
          />
          <span className="sg-node__port-label">value</span>
          <span className="sg-node__port-type">any</span>
        </div>

        <div className="sg-node__divider" />

        {/* Output: value (pass-through) */}
        <div className="sg-node__port-row" style={{ position: 'relative' }}>
          <span className="sg-node__port-type">any</span>
          <span className="sg-node__port-label">value</span>
          <Handle
            type="source"
            position={Position.Right}
            id="value-out"
            className="implicit-port"
            style={{ right: -6 }}
          />
        </div>
      </div>
      )}
    </div>
  );
}
