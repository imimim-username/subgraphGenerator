# Subgraph Wizard — Frontend

React + Vite visual node editor for the Subgraph Wizard.

## Development

```bash
cd frontend
npm install
npm run dev        # starts Vite dev server on :5173 (proxies /api/* → FastAPI)
```

In a separate terminal run the FastAPI backend:

```bash
cd ..
pip install -e .
uvicorn subgraph_wizard.server:app --port 5174 --reload
```

Update `vite.config.js` to proxy `/api` to `:5174` if you use a different port.

## Building for distribution

The pre-built bundle is committed to `../src/subgraph_wizard/static/` so that
end users don't need Node.js at runtime. Rebuild it whenever you change the
frontend source:

```bash
npm run build
# outputs to ../src/subgraph_wizard/static/
```

Commit the updated `static/` directory alongside your source changes.

## Node types

| File | Node type | Description |
|---|---|---|
| `src/nodes/ContractNode.jsx` | `contract` | ABI upload/fetch, event + read ports, multi-instance, Ponder options |
| `src/nodes/EntityNode.jsx` | `entity` | Field ports, ID strategy, `@derivedFrom` support |
| `src/nodes/AggregateEntityNode.jsx` | `aggregateEntity` | Singleton record updated in-place; trigger checklist |
| `src/nodes/MathNode.jsx` | `math` | BigInt / BigDecimal arithmetic |
| `src/nodes/TypeCastNode.jsx` | `typecast` | Type conversion (7 cast modes) |
| `src/nodes/StringConcatNode.jsx` | `strconcat` | String / Bytes concatenation with optional separator |
| `src/nodes/ConditionalNode.jsx` | `conditional` | Boolean guard / early return |
| `src/nodes/ContractReadNode.jsx` | `contractread` | On-chain view function call with auto address binding |

## Key hooks and components

| File | Purpose |
|---|---|
| `src/hooks/useValidation.js` | Debounced POST /api/validate; returns issue maps |
| `src/components/HelpPanel.jsx` | Slide-in help reference covering both Graph and Ponder modes |
| `src/components/GenerateModal.jsx` | Directory picker + Ponder Settings (database, ordering) |
| `src/components/ValidationPanel.jsx` | Collapsible bottom-left issues panel (offset right to clear React Flow Controls) |
| `src/components/NetworksPanel.jsx` | Right-side panel for chain addresses, start/end blocks, advanced options |
| `src/components/Toolbar.jsx` | Left-side node palette + output mode toggle + contract navigator |
