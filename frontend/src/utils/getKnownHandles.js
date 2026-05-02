/**
 * getKnownHandles(node)
 *
 * Returns the set of valid React Flow handle IDs for a given node,
 * split into { inputs: Set<string>, outputs: Set<string> }.
 *
 * Used by:
 *   - useValidation  — to flag edges whose source/target handle doesn't exist
 *   - displayEdges   — (indirectly, via validation issues) to render broken
 *                      wires in a distinct visual style
 *
 * If a node type is unknown or its data is incomplete we return open sets
 * (null) so callers can skip the check gracefully.
 */

/**
 * @param {object} node  — React Flow node ({ id, type, data })
 * @returns {{ inputs: Set<string>|null, outputs: Set<string>|null }}
 */
export function getKnownHandles(node) {
  const { type, data = {} } = node;

  switch (type) {
    // ── Contract ──────────────────────────────────────────────────────────────
    case 'contract': {
      const outputs = new Set([
        'implicit-address',
        'implicit-instance-address',
        'implicit-tx-hash',
        'implicit-block-number',
        'implicit-block-timestamp',
      ]);
      for (const ev of data.events ?? []) {
        outputs.add(`event-${ev.name}`);
        for (const p of ev.params ?? []) {
          outputs.add(`event-${ev.name}-${p.name}`);
        }
      }
      // setup handler adds a virtual event-setup port
      if (data.hasSetupHandler) {
        outputs.add('event-setup');
      }
      for (const fn of data.readFunctions ?? []) {
        outputs.add(`read-${fn.name}`);
      }
      // Contracts have no input handles (nothing wires INTO them)
      return { inputs: new Set(), outputs };
    }

    // ── Entity ────────────────────────────────────────────────────────────────
    case 'entity': {
      const inputs = new Set(['evt', 'field-id']);
      for (const f of data.fields ?? []) {
        const name = f.name;
        if (name && name !== 'id') inputs.add(`field-${name}`);
      }
      // Entities are pure sinks — no output handles
      return { inputs, outputs: new Set() };
    }

    // ── Aggregate Entity ──────────────────────────────────────────────────────
    case 'aggregateentity': {
      const inputs  = new Set(['field-id']);
      const outputs = new Set();
      for (const f of data.fields ?? []) {
        const name = f.name;
        if (!name) continue;
        if (name === 'id') {
          // The id row's left port is field-id (already added); right is field-prev-id
          outputs.add('field-prev-id');
        } else {
          inputs.add(`field-in-${name}`);
          outputs.add(`field-prev-${name}`);
        }
      }
      return { inputs, outputs };
    }

    // ── ContractRead ──────────────────────────────────────────────────────────
    case 'contractread': {
      // We need the referenced contract node's readFunctions to know output handles.
      // Callers that have the full nodes map should use getKnownHandlesWithContext.
      // Here we return the static input and a null outputs set (unknown without ABI).
      const inputs = new Set(['bind-address']);
      // arg-N inputs for each input param — unknown without context
      const outputs = null; // caller must use context-aware variant
      return { inputs, outputs };
    }

    // ── Math ──────────────────────────────────────────────────────────────────
    case 'math':
      return {
        inputs:  new Set(['left', 'right']),
        outputs: new Set(['result']),
      };

    // ── TypeCast ──────────────────────────────────────────────────────────────
    case 'typecast':
      return {
        inputs:  new Set(['value']),
        outputs: new Set(['result']),
      };

    // ── StringConcat ──────────────────────────────────────────────────────────
    case 'strconcat':
      return {
        inputs:  new Set(['left', 'right']),
        outputs: new Set(['result']),
      };

    // ── Conditional ───────────────────────────────────────────────────────────
    case 'conditional':
      return {
        inputs:  new Set(['condition', 'value']),
        outputs: new Set(['value-out']),
      };

    default:
      return { inputs: null, outputs: null };
  }
}

/**
 * Context-aware variant: resolves contractread output handles using the full
 * nodes map (needed to look up the referenced contract's readFunctions).
 *
 * @param {object}              node      — the node to inspect
 * @param {Map<string,object>}  nodesById — all nodes keyed by id
 * @returns {{ inputs: Set<string>|null, outputs: Set<string>|null }}
 */
export function getKnownHandlesWithContext(node, nodesById) {
  if (node.type !== 'contractread') return getKnownHandles(node);

  const data = node.data ?? {};
  const inputs = new Set(['bind-address']);
  const outputs = new Set();

  const contractNode = nodesById.get(data.contractNodeId ?? '');
  if (contractNode) {
    const fns = contractNode.data?.readFunctions ?? [];
    const fn  = fns[data.fnIndex ?? 0];
    if (fn) {
      for (const inp of fn.inputs  ?? []) inputs.add(`in-${inp.name}`);
      for (const out of fn.outputs ?? []) outputs.add(`out-${out.name}`);
    }
  }

  return { inputs, outputs: outputs.size > 0 ? outputs : null };
}

/**
 * Compute broken-handle issues for a set of edges + nodes.
 * Returns an array of issue objects compatible with the server validation schema.
 *
 * @param {Array} nodes
 * @param {Array} edges
 * @returns {Array<{ level: string, message: string, edge_id: string }>}
 */
export function computeBrokenHandleIssues(nodes, edges) {
  const nodesById = new Map(nodes.map((n) => [n.id, n]));
  const issues = [];

  for (const edge of edges) {
    const srcNode = nodesById.get(edge.source);
    const tgtNode = nodesById.get(edge.target);

    // Skip edges to/from missing nodes (other validators handle those)
    if (!srcNode || !tgtNode) continue;

    // Check source handle
    const { outputs } = getKnownHandlesWithContext(srcNode, nodesById);
    if (outputs !== null && edge.sourceHandle && !outputs.has(edge.sourceHandle)) {
      issues.push({
        level:   'warning',
        code:    'BROKEN_HANDLE',
        message: `Wire from "${srcNode.data?.name || srcNode.type}" has unknown port "${edge.sourceHandle}" — this wire has no effect.`,
        edge_id: edge.id,
      });
      continue; // one issue per edge is enough
    }

    // Check target handle
    const { inputs } = getKnownHandlesWithContext(tgtNode, nodesById);
    if (inputs !== null && edge.targetHandle && !inputs.has(edge.targetHandle)) {
      issues.push({
        level:   'warning',
        code:    'BROKEN_HANDLE',
        message: `Wire into "${tgtNode.data?.name || tgtNode.type}" has unknown port "${edge.targetHandle}" — this wire has no effect.`,
        edge_id: edge.id,
      });
    }
  }

  return issues;
}
