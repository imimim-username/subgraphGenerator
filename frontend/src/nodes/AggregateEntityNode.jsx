/**
 * AggregateEntityNode
 *
 * Represents a mutable singleton entity — one record per stable key, updated
 * in-place each event (load-or-create pattern). Each non-id field has:
 *   - A LEFT handle  (`field-in-{name}`)  — new value to write
 *   - A RIGHT handle (`field-prev-{name}`) — previous value before update
 *
 * The `id` field has only a left handle (`field-id`) — the stable key.
 *
 * Generated AssemblyScript:
 *   let entity = MyEntity.load(stableId);
 *   if (entity == null) {
 *     entity = new MyEntity(stableId);
 *     entity.amount = BigInt.fromI32(0);  // zero-init
 *   }
 *   let entity_prev_amount = entity.amount;  // capture previous
 *   entity.amount = newValue;
 *   entity.save();
 */

import { useCallback, useEffect, useState } from 'react';
import { Handle, Position, useUpdateNodeInternals } from '@xyflow/react';
import { LayoutGrid, Plus, Trash2, ChevronDown, ChevronUp, Zap, GripVertical } from 'lucide-react';

// ── Header colour ─────────────────────────────────────────────────────────────
const HEADER_BG = '#1e3a5f'; // deep blue

// ── Supported primitive GraphQL / Graph types ─────────────────────────────────
const FIELD_TYPES = [
  'ID', 'String', 'Bytes', 'Boolean',
  'Int', 'BigInt', 'BigDecimal',
  'Address',
];

// ── Array-type helpers (mirrors EntityNode) ────────────────────────────────────
const isListType   = (t) => Boolean(t && t.startsWith('['));
const baseType     = (t) => { if (!t) return t; if (t.startsWith('[')) return t.slice(1).replace(/!?\]!?$/, ''); return t; };
const toListType   = (t) => `[${baseType(t)}!]`;
const toScalarType = (t) => baseType(t);

function AggFieldRow({
  field, idx, onUpdate, onRemove, isFirst, allEntityNames = [],
  isDragging, isDragOver,
  onDragStart, onDragOver, onDrop, onDragEnd,
}) {
  // Always derive port IDs from the field *name*, never from the numeric index.
  // If the field has no name yet the handle is omitted entirely — this prevents
  // stale numeric-index edges (field-in-2, field-in-3 …) from being created
  // when the user wires a field before giving it a name.
  const inPortId   = isFirst ? 'field-id' : (field.name ? `field-in-${field.name}` : null);
  const prevPortId = field.name ? `field-prev-${field.name}` : null;
  const isList = isListType(field.type);
  const base   = baseType(field.type);

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: '3px 8px 3px 8px',
        minHeight: 28,
        opacity: isDragging ? 0.35 : 1,
        borderTop: isDragOver ? '2px solid #818cf8' : '2px solid transparent',
        transition: 'border-top 0.1s',
      }}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      {/* LEFT — input port (only rendered once the field has a name) */}
      {inPortId && (
        <Handle
          type="target"
          position={Position.Left}
          id={inPortId}
          className="field-port"
          style={{ left: -6 }}
        />
      )}

      {/* Drag grip (non-id fields only).
          draggable must be on a <div>, not the SVG — SVGs are unreliable
          with the HTML5 drag API. nodrag stops React Flow node-move. */}
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
        <div style={{ width: 11, flexShrink: 0 }} />
      )}

      {/* Field name */}
      <input
        className="nodrag"
        placeholder="field name"
        value={field.name}
        onChange={(e) => onUpdate(idx, 'name', e.target.value)}
        style={{
          flex: '0 0 78px',
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
          onUpdate(idx, 'type', newType);
        }}
        style={{
          flex: 1,
          background: 'rgba(0,0,0,0.3)',
          border: '1px solid var(--border)',
          borderRadius: 4,
          padding: '3px 4px',
          color: 'var(--text-primary)',
          fontSize: 11,
          outline: 'none',
        }}
        disabled={isFirst}
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
            onUpdate(idx, 'type', newType);
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

      {/* Required badge / remove button */}
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

      {/* RIGHT — field-out-id for the id row; prev output port for all others */}
      {isFirst ? (
        <Handle
          type="source"
          position={Position.Right}
          id="field-out-id"
          className="read-port"
          style={{ right: -6 }}
          title="Expose this aggregate's stable ID as an output wire"
        />
      ) : prevPortId ? (
        <Handle
          type="source"
          position={Position.Right}
          id={prevPortId}
          className="read-port"
          style={{ right: -6 }}
          title={`Previous value of ${field.name}`}
        />
      ) : null}
    </div>
  );
}

export default function AggregateEntityNode({ id, data, selected }) {
  const {
    name = '',
    fields = [],
    triggerEvents = [],   // [{contractId, contractName, eventName}]
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

  // Re-register handle positions whenever fields change or collapse state changes.
  useEffect(() => {
    updateNodeInternals(id);
  }, [id, fields, collapsed, updateNodeInternals]);

  // Toggle a specific {contractId, eventName} in the triggerEvents list
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
    (idx, key, value) => {
      const next = fields.map((f, i) => (i === idx ? { ...f, [key]: value } : f));
      onChange({ fields: next });
    },
    [fields, onChange]
  );

  const addField = useCallback(() => {
    onChange({
      fields: [...fields, { _id: crypto.randomUUID(), name: '', type: 'BigInt', required: false }],
    });
  }, [fields, onChange]);

  const removeField = useCallback(
    (idx) => {
      onChange({ fields: fields.filter((_, i) => i !== idx) });
    },
    [fields, onChange]
  );

  // ── Drag-to-reorder ────────────────────────────────────────────────────────
  const handleDragStart = useCallback((e, idx) => {
    e.stopPropagation();
    setDraggingIdx(idx);
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragOver = useCallback((e, idx) => {
    e.preventDefault();
    e.stopPropagation();
    if (idx === 0) return; // id field is not a drop target
    e.dataTransfer.dropEffect = 'move';
    setDragOverIdx(idx);
  }, []);

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

  const handleDragEnd = useCallback((e) => {
    e.stopPropagation();
    setDraggingIdx(null);
    setDragOverIdx(null);
  }, []);

  const collapsedSummary = name
    ? `${name} · ${fields.length} field${fields.length !== 1 ? 's' : ''}`
    : `${fields.length} field${fields.length !== 1 ? 's' : ''}`;

  return (
    <div className={`sg-node${selected ? ' sg-node--selected' : ''}`} style={{ minWidth: 280 }}>
      {/* ── Header ── */}
      <div
        className="sg-node__header"
        style={{ background: HEADER_BG, cursor: 'grab', userSelect: 'none' }}
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Expand node' : 'Collapse node'}
      >
        <LayoutGrid size={12} />
        Aggregate Entity
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
              {triggerEvents.length > 0 ? `${triggerEvents.length} selected` : 'none selected'}
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
              placeholder="Entity name (e.g. AlchemistTVL)"
              value={name}
              onChange={handleNameChange}
            />
          </div>

          {/* Fields header */}
          <div className="sg-node__divider" />
          <div
            className="sg-node__section"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
          >
            <span style={{ fontSize: 11, color: 'var(--port-read)', fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Fields
            </span>
            <button className="sg-node__btn nodrag" onClick={addField} title="Add field">
              <Plus size={10} />
            </button>
          </div>

          {/* Hint row */}
          <div className="sg-node__section" style={{ fontSize: 9, color: 'var(--text-muted)', paddingTop: 0, paddingBottom: 2, display: 'flex', justifyContent: 'space-between' }}>
            <span>← new value</span>
            <span>id-out / prev value →</span>
          </div>

          {/* Field rows */}
          {fields.map((field, idx) => (
            <AggFieldRow
              key={field._id || field.name || `field-${idx}`}
              field={field}
              idx={idx}
              onUpdate={updateField}
              onRemove={removeField}
              isFirst={idx === 0}
              allEntityNames={_allEntityNames}
              isDragging={draggingIdx === idx}
              isDragOver={dragOverIdx === idx}
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
