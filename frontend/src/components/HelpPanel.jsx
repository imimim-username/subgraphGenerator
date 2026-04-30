/**
 * HelpPanel
 *
 * A slide-in help panel that explains every node type and UI component in
 * plain English, with examples of real-world usage.
 *
 * Open with the "?" button in the top-right corner.
 */

import { useState } from 'react';
import {
  X,
  Zap,
  Database,
  LayoutGrid,
  Calculator,
  ArrowRightLeft,
  TextCursorInput,
  GitBranch,
  BookOpen,
  Globe,
  FolderOpen,
  FolderPlus,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

// ── Styles ────────────────────────────────────────────────────────────────────

const PANEL_W = 480;

const s = {
  overlay: {
    position: 'fixed',
    inset: 0,
    zIndex: 2000,
    pointerEvents: 'none',
  },
  panel: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    width: PANEL_W,
    background: '#0f172a',
    borderLeft: '1px solid #334155',
    display: 'flex',
    flexDirection: 'column',
    pointerEvents: 'all',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '12px 16px',
    borderBottom: '1px solid #334155',
    flexShrink: 0,
    background: 'rgba(124,58,237,0.12)',
  },
  headerTitle: {
    flex: 1,
    fontSize: 14,
    fontWeight: 700,
    color: '#e2e8f0',
    letterSpacing: '0.02em',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#94a3b8',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    padding: 4,
    borderRadius: 4,
  },
  toc: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    padding: '8px 12px',
    borderBottom: '1px solid #1e293b',
    flexShrink: 0,
    background: 'rgba(0,0,0,0.2)',
  },
  tocLabel: {
    fontSize: 9,
    fontWeight: 700,
    color: '#475569',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    marginBottom: 4,
  },
  tocRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 4,
  },
  tocBtn: (active) => ({
    padding: '3px 8px',
    borderRadius: 4,
    border: `1px solid ${active ? '#7c3aed' : '#334155'}`,
    background: active ? 'rgba(124,58,237,0.2)' : 'rgba(255,255,255,0.03)',
    color: active ? '#a78bfa' : '#94a3b8',
    fontSize: 11,
    fontWeight: 600,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  }),
  body: {
    flex: 1,
    overflowY: 'auto',
    padding: '16px',
  },
  section: {
    marginBottom: 24,
  },
  sectionHeader: (color) => ({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
    paddingBottom: 8,
    borderBottom: `2px solid ${color}22`,
  }),
  sectionTitle: (color) => ({
    fontSize: 15,
    fontWeight: 700,
    color,
  }),
  pill: (color) => ({
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: '0.06em',
    padding: '2px 6px',
    borderRadius: 3,
    background: `${color}22`,
    color,
    border: `1px solid ${color}44`,
    textTransform: 'uppercase',
  }),
  p: {
    fontSize: 12,
    color: '#cbd5e1',
    lineHeight: 1.7,
    marginBottom: 10,
  },
  h4: {
    fontSize: 11,
    fontWeight: 700,
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    marginBottom: 6,
    marginTop: 14,
  },
  portTable: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 11,
    marginBottom: 12,
  },
  th: {
    textAlign: 'left',
    padding: '4px 8px',
    color: '#64748b',
    fontWeight: 600,
    borderBottom: '1px solid #1e293b',
    fontSize: 10,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  td: {
    padding: '4px 8px',
    color: '#cbd5e1',
    borderBottom: '1px solid #0f172a',
    verticalAlign: 'top',
  },
  code: {
    fontFamily: 'ui-monospace, monospace',
    fontSize: 11,
    background: 'rgba(0,0,0,0.35)',
    border: '1px solid #1e293b',
    borderRadius: 4,
    padding: '8px 12px',
    display: 'block',
    color: '#a78bfa',
    marginBottom: 10,
    whiteSpace: 'pre',
    overflowX: 'auto',
  },
  inlineCode: {
    fontFamily: 'ui-monospace, monospace',
    fontSize: 11,
    background: 'rgba(0,0,0,0.4)',
    border: '1px solid #1e293b',
    borderRadius: 3,
    padding: '1px 5px',
    color: '#a78bfa',
  },
  tip: {
    background: 'rgba(16,185,129,0.08)',
    border: '1px solid rgba(16,185,129,0.25)',
    borderRadius: 6,
    padding: '8px 12px',
    fontSize: 11,
    color: '#6ee7b7',
    lineHeight: 1.6,
    marginBottom: 10,
  },
  warn: {
    background: 'rgba(245,158,11,0.08)',
    border: '1px solid rgba(245,158,11,0.25)',
    borderRadius: 6,
    padding: '8px 12px',
    fontSize: 11,
    color: '#fcd34d',
    lineHeight: 1.6,
    marginBottom: 10,
  },
  example: {
    background: 'rgba(124,58,237,0.08)',
    border: '1px solid rgba(124,58,237,0.25)',
    borderRadius: 6,
    padding: '12px',
    marginBottom: 12,
  },
  exampleTitle: {
    fontSize: 12,
    fontWeight: 700,
    color: '#a78bfa',
    marginBottom: 8,
  },
  stepList: {
    margin: 0,
    paddingLeft: 18,
    fontSize: 12,
    color: '#cbd5e1',
    lineHeight: 1.8,
  },
};

// ── Collapsible section ───────────────────────────────────────────────────────

function Collapsible({ title, color, icon: Icon, badge, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={s.section}>
      <div
        onClick={() => setOpen((v) => !v)}
        style={{ ...s.sectionHeader(color), cursor: 'pointer', userSelect: 'none' }}
      >
        {Icon && <Icon size={14} color={color} />}
        <span style={s.sectionTitle(color)}>{title}</span>
        {badge && <span style={s.pill(color)}>{badge}</span>}
        <div style={{ flex: 1 }} />
        {open ? <ChevronDown size={12} color={color} /> : <ChevronRight size={12} color={color} />}
      </div>
      {open && children}
    </div>
  );
}

// ── Port row table helper ─────────────────────────────────────────────────────

function PortTable({ rows }) {
  return (
    <table style={s.portTable}>
      <thead>
        <tr>
          <th style={s.th}>Side</th>
          <th style={s.th}>Port</th>
          <th style={s.th}>Type</th>
          <th style={s.th}>What it carries</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            <td style={s.td}><span style={{ color: r.side === 'in' ? '#3b82f6' : '#10b981', fontWeight: 700, fontSize: 10 }}>{r.side === 'in' ? '← IN' : 'OUT →'}</span></td>
            <td style={{ ...s.td, fontFamily: 'ui-monospace, monospace', fontSize: 10, color: '#a78bfa' }}>{r.id}</td>
            <td style={{ ...s.td, fontSize: 10, color: '#94a3b8' }}>{r.type}</td>
            <td style={s.td}>{r.desc}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── Sections ──────────────────────────────────────────────────────────────────

function OverviewSection() {
  return (
    <Collapsible title="How this tool works" color="#a78bfa" icon={Zap} defaultOpen>
      <p style={s.p}>
        This editor lets you describe what data you want to pull off the blockchain — without writing
        code by hand. You build a <strong style={{ color: '#e2e8f0' }}>visual graph</strong> of
        connected nodes, then click <strong style={{ color: '#e2e8f0' }}>Generate</strong> to produce
        a complete, working subgraph project.
      </p>
      <p style={s.p}>
        <strong style={{ color: '#e2e8f0' }}>The basic idea:</strong>
      </p>
      <ol style={s.stepList}>
        <li>A <strong style={{ color: '#f59e0b' }}>Contract</strong> node represents a smart contract on-chain. It provides event data.</li>
        <li>An <strong style={{ color: '#10b981' }}>Entity</strong> node represents a database record you want to save. It receives data.</li>
        <li>You draw a wire (edge) from a contract's event port to an entity's <code style={s.inlineCode}>evt</code> port. That means "when this event fires, save a record."</li>
        <li>Extra nodes — Math, Type Cast, etc. — let you transform or combine values in between.</li>
        <li>Once your graph looks right, click <strong style={{ color: '#a78bfa' }}>Generate</strong>. A directory-picker modal opens — choose where to write the files. The tool then writes your AssemblyScript mapping files, schema, subgraph.yaml, networks.json, package.json, and a howto.md deployment guide.</li>
      </ol>

      <div style={s.tip}>
        💡 <strong>Quick start:</strong> Add a Contract → upload its ABI → wire an event to an Entity → click Generate.
        That's the entire core workflow.
      </div>

      <p style={{ ...s.p, marginTop: 12 }}>
        <strong style={{ color: '#e2e8f0' }}>Port colors tell you the data type:</strong>
      </p>
      <table style={s.portTable}>
        <tbody>
          <tr><td style={{ ...s.td, width: 14 }}><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: '#f59e0b' }} /></td><td style={s.td}><strong>Amber</strong> — event trigger or event parameter value</td></tr>
          <tr><td style={s.td}><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: '#10b981' }} /></td><td style={s.td}><strong>Green</strong> — string, address, bytes, or read-function result</td></tr>
          <tr><td style={s.td}><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: '#3b82f6' }} /></td><td style={s.td}><strong>Blue</strong> — number (BigInt, Int, BigDecimal) or entity field</td></tr>
          <tr><td style={s.td}><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: '#64748b' }} /></td><td style={s.td}><strong>Slate</strong> — boolean or pass-through</td></tr>
        </tbody>
      </table>

      <div style={s.warn}>
        ⚠️ <strong>Validation errors</strong> (red outline) must be fixed before Generate is enabled.
        Warnings (orange) are advisory only.
      </div>
    </Collapsible>
  );
}

function ContractSection() {
  return (
    <Collapsible title="Contract" color="#818cf8" icon={Zap} badge="Source">
      <p style={s.p}>
        A <strong style={{ color: '#e2e8f0' }}>Contract</strong> node represents one smart contract
        deployed on the blockchain. It is always a <em>source</em> of data — you never wire anything
        into it, only out of it.
      </p>
      <p style={s.p}>
        After you give it a name and upload (or paste) the contract's ABI JSON, the node automatically
        shows output ports for every event and every read/view function in that ABI.
      </p>

      <div style={s.h4}>Setup steps</div>
      <ol style={s.stepList}>
        <li>Click <strong>Contract</strong> in the toolbar (or drag it onto the canvas).</li>
        <li>Type a name like <code style={s.inlineCode}>Alchemist</code> — this becomes your data source name.</li>
        <li>Click <strong>Upload</strong> to load a <code style={s.inlineCode}>.json</code> ABI file, or click <strong>Paste</strong> and paste the JSON directly.</li>
        <li>Ports appear automatically. Each event gets an amber trigger port.</li>
        <li>Click the <code style={s.inlineCode}>▶</code> chevron next to any event to expand its individual parameter ports.</li>
      </ol>

      <div style={s.h4}>Output ports (always available once ABI is loaded)</div>
      <PortTable rows={[
        { side: 'out', id: 'implicit-address', type: 'Address', desc: 'The contract\'s own deployed address' },
        { side: 'out', id: 'implicit-tx-hash', type: 'Bytes', desc: 'Hash of the transaction that triggered this handler' },
        { side: 'out', id: 'implicit-block-number', type: 'BigInt', desc: 'Block number when the event was emitted' },
        { side: 'out', id: 'implicit-block-timestamp', type: 'BigInt', desc: 'Unix timestamp of the block (seconds since epoch)' },
        { side: 'out', id: 'event-{Name}', type: 'trigger', desc: 'Fires once per occurrence of this event — wire this to an Entity or Aggregate Entity evt port' },
        { side: 'out', id: 'event-{Name}-{param}', type: 'varies', desc: 'Individual parameter value from the event. Click the ▶ chevron on the event row to reveal these.' },
      ]} />

      <div style={s.tip}>
        💡 <strong>Read functions</strong> (view/pure) listed on the node show which on-chain calls
        are available, but you call them using a separate <strong>Contract Read</strong> node — not
        by wiring directly from the contract. See the Contract Read section for details.
      </div>

      <div style={s.h4}>Collapsing a Contract node</div>
      <p style={s.p}>
        Click the Contract node's header to <strong>collapse</strong> it. When collapsed, the node
        shrinks to a single title bar and the canvas performs a <strong>BFS traversal</strong> from
        that node's outputs — every downstream node (Math, TypeCast, ContractRead, Entity,
        AggregateEntity, etc.) reachable <em>only</em> via collapsed contracts is hidden, along with
        all connecting edges. This keeps the canvas tidy when you have multiple contracts and want to
        focus on one.
      </p>
      <p style={s.p}>
        A node is <strong>not</strong> hidden if it is also reachable from an <em>expanded</em>
        contract — shared intermediate nodes remain visible as long as at least one of their upstream
        contract sources is expanded.
      </p>
      <div style={s.tip}>
        💡 Click the collapsed header again to expand it and restore all hidden nodes and edges.
      </div>

      <div style={s.h4}>Example</div>
      <div style={s.example}>
        <div style={s.exampleTitle}>📋 Track every ERC-20 Transfer</div>
        <ol style={s.stepList}>
          <li>Add a Contract node, name it <code style={s.inlineCode}>MyToken</code>.</li>
          <li>Paste the ERC-20 ABI. You'll see a <code style={s.inlineCode}>Transfer</code> event port appear (amber).</li>
          <li>Expand the <code style={s.inlineCode}>Transfer</code> chevron — you'll see <code style={s.inlineCode}>from</code>, <code style={s.inlineCode}>to</code>, and <code style={s.inlineCode}>value</code> sub-ports.</li>
          <li>Wire <code style={s.inlineCode}>event-Transfer</code> → an Entity's <code style={s.inlineCode}>evt</code> port to create one record per Transfer.</li>
        </ol>
      </div>
    </Collapsible>
  );
}

function EntitySection() {
  return (
    <Collapsible title="Entity" color="#34d399" icon={Database} badge="Store">
      <p style={s.p}>
        An <strong style={{ color: '#e2e8f0' }}>Entity</strong> node is a database table row.
        Every time the event it's wired to fires on-chain, a <em>new</em> row is created and saved.
        This is the right node when you want to keep a <strong>history</strong> of every event occurrence.
      </p>

      <div style={s.h4}>Two ways to trigger an Entity</div>
      <p style={s.p}>
        You can connect an Entity to contract events in two ways — or combine both:
      </p>
      <table style={s.portTable}>
        <tbody>
          <tr>
            <td style={{ ...s.td, fontFamily: 'ui-monospace, monospace', fontSize: 10, color: '#f59e0b', width: 130 }}>evt wire</td>
            <td style={s.td}>
              Draw a wire from a Contract's amber event port to the entity's <code style={s.inlineCode}>evt</code> port.
              The first time you do this, the entity <strong>auto-fills its fields</strong> from the event's parameters — no typing needed.
              Wire individual event parameter ports into specific field ports to override auto-fill.
            </td>
          </tr>
          <tr>
            <td style={{ ...s.td, fontFamily: 'ui-monospace, monospace', fontSize: 10, color: '#f59e0b' }}>Trigger Events checklist</td>
            <td style={s.td}>
              Tick events in the <strong>Trigger Events</strong> collapsible section at the top of the node body.
              This fires the handler for that event without drawing any wire — useful when you want the <em>same entity type</em> created by multiple events (e.g. both Deposit and Withdraw create history rows).
            </td>
          </tr>
        </tbody>
      </table>

      <div style={s.h4}>Ports</div>
      <PortTable rows={[
        { side: 'in', id: 'evt', type: 'trigger', desc: 'Wire from a Contract event port to trigger this entity and auto-fill fields. Optional when using the Trigger Events checklist.' },
        { side: 'in', id: 'field-{name}', type: 'varies', desc: 'The value to store in this field. If unwired, uses the event parameter of the same name automatically.' },
      ]} />

      <div style={s.tip}>
        💡 <strong>Drag to reorder fields.</strong> Grab the <strong>⠿ grip handle</strong> to the left of any field (non-id fields only)
        and drag it up or down to change the order. Field order in the UI determines the order of assignments in the generated code.
        The <code style={s.inlineCode}>id</code> field is always locked at the top.
      </div>

      <div style={s.h4}>ID Strategy</div>
      <p style={s.p}>
        Every entity needs a unique ID. You can choose from the quick-pick dropdown:
      </p>
      <table style={s.portTable}>
        <tbody>
          <tr><td style={{ ...s.td, fontFamily: 'ui-monospace, monospace', fontSize: 10, color: '#a78bfa', width: 160 }}>tx.hash</td><td style={s.td}>Use the transaction hash. Unique per transaction but not per event within a transaction.</td></tr>
          <tr><td style={{ ...s.td, fontFamily: 'ui-monospace, monospace', fontSize: 10, color: '#a78bfa' }}>tx.hash + log index</td><td style={s.td}>Hash plus the event's log index — guaranteed unique even with multiple events in one tx.</td></tr>
          <tr><td style={{ ...s.td, fontFamily: 'ui-monospace, monospace', fontSize: 10, color: '#a78bfa' }}>event.address</td><td style={s.td}>The contract address — useful when one record per contract is enough.</td></tr>
          <tr><td style={{ ...s.td, fontFamily: 'ui-monospace, monospace', fontSize: 10, color: '#a78bfa' }}>Custom</td><td style={s.td}>Wire your own value into the <code style={s.inlineCode}>field-id</code> port (e.g. from a string concat or a parameter).</td></tr>
        </tbody>
      </table>

      <div style={s.h4}>Field types — Primitives and Entity References</div>
      <p style={s.p}>
        Each field has a <strong>type</strong> selector. The top group lists primitive types
        (<code style={s.inlineCode}>BigInt</code>, <code style={s.inlineCode}>Bytes</code>,
        <code style={s.inlineCode}>String</code>, etc.). If your canvas has other Entity or Aggregate
        Entity nodes, a second group called <strong>Entities</strong> appears so you can pick another
        entity as the field's type.
      </p>
      <p style={s.p}>
        An entity-reference field stores a foreign-key relationship — like a SQL foreign key.
        For example, a <code style={s.inlineCode}>tvl</code> field of type
        <code style={s.inlineCode}> AlchemistTVL</code> in a history entity means each history row
        points to one TVL record. Wire the TVL aggregate's <strong>id-out</strong> port (right dot
        on the id row) into this field's input port.
      </p>

      <div style={s.h4}>@derivedFrom — virtual reverse relations</div>
      <p style={s.p}>
        If you want to navigate <em>backwards</em> from a parent entity to a list of child entities
        (like "all history rows for this TVL record"), use a <strong>@derivedFrom</strong> field.
        This is a read-only, virtual field — it never stores data and has no input port.
      </p>
      <p style={s.p}>
        To add one: select an entity-reference type for the field, then click the small
        <strong> link icon (🔗)</strong> button that appears. Enter the field name in the child
        entity that points back to this one (e.g. <code style={s.inlineCode}>tvl</code>). The
        generated schema will look like:
      </p>
      <pre style={{ ...s.inlineCode, display: 'block', padding: '8px 12px', background: 'rgba(0,0,0,0.3)', borderRadius: 6, fontSize: 11, overflowX: 'auto', marginBottom: 8 }}>
        {`activity: [AlchemistTVLHistory!]! @derivedFrom(field: "tvl")`}
      </pre>
      <p style={s.p}>
        The compiler skips @derivedFrom fields entirely — no AssemblyScript is generated for them.
        They are resolved automatically by The Graph's query layer.
      </p>

      <div style={s.h4}>Example — Save every Deposit event</div>
      <div style={s.example}>
        <div style={s.exampleTitle}>📋 History record using an evt wire</div>
        <ol style={s.stepList}>
          <li>Wire <code style={s.inlineCode}>event-Deposit</code> (amber) → Entity <code style={s.inlineCode}>evt</code>.</li>
          <li>The entity auto-fills with fields matching Deposit's parameters (e.g. <code style={s.inlineCode}>amount</code>, <code style={s.inlineCode}>recipient</code>).</li>
          <li>Set ID strategy to <code style={s.inlineCode}>tx.hash + log index</code> so each deposit gets a unique row.</li>
          <li>Generate → a <code style={s.inlineCode}>Deposit</code> entity is created in your schema and a handler is written.</li>
        </ol>
      </div>
      <div style={s.example}>
        <div style={s.exampleTitle}>📋 One entity type triggered by multiple events (checklist)</div>
        <ol style={s.stepList}>
          <li>Add an Entity, name it <code style={s.inlineCode}>VaultActivity</code>. Add fields: <code style={s.inlineCode}>id</code>, <code style={s.inlineCode}>amount</code> (BigInt), <code style={s.inlineCode}>eventType</code> (String).</li>
          <li>In the <strong>Trigger Events</strong> checklist, tick both <code style={s.inlineCode}>Deposit</code> and <code style={s.inlineCode}>Withdraw</code>.</li>
          <li>Expand each event on the Contract node. Wire the <code style={s.inlineCode}>amount</code> param port → <code style={s.inlineCode}>field-amount</code> for both events.</li>
          <li>Each event now produces a new <code style={s.inlineCode}>VaultActivity</code> row — no separate entity types needed.</li>
        </ol>
      </div>
    </Collapsible>
  );
}

function AggregateEntitySection() {
  return (
    <Collapsible title="Aggregate Entity" color="#60a5fa" icon={LayoutGrid} badge="Running Total">
      <p style={s.p}>
        An <strong style={{ color: '#e2e8f0' }}>Aggregate Entity</strong> is a <em>single, mutable
        record</em> that gets updated in-place every time selected events fire. Use it when you want
        a running total, a cumulative balance, or the latest state of something — not a new row per event.
      </p>
      <p style={s.p}>
        Think of it like a spreadsheet cell that gets overwritten each time, rather than a new row
        being appended.
      </p>

      <div style={s.h4}>Trigger Events — checklist, not a wire</div>
      <p style={s.p}>
        Unlike a regular Entity, an Aggregate Entity is <strong>not wired</strong> to a contract event
        port. Instead, each node has a <strong>Trigger Events</strong> checklist in its header. Tick
        the checkbox next to every event (from any contract on the canvas) that should fire this
        aggregate's handler. You can select events from multiple contracts.
      </p>
      <div style={s.tip}>
        💡 <strong>No evt wire needed.</strong> Ticking an event in the checklist is the only
        connection required. Wiring to an <code style={s.inlineCode}>evt</code> port is not how
        aggregates work — use the checklist.
      </div>

      <div style={s.h4}>Ports</div>
      <PortTable rows={[
        { side: 'in', id: 'field-id', type: 'ID', desc: 'The stable key used to look up (or create) this record. Wire a fixed address or other stable value here.' },
        { side: 'in', id: 'field-in-{name}', type: 'varies', desc: 'The NEW value to write into this field — usually the output of a Math node.' },
        { side: 'out', id: 'field-out-id', type: 'ID', desc: 'Exposes this record\'s stable ID as an output wire — use it as a foreign-key input in a related history Entity.' },
        { side: 'out', id: 'field-prev-{name}', type: 'varies', desc: 'The PREVIOUS value stored in this field BEFORE this update — feed it into a Math node to accumulate.' },
      ]} />

      <div style={s.tip}>
        💡 <strong>Drag to reorder fields.</strong> Grab the <strong>⠿ grip handle</strong> to the left of any non-id field and drag it up or down.
        The <code style={s.inlineCode}>id</code> field is always locked at the top.
        Field order affects the order of generated zero-initialisation and assignment statements.
      </div>

      <div style={s.tip}>
        💡 <strong>The key insight:</strong> To add to a running total, wire
        <code style={s.inlineCode}> field-prev-balance</code> (old value) and the new event amount
        into a <strong>Math (add)</strong> node, then wire the result into <code style={s.inlineCode}>field-in-balance</code>.
      </div>

      <div style={s.h4}>field-out-id — exposing the stable key</div>
      <p style={s.p}>
        The <code style={s.inlineCode}>id</code> field on an Aggregate Entity has a right-side output
        port called <code style={s.inlineCode}>field-out-id</code>. Wire this into a history Entity's
        field to store a foreign-key link — so each history row points back to the aggregate record
        it belongs to.
      </p>

      <div style={s.h4}>Example — Running TVL (net deposits minus withdrawals)</div>
      <div style={s.example}>
        <div style={s.exampleTitle}>📋 Track net balance across Deposit and Withdraw events</div>
        <p style={{ ...s.p, marginBottom: 8 }}>
          Because Deposit and Withdraw are separate events, you need <strong>two</strong> Aggregate
          Entity nodes — both named the same (e.g. <code style={s.inlineCode}>TVL</code>). Each
          compiles to a separate handler for the same entity type.
        </p>
        <p style={{ ...s.p, fontWeight: 600, color: '#a78bfa', marginBottom: 4 }}>For Deposits (adds):</p>
        <ol style={s.stepList}>
          <li>Add Aggregate Entity, name it <code style={s.inlineCode}>TVL</code>, add field <code style={s.inlineCode}>balance</code> (BigInt).</li>
          <li>In the <strong>Trigger Events</strong> checklist, tick <code style={s.inlineCode}>Deposit</code>.</li>
          <li>Wire <code style={s.inlineCode}>implicit-address</code> → <code style={s.inlineCode}>TVL field-id</code> (use the contract address as the stable key).</li>
          <li>Add a <strong>Math (add)</strong> node.</li>
          <li>Wire <code style={s.inlineCode}>TVL field-prev-balance</code> → Math <strong>left</strong>.</li>
          <li>Expand the Deposit chevron on the Contract node. Wire <code style={s.inlineCode}>event-Deposit-amount</code> → Math <strong>right</strong>.</li>
          <li>Wire Math <strong>result</strong> → <code style={s.inlineCode}>TVL field-in-balance</code>.</li>
        </ol>
        <p style={{ ...s.p, fontWeight: 600, color: '#a78bfa', marginBottom: 4, marginTop: 10 }}>For Withdrawals (subtracts) — same pattern, subtract instead of add:</p>
        <ol style={s.stepList}>
          <li>Add a second Aggregate Entity, also named <code style={s.inlineCode}>TVL</code>, same <code style={s.inlineCode}>balance</code> field.</li>
          <li>In its <strong>Trigger Events</strong> checklist, tick <code style={s.inlineCode}>Withdraw</code>.</li>
          <li>Wire <code style={s.inlineCode}>implicit-address</code> → this node's <code style={s.inlineCode}>field-id</code> (same stable key — both handlers update the same record).</li>
          <li>Add a <strong>Math (subtract)</strong> node.</li>
          <li>Wire this node's <code style={s.inlineCode}>field-prev-balance</code> → Math <strong>left</strong>.</li>
          <li>Expand the Withdraw chevron. Wire <code style={s.inlineCode}>event-Withdraw-amount</code> → Math <strong>right</strong>.</li>
          <li>Wire Math <strong>result</strong> → this node's <code style={s.inlineCode}>field-in-balance</code>.</li>
        </ol>
        <div style={{ ...s.tip, marginTop: 8 }}>
          💡 Both Aggregate Entity nodes are named <code style={s.inlineCode}>TVL</code> — they compile to handlers
          for the <em>same</em> entity type in the schema. Each handler independently loads and updates the same single record.
        </div>
      </div>
    </Collapsible>
  );
}

function MathSection() {
  return (
    <Collapsible title="Math" color="#fbbf24" icon={Calculator} badge="Transform">
      <p style={s.p}>
        A <strong style={{ color: '#e2e8f0' }}>Math</strong> node performs a single arithmetic
        operation on two numeric inputs and produces one numeric output. It works with
        <code style={s.inlineCode}> BigInt</code> values (the most common on-chain numeric type).
      </p>

      <div style={s.h4}>Ports</div>
      <PortTable rows={[
        { side: 'in', id: 'left', type: 'BigInt', desc: 'Left-hand operand' },
        { side: 'in', id: 'right', type: 'BigInt', desc: 'Right-hand operand' },
        { side: 'out', id: 'result', type: 'BigInt', desc: 'Result of the operation' },
      ]} />

      <div style={s.h4}>Operations</div>
      <table style={s.portTable}>
        <tbody>
          {[
            ['Add (+)', 'left + right — combine two amounts'],
            ['Subtract (−)', 'left − right — calculate a difference'],
            ['Multiply (×)', 'left × right — scale a value'],
            ['Divide (÷)', 'left ÷ right — integer division'],
            ['Modulo (%)', 'left mod right — remainder after division'],
            ['Power (^)', 'left to the power of right'],
          ].map(([op, desc]) => (
            <tr key={op}>
              <td style={{ ...s.td, fontFamily: 'ui-monospace, monospace', fontSize: 11, color: '#fbbf24', width: 120 }}>{op}</td>
              <td style={s.td}>{desc}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={s.warn}>
        ⚠️ Math nodes work with values that come from wired ports — event parameters, previous
        aggregate values, or other Math results. There is no constant/literal node, so both
        <code style={s.inlineCode}> left</code> and <code style={s.inlineCode}>right</code> must
        be connected to something from the graph.
      </div>

      <div style={s.h4}>Example</div>
      <div style={s.example}>
        <div style={s.exampleTitle}>📋 Running total: add a deposit to the previous balance</div>
        <ol style={s.stepList}>
          <li>Add an Aggregate Entity with a <code style={s.inlineCode}>balance</code> field.</li>
          <li>Add a Math node, set operation to <strong>Add</strong>.</li>
          <li>Wire the aggregate's <code style={s.inlineCode}>field-prev-balance</code> → Math <strong>left</strong> (the old balance).</li>
          <li>Expand the Deposit event chevron on the Contract node. Wire <code style={s.inlineCode}>event-Deposit-amount</code> → Math <strong>right</strong> (the new deposit).</li>
          <li>Wire Math <strong>result</strong> → aggregate's <code style={s.inlineCode}>field-in-balance</code> (the updated balance).</li>
        </ol>
      </div>
    </Collapsible>
  );
}

function TypeCastSection() {
  return (
    <Collapsible title="Type Cast" color="#60a5fa" icon={ArrowRightLeft} badge="Transform">
      <p style={s.p}>
        A <strong style={{ color: '#e2e8f0' }}>Type Cast</strong> node converts a value from one type
        to another. You need this whenever a port's output type doesn't match the input type of where
        you want to connect it.
      </p>
      <p style={s.p}>
        For example, an event might emit an <code style={s.inlineCode}>address</code>, but your entity's
        <code style={s.inlineCode}> id</code> field expects a <code style={s.inlineCode}>String</code>.
        A Type Cast (Address → String) bridges that gap.
      </p>

      <div style={s.h4}>Ports</div>
      <PortTable rows={[
        { side: 'in', id: 'value', type: 'from-type', desc: 'The value to convert' },
        { side: 'out', id: 'result', type: 'to-type', desc: 'The converted value' },
      ]} />

      <div style={s.h4}>Available conversions</div>
      <table style={s.portTable}>
        <tbody>
          {[
            ['BigInt → Int', 'Convert a large integer to a regular 32-bit int (loses precision if value is huge)'],
            ['BigInt → String', 'Turn a number into its decimal string representation, e.g. "12345"'],
            ['Bytes → String', 'Convert raw bytes to a hex string, e.g. "0xdeadbeef"'],
            ['Bytes → Address', 'Reinterpret 20-byte Bytes value as an Address'],
            ['String → Bytes', 'Parse a hex string back into Bytes'],
            ['Address → String', 'Convert an address to its checksummed hex string'],
            ['Address → Bytes', 'Cast an Address to its raw Bytes representation'],
          ].map(([cast, desc]) => (
            <tr key={cast}>
              <td style={{ ...s.td, fontFamily: 'ui-monospace, monospace', fontSize: 10, color: '#60a5fa', width: 150 }}>{cast}</td>
              <td style={s.td}>{desc}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Collapsible>
  );
}

function StrConcatSection() {
  return (
    <Collapsible title="String Concat" color="#4ade80" icon={TextCursorInput} badge="Transform">
      <p style={s.p}>
        A <strong style={{ color: '#e2e8f0' }}>String Concat</strong> node joins two strings into one.
        You can optionally put a separator between them.
      </p>
      <p style={s.p}>
        This is most commonly used to build a <strong>composite ID</strong> — for example, combining
        a pool address with a user address so each user-pool pair gets a unique entity ID.
      </p>

      <div style={s.h4}>Ports</div>
      <PortTable rows={[
        { side: 'in', id: 'left', type: 'String', desc: 'First string' },
        { side: 'in', id: 'right', type: 'String', desc: 'Second string' },
        { side: 'out', id: 'result', type: 'String', desc: 'left + separator + right' },
      ]} />

      <div style={s.h4}>Example</div>
      <div style={s.example}>
        <div style={s.exampleTitle}>📋 Unique ID per user per pool</div>
        <ol style={s.stepList}>
          <li>Add String Concat, set separator to <code style={s.inlineCode}>-</code>.</li>
          <li>Wire <code style={s.inlineCode}>implicit-address</code> → TypeCast (Address→String) → String Concat <strong>left</strong>.</li>
          <li>Wire <code style={s.inlineCode}>event-Deposit-user</code> → TypeCast (Address→String) → String Concat <strong>right</strong>.</li>
          <li>Wire String Concat <strong>result</strong> → Entity <code style={s.inlineCode}>field-id</code>.</li>
          <li>Result: ID looks like <code style={s.inlineCode}>0xpool...-0xuser...</code></li>
        </ol>
      </div>
    </Collapsible>
  );
}

function ConditionalSection() {
  return (
    <Collapsible title="Conditional" color="#c084fc" icon={GitBranch} badge="Filter">
      <p style={s.p}>
        A <strong style={{ color: '#e2e8f0' }}>Conditional</strong> node acts as a gate. If the
        condition wired to it is <code style={s.inlineCode}>false</code>, the entire event handler
        stops immediately — no entity is saved, no calculations happen downstream.
      </p>
      <p style={s.p}>
        Use it to filter out events you don't care about. For example: "only save a record if the
        transfer amount is above zero" or "skip this handler if the caller is a known bot address."
      </p>

      <div style={s.h4}>Ports</div>
      <PortTable rows={[
        { side: 'in', id: 'condition', type: 'Boolean', desc: 'If false, the handler exits early and nothing is saved' },
        { side: 'in', id: 'value', type: 'any', desc: 'A value you want to pass through (optional — can be used to gate a field assignment)' },
        { side: 'out', id: 'value-out', type: 'any', desc: 'Same value, passed through only when condition is true' },
      ]} />

      <div style={s.warn}>
        ⚠️ The condition check happens at the <strong>top of the handler</strong>. If it's false,
        the entire handler returns early — not just one branch.
      </div>

      <div style={s.tip}>
        💡 The Boolean value wired to <code style={s.inlineCode}>condition</code> must come from
        somewhere in your graph — a Boolean event parameter (e.g. a contract emitting an
        <code style={s.inlineCode}> isValid</code> flag), or the result of a Contract Read that
        returns a Boolean. There is no separate comparison/operator node.
      </div>

      <div style={s.h4}>Example</div>
      <div style={s.example}>
        <div style={s.exampleTitle}>📋 Only save if a contract read returns true</div>
        <ol style={s.stepList}>
          <li>Add a Contract Read node that calls a function returning a Boolean (e.g. <code style={s.inlineCode}>isWhitelisted(address)</code>).</li>
          <li>Wire the address parameter into the Contract Read input.</li>
          <li>Add a Conditional node. Wire Contract Read <code style={s.inlineCode}>out-result</code> → Conditional <code style={s.inlineCode}>condition</code>.</li>
          <li>Wire whatever value you want to gate through Conditional <code style={s.inlineCode}>value</code> → <code style={s.inlineCode}>value-out</code> → entity field.</li>
          <li>If <code style={s.inlineCode}>isWhitelisted</code> returns false, the handler exits and nothing is saved.</li>
        </ol>
      </div>
    </Collapsible>
  );
}

function ContractReadSection() {
  return (
    <Collapsible title="Contract Read" color="#34d399" icon={BookOpen} badge="On-chain Query">
      <p style={s.p}>
        A <strong style={{ color: '#e2e8f0' }}>Contract Read</strong> node lets you call a
        view/pure function on a contract <em>during</em> an event handler — before saving the entity.
        Use it to fetch extra on-chain data that wasn't included in the event itself.
      </p>
      <p style={s.p}>
        For example: a <code style={s.inlineCode}>Transfer</code> event tells you <em>who</em>
        transferred and <em>how much</em>, but not the sender's new balance. A Contract Read can
        call <code style={s.inlineCode}>balanceOf(sender)</code> at that block to get the balance.
      </p>

      <div style={s.h4}>Setup</div>
      <ol style={s.stepList}>
        <li>Add a Contract Read node.</li>
        <li>From the <strong>Contract</strong> dropdown, pick the Contract node whose functions you want to call.</li>
        <li>From the <strong>Function</strong> dropdown, pick the read function (view/pure) to call.</li>
        <li>Input ports appear for each function argument. Wire them from event parameters or other values.</li>
        <li>Output ports appear for each return value. Wire them into entity fields.</li>
      </ol>

      <div style={s.h4}>Address binding — automatic, no wire needed</div>
      <p style={s.p}>
        The Contract Read node <strong>automatically uses the instance address</strong> configured
        for the selected contract in the Networks panel. You do <em>not</em> need to wire an address
        to make a cross-contract read work — just pick the contract and function from the dropdowns.
      </p>
      <p style={s.p}>
        If you need to call the function at a <em>dynamic</em> address (one that comes from the
        event itself, for example), wire that address value into the optional
        <code style={s.inlineCode}> address</code> override input port. This overrides the
        auto-bound instance address for that call only.
      </p>

      <div style={s.h4}>Ports (dynamic — set by chosen function)</div>
      <PortTable rows={[
        { side: 'in', id: 'address', type: 'Address', desc: 'Optional override: call the function at this address instead of the configured instance address.' },
        { side: 'in', id: 'in-{paramName}', type: 'varies', desc: 'Argument to pass to the function call. One port per ABI parameter.' },
        { side: 'out', id: 'out-{returnName}', type: 'varies', desc: 'Return value from the function call. One port per ABI return value.' },
      ]} />

      <div style={s.warn}>
        ⚠️ Port names on a Contract Read node (<code style={s.inlineCode}>in-{'{'}paramName{'}'}</code> and <code style={s.inlineCode}>out-{'{'}returnName{'}'}</code>) are generated
        directly from the ABI. The exact names depend on how the function's
        parameters and return values are named in the contract.
      </div>

      <div style={s.h4}>Example</div>
      <div style={s.example}>
        <div style={s.exampleTitle}>📋 Fetch token balance after each Transfer</div>
        <p style={{ ...s.p, marginBottom: 8 }}>
          Assumes <code style={s.inlineCode}>balanceOf(address account)</code> returning <code style={s.inlineCode}>uint256</code>.
          Your ABI's parameter names may differ — check the ports that appear on the node.
        </p>
        <ol style={s.stepList}>
          <li>Wire <code style={s.inlineCode}>event-Transfer</code> → Entity <code style={s.inlineCode}>evt</code>. Add a <code style={s.inlineCode}>senderBalance</code> field (BigInt) to the entity.</li>
          <li>Add a Contract Read node. Pick <code style={s.inlineCode}>MyToken</code> from the Contract dropdown, then pick <code style={s.inlineCode}>balanceOf(address)</code> from the Function dropdown.</li>
          <li>The node auto-binds to the MyToken instance address — no address wire needed.</li>
          <li>Expand the Transfer event chevron. Wire <code style={s.inlineCode}>event-Transfer-from</code> → the Contract Read's <code style={s.inlineCode}>in-account</code> input port (the address argument).</li>
          <li>Wire the Contract Read output port → Entity <code style={s.inlineCode}>field-senderBalance</code>.</li>
        </ol>
      </div>

      <div style={s.example}>
        <div style={s.exampleTitle}>📋 Cross-contract read (e.g. read from a different contract)</div>
        <ol style={s.stepList}>
          <li>Add a second Contract node (e.g. <code style={s.inlineCode}>PriceOracle</code>) and load its ABI.</li>
          <li>Add a Contract Read node → pick <code style={s.inlineCode}>PriceOracle</code> → pick the read function.</li>
          <li>The node auto-binds to PriceOracle's configured instance address. No bind-address wire is needed.</li>
          <li>Wire event parameters into the argument ports and the output into entity fields as normal.</li>
        </ol>
      </div>
    </Collapsible>
  );
}

function GenerateSection() {
  return (
    <Collapsible title="Generate" color="#a78bfa" icon={Zap} badge="Output">
      <p style={s.p}>
        Clicking <strong style={{ color: '#a78bfa' }}>Generate</strong> in the toolbar opens a
        <strong style={{ color: '#e2e8f0' }}> directory-picker modal</strong>. Choose where on your
        filesystem the output files should be written, then confirm. The server creates the directory
        if it doesn't already exist.
      </p>

      <div style={s.h4}>Two input modes</div>
      <table style={s.portTable}>
        <tbody>
          <tr>
            <td style={{ ...s.td, fontWeight: 700, width: 100, color: '#a78bfa', fontFamily: 'ui-monospace, monospace' }}>Type path</td>
            <td style={s.td}>
              Free-form monospace text field. Type or paste any absolute path. Press{' '}
              <code style={s.inlineCode}>Enter</code> or click <strong>Generate</strong> to confirm.
              Press <code style={s.inlineCode}>Escape</code> or click outside the modal to cancel.
            </td>
          </tr>
          <tr>
            <td style={{ ...s.td, fontWeight: 700, color: '#a78bfa', fontFamily: 'ui-monospace, monospace' }}>Browse…</td>
            <td style={s.td}>
              Click <strong>Browse…</strong> to open the server-backed filesystem navigator.
              The text input switches to read-only and shows the currently browsed path.
              Click any folder in the list to descend into it. Use the{' '}
              <strong>↑ chevron</strong> (toolbar left) to go up one level. Click the{' '}
              <FolderPlus size={11} style={{ verticalAlign: 'middle', color: '#a78bfa' }} />{' '}
              icon to create a new subfolder at the current location — type a name and press{' '}
              <code style={s.inlineCode}>Enter</code> or click <strong>Create</strong>.
              Click <strong>Type path</strong> to switch back to free-form entry.
            </td>
          </tr>
        </tbody>
      </table>

      <div style={s.h4}>Output files written</div>
      <table style={s.portTable}>
        <tbody>
          {[
            ['subgraph.yaml', 'Subgraph manifest — data sources, event handlers, ABI references'],
            ['schema.graphql', 'GraphQL entity schema derived from your entity nodes'],
            ['networks.json', 'Per-chain deployed addresses and start blocks from the Networks panel'],
            ['src/mappings/{Contract}.ts', 'Compiled AssemblyScript handler for each contract'],
            ['package.json', 'npm scripts: graph codegen, graph build, graph deploy — ready to run'],
            ['howto.md', 'Step-by-step deployment guide to The Graph Studio'],
          ].map(([file, desc]) => (
            <tr key={file}>
              <td style={{ ...s.td, fontFamily: 'ui-monospace, monospace', fontSize: 10, color: '#a78bfa', whiteSpace: 'nowrap', width: 200 }}>{file}</td>
              <td style={s.td}>{desc}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={s.tip}>
        💡 <strong>After generating:</strong> open a terminal in the output directory and run
        <code style={{ ...s.inlineCode, marginLeft: 4 }}>npm install</code> followed by{' '}
        <code style={s.inlineCode}>npm run codegen</code>,{' '}
        <code style={s.inlineCode}>npm run build</code>, and{' '}
        <code style={s.inlineCode}>npm run deploy</code>. The <code style={s.inlineCode}>howto.md</code>{' '}
        file included in the output walks through each step in detail.
      </div>

      <div style={s.warn}>
        ⚠️ The Generate button is <strong>disabled</strong> while validation errors (red outlines)
        exist. Fix all errors before generating. Warnings (amber) are advisory and do not block
        generation.
      </div>
    </Collapsible>
  );
}

function NetworksSection() {
  return (
    <Collapsible title="Networks panel" color="#94a3b8" icon={Globe}>
      <p style={s.p}>
        The <strong style={{ color: '#e2e8f0' }}>Networks</strong> panel (top-right button) is where
        you configure the actual deployed contract addresses and start blocks for each chain you want
        to index.
      </p>
      <p style={s.p}>
        One <strong>Network</strong> = one deployment target (e.g. mainnet, or Arbitrum One). Within
        each network, you can set addresses for every Contract node in your graph. You can also add
        multiple <strong>instances</strong> of the same contract type — useful for factory contracts
        where many copies of the same contract exist at different addresses.
      </p>

      <div style={s.h4}>Fields per instance</div>
      <table style={s.portTable}>
        <tbody>
          <tr><td style={{ ...s.td, fontWeight: 700, width: 100 }}>Label</td><td style={s.td}>A short name to distinguish instances of the same contract type (e.g. "pool-A", "pool-B"). Can be left blank if there's only one.</td></tr>
          <tr><td style={{ ...s.td, fontWeight: 700 }}>Address</td><td style={s.td}>The deployed contract address on this network, starting with <code style={s.inlineCode}>0x</code>.</td></tr>
          <tr><td style={{ ...s.td, fontWeight: 700 }}>Start Block</td><td style={s.td}>The block number where this contract was deployed. Indexing begins here — don't leave it at 0 or sync will take forever.</td></tr>
        </tbody>
      </table>

      <div style={s.tip}>
        💡 After adding networks and addresses, click <strong>Generate</strong>. The tool produces
        a <code style={s.inlineCode}>networks.json</code> file alongside the subgraph files so you
        can deploy to each network by name.
      </div>
    </Collapsible>
  );
}

function LibrarySection() {
  return (
    <Collapsible title="Canvas Library" color="#94a3b8" icon={FolderOpen}>
      <p style={s.p}>
        The <strong style={{ color: '#e2e8f0' }}>Canvas Library</strong> (Library button, top-center)
        lets you save, load, and manage multiple canvas configurations — like a project manager for
        your subgraph designs.
      </p>
      <table style={s.portTable}>
        <tbody>
          <tr><td style={{ ...s.td, fontWeight: 700, width: 80 }}>Save</td><td style={s.td}>Saves the current canvas under a name of your choice. Overwrites if you save again with the same name.</td></tr>
          <tr><td style={{ ...s.td, fontWeight: 700 }}>Load</td><td style={s.td}>Replaces the current canvas with the saved one. Your unsaved work will be lost.</td></tr>
          <tr><td style={{ ...s.td, fontWeight: 700 }}>New</td><td style={s.td}>Clears the canvas entirely. Asks for confirmation first.</td></tr>
          <tr><td style={{ ...s.td, fontWeight: 700 }}>Export</td><td style={s.td}>Downloads the current canvas as a <code style={s.inlineCode}>.json</code> file you can share or back up.</td></tr>
          <tr><td style={{ ...s.td, fontWeight: 700 }}>Import</td><td style={s.td}>Loads a <code style={s.inlineCode}>.json</code> file exported from this tool (or another instance).</td></tr>
        </tbody>
      </table>
    </Collapsible>
  );
}

function WiringSection() {
  return (
    <Collapsible title="Wiring rules & tips" color="#f472b6" icon={GitBranch}>
      <p style={s.p}>
        Connections (wires) carry data from one node's output port to another node's input port.
        Port IDs are documented in each node's help section above. Drag from any port circle to
        begin drawing a wire; release it on a compatible port on another node.
      </p>

      <div style={s.h4}>Rules</div>
      <ul style={{ ...s.stepList, listStyleType: 'disc' }}>
        <li>You can only wire outputs (right side) to inputs (left side) — not the other way.</li>
        <li>A node cannot connect to itself.</li>
        <li>Type mismatches are flagged as <strong style={{ color: '#ef4444' }}>errors</strong> (red animated wire) — fix them with a Type Cast node.</li>
        <li>Delete a wire by clicking it to select it, then pressing <code style={s.inlineCode}>Delete</code> or <code style={s.inlineCode}>Backspace</code>.</li>
        <li>Delete a node by clicking it to select it, then pressing <code style={s.inlineCode}>Delete</code> / <code style={s.inlineCode}>Backspace</code>, or clicking the <strong>×</strong> button in its header.</li>
        <li>To start a wire, click and drag from any port circle on the right side of a node.</li>
      </ul>

      <div style={s.h4}>The most important connection</div>
      <p style={s.p}>
        Every data flow needs an event trigger to drive it. There are two ways to connect events:
      </p>
      <ul style={{ ...s.stepList, listStyleType: 'disc' }}>
        <li>
          <strong>evt wire</strong> — drag from a Contract's amber event port to an Entity's
          <code style={s.inlineCode}> evt</code> port. When you drop it on a fresh entity, fields auto-populate from the event's parameters.
        </li>
        <li>
          <strong>Trigger Events checklist</strong> — tick events inside the node's Trigger Events panel (both Entity and Aggregate Entity have this).
          No wire needed. Useful for multi-event triggers or when you don't need the auto-populate behaviour.
        </li>
      </ul>
      <p style={s.p}>
        Both methods can be combined. The checklist is the <em>only</em> option for Aggregate Entities, which do not have an
        <code style={s.inlineCode}> evt</code> port.
      </p>

      <div style={s.h4}>Auto-populate</div>
      <p style={s.p}>
        When you wire an event trigger to a fresh Entity, the node automatically
        creates fields matching that event's parameters. You can then add, rename, or remove fields
        manually.
      </p>

      <div style={s.h4}>Unwired fields — auto-fill</div>
      <p style={s.p}>
        If an entity field's input port is not wired, the compiler looks for an event parameter
        with the same name and uses it automatically. The field type in your entity <strong>must
        match</strong> the event parameter's graph type exactly (or be <code style={s.inlineCode}>Bytes</code> when
        the param type is <code style={s.inlineCode}>Address</code> — Address extends Bytes in AssemblyScript).
        Any other type mismatch is a hard error; the generate step will fail with a clear message
        rather than silently producing null fields.
      </p>
      <p style={s.p}>
        Only wire explicitly when you want to use a different value (a transformed value, a read
        function result, etc.).
      </p>
    </Collapsible>
  );
}

function TroubleshootingSection() {
  return (
    <Collapsible title="Troubleshooting" color="#ef4444" icon={GitBranch}>

      <div style={s.h4}>Fields are null / zero in the deployed subgraph</div>
      <p style={s.p}>
        The most common cause is an unwired entity field whose name doesn't match any event
        parameter — auto-fill only kicks in when the names match exactly (case-sensitive).
        Check the field name in your Entity node against the parameter name shown on the
        Contract node's event chevron.
      </p>

      <div style={s.h4}>TS2322 type error during <code style={s.inlineCode}>graph build</code></div>
      <p style={s.p}>
        Example error:
      </p>
      <pre style={{ fontSize: 10, fontFamily: 'ui-monospace, monospace', color: '#fca5a5', background: '#1e1e2e', padding: 8, borderRadius: 6, marginBottom: 8, whiteSpace: 'pre-wrap' }}>
{`ERROR TS2322: Type 'Bytes' is not assignable to
type 'Array<BigInt> | null'

   entity.accounts = event.params.accounts`}
      </pre>
      <p style={s.p}>
        This means auto-fill produced a type mismatch — the entity field type and the event
        param type are different. Since the latest compiler version this is caught <em>before</em>{' '}
        <code style={s.inlineCode}>graph build</code> and shown as a generate error. If you see it in
        <code style={s.inlineCode}>graph build</code>, you are running files generated by an older version —
        hit Generate again to regenerate with the current compiler.
      </p>
      <p style={s.p}>
        Fix: change the entity field type to match the event param type shown on the contract
        node, or draw an explicit wire through a Type Cast node if you need a conversion.
      </p>

      <div style={s.h4}>Indexed array parameter shows as <code style={s.inlineCode}>Bytes</code> not <code style={s.inlineCode}>[Type!]</code></div>
      <p style={s.p}>
        In Ethereum event logs, an <code style={s.inlineCode}>indexed</code> parameter of a reference type
        (any array, <code style={s.inlineCode}>bytes</code>, <code style={s.inlineCode}>string</code>, tuple) is stored as the
        <strong> keccak256 hash</strong> of its ABI-encoded value — not the value itself.
        graph-cli generates <code style={s.inlineCode}>Bytes</code> for these parameters because only the
        32-byte hash is available on-chain; the original array cannot be recovered.
      </p>
      <p style={s.p}>
        The ABI parser in this tool reflects this correctly — it emits <code style={s.inlineCode}>Bytes</code>
        for indexed reference-type params. Your entity field for such a param must also be
        <code style={s.inlineCode}> Bytes</code>. If you want the actual array values, use non-indexed
        parameters or individual per-item events instead.
      </p>

      <div style={s.h4}>Entity field type is wrong after re-parsing the ABI</div>
      <p style={s.p}>
        Re-parsing the ABI updates the <em>Contract node's</em> event param types. It does
        <strong> not</strong> retroactively update field types on Entity nodes you already
        created. If the ABI parser now reports a different type for a param, go to the
        Entity node and manually update the field:
      </p>
      <ol style={s.stepList}>
        <li>Click the type dropdown and select the correct type.</li>
        <li>If the field was a list (<code style={s.inlineCode}>[ ]</code> button lit up) but should now be
          a scalar, click <code style={s.inlineCode}>[ ]</code> to deactivate list mode.</li>
      </ol>

      <div style={s.h4}>Auto-fill type mismatch error on generate</div>
      <p style={s.p}>
        The compiler stops and reports an error like:
      </p>
      <pre style={{ fontSize: 10, fontFamily: 'ui-monospace, monospace', color: '#fca5a5', background: '#1e1e2e', padding: 8, borderRadius: 6, marginBottom: 8, whiteSpace: 'pre-wrap' }}>
{`Auto-fill type mismatch in entity 'MyEntity', field 'accounts':
  Entity field type : [BigInt!]
  Event param type  : Bytes`}
      </pre>
      <p style={s.p}>
        The entity field type does not match the event parameter type. The compiler refuses
        to silently produce a null or wrong-typed field. Fix: change the entity field type
        to match the param type shown in the error (or use an explicit wire through a Type
        Cast node for intentional conversions).
      </p>

      <div style={s.h4}>Contract address shows as the zero address in results</div>
      <p style={s.p}>
        The contract's deployed address was not set in the <strong>Networks panel</strong>.
        The compiler reads the address from there — not from the inline address field on the
        Contract node. Open the Networks panel, find your contract, and enter the deployed
        address in the Instances section.
      </p>

      <div style={s.h4}>Subgraph syncs from block 0 (takes forever)</div>
      <p style={s.p}>
        The <code style={s.inlineCode}>startBlock</code> in the Networks panel was left at 0 or not set.
        Set it to the block your contract was first deployed at — this is visible on Etherscan
        (the "Contract Creation" transaction). Using the correct start block avoids indexing
        millions of irrelevant blocks.
      </p>

    </Collapsible>
  );
}

function ScenariosSection() {
  return (
    <Collapsible title="Example scenarios" color="#fb923c" icon={Zap} defaultOpen>
      <div style={s.example}>
        <div style={s.exampleTitle}>🏦 Scenario 1: Record every ERC-20 transfer</div>
        <p style={s.p}><em>Goal: save one database row per Transfer event, with from, to, and amount.</em></p>
        <ol style={s.stepList}>
          <li>Add Contract → name it <code style={s.inlineCode}>MyToken</code> → paste ERC-20 ABI.</li>
          <li>Add Entity → wire <code style={s.inlineCode}>event-Transfer</code> → <code style={s.inlineCode}>evt</code>. Fields auto-populate.</li>
          <li>Set ID strategy to <strong>tx.hash + log index</strong>.</li>
          <li>Add a Network → enter token address + deploy block.</li>
          <li>Click Generate. Done.</li>
        </ol>
      </div>

      <div style={s.example}>
        <div style={s.exampleTitle}>📈 Scenario 2: Track a running total (TVL)</div>
        <p style={s.p}><em>Goal: maintain one record with a balance that increases on Deposit and decreases on Withdraw.</em></p>
        <ol style={s.stepList}>
          <li>Add Contract → upload ABI with <code style={s.inlineCode}>Deposit(uint256 amount)</code> and <code style={s.inlineCode}>Withdraw(uint256 amount)</code> events.</li>
          <li>Add Aggregate Entity → name <code style={s.inlineCode}>TVL</code> → add field <code style={s.inlineCode}>balance</code> (BigInt).</li>
          <li>In the <strong>Trigger Events</strong> checklist on the TVL node, tick <code style={s.inlineCode}>Deposit</code>.</li>
          <li>Wire <code style={s.inlineCode}>implicit-address</code> → TVL <code style={s.inlineCode}>field-id</code>.</li>
          <li>Add Math (add): TVL <code style={s.inlineCode}>field-prev-balance</code> → left; expand <code style={s.inlineCode}>event-Deposit</code> chevron, wire <code style={s.inlineCode}>event-Deposit-amount</code> → right.</li>
          <li>Wire Math result → TVL <code style={s.inlineCode}>field-in-balance</code>.</li>
          <li>Add a second Aggregate Entity, also named <code style={s.inlineCode}>TVL</code>, same <code style={s.inlineCode}>balance</code> field. Tick <code style={s.inlineCode}>Withdraw</code> in its checklist. Wire Math (subtract) the same way.</li>
        </ol>
      </div>

      <div style={s.example}>
        <div style={s.exampleTitle}>🔑 Scenario 3: Composite ID (user + pool)</div>
        <p style={s.p}><em>Goal: one entity row per unique user-pool combination.</em></p>
        <ol style={s.stepList}>
          <li>Wire <code style={s.inlineCode}>event-Deposit-user</code> (Address) → TypeCast (Address→String) → String Concat <strong>left</strong>.</li>
          <li>Wire <code style={s.inlineCode}>implicit-address</code> → TypeCast (Address→String) → String Concat <strong>right</strong>.</li>
          <li>Set String Concat separator to <code style={s.inlineCode}>-</code>.</li>
          <li>Wire String Concat <strong>result</strong> → Entity <code style={s.inlineCode}>field-id</code> (ID strategy: Custom).</li>
          <li>Result: IDs like <code style={s.inlineCode}>0xuser...-0xpool...</code></li>
        </ol>
      </div>

      <div style={s.example}>
        <div style={s.exampleTitle}>🔭 Scenario 4: Enrich with on-chain read</div>
        <p style={s.p}><em>Goal: save each Transfer plus the sender's token balance at that block (fetched on-chain).</em></p>
        <ol style={s.stepList}>
          <li>Wire <code style={s.inlineCode}>event-Transfer</code> → Entity <code style={s.inlineCode}>evt</code>. Add a <code style={s.inlineCode}>senderBalance</code> field (BigInt) to the entity.</li>
          <li>Add a Contract Read node → pick <code style={s.inlineCode}>MyToken</code> → pick <code style={s.inlineCode}>balanceOf(address)</code>.</li>
          <li>Expand the Transfer event chevron. Wire <code style={s.inlineCode}>event-Transfer-from</code> → the Contract Read's address input port.</li>
          <li>Wire the Contract Read's return value output port → Entity <code style={s.inlineCode}>field-senderBalance</code>. (The output port name matches the ABI return value name.)</li>
        </ol>
      </div>

      <div style={s.example}>
        <div style={s.exampleTitle}>🏦 Scenario 5: Running TVL with full history log (Alchemix pattern)</div>
        <p style={s.p}>
          <em>Goal: keep a single TVL record that updates on every Deposit, AND save one history row
          per Deposit that links back to the TVL record — so you can query both the current balance
          and a complete log of changes.</em>
        </p>
        <p style={{ ...s.p, fontWeight: 600, color: '#a78bfa', marginBottom: 4 }}>Step 1 — Set up the TVL aggregate (running balance)</p>
        <ol style={s.stepList}>
          <li>Add an <strong>Aggregate Entity</strong> node, name it <code style={s.inlineCode}>AlchemistTVL</code>.</li>
          <li>Add a field <code style={s.inlineCode}>netBalance</code> (BigInt).</li>
          <li>Add an <code style={s.inlineCode}>activity</code> field, type → choose <code style={s.inlineCode}>AlchemistTVLHistory</code> from the Entities group. Click the <strong>🔗 link icon</strong> and type <code style={s.inlineCode}>tvl</code> in the box — this creates a <code style={s.inlineCode}>@derivedFrom(field: "tvl")</code> reverse relation.</li>
          <li>In the <strong>Trigger Events</strong> checklist on this node, tick <code style={s.inlineCode}>Deposit</code>. <em>Do not wire an evt port.</em></li>
          <li>Wire <code style={s.inlineCode}>implicit-address</code> → <code style={s.inlineCode}>AlchemistTVL field-id</code>.</li>
          <li>Add a <strong>Math (add)</strong> node.</li>
          <li>Wire <code style={s.inlineCode}>AlchemistTVL field-prev-netBalance</code> → Math <strong>left</strong>.</li>
          <li>Expand the Deposit chevron. Wire <code style={s.inlineCode}>event-Deposit-amount</code> → Math <strong>right</strong>.</li>
          <li>Wire Math <strong>result</strong> → <code style={s.inlineCode}>AlchemistTVL field-in-netBalance</code>.</li>
        </ol>
        <p style={{ ...s.p, fontWeight: 600, color: '#a78bfa', marginBottom: 4, marginTop: 10 }}>Step 2 — Set up the history entity (one row per event)</p>
        <ol style={s.stepList}>
          <li>Add an <strong>Entity</strong> node, name it <code style={s.inlineCode}>AlchemistTVLHistory</code>.</li>
          <li>Add a <code style={s.inlineCode}>tvl</code> field, type → choose <code style={s.inlineCode}>AlchemistTVL</code> from the Entities group. <em>Do NOT click the link icon — this is a real stored foreign key, not a reverse relation.</em></li>
          <li>Add a <code style={s.inlineCode}>netBalance</code> field (BigInt) to record the balance at this point in time.</li>
          <li>Wire <code style={s.inlineCode}>event-Deposit</code> → <code style={s.inlineCode}>AlchemistTVLHistory evt</code>.</li>
          <li>Set ID strategy to <strong>tx.hash + log index</strong> (each Deposit gets its own row).</li>
          <li>Wire <code style={s.inlineCode}>AlchemistTVL field-out-id</code> (right dot on the id row) → <code style={s.inlineCode}>AlchemistTVLHistory field-tvl</code>. This stores the TVL record's ID as the foreign key.</li>
          <li>Wire <code style={s.inlineCode}>event-Deposit-amount</code> → <code style={s.inlineCode}>AlchemistTVLHistory field-netBalance</code>.</li>
        </ol>
        <div style={{ ...s.tip, marginTop: 8 }}>
          💡 After generating, you can query the TVL and navigate its history in one GraphQL request:
          <pre style={{ marginTop: 6, fontSize: 10, lineHeight: 1.5, fontFamily: 'ui-monospace, monospace', color: '#a5b4fc' }}>
{`{ alchemistTVL(id: "0x...") {
    netBalance
    activity { netBalance }
  }
}`}
          </pre>
        </div>
      </div>
    </Collapsible>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

const SECTIONS = [
  { key: 'overview',    label: 'Overview',         icon: Zap },
  { key: 'contract',   label: 'Contract',          icon: Zap },
  { key: 'entity',     label: 'Entity',            icon: Database },
  { key: 'aggregate',  label: 'Aggregate',         icon: LayoutGrid },
  { key: 'math',       label: 'Math',              icon: Calculator },
  { key: 'typecast',   label: 'Type Cast',         icon: ArrowRightLeft },
  { key: 'strconcat',  label: 'Str Concat',        icon: TextCursorInput },
  { key: 'conditional',label: 'Conditional',       icon: GitBranch },
  { key: 'cread',      label: 'Contract Read',     icon: BookOpen },
  { key: 'generate',   label: 'Generate',          icon: FolderPlus },
  { key: 'wiring',          label: 'Wiring',          icon: GitBranch },
  { key: 'troubleshooting', label: 'Troubleshoot',    icon: GitBranch },
  { key: 'scenarios',       label: 'Scenarios',       icon: Zap },
];

export default function HelpPanel({ isOpen, onClose }) {
  const [activeSection, setActiveSection] = useState('overview');

  if (!isOpen) return null;

  const scrollTo = (key) => {
    setActiveSection(key);
    const el = document.getElementById(`help-section-${key}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div style={s.overlay}>
      <div style={s.panel}>
        {/* Header */}
        <div style={s.header}>
          <span style={{ fontSize: 16 }}>📖</span>
          <span style={s.headerTitle}>How to use this editor</span>
          <button style={s.closeBtn} onClick={onClose} title="Close help">
            <X size={14} />
          </button>
        </div>

        {/* Quick-jump TOC */}
        <div style={s.toc}>
          <div style={s.tocLabel}>Jump to</div>
          <div style={s.tocRow}>
            {SECTIONS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                style={s.tocBtn(activeSection === key)}
                onClick={() => scrollTo(key)}
              >
                <Icon size={9} />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Scrollable content */}
        <div style={s.body}>
          <div id="help-section-overview"><OverviewSection /></div>
          <div id="help-section-contract"><ContractSection /></div>
          <div id="help-section-entity"><EntitySection /></div>
          <div id="help-section-aggregate"><AggregateEntitySection /></div>
          <div id="help-section-math"><MathSection /></div>
          <div id="help-section-typecast"><TypeCastSection /></div>
          <div id="help-section-strconcat"><StrConcatSection /></div>
          <div id="help-section-conditional"><ConditionalSection /></div>
          <div id="help-section-cread"><ContractReadSection /></div>
          <div id="help-section-generate"><GenerateSection /></div>
          <div id="help-section-wiring"><WiringSection /></div>
          <div id="help-section-troubleshooting"><TroubleshootingSection /></div>
          <div id="help-section-scenarios"><ScenariosSection /></div>
        </div>
      </div>
    </div>
  );
}
