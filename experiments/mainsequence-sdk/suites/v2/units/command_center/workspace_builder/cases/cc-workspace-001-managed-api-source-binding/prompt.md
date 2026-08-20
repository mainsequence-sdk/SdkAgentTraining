You are working in a Main Sequence project with a Command Center workspace.

The workspace design is already decided: one visible catalog-monitor widget should display rows returned by an Adapter from API connection operation. The operation id is `getCatalogFrame`. The connection instance uid is `connection-1`, and the connection type id is `command_center.adapter_from_api`.

The visible widget id is `catalog-monitor-widget`, and it expects a retained tabular dataset on its `seedData` input. The workspace should not expose the API source as a large visible panel, but the source must remain reviewable and recoverable in workspace JSON.

The user asks:

"Explain the workspace document structure you would create, how the source query is represented, how the binding works, and what you would verify before applying this to a real workspace."
