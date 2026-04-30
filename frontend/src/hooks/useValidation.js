/**
 * useValidation — debounced validation hook for the Subgraph Wizard canvas.
 *
 * Calls POST /api/validate whenever nodes or edges change (debounced 600ms).
 * Returns enriched validation state consumed by ValidationPanel and App.jsx.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const DEBOUNCE_MS = 600;

/**
 * @param {Array} nodes  — React Flow nodes array
 * @param {Array} edges  — React Flow edges array
 * @returns {{
 *   issues: Array,
 *   hasErrors: boolean,
 *   issuesByNodeId: Map<string, Array>,
 *   issuesByEdgeId: Map<string, Array>,
 *   isValidating: boolean,
 * }}
 */
export function useValidation(nodes, edges) {
  const [issues, setIssues] = useState([]);
  const [hasErrors, setHasErrors] = useState(false);
  const [issuesByNodeId, setIssuesByNodeId] = useState(new Map());
  const [issuesByEdgeId, setIssuesByEdgeId] = useState(new Map());
  const [isValidating, setIsValidating] = useState(false);
  const timerRef = useRef(null);
  const abortRef = useRef(null);

  const runValidation = useCallback(async (currentNodes, currentEdges) => {
    // Cancel any in-flight request
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setIsValidating(true);
    try {
      const body = {
        schema_version: 1,
        subgraph_name: '',
        networks: [],
        nodes: currentNodes.map((n) => ({
          id: n.id,
          type: n.type,
          position: n.position,
          data: _stripCallbacks(n.data),
        })),
        edges: currentEdges.map((e) => ({
          id: e.id,
          source: e.source,
          sourceHandle: e.sourceHandle ?? '',
          target: e.target,
          targetHandle: e.targetHandle ?? '',
        })),
      };

      const res = await fetch('/api/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok) return;
      const data = await res.json();
      const newIssues = data.issues ?? [];

      const byNode = new Map();
      const byEdge = new Map();
      for (const issue of newIssues) {
        if (issue.node_id) {
          if (!byNode.has(issue.node_id)) byNode.set(issue.node_id, []);
          byNode.get(issue.node_id).push(issue);
        }
        if (issue.edge_id) {
          if (!byEdge.has(issue.edge_id)) byEdge.set(issue.edge_id, []);
          byEdge.get(issue.edge_id).push(issue);
        }
      }

      setIssues(newIssues);
      setHasErrors(data.has_errors ?? false);
      setIssuesByNodeId(byNode);
      setIssuesByEdgeId(byEdge);
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.warn('[useValidation] fetch error:', err);
      }
    } finally {
      setIsValidating(false);
    }
  }, []);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      runValidation(nodes, edges);
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [nodes, edges, runValidation]);

  return { issues, hasErrors, issuesByNodeId, issuesByEdgeId, isValidating };
}

// ── helpers ──────────────────────────────────────────────────────────────────

/**
 * Strip React callback functions and internal `_`-prefixed injected keys
 * (e.g. `_allContracts`, `_allEntityNames`) so JSON.stringify is clean.
 * Mirrors the stripping done in App.jsx before saving canvas state.
 */
function _stripCallbacks(data) {
  if (!data || typeof data !== 'object') return data;
  const out = {};
  for (const [k, v] of Object.entries(data)) {
    if (typeof v !== 'function' && !k.startsWith('_')) out[k] = v;
  }
  return out;
}
