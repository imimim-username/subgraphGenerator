/**
 * Toolbar — top-left panel with buttons to add nodes.
 * Nodes can be added via click or by dragging onto the canvas.
 */

import { Zap, Database, LayoutGrid, Calculator, ArrowRightLeft, TextCursorInput, GitBranch, BookOpen, Wand2, Trash2 } from 'lucide-react';

const BTN_BASE = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '5px 10px',
  borderRadius: 5,
  border: '1px solid var(--border)',
  background: 'var(--bg-node)',
  color: 'var(--text-primary)',
  fontSize: 11,
  cursor: 'grab',
  userSelect: 'none',
  whiteSpace: 'nowrap',
};

function DraggableNodeButton({ nodeType, icon: Icon, label, color, onClick }) {
  const handleDragStart = (e) => {
    e.dataTransfer.setData('application/subgraph-node-type', nodeType);
    e.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      onClick={onClick}
      style={BTN_BASE}
      title={`Add ${label} node (drag or click)`}
    >
      <Icon size={12} style={{ color, flexShrink: 0 }} />
      {label}
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div
      style={{
        fontSize: 9,
        color: 'var(--text-muted)',
        fontWeight: 700,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        paddingTop: 4,
        paddingBottom: 2,
      }}
    >
      {children}
    </div>
  );
}

export default function Toolbar({
  onAddContract,
  onAddEntity,
  onAddAggregateEntity,
  onAddMath,
  onAddTypeCast,
  onAddStrConcat,
  onAddConditional,
  onAddContractRead,
  onAutoLayout,
  onCleanup,
  cleanupStatus,
  outputMode,
  genDir,
}) {
  // Derive cleanup button label + color from status
  const isCleaning = cleanupStatus === 'cleaning';
  const cleanupOk  = cleanupStatus && cleanupStatus.removed !== undefined;
  const cleanupErr = cleanupStatus?.error;

  let cleanupLabel = 'Clean Up';
  if (isCleaning)  cleanupLabel = 'Cleaning…';
  else if (cleanupOk) {
    const n = cleanupStatus.removed.length;
    cleanupLabel = n === 0 ? '✓ Nothing to clean' : `✓ Removed ${n} file${n > 1 ? 's' : ''}`;
  } else if (cleanupErr) cleanupLabel = `✗ ${cleanupStatus.error}`;

  const cleanupColor = cleanupErr
    ? '#ef4444'
    : cleanupOk
      ? '#4ade80'
      : '#94a3b8';

  const showCleanup = outputMode === 'ponder';

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        padding: '8px 10px',
        background: 'rgba(15,23,42,0.88)',
        backdropFilter: 'blur(8px)',
        borderRadius: 8,
        border: '1px solid var(--border)',
        boxShadow: '0 4px 24px rgba(0,0,0,0.45)',
        minWidth: 150,
      }}
    >
      <SectionLabel>Source / Target</SectionLabel>

      <DraggableNodeButton
        nodeType="contract"
        icon={Zap}
        label="Contract"
        color="#a78bfa"
        onClick={onAddContract}
      />

      <DraggableNodeButton
        nodeType="entity"
        icon={Database}
        label="Entity"
        color="#34d399"
        onClick={onAddEntity}
      />

      <DraggableNodeButton
        nodeType="aggregateentity"
        icon={LayoutGrid}
        label="Aggregate"
        color="#60a5fa"
        onClick={onAddAggregateEntity}
      />

      <DraggableNodeButton
        nodeType="contractread"
        icon={BookOpen}
        label="Contract Read"
        color="#34d399"
        onClick={onAddContractRead}
      />

      <SectionLabel>Transform</SectionLabel>

      <DraggableNodeButton
        nodeType="math"
        icon={Calculator}
        label="Math"
        color="#fbbf24"
        onClick={onAddMath}
      />

      <DraggableNodeButton
        nodeType="typecast"
        icon={ArrowRightLeft}
        label="Type Cast"
        color="#60a5fa"
        onClick={onAddTypeCast}
      />

      <DraggableNodeButton
        nodeType="strconcat"
        icon={TextCursorInput}
        label="Str Concat"
        color="#4ade80"
        onClick={onAddStrConcat}
      />

      <DraggableNodeButton
        nodeType="conditional"
        icon={GitBranch}
        label="Conditional"
        color="#c084fc"
        onClick={onAddConditional}
      />

      <SectionLabel>Canvas</SectionLabel>

      <div
        onClick={onAutoLayout}
        style={{ ...BTN_BASE, cursor: 'pointer' }}
        title="Auto-arrange all visible nodes (dagre LR layout)"
      >
        <Wand2 size={12} style={{ color: '#94a3b8', flexShrink: 0 }} />
        Auto Layout
      </div>

      {showCleanup && (
        <div
          onClick={!isCleaning ? onCleanup : undefined}
          style={{
            ...BTN_BASE,
            cursor: isCleaning ? 'default' : 'pointer',
            opacity: isCleaning ? 0.6 : 1,
            color: cleanupColor,
            borderColor: cleanupErr
              ? 'rgba(239,68,68,0.4)'
              : cleanupOk
                ? 'rgba(74,222,128,0.3)'
                : 'var(--border)',
          }}
          title={
            !genDir
              ? 'Run Generate first to set the output directory'
              : 'Remove stale generated files (deleted contracts, orphan schemas)'
          }
        >
          <Trash2 size={12} style={{ color: cleanupColor, flexShrink: 0 }} />
          {cleanupLabel}
        </div>
      )}
    </div>
  );
}
