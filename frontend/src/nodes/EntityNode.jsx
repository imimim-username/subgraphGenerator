/**
 * EntityNode
 *
 * Represents a GraphQL entity on the canvas. The user defines:
 *   - Entity name (e.g. "TransferEvent")
 *   - Fields (name + GraphQL type) — each becomes an input port
 *
 * The `id` field is always first and required.
 * The user can choose an ID strategy from a quick-pick dropdown or wire manually.
 * Fields (except id) can be dragged to reorder them.
 *
 * Multi-trigger: the entity can be triggered by multiple events via the
 * Trigger Events checklist (same pattern as AggregateEntity), producing
 * a new record per event fire. The `evt` port remains for auto-populating
 * fields from a single event's ABI params.
 *
 * Click the header to collapse/expand the node body.
 */

import { useCallback, useEffect, useState } from 'react';
import { Handle, Position, useUpdateNodeInternals } from '@xyflow/react';
import { Database, Plus, Trash2, ChevronDown, ChevronUp, Link, GripVertical, Zap } from 'lucide-react';

// ── Header colour ─────────────────────────────────────────────────────────────
const HEADER_BG = '#065f46'; // emerald-800

// ── Supported primitive GraphQL / Graph types ─────────────────────────────────
const FIELD_TYPES = [
  'ID', 'String', 'Bytes', 'Boolean',
  'Int', 'BigInt', 'BigDecimal',
  'Address',
];

const FIELD_TYPES_SET = new Set(FIELD_TYPES);

// ── Array-type helpers ────────────────────────────────────────────────────────
// Stored format for list types matches the ABI parser: [BigInt!], [Address!], etc.
const isListType = (t) => Boolean(t && t.startsWith('['));
// Extract the base scalar/entity name from either "BigInt" or "[BigInt!]"
const baseType  = (t) => {
  if (!t) return t;
  if (t.startsWith('[')) return t.slice(1).replace(/!?\]!?$/, '');
  return t;
};
const toListType   = (t) => `[${baseType(t)}!]`;
const toScalarType = (t) => baseType(t);

// ── ID quick-pick strategies ──────────────────────────────────────────────────
const ID_STRATEGIES = [
  { label: 'Custom (wire manually)', value: 'custom' },
  { label: 'tx.hash', value: 'tx_hash' },
  { label: 'tx.hash + log index', value: 'tx_hash_log' },
  { label: 'event.address', value: 'event_address' },
];

// ── Field row ─────────────────────────────────────────────────────────────────
function FieldPortRow({
  field, idx, onUpdate, onRemove, isFirst, allEntityNames = [],
  isDragging, isDragOver,
  onDragStart, onDragOver, onDrop, onDragEnd,
}) {
  const portId = `field-${field.name || idx}`;
  const isList = isListType(field.type);
  const base   = baseType(field.type);
  const isEntityRef = !FIELD_TYPES_SET.has(base) && Boolean(base);
  const hasDerivedFrom = field.derivedFrom !== null && field.derivedFrom !== undefined;

  return (
    <div
      className="sg-node__port-row sg-node__port-row--left"
      style={{
        position: 'relative', gap: 4, paddingRight: 8, flexWrap: 'wrap',
        opacity: isDragging ? 0.35 : 1,
        borderTop: isDragOver ? '2px solid var(--accent-light)' : '2px solid transparent',
        transition: 'border-color 0.1s',
      }}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      {/* Input port — hidden for @derivedFrom virtual relations */}
      {!hasDerivedFrom && (
        <Handle
          type="target"
          position={Position.Left}
          id={portId}
          className="field-port"
          style={{ left: -6 }}
        />
      )}

      {/* Drag handle — only for non-id fields.
          IMPORTANT: draggable must be on a <div>, not on the SVG itself (SVGs are
          unreliable with the HTML5 drag API). nodrag stops React Flow from treating
          this as a node-move interaction. */}
      {!isFirst ? (
        <div
          className="nodrag"
          draggable
          onDragStart={onDragStart}
          onDragEnd={onDragEnd}
          style={{ cursor: 'grab', flexShrink: 0, display: 'flex', alignItems: 'center', touchAction: 'none' }}
          title="Drag to reorder"
        >
          <GripVertical size={11} style={{ color: 'var(--text-muted)', opacity: 0.55, pointerEvents: 'none' }} />
        </div>
      ) : (
        <div style={{ width: 11, flexShrink: 0 }} /> /* spacer keeps alignment */
      )}

      {/* Field name */}
      <input
        className="nodrag"
        placeholder="field name"
        value={field.name}
        onChange={(e) => onUpdate(idx, 'name', e.target.value)}
        style={{
          flex: '0 0 82px',
          background: 'rgba(0,0,0,0.3)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          padding: '3px 6px',
          color: 'var(--text-primary)',
          fontSize: 11,
          outline: 'none',
        }}
        disabled={isFirst}
      />

      {/* Field type */}
      <select
        className="nodrag"
        value={base}
        onChange={(e) => {
          const newBase = e.target.value;
          const newType = isList ? toListType(newBase) : newBase;
          const changes = { type: newType };
          if (FIELD_TYPES_SET.has(newBase)) {
            changes.derivedFrom = undefined;
          }
          onUpdate(idx, changes);
        }}
        style={{
          flex: 1,
          background: 'rgba(0,0,0,0.3)',
          border: isEntityRef ? '1px solid rgba(99,102,241,0.5)' : '1px solid var(--border)',
          borderRadius: 4,
          padding: '3px 4px',
          color: base ? 'var(--text-primary)' : 'var(--text-muted)',
          fontSize: 11,
          outline: 'none',
        }}
      >
        <optgroup label="Primitives">
          {FIELD_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </optgroup>
        {allEntityNames.length > 0 && (
          <optgroup label="Entities">
            {allEntityNames.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </optgroup>
        )}
      </select>

      {/* List-type toggle: [ ] → [Type!] */}
      {!isFirst && (
        <button
          className="nodrag"
          title={isList ? 'Switch to scalar (currently list [Type!])' : 'Switch to list [Type!]'}
          onClick={() => {
            const newType = isList ? toScalarType(field.type) : toListType(field.type);
            onUpdate(idx, { type: newType });
          }}
          style={{
            background: isList ? 'rgba(99,102,241,0.25)' : 'none',
            border: `1px solid ${isList ? '#6366f1' : 'var(--border)'}`,
            borderRadius: 4,
            cursor: 'pointer',
            padding: '2px 4px',
            color: isList ? '#a5b4fc' : 'var(--text-muted)',
            fontSize: 9,
            fontWeight: 700,
            lineHeight: 1.2,
            flexShrink: 0,
          }}
        >
          [ ]
        </button>
      )}

      {/* @derivedFrom toggle — only for entity-ref type, non-id fields */}
      {isEntityRef && !isFirst && (
        <button
          className="nodrag"
          title={hasDerivedFrom ? 'Remove @derivedFrom (restore input port)' : 'Add @derivedFrom virtual reverse relation'}
          onClick={() => onUpdate(idx, 'derivedFrom', hasDerivedFrom ? undefined : '')}
          style={{
            background: hasDerivedFrom ? 'rgba(99,102,241,0.25)' : 'none',
            border: `1px solid ${hasDerivedFrom ? '#6366f1' : 'var(--border)'}`,
            borderRadius: 4,
            cursor: 'pointer',
            padding: '2px 5px',
            color: hasDerivedFrom ? '#a5b4fc' : 'var(--text-muted)',
            fontSize: 10,
            fontWeight: 700,
            lineHeight: 1.2,
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <Link size={9} />
        </button>
      )}

      {/* Required badge / remove */}
      {field.required ? (
        <span style={{ fontSize: 9, color: 'var(--text-muted)', minWidth: 14, textAlign: 'center' }}>*</span>
      ) : (
        <button
          className="sg-node__btn nodrag"
          style={{ padding: '2px 5px', color: '#f87171', borderColor: '#7f1d1d' }}
          onClick={() => onRemove(idx)}
          title="Remove field"
        >
          <Trash2 size={10} />
        </button>
      )}

      {/* @derivedFrom field-name input */}
      {hasDerivedFrom && (
        <div style={{ width: '100%', paddingLeft: 8, paddingTop: 2, paddingBottom: 2 }}>
          <input
            className="nodrag"
            placeholder="via field name (e.g. tvl)"
            value={field.derivedFrom}
            onChange={(e) => onUpdate(idx, 'derivedFrom', e.target.value)}
            style={{
              width: '100%',
              background: 'rgba(99,102,241,0.08)',
              border: '1px solid rgba(99,102,241,0.4)',
              borderRadius: 4,
              padding: '2px 6px',
              color: '#a5b4fc',
              fontSize: 10,
              outline: 'none',
              fontFamily: 'ui-monospace, monospace',
            }}
          />
          <div style={{ fontSize: 9, color: 'rgba(165,180,252,0.6)', marginTop: 2, fontFamily: 'ui-monospace, monospace' }}>
            @derivedFrom(field: &quot;{field.derivedFrom || '?'}&quot;)
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function EntityNode({ id, data, selected }) {
  const {
    name = '',
    fields = [],
    sourceEvent = null,
    idStrategy = 'custom',
    triggerEvents = [],
    _allEntityNames = [],
    _allContracts = [],
    onChange,
    onDelete,
  } = data;

  const [collapsed, setCollapsed] = useState(false);
  const [showTriggers, setShowTriggers] = useState(true);
  const [draggingIdx, setDraggingIdx] = useState(null);
  const [dragOverIdx, setDragOverIdx] = useState(null);
  const updateNodeInternals = useUpdateNodeInternals();

  // Re-register handle positions whenever fields change or node expands/collapses.
  useEffect(() => {
    updateNodeInternals(id);
  }, [id, fields, collapsed, updateNodeInternals]);

  // ── Trigger events checklist ───────────────────────────────────────────────
  const toggleTrigger = useCallback((contractId, contractName, eventName) => {
    const exists = triggerEvents.some(
      (t) => t.contractId === contractId && t.eventName === eventName
    );
    const next = exists
      ? triggerEvents.filter((t) => !(t.contractId === contractId && t.eventName === eventName))
      : [...triggerEvents, { contractId, contractName, eventName }];
    onChange({ triggerEvents: next });
  }, [triggerEvents, onChange]);

  // ── Name change ────────────────────────────────────────────────────────────
  const handleNameChange = useCallback(
    (e) => onChange({ name: e.target.value }),
    [onChange]
  );

  // ── Field management ───────────────────────────────────────────────────────
  const updateField = useCallback(
    (idx, keyOrChanges, value) => {
      const changes =
        typeof keyOrChanges === 'string'
          ? { [keyOrChanges]: value }
          : keyOrChanges;
      const next = fields.map((f, i) => (i === idx ? { ...f, ...changes } : f));
      onChange({ fields: next });
    },
    [fields, onChange]
  );

  const addField = useCallback(() => {
    onChange({
      fields: [...fields, { _id: crypto.randomUUID(), name: '', type: 'String', required: false }],
    });
  }, [fields, onChange]);

  const removeField = useCallback(
    (idx) => onChange({ fields: fields.filter((_, i) => i !== idx) }),
    [fields, onChange]
  );

  // ── ID strategy quick-pick ─────────────────────────────────────────────────
  const handleIdStrategy = useCallback(
    (e) => {
      const strategy = e.target.value;
      const typeMap = { tx_hash: 'Bytes', tx_hash_log: 'String', event_address: 'Bytes', custom: 'ID' };
      onChange({ idStrategy: strategy });
      updateField(0, 'type', typeMap[strategy] ?? 'ID');
    },
    [onChange, updateField]
  );

  // ── Field drag-to-reorder ──────────────────────────────────────────────────
  // The id field (idx=0) is fixed; only non-id fields can be reordered.

  const handleDragStart = useCallback((e, idx) => {
    e.stopPropagation(); // don't let React Flow start a node drag
    setDraggingIdx(idx);
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragOver = useCallback((e, idx) => {
    e.preventDefault();
    e.stopPropagation();
    // id field (idx=0) is not a valid drop target
    if (draggingIdx !== null && idx !== draggingIdx && idx > 0) {
      setDragOverIdx(idx);
    }
  }, [draggingIdx]);

  const handleDrop = useCallback((e, idx) => {
    e.preventDefault();
    e.stopPropagation();
    if (draggingIdx === null || draggingIdx === idx || idx === 0) {
      setDraggingIdx(null);
      setDragOverIdx(null);
      return;
    }
    const next = [...fields];
    const [item] = next.splice(draggingIdx, 1);
    next.splice(idx, 0, item);
    onChange({ fields: next });
    setDraggingIdx(null);
    setDragOverIdx(null);
  }, [draggingIdx, fields, onChange]);

  const handleDragEnd = useCallback(() => {
    setDraggingIdx(null);
    setDragOverIdx(null);
  }, []);

  const collapsedSummary = name
    ? `${name} · ${fields.length} field${fields.length !== 1 ? 's' : ''}`
    : `${fields.length} field${fields.length !== 1 ? 's' : ''}`;

  return (
    <div className={`sg-node${selected ? ' sg-node--selected' : ''}`} style={{ minWidth: 270 }}>
      {/* ── Header ── */}
      <div
        className="sg-node__header"
        style={{ background: HEADER_BG, cursor: 'grab', userSelect: 'none' }}
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Expand node' : 'Collapse node'}
      >
        <Database size={12} />
        Entity
        <div style={{ flex: 1 }} />
        {collapsed && (
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.55)', maxWidth: 110, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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

      {/* ── Body ── */}
      {!collapsed && (
        <div className="sg-node__body">

          {/* ── Event trigger port (single-event wire + field auto-populate) ── */}
          <div className="sg-node__port-row sg-node__port-row--left" style={{ position: 'relative', paddingTop: 6, paddingBottom: 6 }}>
            <Handle
              type="target"
              position={Position.Left}
              id="evt"
              className="event-port"
              style={{ left: -6 }}
            />
            <span className="sg-node__port-label" style={{ fontWeight: 600 }}>event</span>
            {sourceEvent ? (
              <span style={{ fontSize: 10, color: 'var(--port-event)', fontFamily: 'ui-monospace, monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {sourceEvent}
              </span>
            ) : (
              <span style={{ fontSize: 10, color: 'var(--text-muted)', fontStyle: 'italic' }}>wire to auto-fill fields</span>
            )}
          </div>

          {/* ── Trigger Events checklist ── */}
          <div className="sg-node__divider" style={{ marginTop: 0 }} />
          <div
            className="sg-node__section"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer', paddingBottom: 4 }}
            onClick={() => setShowTriggers((v) => !v)}
          >
            <span style={{ fontSize: 11, color: 'var(--port-event)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 4 }}>
              <Zap size={10} /> Trigger Events
            </span>
            <span style={{ fontSize: 9, color: 'var(--text-muted)', marginRight: 4 }}>
              {sourceEvent === 'setup'
                ? 'setup (wired)'
                : triggerEvents.length > 0
                  ? `${triggerEvents.length} selected`
                  : 'none'}
            </span>
            {showTriggers ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </div>

          {showTriggers && (
            _allContracts.length === 0 ? (
              <div className="sg-node__section" style={{ fontSize: 10, color: 'var(--text-muted)', fontStyle: 'italic', paddingTop: 0 }}>
                No contracts on canvas yet
              </div>
            ) : (
              <div className="sg-node__section nodrag" style={{ paddingTop: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                {_allContracts.map((contract) => (
                  <div key={contract.id}>
                    {contract.events.length > 0 && (
                      <div style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4, marginBottom: 2 }}>
                        {contract.name}
                      </div>
                    )}
                    {contract.events.map((ev) => {
                      const checked = triggerEvents.some(
                        (t) => t.contractId === contract.id && t.eventName === ev.name
                      );
                      return (
                        <label
                          key={`${contract.id}-${ev.name}`}
                          className="nodrag"
                          style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', padding: '2px 0' }}
                        >
                          <input
                            type="checkbox"
                            className="nodrag"
                            checked={checked}
                            onChange={() => toggleTrigger(contract.id, contract.name, ev.name)}
                            style={{ accentColor: 'var(--port-event)', cursor: 'pointer' }}
                          />
                          <span style={{ fontSize: 10, color: checked ? 'var(--port-event)' : 'var(--text-muted)', fontFamily: 'ui-monospace, monospace' }}>
                            {ev.name}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                ))}
              </div>
            )
          )}

          <div className="sg-node__divider" />

          {/* Entity name */}
          <div className="sg-node__section">
            <input
              className="sg-node__input nodrag"
              placeholder="Entity name (e.g. DepositEvent)"
              value={name}
              onChange={handleNameChange}
            />
          </div>

          {/* ID strategy */}
          <div className="sg-node__section">
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              ID Strategy
            </div>
            <select
              className="nodrag"
              value={idStrategy}
              onChange={handleIdStrategy}
              style={{
                width: '100%',
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid var(--border)',
                borderRadius: 4,
                padding: '4px 6px',
                color: 'var(--text-primary)',
                fontSize: 11,
                outline: 'none',
              }}
            >
              {ID_STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>

          {/* Fields */}
          <div className="sg-node__divider" />
          <div
            className="sg-node__section"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
          >
            <span style={{ fontSize: 11, color: 'var(--port-field)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Fields
            </span>
            <button className="sg-node__btn nodrag" onClick={addField} title="Add field">
              <Plus size={10} />
            </button>
          </div>

          {fields.map((field, idx) => (
            <FieldPortRow
              key={field._id || field.name || `field-${idx}`}
              field={field}
              idx={idx}
              onUpdate={updateField}
              onRemove={removeField}
              isFirst={idx === 0}
              allEntityNames={_allEntityNames}
              isDragging={draggingIdx === idx}
              isDragOver={dragOverIdx === idx && draggingIdx !== null && draggingIdx !== idx}
              onDragStart={(e) => handleDragStart(e, idx)}
              onDragOver={(e) => handleDragOver(e, idx)}
              onDrop={(e) => handleDrop(e, idx)}
              onDragEnd={handleDragEnd}
            />
          ))}

          {fields.length === 0 && (
            <div className="sg-node__section" style={{ color: 'var(--text-muted)', fontSize: 11, fontStyle: 'italic' }}>
              No fields yet — click + to add
            </div>
          )}
        </div>
      )}
    </div>
  );
}
