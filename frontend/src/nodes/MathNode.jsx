/**
 * MathNode
 *
 * Binary arithmetic operation on two numeric inputs.
 * Operations: add, subtract, multiply, divide, mod, pow
 *
 * Inputs:  left  (BigInt | Int)
 *          right (BigInt | Int)
 * Output:  result
 *
 * Generated AssemblyScript (example for add):
 *   let result = left.plus(right)   // BigInt uses .plus(), not +
 *
 * Click the header to collapse/expand the node body.
 */

import { useCallback, useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Calculator, ChevronDown, ChevronUp } from 'lucide-react';

const HEADER_BG = '#78350f'; // amber-900

const OPERATIONS = [
  { value: 'add',      label: 'Add',      symbol: '+' },
  { value: 'subtract', label: 'Subtract', symbol: '−' },
  { value: 'multiply', label: 'Multiply', symbol: '×' },
  { value: 'divide',   label: 'Divide',   symbol: '÷' },
  { value: 'mod',      label: 'Modulo',   symbol: '%' },
  { value: 'pow',      label: 'Power',    symbol: '^' },
];

// Solidity/Graph BigInt method names used in code generation
export const MATH_AS_OPS = {
  add:      'plus',
  subtract: 'minus',
  multiply: 'times',
  divide:   'div',
  mod:      'mod',
  pow:      'pow',
};

function InputPort({ id, label, typeHint }) {
  return (
    <div className="sg-node__port-row sg-node__port-row--left" style={{ position: 'relative' }}>
      <Handle
        type="target"
        position={Position.Left}
        id={id}
        className="field-port"
        style={{ left: -6 }}
      />
      <span className="sg-node__port-label">{label}</span>
      <span className="sg-node__port-type">{typeHint}</span>
    </div>
  );
}

function OutputPort({ id, label, typeHint }) {
  return (
    <div className="sg-node__port-row" style={{ position: 'relative' }}>
      <span className="sg-node__port-type">{typeHint}</span>
      <span className="sg-node__port-label">{label}</span>
      <Handle
        type="source"
        position={Position.Right}
        id={id}
        className="field-port"
        style={{ right: -6 }}
      />
    </div>
  );
}

export default function MathNode({ id, data, selected }) {
  const { operation = 'add', onChange, onDelete } = data;
  const [collapsed, setCollapsed] = useState(false);

  const handleOpChange = useCallback(
    (e) => onChange({ operation: e.target.value }),
    [onChange]
  );

  const currentOp = OPERATIONS.find((o) => o.value === operation) ?? OPERATIONS[0];

  return (
    <div className={`sg-node${selected ? ' sg-node--selected' : ''}`} style={{ minWidth: 180 }}>
      {/* Header (click to collapse/expand) */}
      <div
        className="sg-node__header"
        style={{ background: HEADER_BG, cursor: 'grab', userSelect: 'none' }}
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Expand node' : 'Collapse node'}
      >
        <Calculator size={12} />
        Math
        <div style={{ flex: 1 }} />
        {collapsed && (
          <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.7)', marginRight: 2 }}>
            {currentOp.symbol}
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
          {/* Operation picker */}
          <div className="sg-node__section" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              style={{
                fontSize: 22,
                fontWeight: 700,
                color: 'var(--port-event)',
                width: 28,
                textAlign: 'center',
                lineHeight: 1,
              }}
            >
              {currentOp.symbol}
            </span>
            <select
              className="nodrag"
              value={operation}
              onChange={handleOpChange}
              style={{
                flex: 1,
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid var(--border)',
                borderRadius: 4,
                padding: '4px 6px',
                color: 'var(--text-primary)',
                fontSize: 12,
                outline: 'none',
              }}
            >
              {OPERATIONS.map((op) => (
                <option key={op.value} value={op.value}>
                  {op.label}
                </option>
              ))}
            </select>
          </div>

          <div className="sg-node__divider" />

          {/* Input ports */}
          <InputPort id="left"  label="left"  typeHint="BigInt" />
          <InputPort id="right" label="right" typeHint="BigInt" />

          <div className="sg-node__divider" />

          {/* Output port */}
          <OutputPort id="result" label="result" typeHint="BigInt" />
        </div>
      )}
    </div>
  );
}
