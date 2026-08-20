The answer should describe the provider-side Adapter from API contract.

Expected decisions:

- Expose `GET /.well-known/command-center/connection-contract` as the adapter discovery source of truth.
- Keep `GET /openapi.json` available, but treat it as supporting API documentation, not the Command Center contract itself.
- Expose a dedicated zero-argument or trivial health operation such as `GET /health`.
- Reference the health route by stable `health.operationId` in the contract.
- Build `availableOperations` as an explicit allowlist of operations Command Center may call.
- Use stable `operationId` values and keep them consistent with the FastAPI routes.
- Classify read operations as `kind: query` with query capability.
- Classify mutating operations as `kind: mutation`, without query capability, and disable cache for mutations.
- Include parameter and request body metadata where relevant.
- Separate public `configVariables` from `secretVariables`.
- Keep secret values out of public config, query payloads, logs, cache keys, and returned connection JSON.
- For operations that directly return a full canonical tabular payload, declare `core.tabular_frame@v1` and use the SDK tabular frame response model at the API boundary.
- For provider-native JSON, optional `responseMappings` may document a future or editor-facing interpretation, but the answer must not claim that a mapping converts the runtime payload into `core.tabular_frame@v1`.

Important non-goals:

- Do not let Command Center call arbitrary OpenAPI routes.
- Do not use a parameterized data route as the health check.
- Do not treat provider-native JSON as directly usable by generic tabular consumers just because a mapping exists.
- Do not create workspace widgets until the API can be called through a valid Adapter from API connection.
