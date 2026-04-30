/**
 * ContractNode
 *
 * Represents a smart contract on the canvas. The user provides:
 *   - A type name (e.g. "Alchemist")
 *   - An ABI (uploaded, pasted, or fetched from Etherscan)
 *   - One or more instances (label + address per deployment)
 *
 * Output ports are auto-generated from the ABI:
 *   - One trigger port per event (amber)  → wire to entity/aggregate "evt"
 *   - Per-parameter ports under each event (click ▶ to expand) → wire to Math / field inputs
 *   - Implicit ports: address, tx.hash, block.number, block.timestamp
 *   - One per read/view function (green)
 *
 * Click the header to collapse/expand the node body.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Handle, Position, useUpdateNodeInternals } from '@xyflow/react';
import { Upload, Clipboard, ChevronDown, ChevronUp, Zap, BookOpen, Search } from 'lucide-react';

// ── Supported EVM networks ────────────────────────────────────────────────────
const NETWORKS = [
  { value: 'mainnet',      label: 'Ethereum Mainnet' },
  { value: 'arbitrum-one', label: 'Arbitrum One' },
  { value: 'base',         label: 'Base' },
  { value: 'optimism',     label: 'Optimism' },
  { value: 'polygon',      label: 'Polygon' },
  { value: 'bnb',          label: 'BNB Chain' },
  { value: 'avalanche',    label: 'Avalanche C-Chain' },
  { value: 'gnosis',       label: 'Gnosis' },
  { value: 'linea',        label: 'Linea' },
  { value: 'scroll',       label: 'Scroll' },
];

// ── Header colour ────────────────────────────────────────────────────────────
const HEADER_BG = '#3730a3'; // indigo-800

// ── Implicit ports always available from any event handler ───────────────────
const IMPLICIT_PORTS = [
  { id: 'implicit-address',          label: 'address',          type: 'Address' },
  { id: 'implicit-instance-address', label: 'deployed address', type: 'Address' },
  { id: 'implicit-tx-hash',          label: 'tx.hash',          type: 'Bytes'   },
  { id: 'implicit-block-number',     label: 'block.number',     type: 'BigInt'  },
  { id: 'implicit-block-timestamp',  label: 'block.timestamp',  type: 'BigInt'  },
];

// ── Simple right-side port row ────────────────────────────────────────────────
function PortRow({ id, label, portType, portClass, indent = false }) {
  return (
    <div
      className="sg-node__port-row"
      style={{ position: 'relative', paddingLeft: indent ? 16 : undefined }}
    >
      {portType && (
        <span className="sg-node__port-type" style={{ fontSize: indent ? 9 : undefined, opacity: indent ? 0.7 : 1 }}>
          {portType}
        </span>
      )}
      <span className="sg-node__port-label" style={{ fontSize: indent ? 10 : undefined, color: indent ? 'var(--text-muted)' : undefined }}>
        {label}
      </span>
      <Handle
        type="source"
        position={Position.Right}
        id={id}
        className={portClass}
        style={{ right: -6, opacity: indent ? 0.8 : 1 }}
      />
    </div>
  );
}

// ── Event port group: trigger port + expandable per-param ports ───────────────
function EventPortGroup({ ev }) {
  const [open, setOpen] = useState(false);
  const hasParams = ev.params && ev.params.length > 0;

  return (
    <>
      {/* Event trigger row */}
      <div className="sg-node__port-row" style={{ position: 'relative' }}>
        <span className="sg-node__port-type" style={{ fontSize: 9, color: 'var(--port-event)', opacity: 0.7 }}>
          trigger
        </span>
        <span className="sg-node__port-label">{ev.name}</span>
        {hasParams && (
          <button
            className="nodrag"
            onClick={() => setOpen((v) => !v)}
            title={open ? 'Hide params' : 'Show params'}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '0 3px',
              color: open ? 'var(--port-event)' : 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
              borderRadius: 3,
            }}
          >
            {open ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
          </button>
        )}
        <Handle
          type="source"
          position={Position.Right}
          id={`event-${ev.name}`}
          className="event-port"
          style={{ right: -6 }}
        />
      </div>

      {/* Per-param ports (shown when expanded) */}
      {open && ev.params.map((p) => (
        <PortRow
          key={p.name}
          id={`event-${ev.name}-${p.name}`}
          label={p.name}
          portType={p.graph_type}
          portClass="event-port"
          indent
        />
      ))}
    </>
  );
}

export default function ContractNode({ id, data, selected }) {
  const {
    name = '', abi, events = [], readFunctions = [], collapsed = false,
    address = '', startBlock = '', network = 'mainnet',
    onChange, onDelete,
  } = data;
  const fileInputRef = useRef(null);
  const [showEvents, setShowEvents] = useState(true);
  const [showReads, setShowReads] = useState(true);
  const [abiError, setAbiError] = useState(null);
  const [pasteMode, setPasteMode] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [detecting, setDetecting] = useState(false);
  const [detectErr, setDetectErr] = useState(null);
  const updateNodeInternals = useUpdateNodeInternals();

  // Re-register handle positions after ABI load, expand/collapse, or event param expand.
  useEffect(() => {
    updateNodeInternals(id);
  }, [id, events, collapsed, showEvents, showReads, updateNodeInternals]);

  // ── Name change ────────────────────────────────────────────────────────────
  const handleNameChange = useCallback(
    (e) => onChange({ name: e.target.value }),
    [onChange]
  );

  // ── Shared ABI parse (called by both upload and paste) ────────────────────
  const parseAndApplyAbi = useCallback(
    (abiArray) => {
      return fetch('/api/abi/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ abi: abiArray }),
      })
        .then((r) => {
          if (!r.ok) return r.json().then((d) => { throw new Error(d.detail || 'Parse error'); });
          return r.json();
        })
        .then(({ events, read_functions }) => {
          onChange({ abi: abiArray, events, readFunctions: read_functions });
        });
    },
    [onChange]
  );

  // ── ABI upload ─────────────────────────────────────────────────────────────
  const handleAbiFile = useCallback(
    (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setAbiError(null);
      file.text().then((text) => {
        try {
          const parsed = JSON.parse(text);
          const abiArray = Array.isArray(parsed) ? parsed : parsed.abi;
          if (!Array.isArray(abiArray)) throw new Error('Expected an array or {abi:[…]}');
          parseAndApplyAbi(abiArray).catch((err) => setAbiError(err.message));
        } catch (err) {
          setAbiError(err.message);
        }
      });
      e.target.value = '';
    },
    [parseAndApplyAbi]
  );

  // ── ABI paste ──────────────────────────────────────────────────────────────
  const handleAbiPaste = useCallback(() => {
    setAbiError(null);
    try {
      const parsed = JSON.parse(pasteText.trim());
      const abiArray = Array.isArray(parsed) ? parsed : parsed.abi;
      if (!Array.isArray(abiArray)) throw new Error('Expected a JSON array or {abi:[…]}');
      parseAndApplyAbi(abiArray)
        .then(() => { setPasteMode(false); setPasteText(''); })
        .catch((err) => setAbiError(err.message));
    } catch (err) {
      setAbiError(err.message);
    }
  }, [pasteText, parseAndApplyAbi]);

  const closePaste = useCallback(() => {
    setPasteMode(false);
    setPasteText('');
    setAbiError(null);
  }, []);

  // ── Deployment: detect start block via RPC binary search ──────────────────
  const handleDetect = useCallback(async () => {
    const addr = (address || '').trim();
    if (!addr.startsWith('0x')) {
      setDetectErr('Enter a 0x address first');
      return;
    }
    setDetecting(true);
    setDetectErr(null);
    try {
      const net = network || 'mainnet';
      const res = await fetch(`/api/detect-start-block?address=${encodeURIComponent(addr)}&network=${encodeURIComponent(net)}`);
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? `HTTP ${res.status}`);
      }
      const { block } = await res.json();
      if (block === 0) {
        setDetectErr('No contract found at this address on ' + net);
      } else {
        onChange({ startBlock: String(block) });
        setDetectErr(null);
      }
    } catch (e) {
      setDetectErr(String(e.message ?? e));
    } finally {
      setDetecting(false);
    }
  }, [address, network, onChange]);

  const hasAbi = abi !== null;
  const collapsedSummary = name || 'unnamed';

  return (
    <div className={`sg-node${selected ? ' sg-node--selected' : ''}`} style={{ minWidth: 260 }}>
      {/* ── Header (click to collapse/expand) ── */}
      <div
        className="sg-node__header"
        style={{ background: HEADER_BG, cursor: 'grab', userSelect: 'none' }}
        onClick={() => onChange({ collapsed: !collapsed })}
        title={collapsed ? 'Expand node' : 'Collapse node'}
      >
        <Zap size={12} />
        Contract
        <div style={{ flex: 1 }} />
        {collapsed && (
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)', maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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

      {/* ── Body (hidden when collapsed) ── */}
      {!collapsed && (
        <div className="sg-node__body">
          {/* Type name */}
          <div className="sg-node__section">
            <input
              className="sg-node__input nodrag"
              placeholder="Contract type name (e.g. Alchemist)"
              value={name}
              onChange={handleNameChange}
            />
          </div>

          {/* ── Deployment info: network / address / startBlock ── */}
          <div className="sg-node__section" style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            {/* Network */}
            <select
              className="sg-node__input nodrag"
              value={network || 'mainnet'}
              onChange={(e) => onChange({ network: e.target.value })}
              style={{ fontSize: 11 }}
            >
              {NETWORKS.map((n) => (
                <option key={n.value} value={n.value}>{n.label}</option>
              ))}
            </select>

            {/* Address */}
            <input
              className="sg-node__input nodrag"
              placeholder="Contract address (0x…)"
              value={address}
              onChange={(e) => onChange({ address: e.target.value })}
              style={{ fontFamily: 'ui-monospace, monospace', fontSize: 10 }}
            />

            {/* Start block + detect button */}
            <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <input
                className="sg-node__input nodrag"
                placeholder="Start block"
                value={startBlock}
                onChange={(e) => onChange({ startBlock: e.target.value })}
                style={{ flex: 1, fontFamily: 'ui-monospace, monospace', fontSize: 10 }}
              />
              <button
                className="sg-node__btn nodrag"
                onClick={handleDetect}
                disabled={detecting || !(address || '').trim().startsWith('0x')}
                title="Auto-detect deployment block via RPC"
                style={{ flexShrink: 0, padding: '3px 7px', display: 'flex', alignItems: 'center', gap: 3 }}
              >
                <Search size={10} />
                {detecting ? '…' : 'Detect'}
              </button>
            </div>
            {detectErr && (
              <div style={{ fontSize: 10, color: '#f87171' }}>{detectErr}</div>
            )}
          </div>

          {/* ABI source buttons */}
          <div className="sg-node__section" style={{ display: 'flex', gap: 6 }}>
            <button
              className="sg-node__btn nodrag"
              style={{ flex: 1 }}
              onClick={() => { fileInputRef.current?.click(); setPasteMode(false); setAbiError(null); }}
              title="Upload ABI JSON file"
            >
              <Upload size={11} style={{ display: 'inline', marginRight: 4 }} />
              {hasAbi && !pasteMode ? `ABI (${events.length}ev / ${readFunctions.length}fn)` : 'Upload'}
            </button>
            <button
              className="sg-node__btn nodrag"
              style={{ flex: 1, background: pasteMode ? '#1e1b4b' : undefined, borderColor: pasteMode ? '#6366f1' : undefined }}
              onClick={() => { setPasteMode((v) => !v); setAbiError(null); }}
              title="Paste ABI JSON"
            >
              <Clipboard size={11} style={{ display: 'inline', marginRight: 4 }} />
              Paste
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              style={{ display: 'none' }}
              onChange={handleAbiFile}
            />
          </div>

          {/* Paste area */}
          {pasteMode && (
            <div className="sg-node__section nodrag" style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <div style={{ display: 'flex', gap: 5 }}>
                <button
                  className="sg-node__btn nodrag"
                  style={{ flex: 1, background: '#312e81', borderColor: '#6366f1', color: '#e0e7ff' }}
                  onClick={handleAbiPaste}
                  disabled={!pasteText.trim()}
                >
                  Parse ABI
                </button>
                <button className="sg-node__btn nodrag" onClick={closePaste}>
                  Cancel
                </button>
              </div>
              <textarea
                className="sg-node__input nodrag"
                placeholder={'Paste ABI JSON here\n[...] or {"abi":[...]}'}
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                rows={5}
                style={{ fontFamily: 'ui-monospace, monospace', fontSize: 10, resize: 'vertical', width: '100%' }}
                autoFocus
              />
            </div>
          )}

          {/* ABI status line */}
          {hasAbi && !pasteMode && (
            <div className="sg-node__section" style={{ fontSize: 10, color: 'var(--text-muted)', paddingTop: 0 }}>
              {events.length} event{events.length !== 1 ? 's' : ''}, {readFunctions.length} read fn{readFunctions.length !== 1 ? 's' : ''} loaded
            </div>
          )}

          {abiError && (
            <div className="sg-node__section" style={{ color: '#f87171', fontSize: 11 }}>
              {abiError}
            </div>
          )}

          {/* ── Implicit ports (always visible when ABI loaded) ── */}
          {hasAbi && (
            <>
              <div className="sg-node__divider" />
              <div className="sg-node__section" style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', paddingBottom: 2 }}>
                Implicit
              </div>
              {IMPLICIT_PORTS.map((p) => (
                <PortRow
                  key={p.id}
                  id={p.id}
                  label={p.label}
                  portType={p.type}
                  portClass="read-port"
                />
              ))}
            </>
          )}

          {/* ── Event ports ── */}
          {hasAbi && events.length > 0 && (
            <>
              <div className="sg-node__divider" />
              <div
                className="sg-node__section"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                onClick={() => setShowEvents((v) => !v)}
              >
                <span style={{ fontSize: 11, color: 'var(--port-event)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Zap size={10} /> Events
                </span>
                <span style={{ fontSize: 9, color: 'var(--text-muted)', marginRight: 4 }}>click ▶ for params</span>
                {showEvents ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </div>
              {showEvents && events.map((ev) => (
                <EventPortGroup key={ev.name} ev={ev} />
              ))}
            </>
          )}

          {/* ── Read function ports ── */}
          {hasAbi && readFunctions.length > 0 && (
            <>
              <div className="sg-node__divider" />
              <div
                className="sg-node__section"
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
                onClick={() => setShowReads((v) => !v)}
              >
                <span style={{ fontSize: 11, color: 'var(--port-read)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <BookOpen size={10} /> Read Fns
                </span>
                {showReads ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </div>
              {showReads && readFunctions.map((fn) => (
                <PortRow
                  key={`read-${fn.name}`}
                  id={`read-${fn.name}`}
                  label={fn.name}
                  portType={fn.signature}
                  portClass="read-port"
                />
              ))}
            </>
          )}

          {/* Placeholder when no ABI yet */}
          {!hasAbi && !pasteMode && (
            <div className="sg-node__section" style={{ color: 'var(--text-muted)', fontSize: 11, fontStyle: 'italic', paddingTop: 4 }}>
              Upload or paste an ABI to reveal ports
            </div>
          )}
        </div>
      )}
    </div>
  );
}
