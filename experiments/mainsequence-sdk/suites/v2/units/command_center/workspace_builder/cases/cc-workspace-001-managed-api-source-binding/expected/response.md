The answer should describe a safe workspace JSON plan.

Expected decisions:

- Verify the registered widget types before authoring or applying the workspace.
- Use a `connection-query` source widget for the Adapter from API operation.
- Put the connection identity in `connectionRef` with the provided connection uid and type id.
- Use `queryModelId: api-operation`.
- Use a typed query payload whose `kind` is `api-operation` and whose `operationId` is `getCatalogFrame`.
- Keep the source widget hidden or sidebar-presented, but still present in durable workspace JSON.
- Mark the source widget with `managedBy.ownerInstanceId` pointing to the visible catalog-monitor widget and role `embedded-connection-source` if it is managed by the visible widget.
- Bind from the source widget output `dataset` to the visible widget input `seedData`.
- Store the binding on the visible target widget under `bindings`, not in the source widget and not inside `props`.
- Keep durable workspace fields such as metadata, grid, controls, widgets, props, layout, position, bindings, `managedBy`, and `presentation` in workspace JSON.
- Do not store credentials, raw provider URLs, native route fragments, or backend route fragments in widget props.
- Treat current-user runtime/view state separately from shared workspace JSON.
- For a real mutation, export the current workspace first, save versioned workspace/widget JSON under `workspaces/`, then apply through the CLI and re-read the workspace for verification.

Important non-goals:

- Do not mount the visible consumer as if it owns the API fetch directly unless its registry contract explicitly says so.
- Do not bind `dataset` to `liveUpdates`.
- Do not put bindings on the source widget.
- Do not claim the workspace is usable if the API resource, release, connection instance, or widget registry entries have not been verified.
