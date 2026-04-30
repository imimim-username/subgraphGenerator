/**
 * Tests for getKnownHandles.js
 *
 * Covers:
 *   - getKnownHandles()            — static handle sets per node type
 *   - getKnownHandlesWithContext() — contractread resolved from ABI
 *   - computeBrokenHandleIssues()  — broken-wire detection
 */

import { describe, it, expect } from 'vitest';
import {
  getKnownHandles,
  getKnownHandlesWithContext,
  computeBrokenHandleIssues,
} from './getKnownHandles.js';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function makeNode(type, data = {}, id = 'n1') {
  return { id, type, data };
}

function makeEdge(source, sourceHandle, target, targetHandle, id = 'e1') {
  return { id, source, sourceHandle, target, targetHandle };
}

// ─── getKnownHandles ──────────────────────────────────────────────────────────

describe('getKnownHandles — contract', () => {
  it('has no input handles', () => {
    const n = makeNode('contract', { events: [], readFunctions: [] });
    const { inputs } = getKnownHandles(n);
    expect(inputs.size).toBe(0);
  });

  it('always has implicit output handles', () => {
    const n = makeNode('contract', { events: [], readFunctions: [] });
    const { outputs } = getKnownHandles(n);
    expect(outputs.has('implicit-address')).toBe(true);
    expect(outputs.has('implicit-tx-hash')).toBe(true);
    expect(outputs.has('implicit-block-number')).toBe(true);
    expect(outputs.has('implicit-block-timestamp')).toBe(true);
    expect(outputs.has('implicit-instance-address')).toBe(true);
  });

  it('adds event trigger + per-param ports', () => {
    const n = makeNode('contract', {
      events: [
        { name: 'Deposit', params: [{ name: 'amount' }, { name: 'user' }] },
      ],
      readFunctions: [],
    });
    const { outputs } = getKnownHandles(n);
    expect(outputs.has('event-Deposit')).toBe(true);
    expect(outputs.has('event-Deposit-amount')).toBe(true);
    expect(outputs.has('event-Deposit-user')).toBe(true);
  });

  it('adds read-function ports', () => {
    const n = makeNode('contract', {
      events: [],
      readFunctions: [{ name: 'balanceOf' }, { name: 'totalSupply' }],
    });
    const { outputs } = getKnownHandles(n);
    expect(outputs.has('read-balanceOf')).toBe(true);
    expect(outputs.has('read-totalSupply')).toBe(true);
  });

  it('handles missing data gracefully', () => {
    const n = makeNode('contract');
    const { inputs, outputs } = getKnownHandles(n);
    expect(inputs.size).toBe(0);
    // 5 implicit ports only
    expect(outputs.size).toBe(5);
  });
});

describe('getKnownHandles — entity', () => {
  it('has no output handles', () => {
    const n = makeNode('entity', { fields: [{ name: 'id' }, { name: 'value' }] });
    const { outputs } = getKnownHandles(n);
    expect(outputs.size).toBe(0);
  });

  it('always includes evt and field-id input handles', () => {
    const n = makeNode('entity', { fields: [] });
    const { inputs } = getKnownHandles(n);
    expect(inputs.has('evt')).toBe(true);
    expect(inputs.has('field-id')).toBe(true);
  });

  it('adds field-{name} for each non-id field', () => {
    const n = makeNode('entity', {
      fields: [{ name: 'id' }, { name: 'amount' }, { name: 'owner' }],
    });
    const { inputs } = getKnownHandles(n);
    expect(inputs.has('field-amount')).toBe(true);
    expect(inputs.has('field-owner')).toBe(true);
    // id gets field-id, not field-id again from the loop
    expect(inputs.has('field-id')).toBe(true);
  });

  it('skips fields with no name', () => {
    const n = makeNode('entity', { fields: [{ name: '' }, { name: 'value' }] });
    const { inputs } = getKnownHandles(n);
    expect(inputs.has('field-')).toBe(false);
    expect(inputs.has('field-value')).toBe(true);
  });
});

describe('getKnownHandles — aggregateentity', () => {
  it('has field-id input and field-prev-id output for the id row', () => {
    const n = makeNode('aggregateentity', {
      fields: [{ name: 'id' }, { name: 'balance' }],
    });
    const { inputs, outputs } = getKnownHandles(n);
    expect(inputs.has('field-id')).toBe(true);
    expect(outputs.has('field-prev-id')).toBe(true);
  });

  it('adds field-in-{name} inputs and field-prev-{name} outputs for non-id fields', () => {
    const n = makeNode('aggregateentity', {
      fields: [{ name: 'id' }, { name: 'balance' }, { name: 'count' }],
    });
    const { inputs, outputs } = getKnownHandles(n);
    expect(inputs.has('field-in-balance')).toBe(true);
    expect(inputs.has('field-in-count')).toBe(true);
    expect(outputs.has('field-prev-balance')).toBe(true);
    expect(outputs.has('field-prev-count')).toBe(true);
  });

  it('does NOT add field-in-id (only field-id for the id row)', () => {
    const n = makeNode('aggregateentity', { fields: [{ name: 'id' }] });
    const { inputs } = getKnownHandles(n);
    expect(inputs.has('field-in-id')).toBe(false);
  });
});

describe('getKnownHandles — math / typecast / strconcat / conditional', () => {
  it('math: left+right in, result out', () => {
    const { inputs, outputs } = getKnownHandles(makeNode('math'));
    expect(inputs).toEqual(new Set(['left', 'right']));
    expect(outputs).toEqual(new Set(['result']));
  });

  it('typecast: value in, result out', () => {
    const { inputs, outputs } = getKnownHandles(makeNode('typecast'));
    expect(inputs).toEqual(new Set(['value']));
    expect(outputs).toEqual(new Set(['result']));
  });

  it('strconcat: left+right in, result out', () => {
    const { inputs, outputs } = getKnownHandles(makeNode('strconcat'));
    expect(inputs).toEqual(new Set(['left', 'right']));
    expect(outputs).toEqual(new Set(['result']));
  });

  it('conditional: condition+value in, value-out out', () => {
    const { inputs, outputs } = getKnownHandles(makeNode('conditional'));
    expect(inputs).toEqual(new Set(['condition', 'value']));
    expect(outputs).toEqual(new Set(['value-out']));
  });
});

describe('getKnownHandles — contractread (static)', () => {
  it('returns bind-address as input and null outputs (needs context)', () => {
    const { inputs, outputs } = getKnownHandles(makeNode('contractread'));
    expect(inputs.has('bind-address')).toBe(true);
    expect(outputs).toBeNull();
  });
});

describe('getKnownHandles — unknown type', () => {
  it('returns null for both inputs and outputs', () => {
    const { inputs, outputs } = getKnownHandles(makeNode('unknowntype'));
    expect(inputs).toBeNull();
    expect(outputs).toBeNull();
  });
});

// ─── getKnownHandlesWithContext ───────────────────────────────────────────────

describe('getKnownHandlesWithContext — contractread', () => {
  it('resolves in-/out- handles from the referenced contract node', () => {
    const contractNode = makeNode(
      'contract',
      {
        events: [],
        readFunctions: [
          {
            name: 'getBalance',
            inputs: [{ name: 'account' }],
            outputs: [{ name: 'balance' }],
          },
        ],
      },
      'contract-1',
    );

    const readNode = makeNode(
      'contractread',
      { contractNodeId: 'contract-1', fnIndex: 0 },
      'read-1',
    );

    const nodesById = new Map([
      ['contract-1', contractNode],
      ['read-1', readNode],
    ]);

    const { inputs, outputs } = getKnownHandlesWithContext(readNode, nodesById);
    expect(inputs.has('bind-address')).toBe(true);
    expect(inputs.has('in-account')).toBe(true);
    expect(outputs.has('out-balance')).toBe(true);
  });

  it('returns null outputs when contract node is not found', () => {
    const readNode = makeNode('contractread', { contractNodeId: 'missing' }, 'r1');
    const nodesById = new Map([['r1', readNode]]);
    const { outputs } = getKnownHandlesWithContext(readNode, nodesById);
    expect(outputs).toBeNull();
  });

  it('delegates to getKnownHandles for non-contractread nodes', () => {
    const n = makeNode('math');
    const { inputs, outputs } = getKnownHandlesWithContext(n, new Map());
    expect(inputs).toEqual(new Set(['left', 'right']));
    expect(outputs).toEqual(new Set(['result']));
  });
});

// ─── computeBrokenHandleIssues ───────────────────────────────────────────────

describe('computeBrokenHandleIssues', () => {
  it('returns no issues for a valid edge', () => {
    const src = makeNode('contract', { events: [{ name: 'Transfer', params: [] }], readFunctions: [] }, 'src');
    const tgt = makeNode('entity', { fields: [{ name: 'id' }, { name: 'amount' }] }, 'tgt');
    const edge = makeEdge('src', 'event-Transfer', 'tgt', 'field-amount');

    const issues = computeBrokenHandleIssues([src, tgt], [edge]);
    expect(issues).toHaveLength(0);
  });

  it('flags an edge with a bad sourceHandle', () => {
    const src = makeNode('contract', { events: [], readFunctions: [] }, 'src');
    const tgt = makeNode('entity', { fields: [{ name: 'id' }] }, 'tgt');
    const edge = makeEdge('src', 'event-Nonexistent', 'tgt', 'field-id');

    const issues = computeBrokenHandleIssues([src, tgt], [edge]);
    expect(issues).toHaveLength(1);
    expect(issues[0].code).toBe('BROKEN_HANDLE');
    expect(issues[0].level).toBe('warning');
    expect(issues[0].edge_id).toBe('e1');
    expect(issues[0].message).toMatch(/unknown port/i);
  });

  it('flags an edge with a bad targetHandle', () => {
    const src = makeNode('math', {}, 'src');
    const tgt = makeNode('entity', { fields: [{ name: 'id' }, { name: 'amount' }] }, 'tgt');
    const edge = makeEdge('src', 'result', 'tgt', 'field-nonexistent');

    const issues = computeBrokenHandleIssues([src, tgt], [edge]);
    expect(issues).toHaveLength(1);
    expect(issues[0].code).toBe('BROKEN_HANDLE');
    expect(issues[0].edge_id).toBe('e1');
  });

  it('only emits one issue per edge (source wins over target)', () => {
    const src = makeNode('math', {}, 'src');
    const tgt = makeNode('entity', { fields: [{ name: 'id' }] }, 'tgt');
    // Both handles are bad — should only get one issue
    const edge = makeEdge('src', 'bad-src', 'tgt', 'bad-tgt');

    const issues = computeBrokenHandleIssues([src, tgt], [edge]);
    expect(issues).toHaveLength(1);
  });

  it('skips edges to/from unknown node ids', () => {
    const n = makeNode('math', {}, 'n1');
    const edge = makeEdge('n1', 'result', 'missing', 'field-x');
    const issues = computeBrokenHandleIssues([n], [edge]);
    expect(issues).toHaveLength(0);
  });

  it('skips check when handles are null (unknown node type on either end)', () => {
    const src = makeNode('unknowntype', {}, 'src');
    const tgt = makeNode('entity', { fields: [{ name: 'id' }] }, 'tgt');
    const edge = makeEdge('src', 'anything', 'tgt', 'field-id');
    const issues = computeBrokenHandleIssues([src, tgt], [edge]);
    // src has null outputs — check is skipped
    expect(issues).toHaveLength(0);
  });

  it('handles multiple edges, flagging only the broken ones', () => {
    const src = makeNode('contract', {
      events: [{ name: 'Transfer', params: [{ name: 'value' }] }],
      readFunctions: [],
    }, 'src');
    const tgt = makeNode('entity', { fields: [{ name: 'id' }, { name: 'value' }] }, 'tgt');

    const goodEdge = makeEdge('src', 'event-Transfer-value', 'tgt', 'field-value', 'e-good');
    const badEdge  = makeEdge('src', 'event-OldEvent',      'tgt', 'field-value', 'e-bad');

    const issues = computeBrokenHandleIssues([src, tgt], [goodEdge, badEdge]);
    expect(issues).toHaveLength(1);
    expect(issues[0].edge_id).toBe('e-bad');
  });

  it('aggregateentity field-in-{name} and field-prev-{name} are valid handles', () => {
    const src = makeNode('aggregateentity', {
      fields: [{ name: 'id' }, { name: 'balance' }],
    }, 'agg');
    const tgt = makeNode('math', {}, 'math');

    // agg → math: field-prev-balance (output of agg) → left (input of math)
    const edge = makeEdge('agg', 'field-prev-balance', 'math', 'left');
    const issues = computeBrokenHandleIssues([src, tgt], [edge]);
    expect(issues).toHaveLength(0);
  });

  it('aggregateentity field-in-{name} is a valid target handle', () => {
    const src = makeNode('math', {}, 'math');
    const tgt = makeNode('aggregateentity', {
      fields: [{ name: 'id' }, { name: 'balance' }],
    }, 'agg');

    const edge = makeEdge('math', 'result', 'agg', 'field-in-balance');
    const issues = computeBrokenHandleIssues([src, tgt], [edge]);
    expect(issues).toHaveLength(0);
  });
});
