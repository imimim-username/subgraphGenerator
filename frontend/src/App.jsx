import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import ContractNode from './nodes/ContractNode';
import EntityNode from './nodes/EntityNode';
import AggregateEntityNode from './nodes/AggregateEntityNode';
import MathNode from './nodes/MathNode';
import TypeCastNode from './nodes/TypeCastNode';
import StringConcatNode from './nodes/StringConcatNode';
import ConditionalNode from './nodes/ConditionalNode';
import ContractReadNode from './nodes/ContractReadNode';
import Toolbar from './components/Toolbar';
import NetworksPanel from './components/NetworksPanel';
import CanvasLibraryPanel from './components/CanvasLibraryPanel';
import HelpPanel from './components/HelpPanel';
import SimulatePanel from './components/SimulatePanel';
import { ValidationPanel } from './components/ValidationPanel';
import GenerateModal from './components/GenerateModal';
import { useValidation } from './hooks/useValidation';
import { useAutoLayout } from './hooks/useAutoLayout';
import { BookOpen, FolderOpen, Globe, HelpCircle, Save, Zap } from 'lucide-react';

// ── Node type registry ──────────────────────────────────────────────────────
const NODE_TYPES = {
  contract:         ContractNode,
  entity:           EntityNode,
  aggregateentity:  AggregateEntityNode,
  math:             MathNode,
  typecast:         TypeCastNode,
  strconcat:        StringConcatNode,
  conditional:      ConditionalNode,
  contractread:     ContractReadNode,
};

// ── Module-level ID sequence (updated on load to avoid collisions) ───────────
let _nodeIdSeq = 1;
function nextId(prefix) {
  return `${prefix}-${_nodeIdSeq++}`;
}
function _bumpSeqFromNodes(nodes) {
  for (const n of nodes) {
    const parts = n.id.split('-');
    const num = parseInt(parts[parts.length - 1], 10);
    if (!isNaN(num) && num >= _nodeIdSeq) _nodeIdSeq = num + 1;
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Strip non-serialisable values (functions) from node data before sending to the API. */
function _stripCallbacks(data) {
  if (!data || typeof data !== 'object') return data;
  const out = {};
  for (const [k, v] of Object.entries(data)) {
    if (typeof v !== 'function' && !k.startsWith('_')) out[k] = v;
  }
  return out;
}

// ── Edge style ───────────────────────────────────────────────────────────────
const DEFAULT_EDGE_OPTIONS = {
  style: { stroke: '#475569', strokeWidth: 2 },
  animated: false,
};

// ── Connection validator ─────────────────────────────────────────────────────
function isValidConnection(connection) {
  return connection.source !== connection.target;
}

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const reactFlowWrapper = useRef(null);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  const [networksOpen, setNetworksOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [simulateOpen, setSimulateOpen] = useState(false);
  const [networks, setNetworks] = useState([]);
  const [subgraphName, setSubgraphName] = useState('');
  const [saveStatus, setSaveStatus] = useState(null); // null | 'saving' | 'saved' | 'error'
  const [genStatus, setGenStatus] = useState(null);   // null | 'generating' | { files: [...] } | { error: string }
  const [genModalOpen, setGenModalOpen] = useState(false);
  const [genDir, setGenDir] = useState('');           // user-chosen output directory

  // ── Node data updater (passed into each node via data.onChange) ───────────
  const updateNodeData = useCallback((nodeId, patch) => {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...patch } } : n))
    );
  }, [setNodes]);

  // ── Node deleter (removes node + all its edges) ──────────────────────────
  const deleteNode = useCallback((nodeId) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
  }, [setNodes, setEdges]);

  // ── Load a full canvas from a data object (used by CanvasLibraryPanel) ──
  const loadCanvasData = useCallback((data) => {
    const rawNodes = data.nodes ?? [];
    // Pre-resolve contractread nodes whose contractNodeId was saved as '' —
    // this can happen when a node was created but its contract picker was never
    // explicitly changed. Without this, hidden (collapsed-contract) contractread
    // nodes never mount and their useEffect auto-persist never fires.
    const firstContractId = rawNodes.find((n) => n.type === 'contract' && n.data?.name)?.id ?? '';
    const rehydrated = rawNodes.map((rawNode) => {
      const nodeData = { ...rawNode.data };
      if (rawNode.type === 'contractread' && !nodeData.contractNodeId && firstContractId) {
        nodeData.contractNodeId = firstContractId;
      }
      return {
        ...rawNode,
        data: {
          ...nodeData,
          onChange: (patch) => updateNodeData(rawNode.id, patch),
          onDelete: () => deleteNode(rawNode.id),
        },
      };
    });
    _bumpSeqFromNodes(rehydrated);
    setNodes(rehydrated);
    setEdges(
      (data.edges ?? []).map((e) => ({
        ...e,
        style: e.style ?? DEFAULT_EDGE_OPTIONS.style,
        animated: e.animated ?? false,
      }))
    );
    setSubgraphName(data.subgraph_name ?? '');
    setNetworks(data.networks ?? []);
  }, [updateNodeData, deleteNode, setNodes, setEdges, setSubgraphName, setNetworks]);

  // ── Clear the canvas (new canvas) ────────────────────────────────────────
  const newCanvas = useCallback(() => {
    setNodes([]);
    setEdges([]);
    setSubgraphName('');
  }, [setNodes, setEdges, setSubgraphName]);

  // ── Rehydrate a raw node from disk (attach callbacks) ────────────────────
  const rehydrateNode = useCallback(
    (rawNode) => ({
      ...rawNode,
      data: {
        ...rawNode.data,
        onChange: (patch) => updateNodeData(rawNode.id, patch),
        onDelete: () => deleteNode(rawNode.id),
      },
    }),
    [updateNodeData, deleteNode]
  );

  // ── Load visual-config.json on mount ─────────────────────────────────────
  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((config) => {
        if (config.nodes && config.nodes.length > 0) {
          // Pre-resolve empty contractNodeId (same logic as loadCanvasData)
          const firstContractId = config.nodes.find((n) => n.type === 'contract' && n.data?.name)?.id ?? '';
          const rehydrated = config.nodes.map((rawNode) => {
            const nodeData = { ...rawNode.data };
            if (rawNode.type === 'contractread' && !nodeData.contractNodeId && firstContractId) {
              nodeData.contractNodeId = firstContractId;
            }
            return { ...rehydrateNode({ ...rawNode, data: nodeData }) };
          });
          _bumpSeqFromNodes(rehydrated);
          setNodes(rehydrated);
          setEdges(
            (config.edges ?? []).map((e) => ({
              ...e,
              style: e.style ?? DEFAULT_EDGE_OPTIONS.style,
              animated: e.animated ?? false,
            }))
          );
          setNetworks(config.networks ?? []);
          setSubgraphName(config.subgraph_name ?? '');
        }
      })
      .catch((err) => console.warn('[load] failed to load config:', err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // mount only — updateNodeData/rehydrateNode are stable

  // ── Default data per node type ────────────────────────────────────────────
  const defaultData = useCallback(
    (type, id) => {
      const base = { onChange: (patch) => updateNodeData(id, patch), onDelete: () => deleteNode(id) };
      switch (type) {
        case 'contract':
          return { ...base, name: '', abi: null, events: [], readFunctions: [], collapsed: false };
        case 'entity':
          return { ...base, name: '', idStrategy: 'custom', fields: [{ name: 'id', type: 'ID', required: true }] };
        case 'aggregateentity':
          return { ...base, name: '', fields: [{ name: 'id', type: 'ID', required: true }], sourceEvent: null };
        case 'math':
          return { ...base, operation: 'add' };
        case 'typecast':
          return { ...base, castIndex: 0 };
        case 'strconcat':
          return { ...base, separator: '' };
        case 'conditional':
          return { ...base };
        case 'contractread':
          return { ...base, contractNodeId: '', fnIndex: 0 };
        default:
          return base;
      }
    },
    [updateNodeData]
  );

  // ── Generic add-node factory ───────────────────────────────────────────────
  const addNode = useCallback(
    (type, screenPos) => {
      const id = nextId(type);
      const position = reactFlowInstance
        ? reactFlowInstance.screenToFlowPosition(screenPos ?? { x: 250, y: 200 })
        : (screenPos ?? { x: 250, y: 200 });
      setNodes((nds) => [
        ...nds,
        { id, type, position, data: defaultData(type, id) },
      ]);
    },
    [reactFlowInstance, setNodes, defaultData]
  );

  const addContractNode        = useCallback(() => addNode('contract'),         [addNode]);
  const addEntityNode          = useCallback(() => addNode('entity'),           [addNode]);
  const addAggregateEntityNode = useCallback(() => addNode('aggregateentity'),  [addNode]);
  const addMathNode            = useCallback(() => addNode('math'),             [addNode]);
  const addTypeCastNode        = useCallback(() => addNode('typecast'),         [addNode]);
  const addStrConcatNode       = useCallback(() => addNode('strconcat'),        [addNode]);
  const addConditionalNode     = useCallback(() => addNode('conditional'),      [addNode]);
  const addContractReadNode    = useCallback(() => addNode('contractread'),     [addNode]);

  // ── Edge connection ────────────────────────────────────────────────────────
  const onConnect = useCallback(
    (params) => {
      // When an event port is wired to an entity's "evt" trigger port,
      // auto-populate the entity's fields from the ABI event params.
      if (params.targetHandle === 'evt') {
        const sourceNode = nodes.find((n) => n.id === params.source);
        const targetNode = nodes.find((n) => n.id === params.target);
        const isEntityTarget = targetNode?.type === 'entity' || targetNode?.type === 'aggregateentity';
        if (sourceNode?.type === 'contract' && isEntityTarget) {
          const eventName = params.sourceHandle?.replace(/^event-/, '');
          const event = sourceNode.data.events?.find((e) => e.name === eventName);
          if (event) {
            const existingFields = targetNode.data.fields ?? [];
            const hasCustomFields = existingFields.some((f) => !f.required && f.name.trim());
            if (!hasCustomFields) {
              const newFields = [
                { name: 'id', type: 'ID', required: true },
                ...event.params.map((p) => ({ name: p.name, type: p.graph_type, required: false })),
              ];
              updateNodeData(targetNode.id, {
                fields: newFields,
                sourceEvent: eventName,
                // Suggest entity name from event name if not already set
                name: targetNode.data.name.trim() || eventName,
              });
            } else {
              // Fields already set — just record the source event
              updateNodeData(targetNode.id, { sourceEvent: eventName });
            }
          }
        }
      }
      setEdges((eds) => addEdge({ ...params, ...DEFAULT_EDGE_OPTIONS }, eds));
    },
    [setEdges, nodes, updateNodeData]
  );

  // ── Drag-and-drop from toolbar ─────────────────────────────────────────────
  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData('application/subgraph-node-type');
      if (!nodeType || !reactFlowInstance) return;
      addNode(nodeType, { x: event.clientX, y: event.clientY });
    },
    [reactFlowInstance, addNode]
  );

  // ── Build payload for API calls ───────────────────────────────────────────
  const buildPayload = useCallback(() => ({
    schema_version: 1,
    subgraph_name: subgraphName,
    networks,
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: _stripCallbacks(n.data),
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      sourceHandle: e.sourceHandle ?? '',
      target: e.target,
      targetHandle: e.targetHandle ?? '',
    })),
  }), [subgraphName, networks, nodes, edges]);

  // ── Save visual-config.json ───────────────────────────────────────────────
  const saveConfig = useCallback(async () => {
    setSaveStatus('saving');
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload()),
      });
      if (res.ok) {
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus(null), 2000);
      } else {
        setSaveStatus('error');
        setTimeout(() => setSaveStatus(null), 3000);
      }
    } catch {
      setSaveStatus('error');
      setTimeout(() => setSaveStatus(null), 3000);
    }
  }, [buildPayload]);

  // ── Generate output files ─────────────────────────────────────────────────
  const generateFiles = useCallback(async (dir) => {
    setGenModalOpen(false);
    setGenStatus('generating');
    try {
      const url = dir ? `/api/generate?dir=${encodeURIComponent(dir)}` : '/api/generate';
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload()),
      });
      if (res.ok) {
        const data = await res.json();
        setGenStatus({ files: data.files ?? [], dir: data.dir ?? dir ?? '' });
        setTimeout(() => setGenStatus(null), 8000);
      } else {
        const data = await res.json().catch(() => ({}));
        setGenStatus({ error: data.detail ?? 'Generation failed' });
        setTimeout(() => setGenStatus(null), 6000);
      }
    } catch (err) {
      setGenStatus({ error: String(err) });
      setTimeout(() => setGenStatus(null), 6000);
    }
  }, [buildPayload]);

  // ── Validation ────────────────────────────────────────────────────────────
  const { issues, hasErrors, issuesByNodeId, issuesByEdgeId, isValidating } =
    useValidation(nodes, edges);

  // ── Auto-layout ───────────────────────────────────────────────────────────
  const applyLayout = useAutoLayout(nodes, edges, setNodes, reactFlowInstance);

  // BFS from collapsed contracts → hide ALL downstream nodes (not just entities).
  // A node stays visible if it is also reachable from an expanded contract (shared-node case).
  const hiddenNodeIds = useMemo(() => {
    const contractNodes = nodes.filter((n) => n.type === 'contract');
    if (contractNodes.every((n) => !n.data?.collapsed)) return new Set(); // fast path

    const collapsedIds = new Set(contractNodes.filter((n) => n.data?.collapsed).map((n) => n.id));
    const expandedIds  = new Set(contractNodes.filter((n) => !n.data?.collapsed).map((n) => n.id));

    // Build outgoing adjacency from edges
    const adj = new Map();
    for (const edge of edges) {
      if (!adj.has(edge.source)) adj.set(edge.source, []);
      adj.get(edge.source).push(edge.target);
    }

    function reachableFrom(startIds) {
      const visited = new Set();
      const queue = [...startIds];
      while (queue.length > 0) {
        const cur = queue.shift();
        if (visited.has(cur)) continue;
        visited.add(cur);
        for (const next of (adj.get(cur) ?? [])) queue.push(next);
      }
      return visited;
    }

    const fromCollapsed = reachableFrom([...collapsedIds]);
    const fromExpanded  = reachableFrom([...expandedIds]);

    // Hide nodes reachable only from collapsed contracts (exclude the contract nodes themselves)
    const hidden = new Set();
    for (const nodeId of fromCollapsed) {
      if (!fromExpanded.has(nodeId) && !collapsedIds.has(nodeId)) {
        hidden.add(nodeId);
      }
    }
    return hidden;
  // Intentionally exclude node `hidden` flags from deps to avoid infinite loop.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    // eslint-disable-next-line react-hooks/exhaustive-deps
    edges,
    // Only re-run when contract collapsed state or the node list itself changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
    nodes.map((n) => (n.type === 'contract' ? `${n.id}:${n.data?.collapsed}` : n.id)).join(','),
  ]);

  // Derived nodes: attach _issues, _allEntityNames, _allContracts and className
  // for visual feedback; hide all downstream nodes of collapsed contracts
  const displayNodes = useMemo(() => {
    // Collect all entity/aggregateentity names so nodes can populate their type dropdowns
    const _allEntityNames = nodes
      .filter((n) => (n.type === 'entity' || n.type === 'aggregateentity') && n.data.name)
      .map((n) => n.data.name);

    // Collect all contract nodes (id + name + events) so aggregate entity nodes
    // can show a "Trigger Events" checklist without requiring per-event wiring.
    const _allContracts = nodes
      .filter((n) => n.type === 'contract' && n.data.name)
      .map((n) => ({ id: n.id, name: n.data.name, events: n.data.events ?? [] }));

    return nodes.map((n) => {
      const nIssues = issuesByNodeId.get(n.id) ?? [];
      const hasErr  = nIssues.some((i) => i.level === 'error');
      const hasWarn = nIssues.some((i) => i.level === 'warning');
      const cls = [
        n.className,
        hasErr  ? 'has-validation-error'   : '',
        hasWarn ? 'has-validation-warning' : '',
      ]
        .filter(Boolean)
        .join(' ');
      return {
        ...n,
        hidden: hiddenNodeIds.has(n.id),
        className: cls,
        data: { ...n.data, _issues: nIssues, _allEntityNames, _allContracts },
      };
    });
  }, [nodes, issuesByNodeId, hiddenNodeIds]);

  // Collapsed contract IDs — used to suppress their outgoing edges too
  const collapsedContractIds = useMemo(
    () => new Set(nodes.filter((n) => n.type === 'contract' && n.data?.collapsed).map((n) => n.id)),
    [nodes]
  );

  // Derived edges: highlight TYPE_MISMATCH edges red; hide edges leaving collapsed
  // contracts or connecting to hidden nodes.
  const displayEdges = useMemo(
    () =>
      edges.map((e) => {
        // Hide edge if its source is a collapsed contract or either endpoint is hidden
        if (collapsedContractIds.has(e.source) || hiddenNodeIds.has(e.source) || hiddenNodeIds.has(e.target)) {
          return { ...e, hidden: true };
        }
        const eIssues = issuesByEdgeId.get(e.id) ?? [];
        const hasErr  = eIssues.some((i) => i.level === 'error');
        const hasWarn = eIssues.some((i) => i.level === 'warning');
        if (!hasErr && !hasWarn) return { ...e, hidden: false };
        return {
          ...e,
          hidden: false,
          animated: hasErr,
          style: {
            stroke: hasErr ? '#ef4444' : '#f59e0b',
            strokeWidth: 2,
          },
        };
      }),
    [edges, issuesByEdgeId, collapsedContractIds, hiddenNodeIds]
  );

  // Scroll/focus canvas to a specific node
  const focusNode = useCallback(
    (nodeId) => {
      if (!reactFlowInstance) return;
      const node = nodes.find((n) => n.id === nodeId);
      if (node) {
        reactFlowInstance.setCenter(node.position.x + 100, node.position.y + 60, {
          zoom: 1.2,
          duration: 400,
        });
      }
    },
    [reactFlowInstance, nodes]
  );

  const handleIssueClick = useCallback(
    (issue) => {
      if (issue.node_id) focusNode(issue.node_id);
    },
    [focusNode]
  );

  // Named contract nodes — used by NetworksPanel to show per-contract tables
  const contractNames = nodes
    .filter((n) => n.type === 'contract' && n.data.name)
    .map((n) => n.data.name);

  // ── Save / Generate status label ─────────────────────────────────────────
  const saveLabel = saveStatus === 'saving' ? 'Saving…'
    : saveStatus === 'saved' ? '✓ Saved'
    : saveStatus === 'error' ? '✗ Error'
    : 'Save';

  const genLabel = genStatus === 'generating' ? 'Generating…'
    : genStatus?.files ? `✓ ${genStatus.files.length} files written`
    : genStatus?.error ? `✗ ${genStatus.error}`
    : 'Generate';

  return (
    <div style={{ width: '100vw', height: '100vh', background: 'var(--bg-canvas)' }}>
      <ReactFlow
        ref={reactFlowWrapper}
        nodes={displayNodes}
        edges={displayEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onInit={setReactFlowInstance}
        onDrop={onDrop}
        onDragOver={onDragOver}
        nodeTypes={NODE_TYPES}
        defaultEdgeOptions={DEFAULT_EDGE_OPTIONS}
        isValidConnection={isValidConnection}
        deleteKeyCode={['Delete', 'Backspace']}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
      >
        <Background color="#1e293b" gap={24} size={1} />
        <Controls style={{ background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }} />
        <MiniMap
          style={{ background: '#1e293b', border: '1px solid #334155' }}
          nodeColor="#334155"
          maskColor="rgba(15,23,42,0.7)"
        />

        {/* Left toolbar — node palette */}
        <Panel position="top-left">
          <Toolbar
            onAddContract={addContractNode}
            onAddEntity={addEntityNode}
            onAddAggregateEntity={addAggregateEntityNode}
            onAddMath={addMathNode}
            onAddTypeCast={addTypeCastNode}
            onAddStrConcat={addStrConcatNode}
            onAddConditional={addConditionalNode}
            onAddContractRead={addContractReadNode}
            onAutoLayout={applyLayout}
          />
        </Panel>

        {/* Center top — subgraph name + save/generate */}
        <Panel position="top-center">
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '4px 8px',
            background: 'rgba(15,23,42,0.88)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            backdropFilter: 'blur(8px)',
          }}>
            <button
              onClick={() => setLibraryOpen(true)}
              title="Open Canvas Library"
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '4px 10px',
                background: libraryOpen ? 'rgba(124,58,237,0.2)' : 'rgba(255,255,255,0.06)',
                border: `1px solid ${libraryOpen ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 5,
                color: libraryOpen ? 'var(--accent-light)' : 'var(--text-muted)',
                fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}
            >
              <FolderOpen size={11} />
              Library
            </button>
            <input
              value={subgraphName}
              onChange={(e) => setSubgraphName(e.target.value)}
              placeholder="subgraph-name"
              style={{
                background: 'rgba(0,0,0,0.3)',
                border: '1px solid var(--border)',
                borderRadius: 4,
                padding: '4px 10px',
                color: 'var(--text-primary)',
                fontSize: 13,
                fontWeight: 500,
                outline: 'none',
                width: 180,
              }}
            />
            <button
              onClick={saveConfig}
              disabled={saveStatus === 'saving'}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '4px 12px',
                background: saveStatus === 'saved' ? 'rgba(34,197,94,0.2)' : saveStatus === 'error' ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.06)',
                border: `1px solid ${saveStatus === 'saved' ? '#22c55e' : saveStatus === 'error' ? '#ef4444' : 'var(--border)'}`,
                borderRadius: 5,
                color: saveStatus === 'saved' ? '#22c55e' : saveStatus === 'error' ? '#ef4444' : 'var(--text-muted)',
                fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}
            >
              <Save size={11} />
              {saveLabel}
            </button>
            <button
              onClick={() => setSimulateOpen(true)}
              title="Preview subgraph structure"
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '4px 12px',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid var(--border)',
                borderRadius: 5,
                color: 'var(--text-muted)',
                fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}
            >
              <BookOpen size={11} />
              Simulate
            </button>
            <button
              onClick={() => { if (!hasErrors && genStatus !== 'generating') setGenModalOpen(true); }}
              disabled={hasErrors || genStatus === 'generating'}
              title={hasErrors ? 'Fix validation errors before generating' : 'Generate subgraph files'}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '4px 12px',
                background: genStatus?.files ? 'rgba(124,58,237,0.2)' : genStatus?.error ? 'rgba(239,68,68,0.2)' : hasErrors ? 'rgba(255,255,255,0.02)' : 'rgba(124,58,237,0.12)',
                border: `1px solid ${genStatus?.files ? 'var(--accent)' : genStatus?.error ? '#ef4444' : hasErrors ? '#334155' : 'var(--accent)'}`,
                borderRadius: 5,
                color: genStatus?.files ? 'var(--accent-light)' : genStatus?.error ? '#ef4444' : hasErrors ? '#475569' : 'var(--accent-light)',
                fontSize: 12, fontWeight: 600, cursor: hasErrors ? 'not-allowed' : 'pointer',
                opacity: hasErrors ? 0.5 : 1,
              }}
            >
              <Zap size={11} />
              {genLabel}
            </button>
          </div>
        </Panel>

        {/* Networks toggle + Help button */}
        <Panel position="top-right">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              onClick={() => setNetworksOpen((v) => !v)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                background: networksOpen ? 'rgba(124,58,237,0.25)' : 'rgba(15,23,42,0.88)',
                border: `1px solid ${networksOpen ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 6,
                color: networksOpen ? 'var(--accent-light)' : 'var(--text-primary)',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                backdropFilter: 'blur(8px)',
              }}
              title="Open Networks panel"
            >
              <Globe size={13} />
              Networks {networks.length > 0 ? `(${networks.length})` : ''}
            </button>
            <button
              onClick={() => setHelpOpen((v) => !v)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '6px 10px',
                background: helpOpen ? 'rgba(124,58,237,0.25)' : 'rgba(15,23,42,0.88)',
                border: `1px solid ${helpOpen ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 6,
                color: helpOpen ? 'var(--accent-light)' : 'var(--text-muted)',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
                backdropFilter: 'blur(8px)',
              }}
              title="Open help"
            >
              <HelpCircle size={13} />
              ?
            </button>
          </div>
        </Panel>
      </ReactFlow>

      {/* Help panel — right-side overlay */}
      <HelpPanel isOpen={helpOpen} onClose={() => setHelpOpen(false)} />

      {/* Simulate modal */}
      {simulateOpen && (
        <SimulatePanel
          onClose={() => setSimulateOpen(false)}
          nodes={nodes}
          edges={edges}
        />
      )}

      {/* Canvas Library modal */}
      <CanvasLibraryPanel
        isOpen={libraryOpen}
        onClose={() => setLibraryOpen(false)}
        onLoad={loadCanvasData}
        onNew={newCanvas}
        buildPayload={buildPayload}
        subgraphName={subgraphName}
      />

      {/* Networks sidebar — outside ReactFlow so it overlays correctly */}
      <NetworksPanel
        isOpen={networksOpen}
        onClose={() => setNetworksOpen(false)}
        networks={networks}
        onChange={setNetworks}
        contractNames={contractNames}
      />

      {/* Validation panel — bottom-left overlay */}
      <ValidationPanel
        issues={issues}
        hasErrors={hasErrors}
        isValidating={isValidating}
        onIssueClick={handleIssueClick}
      />

      {/* ── Generate modal — directory picker ─────────────────────────────── */}
      {genModalOpen && (
        <GenerateModal
          initialDir={genDir}
          onConfirm={(dir) => { setGenDir(dir); generateFiles(dir); }}
          onClose={() => setGenModalOpen(false)}
        />
      )}
    </div>
  );
}
