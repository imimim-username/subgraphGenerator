/**
 * SimulatePanel — modal showing a human-readable subgraph simulation.
 *
 * Three collapsible top-level sections:
 *   1. Event Handlers — per-event steps (contract reads, entity load/write/save)
 *   2. GraphQL Schema — entity type definitions
 *   3. Example Queries — full query shape for each entity
 */

import { useState, useEffect } from 'react';
import {
  ChevronDown, ChevronRight, X, Zap, Database, Search, AlertTriangle,
  ArrowRight, RefreshCw, Save, BookOpen,
} from 'lucide-react';

// ── Collapsible section wrapper ───────────────────────────────────────────────

function Section({ title, icon: Icon, defaultOpen = true, badge, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ marginBottom: 16 }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          width: '100%', background: 'var(--bg-node)',
          border: '1px solid var(--border)', borderRadius: 6,
          padding: '8px 12px', cursor: 'pointer', color: 'var(--text)',
          fontSize: 13, fontWeight: 600,
        }}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        {Icon && <Icon size={14} style={{ opacity: 0.7 }} />}
        <span style={{ flex: 1, textAlign: 'left' }}>{title}</span>
        {badge != null && (
          <span style={{
            background: 'var(--accent)', color: '#fff',
            borderRadius: 10, padding: '1px 7px', fontSize: 11,
          }}>{badge}</span>
        )}
      </button>
      {open && <div style={{ paddingTop: 8 }}>{children}</div>}
    </div>
  );
}

// ── Collapsible handler block (one per contract.Event) ────────────────────────

function HandlerBlock({ handler }) {
  const [open, setOpen] = useState(true);
  const { contract, event, steps } = handler;

  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 6,
      marginBottom: 8, overflow: 'hidden',
    }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          width: '100%', background: '#1e293b',
          border: 'none', padding: '7px 12px', cursor: 'pointer',
          color: 'var(--text)', fontSize: 12,
        }}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Zap size={12} style={{ color: 'var(--port-event)', flexShrink: 0 }} />
        <span style={{ fontWeight: 600 }}>{contract}</span>
        <span style={{ color: 'var(--text-muted)' }}>·</span>
        <span style={{ color: 'var(--port-event)' }}>{event}</span>
      </button>

      {open && (
        <div style={{ padding: '8px 12px 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {steps.map((step, i) => <StepRow key={`${step.type}-${i}`} step={step} />)}
        </div>
      )}
    </div>
  );
}

// ── Single step row ───────────────────────────────────────────────────────────

const STEP_STYLES = {
  contract_read:   { color: 'var(--port-read)',     icon: RefreshCw,    label: 'Contract Read' },
  entity_load:     { color: 'var(--port-field)',    icon: Database,     label: 'Load / Create' },
  field_write:     { color: 'var(--text)',          icon: ArrowRight,   label: 'Set field' },
  field_unchanged: { color: 'var(--text-muted)',    icon: ArrowRight,   label: 'Unchanged' },
  entity_save:     { color: 'var(--accent-light)',  icon: Save,         label: 'Save' },
};

function StepRow({ step }) {
  const style = STEP_STYLES[step.type] || { color: 'var(--text-muted)', icon: ArrowRight, label: step.type };
  const Icon = style.icon;

  if (step.type === 'contract_read') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2,
        background: 'rgba(255,255,255,0.03)', borderRadius: 4, padding: '5px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon size={11} style={{ color: style.color, flexShrink: 0 }} />
          <span style={{ color: style.color, fontWeight: 600, fontSize: 12 }}>{step.label}</span>
          <code style={{ fontSize: 11, color: 'var(--text)', background: 'rgba(0,0,0,0.2)',
            padding: '1px 5px', borderRadius: 3 }}>{step.result}</code>
        </div>
        <div style={{ paddingLeft: 17, fontSize: 11, color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span><span style={{ color: 'var(--text-muted)' }}>call</span> <code style={{ color: 'var(--text)' }}>{step.label}</code></span>
          <span><span style={{ color: 'var(--text-muted)' }}>bind</span> <code style={{ color: 'var(--port-event)', fontSize: 10 }}>{step.bind}</code></span>
          {step.args && step.args.map((a, i) => (
            <span key={i}><span style={{ color: 'var(--text-muted)' }}>arg</span> <code style={{ color: 'var(--text)', fontSize: 10 }}>{a}</code></span>
          ))}
        </div>
      </div>
    );
  }

  if (step.type === 'entity_load') {
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, padding: '3px 0' }}>
        <Icon size={11} style={{ color: style.color, flexShrink: 0, marginTop: 2 }} />
        <div style={{ fontSize: 12 }}>
          <span style={{ color: style.color, fontWeight: 600 }}>
            {step.is_aggregate ? 'Load or create' : 'Load or create'}
          </span>
          {' '}
          <span style={{ color: 'var(--accent-light)', fontWeight: 600 }}>{step.entity}</span>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            id = <code style={{ color: 'var(--text)', fontSize: 10 }}>{step.id_source}</code>
          </div>
        </div>
      </div>
    );
  }

  if (step.type === 'field_write') {
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, padding: '2px 0', paddingLeft: 8 }}>
        <Icon size={10} style={{ color: style.color, flexShrink: 0, marginTop: 3 }} />
        <div style={{ fontSize: 12 }}>
          <span style={{ color: 'var(--accent-light)' }}>{step.entity}</span>
          <span style={{ color: 'var(--text-muted)' }}>.</span>
          <span style={{ fontWeight: 600 }}>{step.field}</span>
          <span style={{ color: 'var(--text-muted)', margin: '0 4px' }}>=</span>
          <code style={{ fontSize: 11, color: 'var(--port-event)' }}>{step.source}</code>
        </div>
      </div>
    );
  }

  if (step.type === 'field_unchanged') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 0', paddingLeft: 8, opacity: 0.45 }}>
        <Icon size={10} style={{ color: style.color, flexShrink: 0 }} />
        <span style={{ fontSize: 11, color: style.color, fontStyle: 'italic' }}>
          {step.entity}.{step.field} — {step.note}
        </span>
      </div>
    );
  }

  if (step.type === 'entity_save') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 0' }}>
        <Icon size={11} style={{ color: style.color, flexShrink: 0 }} />
        <span style={{ fontSize: 12, color: style.color, fontWeight: 600 }}>Save</span>
        <span style={{ fontSize: 12, color: 'var(--accent-light)' }}>{step.entity}</span>
      </div>
    );
  }

  return (
    <div style={{ fontSize: 11, color: 'var(--text-muted)', paddingLeft: 8 }}>
      {step.type}: {JSON.stringify(step)}
    </div>
  );
}

// ── Schema block (one per entity) ─────────────────────────────────────────────

function SchemaBlock({ entry }) {
  const [open, setOpen] = useState(true);
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 6, marginBottom: 8, overflow: 'hidden' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          width: '100%', background: '#1e293b',
          border: 'none', padding: '7px 12px', cursor: 'pointer',
          color: 'var(--text)', fontSize: 12,
        }}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Database size={12} style={{ color: 'var(--port-field)', flexShrink: 0 }} />
        <span style={{ fontWeight: 600 }}>{entry.name}</span>
        {entry.is_aggregate && (
          <span style={{ fontSize: 10, color: 'var(--text-muted)', background: 'rgba(255,255,255,0.08)',
            borderRadius: 3, padding: '1px 5px' }}>aggregate</span>
        )}
      </button>
      {open && (
        <pre style={{
          margin: 0, padding: '8px 14px', fontSize: 11,
          color: 'var(--text)', lineHeight: 1.7, overflowX: 'auto',
          background: 'rgba(0,0,0,0.15)',
        }}>
          <span style={{ color: 'var(--accent-light)' }}>type</span>
          {' '}
          <span style={{ color: 'var(--port-event)', fontWeight: 700 }}>{entry.name}</span>
          {' '}
          <span style={{ color: 'var(--text-muted)' }}>@entity</span>
          {' {'}{'\n'}
          {entry.fields.map((f) => {
            const bang = f.required ? '!' : '';
            const annotation = f.derivedFrom
              ? ` @derivedFrom(field: "${f.derivedFrom}")`
              : '';
            return (
              <span key={f.name}>
                {'  '}
                <span style={{ color: 'var(--text)' }}>{f.name}</span>
                <span style={{ color: 'var(--text-muted)' }}>: </span>
                <span style={{ color: 'var(--port-field)' }}>{f.type}{bang}</span>
                {annotation && <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>{annotation}</span>}
                {'\n'}
              </span>
            );
          })}
          {'}'}
        </pre>
      )}
    </div>
  );
}

// ── Query block (one per entity) ──────────────────────────────────────────────

function QueryBlock({ query }) {
  const [open, setOpen] = useState(true);
  const indent = '  ';
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 6, marginBottom: 8, overflow: 'hidden' }}>
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          width: '100%', background: '#1e293b',
          border: 'none', padding: '7px 12px', cursor: 'pointer',
          color: 'var(--text)', fontSize: 12,
        }}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Search size={12} style={{ color: 'var(--port-read)', flexShrink: 0 }} />
        <span style={{ fontWeight: 600, color: 'var(--accent-light)' }}>{query.entity}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>— singular + list</span>
      </button>
      {open && (
        <div style={{ display: 'flex', gap: 8, padding: '8px 12px', flexWrap: 'wrap' }}>
          {/* Singular query */}
          <pre style={{
            flex: 1, minWidth: 180, margin: 0, padding: '8px 10px',
            fontSize: 11, color: 'var(--text)', lineHeight: 1.7,
            background: 'rgba(0,0,0,0.15)', borderRadius: 4, overflowX: 'auto',
          }}>
            <span style={{ color: 'var(--text-muted)' }}>{'{\n'}</span>
            {indent}<span style={{ color: 'var(--port-read)' }}>{query.singular}</span>
            <span style={{ color: 'var(--text-muted)' }}>(id: </span>
            <span style={{ color: 'var(--port-event)' }}>"…"</span>
            <span style={{ color: 'var(--text-muted)' }}>) {'{\n'}</span>
            {query.fields.map((f) => (
              <span key={f}>{indent}{indent}<span style={{ color: 'var(--text)' }}>{f}</span>{'\n'}</span>
            ))}
            {indent}<span style={{ color: 'var(--text-muted)' }}>{'}\n}'}</span>
          </pre>

          {/* Plural / list query */}
          <pre style={{
            flex: 1, minWidth: 180, margin: 0, padding: '8px 10px',
            fontSize: 11, color: 'var(--text)', lineHeight: 1.7,
            background: 'rgba(0,0,0,0.15)', borderRadius: 4, overflowX: 'auto',
          }}>
            <span style={{ color: 'var(--text-muted)' }}>{'{\n'}</span>
            {indent}<span style={{ color: 'var(--port-read)' }}>{query.plural}</span>
            <span style={{ color: 'var(--text-muted)' }}>(</span>
            {'\n'}{indent}{indent}
            <span style={{ color: 'var(--text-muted)' }}>orderBy: </span>
            <span style={{ color: 'var(--port-event)' }}>{query.fields[1] || 'id'}</span>
            {'\n'}{indent}{indent}
            <span style={{ color: 'var(--text-muted)' }}>orderDirection: </span>
            <span style={{ color: 'var(--port-event)' }}>desc</span>
            {'\n'}{indent}
            <span style={{ color: 'var(--text-muted)' }}>{')'} {'{\n'}</span>
            {query.fields.map((f) => (
              <span key={f}>{indent}{indent}<span style={{ color: 'var(--text)' }}>{f}</span>{'\n'}</span>
            ))}
            {indent}<span style={{ color: 'var(--text-muted)' }}>{'}\n}'}</span>
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Main SimulatePanel modal ───────────────────────────────────────────────────

export default function SimulatePanel({ onClose, nodes, edges }) {
  const [status, setStatus] = useState('idle'); // idle | loading | done | error
  const [result, setResult] = useState(null);
  const [error, setError]   = useState(null);

  async function runSimulate() {
    setStatus('loading');
    setError(null);
    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes, edges }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      setResult(data);
      setStatus('done');
    } catch (e) {
      setError(e.message);
      setStatus('error');
    }
  }

  // Auto-run on mount
  useEffect(() => { runSimulate(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000,
    }}>
      <div style={{
        background: '#0f172a', border: '1px solid var(--border)',
        borderRadius: 10, width: 760, maxWidth: '95vw',
        maxHeight: '88vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 8px 48px rgba(0,0,0,0.8)',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '14px 18px', borderBottom: '1px solid var(--border)',
          flexShrink: 0,
        }}>
          <BookOpen size={16} style={{ color: 'var(--accent-light)' }} />
          <span style={{ fontWeight: 700, fontSize: 14, flex: 1 }}>Subgraph Simulation</span>
          <button
            onClick={runSimulate}
            disabled={status === 'loading'}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              background: 'var(--accent)', border: 'none', borderRadius: 5,
              color: '#fff', padding: '5px 12px', cursor: 'pointer', fontSize: 12,
              opacity: status === 'loading' ? 0.6 : 1,
            }}
          >
            <RefreshCw size={12} style={{ animation: status === 'loading' ? 'spin 1s linear infinite' : 'none' }} />
            {status === 'loading' ? 'Simulating…' : 'Re-run'}
          </button>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)',
              cursor: 'pointer', padding: 4, borderRadius: 4 }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 18 }}>
          {status === 'loading' && (
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>
              Simulating…
            </div>
          )}

          {status === 'error' && (
            <div style={{ display: 'flex', gap: 8, color: '#f87171', padding: 16,
              background: 'rgba(248,113,113,0.1)', borderRadius: 6 }}>
              <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{error}</span>
            </div>
          )}

          {status === 'done' && result && (
            <>
              {/* ── Event Handlers ── */}
              <Section
                title="Event Handlers"
                icon={Zap}
                badge={result.handlers.length}
                defaultOpen
              >
                {result.handlers.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '4px 8px' }}>
                    No event handlers found — wire a contract event to an entity.
                  </div>
                ) : (
                  result.handlers.map((h, i) => (
                    <HandlerBlock key={`${h.contract}-${h.event}-${i}`} handler={h} />
                  ))
                )}
              </Section>

              {/* ── GraphQL Schema ── */}
              <Section
                title="GraphQL Schema"
                icon={Database}
                badge={result.schema.length}
                defaultOpen
              >
                {result.schema.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '4px 8px' }}>
                    No entity types defined yet.
                  </div>
                ) : (
                  result.schema.map((s) => <SchemaBlock key={s.name} entry={s} />)
                )}
              </Section>

              {/* ── Example Queries ── */}
              <Section
                title="Example Queries"
                icon={Search}
                badge={result.queries.length}
                defaultOpen
              >
                {result.queries.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: 12, padding: '4px 8px' }}>
                    No queryable entities yet.
                  </div>
                ) : (
                  result.queries.map((q) => <QueryBlock key={q.entity} query={q} />)
                )}
              </Section>
            </>
          )}
        </div>
      </div>

      {/* CSS for spin animation */}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
