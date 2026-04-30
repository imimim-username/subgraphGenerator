/**
 * NetworksPanel
 *
 * Sidebar for defining deployment targets.
 *
 * For each network (mainnet, optimism, arbitrum, …) the user specifies,
 * per contract type, one row per deployed instance:
 *   label | address | startBlock
 *
 * The panel reads the list of named Contract nodes from the canvas so it
 * can auto-populate contract type rows as the user adds Contract nodes.
 *
 * Produces the `networks` section of visual-config.json, which maps to
 * networks.json on disk:
 *   {
 *     "mainnet": {
 *       "Alchemist": {
 *         "instances": [
 *           { "label": "alUSD", "address": "0xAAA...", "startBlock": 14265505 }
 *         ]
 *       }
 *     }
 *   }
 */

import { useCallback, useState } from 'react';
import { Plus, Trash2, ChevronDown, ChevronUp, Globe } from 'lucide-react';

// ── Known networks ────────────────────────────────────────────────────────────
const KNOWN_NETWORKS = [
  'mainnet', 'goerli', 'sepolia',
  'optimism', 'optimism-goerli',
  'arbitrum-one', 'arbitrum-goerli',
  'polygon', 'mumbai',
  'base', 'base-goerli',
  'bnb', 'avalanche',
  'gnosis',
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function newInstance() {
  return { label: '', address: '', startBlock: '', endBlock: '' };
}

function newNetworkEntry(contractNames) {
  const contracts = {};
  for (const name of contractNames) {
    contracts[name] = { instances: [newInstance()] };
  }
  return { network: 'mainnet', contracts };
}

// ── Sub-components ────────────────────────────────────────────────────────────

const INPUT_STYLE = {
  background: 'rgba(0,0,0,0.3)',
  border: '1px solid var(--border)',
  borderRadius: 4,
  padding: '3px 6px',
  color: 'var(--text-primary)',
  fontSize: 11,
  outline: 'none',
};

function InstanceRow({ inst, onChange, onRemove, canRemove }) {
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center', marginBottom: 4 }}>
      <input
        className="nodrag"
        placeholder="label"
        value={inst.label}
        onChange={(e) => onChange('label', e.target.value)}
        style={{ ...INPUT_STYLE, flex: '0 0 58px' }}
      />
      <input
        className="nodrag"
        placeholder="0x…"
        value={inst.address}
        onChange={(e) => onChange('address', e.target.value)}
        style={{ ...INPUT_STYLE, flex: 1, fontFamily: 'ui-monospace, monospace', fontSize: 10 }}
      />
      <input
        className="nodrag"
        placeholder="start"
        value={inst.startBlock}
        onChange={(e) => onChange('startBlock', e.target.value)}
        style={{ ...INPUT_STYLE, flex: '0 0 50px' }}
      />
      <input
        className="nodrag"
        placeholder="end"
        value={inst.endBlock ?? ''}
        onChange={(e) => onChange('endBlock', e.target.value)}
        style={{ ...INPUT_STYLE, flex: '0 0 50px' }}
      />
      {canRemove && (
        <button
          onClick={onRemove}
          style={{
            background: 'none',
            border: 'none',
            color: '#f87171',
            cursor: 'pointer',
            padding: '2px 4px',
            display: 'flex',
            alignItems: 'center',
          }}
          title="Remove instance"
        >
          <Trash2 size={11} />
        </button>
      )}
    </div>
  );
}

function ContractSection({ contractName, contractData, onUpdate }) {
  const instances = contractData?.instances ?? [];

  const updateInstance = (idx, field, value) => {
    const next = instances.map((inst, i) =>
      i === idx ? { ...inst, [field]: value } : inst
    );
    onUpdate({ instances: next });
  };

  const addInstance = () => {
    onUpdate({ instances: [...instances, newInstance()] });
  };

  const removeInstance = (idx) => {
    onUpdate({ instances: instances.filter((_, i) => i !== idx) });
  };

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-light)' }}>
          {contractName}
        </span>
        <button
          onClick={addInstance}
          style={{
            background: 'none',
            border: '1px solid var(--border)',
            borderRadius: 4,
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '1px 6px',
            fontSize: 10,
            display: 'flex',
            alignItems: 'center',
            gap: 3,
          }}
          title="Add instance"
        >
          <Plus size={9} /> instance
        </button>
      </div>

      {/* Column headers */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 3 }}>
        {[
          { key: 'label', flex: '0 0 58px' },
          { key: 'address', flex: 1 },
          { key: 'start', flex: '0 0 50px' },
          { key: 'end', flex: '0 0 50px' },
        ].map(({ key, flex }) => (
          <div
            key={key}
            style={{
              fontSize: 9,
              color: 'var(--text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              flex,
            }}
          >
            {key}
          </div>
        ))}
      </div>

      {instances.map((inst, idx) => (
        <InstanceRow
          key={idx}
          inst={inst}
          onChange={(field, val) => updateInstance(idx, field, val)}
          onRemove={() => removeInstance(idx)}
          canRemove={instances.length > 1}
        />
      ))}
    </div>
  );
}

function NetworkSection({ entry, idx, contractNames, onUpdate, onRemove }) {
  const [collapsed, setCollapsed] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const updateContract = (contractName, patch) => {
    onUpdate({
      ...entry,
      contracts: {
        ...entry.contracts,
        [contractName]: { ...(entry.contracts[contractName] ?? {}), ...patch },
      },
    });
  };

  const handleNetworkChange = (e) => {
    onUpdate({ ...entry, network: e.target.value });
  };

  return (
    <div
      style={{
        background: 'rgba(0,0,0,0.2)',
        border: '1px solid var(--border)',
        borderRadius: 6,
        marginBottom: 8,
        overflow: 'hidden',
      }}
    >
      {/* Network header row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 10px',
          background: 'rgba(255,255,255,0.04)',
          borderBottom: '1px solid var(--border)',
          cursor: 'pointer',
        }}
        onClick={() => setCollapsed((v) => !v)}
      >
        <Globe size={12} style={{ color: 'var(--accent-light)', flexShrink: 0 }} />
        <select
          value={entry.network}
          onChange={handleNetworkChange}
          onClick={(e) => e.stopPropagation()}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            color: 'var(--text-primary)',
            fontSize: 12,
            fontWeight: 600,
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          {KNOWN_NETWORKS.map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
          <option value="custom">custom…</option>
        </select>
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', padding: 2, display: 'flex', alignItems: 'center' }}
          title="Remove network"
        >
          <Trash2 size={12} />
        </button>
        {collapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
      </div>

      {/* Contract instance tables */}
      {!collapsed && (
        <div style={{ padding: '8px 10px' }}>
          {contractNames.length === 0 ? (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>
              Add a named Contract node to the canvas first
            </div>
          ) : (
            contractNames.map((name) => (
              <ContractSection
                key={name}
                contractName={name}
                contractData={entry.contracts[name]}
                onUpdate={(patch) => updateContract(name, patch)}
              />
            ))
          )}
          {/* Advanced per-chain options */}
          <div style={{ marginTop: 6, borderTop: '1px solid var(--border)', paddingTop: 6 }}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', userSelect: 'none' }}
              onClick={() => setShowAdvanced((v) => !v)}
            >
              {showAdvanced ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
              <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                Advanced
              </span>
            </div>
            {showAdvanced && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', flex: '0 0 116px' }}>pollingInterval (ms)</span>
                  <input
                    type="number"
                    className="nodrag"
                    value={entry.pollingInterval ?? ''}
                    onChange={(e) => onUpdate({ ...entry, pollingInterval: e.target.value !== '' ? Number(e.target.value) : undefined })}
                    placeholder="default"
                    style={{ ...INPUT_STYLE, width: 80 }}
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', flex: '0 0 116px' }}>ethGetLogsBlockRange</span>
                  <input
                    type="number"
                    className="nodrag"
                    value={entry.ethGetLogsBlockRange ?? ''}
                    onChange={(e) => onUpdate({ ...entry, ethGetLogsBlockRange: e.target.value !== '' ? Number(e.target.value) : undefined })}
                    placeholder="default"
                    style={{ ...INPUT_STYLE, width: 80 }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function NetworksPanel({ networks, onChange, contractNames = [], isOpen, onClose }) {
  const addNetwork = useCallback(() => {
    onChange([...networks, newNetworkEntry(contractNames)]);
  }, [networks, onChange, contractNames]);

  const updateNetwork = useCallback(
    (idx, patch) => {
      onChange(networks.map((n, i) => (i === idx ? patch : n)));
    },
    [networks, onChange]
  );

  const removeNetwork = useCallback(
    (idx) => {
      onChange(networks.filter((_, i) => i !== idx));
    },
    [networks, onChange]
  );

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: 360,
        background: '#0f172a',
        borderLeft: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 10,
        boxShadow: '-4px 0 24px rgba(0,0,0,0.5)',
      }}
    >
      {/* Panel header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Globe size={15} style={{ color: 'var(--accent-light)' }} />
          <span style={{ fontWeight: 700, fontSize: 13 }}>Networks</span>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            onClick={addNetwork}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '4px 10px',
              background: 'rgba(124,58,237,0.2)',
              border: '1px solid var(--accent)',
              borderRadius: 5,
              color: 'var(--accent-light)',
              fontSize: 11,
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            <Plus size={11} /> Add Network
          </button>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: 18,
              lineHeight: 1,
              padding: '0 4px',
            }}
            title="Close panel"
          >
            ×
          </button>
        </div>
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {networks.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', paddingTop: 24 }}>
            Click <strong>Add Network</strong> to define a deployment target.
          </div>
        ) : (
          networks.map((entry, idx) => (
            <NetworkSection
              key={idx}
              entry={entry}
              idx={idx}
              contractNames={contractNames}
              onUpdate={(patch) => updateNetwork(idx, patch)}
              onRemove={() => removeNetwork(idx)}
            />
          ))
        )}
      </div>
    </div>
  );
}
