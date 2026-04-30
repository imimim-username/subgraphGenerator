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
| `src/nodes/ContractNode.jsx` | `contract` | ABI upload/fetch, event + read ports, multi-instance |
| `src/nodes/EntityNode.jsx` | `entity` | Field ports, ID strategy |
| `src/nodes/MathNode.jsx` | `math` | BigInt arithmetic |
| `src/nodes/TypeCastNode.jsx` | `typecast` | Type conversion |
| `src/nodes/StringConcatNode.jsx` | `strconcat` | String concatenation |
| `src/nodes/ConditionalNode.jsx` | `conditional` | Boolean guard / early return |
| `src/nodes/ContractReadNode.jsx` | `contractread` | On-chain view function call |

## Key hooks and components

| File | Purpose |
|---|---|
| `src/hooks/useValidation.js` | Debounced POST /api/validate; returns issue maps |
| `src/components/ValidationPanel.jsx` | Collapsible bottom-left issues panel |
| `src/components/NetworksPanel.jsx` | Right-side panel for chain addresses |
| `src/components/Toolbar.jsx` | Left-side node palette |
