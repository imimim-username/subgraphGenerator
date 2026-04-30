/**
 * useValidation — debounced validation hook for the Subgraph Wizard canvas.
 *
 * Two layers of validation:
 *   1. Client-side broken-handle check — runs synchronously on every change,
 *      highlights wires whose source/target handle doesn't exist on the node.
 *   2. Server-side semantic check — debounced 600ms, calls POST /api/validate.
 *
 * Both sets of issues are merged and returned together.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { computeBrokenHandleIssues } from '../utils/getKnownHandles';

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
  const [serverIssues, setServerIssues]     = useState([]);
  const [hasServerErrors, setHasServerErrors] = useState(false);
  const [isValidating, setIsValidating]     = useState(false);
  const timerRef  = useRef(null);
  const abortRef  = useRef(null);

  // ── 1. Client-side broken-handle check (synchronous, no debounce) ──────────
  const brokenHandleIssues = useMemo(
    () => computeBrokenHandleIssues(nodes, edges),
    // Recompute whenever node fields or edge handles change.
    // Use a stable key derived from the handles so useMemo memoises correctly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      // eslint-disable-next-line react-hooks/exhaustive-deps
      edges.map((e) => `${e.id}:${e.sourceHandle}:${e.targetHandle}`).join('|'),
      // eslint-disable-next-line react-hooks/exhaustive-deps
      nodes.map((n) => {
        const fields = n.data?.fields ?? [];
        return `${n.id}:${n.type}:${fields.map((f) => f.name).join(',')}`;
      }).join('|'),
    ]
  );

  // ── 2. Server-side semantic validation (debounced) ──────────────────────────
  const runValidation = useCallback(async (currentNodes, currentEdges) => {
    if (abortRef.current) abortRef.current.abort();
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
      setServerIssues(data.issues ?? []);
      setHasServerErrors(data.has_errors ?? false);
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
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [nodes, edges, runValidation]);

  // ── Merge both issue sets ───────────────────────────────────────────────────
  const issues = useMemo(
    () => [...serverIssues, ...brokenHandleIssues],
    [serverIssues, brokenHandleIssues]
  );

  const hasErrors = hasServerErrors; // broken handles are warnings, not errors

  const { issuesByNodeId, issuesByEdgeId } = useMemo(() => {
    const byNode = new Map();
    const byEdge = new Map();
    for (const issue of issues) {
      if (issue.node_id) {
        if (!byNode.has(issue.node_id)) byNode.set(issue.node_id, []);
        byNode.get(issue.node_id).push(issue);
      }
      if (issue.edge_id) {
        if (!byEdge.has(issue.edge_id)) byEdge.set(issue.edge_id, []);
        byEdge.get(issue.edge_id).push(issue);
      }
    }
    return { issuesByNodeId: byNode, issuesByEdgeId: byEdge };
  }, [issues]);

  return { issues, hasErrors, issuesByNodeId, issuesByEdgeId, isValidating };
}

// ── helpers ──────────────────────────────────────────────────────────────────

function _stripCallbacks(data) {
  if (!data || typeof data !== 'object') return data;
  const out = {};
  for (const [k, v] of Object.entries(data)) {
    if (typeof v !== 'function' && !k.startsWith('_')) out[k] = v;
  }
  return out;
}
