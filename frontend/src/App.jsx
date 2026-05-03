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
import UnsavedChangesDialog from './components/UnsavedChangesDialog';
import SaveAsDialog from './components/SaveAsDialog';
import { BookOpen, FilePlus, FolderOpen, Globe, HelpCircle, Save, SaveAll, Zap } from 'lucide-react';

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
  const [nodes, setNodes, _onNodesChange] = useNodesState([]);
  const [edges, setEdges, _onEdgesChange] = useEdgesState([]);
  const reactFlowWrapper = useRef(null);
  const [reactFlowInstance, setReactFlowInstance] = useState(null);
  const [networksOpen, setNetworksOpen] = useState(false);
  const [openDialogOpen, setOpenDialogOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [simulateOpen, setSimulateOpen] = useState(false);
  const [networks, setNetworks] = useState([]);
  const [subgraphName, setSubgraphName] = useState('');
  const [genStatus, setGenStatus] = useState(null);   // null | 'generating' | { files: [...] } | { error: string }
  const [genModalOpen, setGenModalOpen] = useState(false);
  const [genDir, setGenDir] = useState('');           // user-chosen output directory
  const [cleanupStatus, setCleanupStatus] = useState(null); // null | 'cleaning' | { removed, kept } | { error }
  const [outputMode, setOutputMode] = useState('graph'); // 'graph' | 'ponder'
  const [ponderSettings, setPonderSettings] = useState({ // persisted Ponder config
    database: 'pglite', dbUrl: '', ordering: 'multichain',
  });

  // ── File management state ─────────────────────────────────────────────────
  const [currentFile, setCurrentFile]       = useState(null);   // name of open canvas file (null = untitled)
  const [isDirty, setIsDirty]               = useState(false);  // unsaved changes?
  const [saveStatus, setSaveStatus]         = useState(null);   // null | 'saving' | 'saved' | 'error'
  const [saveAsOpen, setSaveAsOpen]         = useState(false);
  const [unsavedOpen, setUnsavedOpen]       = useState(false);
  // Callback to run after the unsaved-changes dialog is resolved (Save or Discard)
  const pendingActionRef = useRef(null);
  // When true, the next state-change event should NOT mark dirty (e.g. during load)
  const suppressDirtyRef = useRef(false);

  // ── Dirty-tracking helpers ────────────────────────────────────────────────
  const markDirty = useCallback(() => {
    if (!suppressDirtyRef.current) setIsDirty(true);
  }, []);

  // Wrap React Flow's change handlers to mark dirty on meaningful changes
  const onNodesChange = useCallback((changes) => {
    _onNodesChange(changes);
    // 'select' and 'dimensions' are internal bookkeeping — not user edits
    if (changes.some((c) => c.type !== 'select' && c.type !== 'dimensions')) {
      markDirty();
    }
  }, [_onNodesChange, markDirty]);

  const onEdgesChange = useCallback((changes) => {
    _onEdgesChange(changes);
    if (changes.some((c) => c.type !== 'select')) markDirty();
  }, [_onEdgesChange, markDirty]);

  // Stable ref so updateNodeData can read current nodes without being in deps
  const nodesRef = useRef(nodes);
  useEffect(() => { nodesRef.current = nodes; }, [nodes]);

  // ── Node data updater (passed into each node via data.onChange) ───────────
  const updateNodeData = useCallback((nodeId, patch) => {
    // When fields change, detect renames and update connected edge handles.
    // We read current node state from the stable ref (avoids adding `nodes` to deps).
    if (patch.fields) {
      const oldNode   = nodesRef.current.find((n) => n.id === nodeId);
      const oldFields = oldNode?.data?.fields ?? [];
      const newFields = patch.fields;
      const nodeType  = oldNode?.type;
      const renames   = []; // [{ old: handle, new: handle }]

      for (let i = 0; i < Math.min(oldFields.length, newFields.length); i++) {
        const oldF = oldFields[i];
        const newF = newFields[i];
        // Match by stable _id when both have one; otherwise by position
        const sameField = (oldF._id && newF._id) ? oldF._id === newF._id : true;
        if (!sameField) continue;
        const oldName = oldF.name;
        const newName = newF.name;
        if (!oldName || !newName || oldName === newName) continue;

        if (nodeType === 'entity') {
          renames.push({ old: `field-${oldName}`, new: `field-${newName}` });
        } else if (nodeType === 'aggregateentity') {
          // id field handle is always 'field-id' — doesn't change
          if (oldName !== 'id') {
            renames.push({ old: `field-in-${oldName}`,   new: `field-in-${newName}` });
            renames.push({ old: `field-prev-${oldName}`, new: `field-prev-${newName}` });
          }
        }
      }

      if (renames.length > 0) {
        const renameMap = Object.fromEntries(renames.map((r) => [r.old, r.new]));
        setEdges((eds) =>
          eds.map((e) => {
            const newSrc = e.source === nodeId ? (renameMap[e.sourceHandle] ?? e.sourceHandle) : e.sourceHandle;
            const newTgt = e.target === nodeId ? (renameMap[e.targetHandle] ?? e.targetHandle) : e.targetHandle;
            if (newSrc === e.sourceHandle && newTgt === e.targetHandle) return e;
            // Rebuild edge id to reflect new handles
            const newId = e.id
              .replace(e.sourceHandle, newSrc)
              .replace(e.targetHandle, newTgt);
            return { ...e, id: newId, sourceHandle: newSrc, targetHandle: newTgt };
          })
        );
      }
    }

    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, ...patch } } : n))
    );
    markDirty();
  }, [setNodes, setEdges, markDirty]);

  // ── Node deleter (removes node + all its edges) ──────────────────────────
  const deleteNode = useCallback((nodeId) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    markDirty();
  }, [setNodes, setEdges, markDirty]);

  // ── Load a full canvas from a data object ────────────────────────────────
  // `name` — the canvas filename (without .json); null for imports / untitled
  const loadCanvasData = useCallback((data, name = null) => {
    // Suppress dirty marking while we apply all the state updates
    suppressDirtyRef.current = true;

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
    setOutputMode(data.output_mode ?? 'graph');
    setPonderSettings({ database: 'pglite', dbUrl: '', ordering: 'multichain', ...(data.ponder_settings ?? {}) });
    setCurrentFile(name);

    // Allow React to flush all the state updates, then clear dirty flag
    setTimeout(() => {
      suppressDirtyRef.current = false;
      setIsDirty(false);
    }, 0);
  }, [updateNodeData, deleteNode, setNodes, setEdges, setSubgraphName, setNetworks, setOutputMode, setPonderSettings]);

  // ── Clear the canvas (new canvas) — assumes dirty check already done ─────
  const newCanvas = useCallback(() => {
    suppressDirtyRef.current = true;
    setNodes([]);
    setEdges([]);
    setSubgraphName('');
    setCurrentFile(null);
    setTimeout(() => {
      suppressDirtyRef.current = false;
      setIsDirty(false);
    }, 0);
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

  // ── Load visual-config.json on mount (session restore) ───────────────────
  useEffect(() => {
    fetch('/api/config')
      .then((r) => r.json())
      .then((config) => {
        if (config.nodes && config.nodes.length > 0) {
          // Suppress dirty marking during session restore
          suppressDirtyRef.current = true;

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
          setOutputMode(config.output_mode ?? 'graph');
          setPonderSettings({ database: 'pglite', dbUrl: '', ordering: 'multichain', ...(config.ponder_settings ?? {}) });
          // Restore which file was open in the last session
          if (config.current_file) setCurrentFile(config.current_file);

          setTimeout(() => {
            suppressDirtyRef.current = false;
            setIsDirty(false);
          }, 0);
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
          return { ...base, name: '', abi: null, events: [], readFunctions: [], collapsed: false, showEvents: true, showReads: true, expandedEvents: {} };
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
      markDirty();
    },
    [reactFlowInstance, setNodes, defaultData, markDirty]
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
          if (eventName === 'setup') {
            // setup is a virtual event with no params — just record it as the source
            updateNodeData(targetNode.id, { sourceEvent: 'setup' });
          } else {
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
      }
      setEdges((eds) => addEdge({ ...params, ...DEFAULT_EDGE_OPTIONS }, eds));
      markDirty();
    },
    [setEdges, nodes, updateNodeData, markDirty]
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
    current_file: currentFile,
    output_mode: outputMode,
    ponder_settings: ponderSettings,
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
  }), [subgraphName, currentFile, outputMode, ponderSettings, networks, nodes, edges]);

  // ── Session save (visual-config.json) — for restore on next startup ──────
  // Called automatically whenever an explicit Save or Save As completes.
  const saveSession = useCallback(async () => {
    try {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildPayload()),
      });
    } catch {
      // Session save failure is non-fatal — explicit file saves are separate
    }
  }, [buildPayload]);

  // ── File management ───────────────────────────────────────────────────────

  // If dirty, stash the action and show the unsaved-changes dialog.
  // Otherwise, run it immediately.
  const guardDirty = useCallback((action) => {
    if (isDirty) {
      pendingActionRef.current = action;
      setUnsavedOpen(true);
    } else {
      action();
    }
  }, [isDirty]);

  // Save to a specific named canvas file
  const saveToFile = useCallback(async (name) => {
    setSaveStatus('saving');
    try {
      const payload = buildPayload();
      const res = await fetch(`/api/canvases/${encodeURIComponent(name)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, current_file: name }),
      });
      if (res.ok) {
        setCurrentFile(name);
        setIsDirty(false);
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus(null), 2000);
        // Also update the session-restore file so the next startup knows which file was open
        setTimeout(() => saveSession(), 0);
        return true;
      } else {
        setSaveStatus('error');
        setTimeout(() => setSaveStatus(null), 3000);
        return false;
      }
    } catch {
      setSaveStatus('error');
      setTimeout(() => setSaveStatus(null), 3000);
      return false;
    }
  }, [buildPayload, saveSession]);

  // "Save" — save to current file or trigger Save As
  const handleSave = useCallback(async () => {
    if (currentFile) {
      await saveToFile(currentFile);
    } else {
      setSaveAsOpen(true);
    }
  }, [currentFile, saveToFile]);

  // "Save As" confirmed with a name
  const handleSaveAsConfirm = useCallback(async (name) => {
    setSaveAsOpen(false);
    const ok = await saveToFile(name);
    // If there was a pending action (e.g. user picked Save in the unsaved dialog),
    // execute it now that the save is complete.
    if (ok && pendingActionRef.current) {
      const action = pendingActionRef.current;
      pendingActionRef.current = null;
      setUnsavedOpen(false);
      action();
    }
  }, [saveToFile]);

  // "New" — guard dirty state first
  const handleNew = useCallback(() => {
    guardDirty(() => newCanvas());
  }, [guardDirty, newCanvas]);

  // "Open" — guard dirty state first, then show dialog
  const handleOpenDialog = useCallback(() => {
    guardDirty(() => setOpenDialogOpen(true));
  }, [guardDirty]);

  // Unsaved dialog: "Save" clicked
  const handleUnsavedSave = useCallback(() => {
    if (currentFile) {
      // Save directly, then run pending action when done
      saveToFile(currentFile).then((ok) => {
        if (ok) {
          const action = pendingActionRef.current;
          pendingActionRef.current = null;
          setUnsavedOpen(false);
          action?.();
        }
      });
    } else {
      // No current file — open Save As; handleSaveAsConfirm will run pending action
      setSaveAsOpen(true);
    }
  }, [currentFile, saveToFile]);

  // Unsaved dialog: "Don't Save" clicked
  const handleUnsavedDiscard = useCallback(() => {
    const action = pendingActionRef.current;
    pendingActionRef.current = null;
    setUnsavedOpen(false);
    setIsDirty(false);
    action?.();
  }, []);

  // Unsaved dialog: "Cancel" clicked
  const handleUnsavedCancel = useCallback(() => {
    pendingActionRef.current = null;
    setUnsavedOpen(false);
  }, []);

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

  // ── Clean up orphan canvas nodes ─────────────────────────────────────────
  // Removes any non-contract node (entity, aggregate, transform, contractread)
  // that has no connection — directly or indirectly — to any contract node.
  // Strategy: bidirectional BFS from every contract node across all edges,
  // then delete anything that was never reached.
  const cleanupCanvas = useCallback(() => {
    const contractIds = new Set(
      nodes.filter((n) => n.type === 'contract').map((n) => n.id)
    );

    if (contractIds.size === 0) {
      // No contracts on canvas — nothing meaningful to clean up.
      setCleanupStatus({ removed: 0 });
      setTimeout(() => setCleanupStatus(null), 4000);
      return;
    }

    // Build adjacency lists in both directions so we catch nodes that feed
    // data INTO a contract chain as well as nodes that receive data FROM it.
    const fwd = new Map(); // source → [target, ...]
    const bwd = new Map(); // target → [source, ...]
    for (const edge of edges) {
      if (!fwd.has(edge.source)) fwd.set(edge.source, []);
      fwd.get(edge.source).push(edge.target);
      if (!bwd.has(edge.target)) bwd.set(edge.target, []);
      bwd.get(edge.target).push(edge.source);
    }

    // BFS — visit neighbours in both directions from contract nodes.
    const visited = new Set(contractIds);
    const queue = [...contractIds];
    while (queue.length) {
      const curr = queue.shift();
      for (const nbr of [...(fwd.get(curr) ?? []), ...(bwd.get(curr) ?? [])]) {
        if (!visited.has(nbr)) {
          visited.add(nbr);
          queue.push(nbr);
        }
      }
    }

    // Non-contract nodes not reachable from/to any contract are orphans.
    const orphanIds = new Set(
      nodes
        .filter((n) => n.type !== 'contract' && !visited.has(n.id))
        .map((n) => n.id)
    );

    if (orphanIds.size === 0) {
      setCleanupStatus({ removed: 0 });
      setTimeout(() => setCleanupStatus(null), 4000);
      return;
    }

    setNodes((prev) => prev.filter((n) => !orphanIds.has(n.id)));
    setEdges((prev) =>
      prev.filter((e) => !orphanIds.has(e.source) && !orphanIds.has(e.target))
    );
    setCleanupStatus({ removed: orphanIds.size });
    setTimeout(() => setCleanupStatus(null), 5000);
  }, [nodes, edges, setNodes, setEdges]);

  // ── Validation ────────────────────────────────────────────────────────────
  const { issues, hasErrors, issuesByNodeId, issuesByEdgeId, isValidating } =
    useValidation(nodes, edges, networks);

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
        const hasErr         = eIssues.some((i) => i.level === 'error');
        const hasWarn        = eIssues.some((i) => i.level === 'warning');
        const hasBrokenHandle = eIssues.some((i) => i.code === 'BROKEN_HANDLE');
        if (!hasErr && !hasWarn) return { ...e, hidden: false };
        // Broken-handle wires: dashed orange — visually distinct from type-mismatch (solid amber)
        if (hasBrokenHandle && !hasErr) {
          return {
            ...e,
            hidden: false,
            animated: false,
            style: { stroke: '#f59e0b', strokeWidth: 2, strokeDasharray: '6 3' },
          };
        }
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
      if (!node) return;
      // Use measured dimensions when available (React Flow sets these after mount)
      const w = node.measured?.width  ?? node.width  ?? 200;
      const h = node.measured?.height ?? node.height ?? 120;
      reactFlowInstance.setCenter(
        node.position.x + w / 2,
        node.position.y + h / 2,
        { zoom: 1.2, duration: 400 },
      );
    },
    [reactFlowInstance, nodes]
  );

  const handleIssueClick = useCallback(
    (issue) => {
      if (issue.node_id) {
        focusNode(issue.node_id);
        return;
      }
      if (issue.edge_id && reactFlowInstance) {
        // Focus the midpoint between the edge's source and target nodes
        const edge = edges.find((e) => e.id === issue.edge_id);
        if (!edge) return;
        const srcNode = nodes.find((n) => n.id === edge.source);
        const tgtNode = nodes.find((n) => n.id === edge.target);
        if (!srcNode || !tgtNode) return;
        const srcW = srcNode.measured?.width  ?? srcNode.width  ?? 200;
        const srcH = srcNode.measured?.height ?? srcNode.height ?? 120;
        const tgtW = tgtNode.measured?.width  ?? tgtNode.width  ?? 200;
        const tgtH = tgtNode.measured?.height ?? tgtNode.height ?? 120;
        const cx = (srcNode.position.x + srcW / 2 + tgtNode.position.x + tgtW / 2) / 2;
        const cy = (srcNode.position.y + srcH / 2 + tgtNode.position.y + tgtH / 2) / 2;
        reactFlowInstance.setCenter(cx, cy, { zoom: 1.1, duration: 400 });
      }
    },
    [focusNode, reactFlowInstance, nodes, edges]
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
    : outputMode === 'ponder' ? 'Generate Ponder' : 'Generate Subgraph';

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
            onCleanup={cleanupCanvas}
            cleanupStatus={cleanupStatus}
            contractNodes={nodes.filter((n) => n.type === 'contract')}
            onFocusNode={focusNode}
          />
        </Panel>

        {/* Center top — file management + subgraph name + generate */}
        <Panel position="top-center">
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 8px',
            background: 'rgba(15,23,42,0.88)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            backdropFilter: 'blur(8px)',
          }}>

            {/* ── File: New / Open ── */}
            <button
              onClick={handleNew}
              title="New canvas"
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '4px 9px',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid var(--border)',
                borderRadius: 5,
                color: 'var(--text-muted)',
                fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}
            >
              <FilePlus size={11} />
              New
            </button>

            <button
              onClick={handleOpenDialog}
              title="Open a saved canvas"
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '4px 9px',
                background: openDialogOpen ? 'rgba(124,58,237,0.2)' : 'rgba(255,255,255,0.06)',
                border: `1px solid ${openDialogOpen ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 5,
                color: openDialogOpen ? 'var(--accent-light)' : 'var(--text-muted)',
                fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}
            >
              <FolderOpen size={11} />
              Open
            </button>

            {/* ── Divider ── */}
            <div style={{ width: 1, height: 18, background: 'var(--border)', margin: '0 2px' }} />

            {/* ── Subgraph name input ── */}
            <input
              value={subgraphName}
              onChange={(e) => { setSubgraphName(e.target.value); markDirty(); }}
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
                width: 160,
              }}
            />

            {/* ── Current file + dirty indicator ── */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 11, color: isDirty ? '#f59e0b' : '#475569',
              minWidth: 80, maxWidth: 130,
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              title: currentFile || 'Untitled',
            }}>
              {isDirty && <span style={{ color: '#f59e0b', fontSize: 14, lineHeight: 1 }}>●</span>}
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {currentFile || 'Untitled'}
              </span>
            </div>

            {/* ── Divider ── */}
            <div style={{ width: 1, height: 18, background: 'var(--border)', margin: '0 2px' }} />

            {/* ── Save / Save As ── */}
            <button
              onClick={handleSave}
              disabled={saveStatus === 'saving'}
              title={currentFile ? `Save to "${currentFile}"` : 'Save (will prompt for a name)'}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '4px 10px',
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
              onClick={() => setSaveAsOpen(true)}
              title="Save a copy with a new name"
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '4px 10px',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid var(--border)',
                borderRadius: 5,
                color: 'var(--text-muted)',
                fontSize: 12, fontWeight: 600, cursor: 'pointer',
              }}
            >
              <SaveAll size={11} />
              Save As
            </button>

            {/* ── Divider ── */}
            <div style={{ width: 1, height: 18, background: 'var(--border)', margin: '0 2px' }} />

            {/* ── Output mode toggle: Graph | Ponder ── */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 0,
              background: 'rgba(0,0,0,0.25)',
              border: '1px solid var(--border)',
              borderRadius: 5,
              overflow: 'hidden',
            }}>
              <button
                onClick={() => { setOutputMode('graph'); markDirty(); }}
                title="Generate a Graph Protocol subgraph"
                style={{
                  padding: '4px 9px',
                  background: outputMode === 'graph' ? 'rgba(124,58,237,0.28)' : 'transparent',
                  border: 'none',
                  borderRight: '1px solid var(--border)',
                  color: outputMode === 'graph' ? 'var(--accent-light)' : 'var(--text-muted)',
                  fontSize: 11, fontWeight: 700, cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
              >
                Graph
              </button>
              <button
                onClick={() => { setOutputMode('ponder'); markDirty(); }}
                title="Generate a Ponder TypeScript indexer"
                style={{
                  padding: '4px 9px',
                  background: outputMode === 'ponder' ? 'rgba(59,130,246,0.28)' : 'transparent',
                  border: 'none',
                  color: outputMode === 'ponder' ? '#93c5fd' : 'var(--text-muted)',
                  fontSize: 11, fontWeight: 700, cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
              >
                Ponder
              </button>
            </div>

            {/* ── Divider ── */}
            <div style={{ width: 1, height: 18, background: 'var(--border)', margin: '0 2px' }} />

            {/* ── Simulate / Generate ── */}
            <button
              onClick={() => setSimulateOpen(true)}
              title="Preview subgraph structure"
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '4px 10px',
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
              title={hasErrors ? 'Fix validation errors before generating' : outputMode === 'ponder' ? 'Generate Ponder TypeScript indexer' : 'Generate subgraph files'}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
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

      {/* Open dialog */}
      <CanvasLibraryPanel
        isOpen={openDialogOpen}
        onClose={() => setOpenDialogOpen(false)}
        onLoad={loadCanvasData}
        buildPayload={buildPayload}
        currentFile={currentFile}
        subgraphName={subgraphName}
      />

      {/* Save As dialog */}
      {saveAsOpen && (
        <SaveAsDialog
          initialName={currentFile || subgraphName || ''}
          onConfirm={handleSaveAsConfirm}
          onClose={() => setSaveAsOpen(false)}
        />
      )}

      {/* Unsaved changes dialog */}
      {unsavedOpen && (
        <UnsavedChangesDialog
          filename={currentFile}
          onSave={handleUnsavedSave}
          onDiscard={handleUnsavedDiscard}
          onCancel={handleUnsavedCancel}
        />
      )}

      {/* Networks sidebar — outside ReactFlow so it overlays correctly */}
      <NetworksPanel
        isOpen={networksOpen}
        onClose={() => setNetworksOpen(false)}
        networks={networks}
        onChange={(nets) => { setNetworks(nets); markDirty(); }}
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
          outputMode={outputMode}
          ponderSettings={ponderSettings}
          onPonderSettingsChange={setPonderSettings}
          onConfirm={(dir) => { setGenDir(dir); generateFiles(dir); }}
          onClose={() => setGenModalOpen(false)}
        />
      )}
    </div>
  );
}
