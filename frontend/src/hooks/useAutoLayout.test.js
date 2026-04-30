/**
 * Tests for computeLayout (pure function) from useAutoLayout.js
 *
 * We test the pure `computeLayout` function in isolation — no React, no DOM.
 * The React hook wrapper (`useAutoLayout`) is thin and covered by integration.
 */

import { describe, it, expect } from 'vitest';
import { computeLayout } from './useAutoLayout';

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeNode(id, type = 'entity', extra = {}) {
  return { id, type, position: { x: 0, y: 0 }, ...extra };
}

function makeEdge(source, target) {
  return { id: `${source}->${target}`, source, target };
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('computeLayout', () => {
  it('returns empty array for empty input', () => {
    expect(computeLayout([], [])).toEqual([]);
  });

  it('returns same reference array structure for null/undefined nodes', () => {
    expect(computeLayout(null, [])).toEqual([]);
    expect(computeLayout(undefined, [])).toEqual([]);
  });

  it('assigns positions to a single orphan node', () => {
    const nodes = [makeNode('n1', 'contract')];
    const result = computeLayout(nodes, []);
    expect(result).toHaveLength(1);
    expect(typeof result[0].position.x).toBe('number');
    expect(typeof result[0].position.y).toBe('number');
  });

  it('preserves all non-position node fields', () => {
    const nodes = [makeNode('n1', 'entity', { data: { name: 'Transfer', fields: [] } })];
    const result = computeLayout(nodes, []);
    expect(result[0].id).toBe('n1');
    expect(result[0].type).toBe('entity');
    expect(result[0].data).toEqual({ name: 'Transfer', fields: [] });
  });

  it('places source node to the left of target in LR layout', () => {
    const nodes = [makeNode('contract-1', 'contract'), makeNode('entity-1', 'entity')];
    const edges = [makeEdge('contract-1', 'entity-1')];
    const result = computeLayout(nodes, edges, { direction: 'LR' });

    const contractPos = result.find((n) => n.id === 'contract-1').position;
    const entityPos   = result.find((n) => n.id === 'entity-1').position;

    // In LR layout, source (contract) must be left of target (entity)
    expect(contractPos.x).toBeLessThan(entityPos.x);
  });

  it('places source node above target in TB layout', () => {
    const nodes = [makeNode('contract-1', 'contract'), makeNode('entity-1', 'entity')];
    const edges = [makeEdge('contract-1', 'entity-1')];
    const result = computeLayout(nodes, edges, { direction: 'TB' });

    const contractPos = result.find((n) => n.id === 'contract-1').position;
    const entityPos   = result.find((n) => n.id === 'entity-1').position;

    // In TB layout, source must be above target
    expect(contractPos.y).toBeLessThan(entityPos.y);
  });

  it('handles a 3-node chain: contract → math → entity', () => {
    const nodes = [
      makeNode('contract-1', 'contract'),
      makeNode('math-1',     'math'),
      makeNode('entity-1',   'entity'),
    ];
    const edges = [
      makeEdge('contract-1', 'math-1'),
      makeEdge('math-1',     'entity-1'),
    ];
    const result = computeLayout(nodes, edges, { direction: 'LR' });

    const cx = result.find((n) => n.id === 'contract-1').position.x;
    const mx = result.find((n) => n.id === 'math-1').position.x;
    const ex = result.find((n) => n.id === 'entity-1').position.x;

    expect(cx).toBeLessThan(mx);
    expect(mx).toBeLessThan(ex);
  });

  it('uses measured dimensions when provided', () => {
    // Two nodes connected; both measured. The layout should still run without error.
    const nodes = [
      makeNode('a', 'contract', { measured: { width: 300, height: 400 } }),
      makeNode('b', 'entity',   { measured: { width: 200, height: 150 } }),
    ];
    const edges = [makeEdge('a', 'b')];
    const result = computeLayout(nodes, edges);

    expect(result).toHaveLength(2);
    const ax = result.find((n) => n.id === 'a').position.x;
    const bx = result.find((n) => n.id === 'b').position.x;
    expect(ax).toBeLessThan(bx);
  });

  it('ignores edges referencing unknown nodes', () => {
    const nodes = [makeNode('n1', 'entity'), makeNode('n2', 'entity')];
    const edges = [
      makeEdge('n1',      'n2'),
      makeEdge('ghost-99', 'n1'),  // unknown source — should not throw
    ];
    expect(() => computeLayout(nodes, edges)).not.toThrow();
    const result = computeLayout(nodes, edges);
    expect(result).toHaveLength(2);
  });

  it('lays out multiple orphan nodes without overlap', () => {
    // 5 disconnected nodes should each get a distinct Y position
    const nodes = ['a', 'b', 'c', 'd', 'e'].map((id) => makeNode(id, 'entity'));
    const result = computeLayout(nodes, []);

    const ys = result.map((n) => n.position.y);
    const unique = new Set(ys.map((y) => Math.round(y)));
    // Each orphan lands in its own row
    expect(unique.size).toBe(5);
  });

  it('respects custom rankSep and nodeSep options', () => {
    const nodes = [makeNode('a', 'contract'), makeNode('b', 'entity')];
    const edges = [makeEdge('a', 'b')];

    const tight = computeLayout(nodes, edges, { direction: 'LR', rankSep: 10 });
    const wide  = computeLayout(nodes, edges, { direction: 'LR', rankSep: 500 });

    const tightGap = tight.find((n) => n.id === 'b').position.x - tight.find((n) => n.id === 'a').position.x;
    const wideGap  = wide.find((n)  => n.id === 'b').position.x - wide.find((n)  => n.id === 'a').position.x;

    expect(wideGap).toBeGreaterThan(tightGap);
  });

  it('returns positions as finite numbers (no NaN / Infinity)', () => {
    const nodes = [
      makeNode('c1', 'contract'),
      makeNode('m1', 'math'),
      makeNode('e1', 'entity'),
    ];
    const edges = [makeEdge('c1', 'm1'), makeEdge('m1', 'e1')];
    const result = computeLayout(nodes, edges);

    for (const n of result) {
      expect(Number.isFinite(n.position.x)).toBe(true);
      expect(Number.isFinite(n.position.y)).toBe(true);
    }
  });

  it('does not mutate the original node objects', () => {
    const nodes = [makeNode('n1', 'contract'), makeNode('n2', 'entity')];
    const edges = [makeEdge('n1', 'n2')];
    const origX = nodes[0].position.x;

    computeLayout(nodes, edges);

    expect(nodes[0].position.x).toBe(origX); // original unchanged
  });
});
