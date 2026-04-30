/**
 * ContractReadNode
 *
 * Represents a call to a view/pure function on a contract inside an event
 * handler, using The Graph's generated contract bindings.
 *
 * The user:
 *   1. Picks a Contract node (by node ID) — determines which ABI binding to use
 *   2. Picks a read function from that contract's ABI
 *   3. Optionally wires an Address into "address" port to specify which deployed
 *      instance to call — defaults to event.address if left unwired
 *   4. Wires upstream values into the function's input ports
 *   5. Wires the output port(s) downstream into Entity fields or transform nodes
 *
 * Generated AssemblyScript (example, address port wired):
 *   let contract = MYT.bind(myWiredAddress)
 *   let balance = contract.balanceOf(event.params.from)
 *
 * Generated AssemblyScript (address port NOT wired — falls back to event.address):
 *   let contract = ERC20.bind(event.address)
 *   let balance = contract.balanceOf(event.params.from)
 *
 * Input ports:  "address" (optional bind address) + one per function argument
 * Output ports: one per return value
 */

import { useCallback, useEffect, useState } from 'react';
import { Handle, Position, useUpdateNodeInternals } from '@xyflow/react';
import { BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import { useReactFlow } from '@xyflow/react';

const HEADER_BG = '#064e3b'; // green-950

// Colour helpers — mirror the index.css port colour scheme
function portClass(graphType) {
  switch (graphType) {
    case 'BigInt':
    case 'Int':
    case 'BigDecimal': return 'field-port';   // blue
    case 'Bytes':
    case 'Address':    return 'event-port';   // amber
    case 'String':
    case 'Boolean':    return 'read-port';    // green
    default:           return 'implicit-port';
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function InputPort({ portId, label, graphType }) {
  return (
    <div className="sg-node__port-row sg-node__port-row--left" style={{ position: 'relative' }}>
      <Handle
        type="target"
        position={Position.Left}
        id={portId}
        className={portClass(graphType)}
        style={{ left: -6 }}
      />
      <span className="sg-node__port-label">{label}</span>
      <span className="sg-node__port-type">{graphType}</span>
    </div>
  );
}

function OutputPort({ portId, label, graphType }) {
  return (
    <div className="sg-node__port-row" style={{ position: 'relative' }}>
      <span className="sg-node__port-type">{graphType}</span>
      <span className="sg-node__port-label">{label}</span>
      <Handle
        type="source"
        position={Position.Right}
        id={portId}
        className={portClass(graphType)}
        style={{ right: -6 }}
      />
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ContractReadNode({ id, data, selected }) {
  const { contractNodeId = '', fnIndex = 0, onChange, onDelete } = data;
  const { getNodes } = useReactFlow();
  const [collapsed, setCollapsed] = useState(false);
  const updateNodeInternals = useUpdateNodeInternals();

  // Re-register handles whenever the selected function changes (different input/output ports).
  useEffect(() => {
    updateNodeInternals(id);
  }, [id, contractNodeId, fnIndex, collapsed, updateNodeInternals]);

  // Find all contract nodes on the canvas
  const contractNodes = getNodes().filter((n) => n.type === 'contract' && n.data.name);

  // The currently selected contract node
  const selectedContract = contractNodes.find((n) => n.id === contractNodeId) ?? contractNodes[0];

  // Auto-persist the fallback selection: if contractNodeId is empty but we resolved a contract,
  // save the real ID immediately so the validator (and saved state) reflect the actual selection.
  useEffect(() => {
    if (!contractNodeId && selectedContract?.id) {
      onChange({ contractNodeId: selectedContract.id });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contractNodeId, selectedContract?.id]);
  const readFunctions = selectedContract?.data?.readFunctions ?? [];
  const selectedFn = readFunctions[fnIndex] ?? null;

  const handleContractChange = useCallback(
    (e) => onChange({ contractNodeId: e.target.value, fnIndex: 0 }),
    [onChange]
  );

  const handleFnChange = useCallback(
    (e) => onChange({ fnIndex: Number(e.target.value) }),
    [onChange]
  );

  // Code preview — show the auto-resolved bind address when available
  const contractName = selectedContract?.data?.name || 'Contract';
  const fnSig = selectedFn?.signature ?? '…';
  const instances = selectedContract?.data?.instances ?? [];
  const firstAddr = instances[0]?.address;
  const bindExpr = firstAddr
    ? `Address.fromString("${firstAddr.slice(0, 6)}…")`
    : 'event.address';
  const codePreview = `let c = ${contractName}.bind(${bindExpr})\nlet result = c.${fnSig}`;

  const collapsedSummary = selectedFn?.signature ?? (selectedContract?.data?.name ?? 'no contract');

  return (
    <div className={`sg-node${selected ? ' sg-node--selected' : ''}`} style={{ minWidth: 220 }}>
      {/* Header (click to collapse/expand) */}
      <div
        className="sg-node__header"
        style={{ background: HEADER_BG, cursor: 'grab', userSelect: 'none' }}
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Expand node' : 'Collapse node'}
      >
        <BookOpen size={12} />
        Contract Read
        <div style={{ flex: 1 }} />
        {collapsed && (
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)', maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'ui-monospace, monospace' }}>
            {collapsedSummary}
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
        {/* Contract selector */}
        <div className="sg-node__section">
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Contract
          </div>
          {contractNodes.length === 0 ? (
            <div style={{ fontSize: 11, color: '#f87171', fontStyle: 'italic' }}>
              No contract nodes with a name found
            </div>
          ) : (
            <select
              className="nodrag"
              value={contractNodeId || selectedContract?.id || ''}
              onChange={handleContractChange}
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
              {contractNodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.data.name} ({n.id})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Function selector */}
        <div className="sg-node__section">
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Read Function
          </div>
          {readFunctions.length === 0 ? (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>
              {selectedContract ? 'Contract has no read functions' : 'Select a contract first'}
            </div>
          ) : (
            <select
              className="nodrag"
              value={fnIndex}
              onChange={handleFnChange}
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
              {readFunctions.map((fn, i) => (
                <option key={i} value={i}>{fn.signature}</option>
              ))}
            </select>
          )}
        </div>

        {/* Code preview */}
        {selectedFn && (
          <div className="sg-node__section">
            <div
              style={{
                fontFamily: 'ui-monospace, monospace',
                fontSize: 9,
                color: 'var(--text-muted)',
                background: 'rgba(0,0,0,0.25)',
                borderRadius: 4,
                padding: '4px 6px',
                whiteSpace: 'pre',
                lineHeight: 1.5,
              }}
            >
              {codePreview}
            </div>
          </div>
        )}

        {/* Bind-address port — always shown when a fn is selected */}
        {selectedFn && (
          <>
            <div className="sg-node__divider" />
            <InputPort
              portId="bind-address"
              label="address"
              graphType="Address"
            />
          </>
        )}

        {/* Input ports — one per fn argument */}
        {selectedFn && selectedFn.inputs.length > 0 && (
          <>
            <div className="sg-node__divider" />
            {selectedFn.inputs.map((inp) => (
              <InputPort
                key={`in-${inp.name}`}
                portId={`in-${inp.name}`}
                label={inp.name}
                graphType={inp.graph_type}
              />
            ))}
          </>
        )}

        {/* Output ports — one per return value */}
        {selectedFn && selectedFn.outputs.length > 0 && (
          <>
            <div className="sg-node__divider" />
            {selectedFn.outputs.map((out) => (
              <OutputPort
                key={`out-${out.name}`}
                portId={`out-${out.name}`}
                label={out.name}
                graphType={out.graph_type}
              />
            ))}
          </>
        )}

        {!selectedFn && (
          <div className="sg-node__section" style={{ color: 'var(--text-muted)', fontSize: 11, fontStyle: 'italic' }}>
            Select a contract and function to reveal ports
          </div>
        )}
      </div>
      )}
    </div>
  );
}
