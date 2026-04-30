/**
 * StringConcatNode
 *
 * Concatenate two String values.
 *
 * Inputs:  left  (String)
 *          right (String)
 * Output:  result (String)
 *
 * Generated AssemblyScript:
 *   let result = left.concat(right)
 *   // or with a separator: left.concat(sep).concat(right)
 *
 * Click the header to collapse/expand the node body.
 */

import { useCallback, useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import { TextCursorInput, ChevronDown, ChevronUp } from 'lucide-react';

const HEADER_BG = '#14532d'; // green-900

export default function StringConcatNode({ id, data, selected }) {
  const { separator = '', onChange, onDelete } = data;
  const [collapsed, setCollapsed] = useState(false);

  const handleSepChange = useCallback(
    (e) => onChange({ separator: e.target.value }),
    [onChange]
  );

  // Code preview
  const codePreview = separator
    ? `left.concat("${separator}").concat(right)`
    : 'left.concat(right)';

  return (
    <div className={`sg-node${selected ? ' sg-node--selected' : ''}`} style={{ minWidth: 200 }}>
      {/* Header (click to collapse/expand) */}
      <div
        className="sg-node__header"
        style={{ background: HEADER_BG, cursor: 'grab', userSelect: 'none' }}
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Expand node' : 'Collapse node'}
      >
        <TextCursorInput size={12} />
        String Concat
        <div style={{ flex: 1 }} />
        {collapsed && separator && (
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)', fontFamily: 'ui-monospace, monospace' }}>
            "{separator}"
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
          {/* Optional separator */}
          <div className="sg-node__section">
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Separator (optional)
            </div>
            <input
              className="sg-node__input nodrag"
              placeholder='e.g. "-" or leave blank'
              value={separator}
              onChange={handleSepChange}
            />
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
                wordBreak: 'break-all',
              }}
            >
              {codePreview}
            </div>
          </div>

          <div className="sg-node__divider" />

          {/* Input ports */}
          <div className="sg-node__port-row sg-node__port-row--left" style={{ position: 'relative' }}>
            <Handle type="target" position={Position.Left} id="left" className="read-port" style={{ left: -6 }} />
            <span className="sg-node__port-label">left</span>
            <span className="sg-node__port-type">String</span>
          </div>
          <div className="sg-node__port-row sg-node__port-row--left" style={{ position: 'relative' }}>
            <Handle type="target" position={Position.Left} id="right" className="read-port" style={{ left: -6 }} />
            <span className="sg-node__port-label">right</span>
            <span className="sg-node__port-type">String</span>
          </div>

          <div className="sg-node__divider" />

          {/* Output port */}
          <div className="sg-node__port-row" style={{ position: 'relative' }}>
            <span className="sg-node__port-type">String</span>
            <span className="sg-node__port-label">result</span>
            <Handle type="source" position={Position.Right} id="result" className="read-port" style={{ right: -6 }} />
          </div>
        </div>
      )}
    </div>
  );
}
