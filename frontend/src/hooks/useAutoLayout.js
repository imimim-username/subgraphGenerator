/**
 * useAutoLayout — dagre-powered auto-layout for the React Flow canvas.
 *
 * Exports:
 *   computeLayout(nodes, edges, options?) → layoutedNodes
 *     Pure function — usable in tests without React.
 *
 *   useAutoLayout(nodes, edges, setNodes, reactFlowInstance) → applyLayout()
 *     React hook — returns a stable callback that layouts and fits the view.
 */

import dagre from 'dagre';
import { useCallback } from 'react';

// ── Fallback dimensions per node type ────────────────────────────────────────
// These are used when React Flow hasn't measured the node yet.
// Values are intentionally generous to avoid overlap on first layout.
const FALLBACK_DIMS = {
  contract:        { width: 270, height: 320 },
  entity:          { width: 230, height: 210 },
  aggregateentity: { width: 230, height: 210 },
  math:            { width: 170, height: 110 },
  typecast:        { width: 170, height:  90 },
  strconcat:       { width: 170, height:  90 },
  conditional:     { width: 170, height: 110 },
  contractread:    { width: 210, height: 130 },
  _default:        { width: 210, height: 150 },
};

/**
 * Compute dagre layout positions for a set of React Flow nodes + edges.
 *
 * @param {Array}  nodes     - React Flow node objects (may include `measured` field)
 * @param {Array}  edges     - React Flow edge objects
 * @param {Object} [options]
 * @param {string} [options.direction='LR']   - dagre rankdir ('LR' | 'TB')
 * @param {number} [options.rankSep=100]      - gap between ranks (columns in LR)
 * @param {number} [options.nodeSep=50]       - gap between nodes in the same rank
 * @returns {Array} New node array with updated `position` fields (all other fields unchanged)
 */
export function computeLayout(nodes, edges, options = {}) {
  if (!nodes || nodes.length === 0) return nodes ?? [];

  const { direction = 'LR', rankSep = 100, nodeSep = 50 } = options;

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, ranksep: rankSep, nodesep: nodeSep });

  // Register nodes with their actual or fallback dimensions
  for (const node of nodes) {
    const fallback = FALLBACK_DIMS[node.type] ?? FALLBACK_DIMS._default;
    const width  = node.measured?.width  ?? fallback.width;
    const height = node.measured?.height ?? fallback.height;
    g.setNode(node.id, { width, height });
  }

  // Register edges (skip if an endpoint isn't in the graph)
  const nodeIds = new Set(nodes.map((n) => n.id));
  for (const edge of edges) {
    if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
      g.setEdge(edge.source, edge.target);
    }
  }

  dagre.layout(g);

  // dagre returns centre coordinates; React Flow uses top-left
  return nodes.map((node) => {
    const pos = g.node(node.id);
    if (!pos) return node; // shouldn't happen, but guard anyway

    const fallback = FALLBACK_DIMS[node.type] ?? FALLBACK_DIMS._default;
    const width  = node.measured?.width  ?? fallback.width;
    const height = node.measured?.height ?? fallback.height;

    return {
      ...node,
      position: {
        x: pos.x - width  / 2,
        y: pos.y - height / 2,
      },
    };
  });
}

/**
 * React hook that returns a stable `applyLayout` callback.
 *
 * Calling `applyLayout()` re-positions all visible (non-hidden) nodes using
 * dagre LR layout, then calls `fitView` on the React Flow instance.
 *
 * @param {Array}    nodes              - current React Flow nodes
 * @param {Array}    edges              - current React Flow edges
 * @param {Function} setNodes           - React Flow setNodes
 * @param {Object}   reactFlowInstance  - from onInit / useReactFlow
 * @returns {Function} applyLayout()
 */
export function useAutoLayout(nodes, edges, setNodes, reactFlowInstance) {
  return useCallback(() => {
    // Only layout visible nodes (hidden nodes belong to collapsed contracts)
    const visibleNodes = nodes.filter((n) => !n.hidden);
    const visibleIds   = new Set(visibleNodes.map((n) => n.id));
    const visibleEdges = edges.filter(
      (e) => visibleIds.has(e.source) && visibleIds.has(e.target)
    );

    const layouted = computeLayout(visibleNodes, visibleEdges);

    // Merge layouted positions back (hidden nodes keep their old positions)
    const posMap = new Map(layouted.map((n) => [n.id, n.position]));
    setNodes((nds) =>
      nds.map((n) => {
        const newPos = posMap.get(n.id);
        return newPos ? { ...n, position: newPos } : n;
      })
    );

    // Fit the view after React has rendered the new positions
    setTimeout(() => reactFlowInstance?.fitView({ padding: 0.2, duration: 300 }), 50);
  }, [nodes, edges, setNodes, reactFlowInstance]);
}
