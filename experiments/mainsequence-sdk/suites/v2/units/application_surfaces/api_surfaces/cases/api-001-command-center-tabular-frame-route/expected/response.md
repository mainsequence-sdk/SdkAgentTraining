The answer should design a FastAPI consumer surface, not a new producer.

Expected decisions:

- Use FastAPI in `apps/v1` with explicit routers and `response_model` declarations.
- Keep the normal browsing endpoint separate from the widget-facing frame endpoint.
- Use a paginated business response model for the normal list endpoint.
- Use the SDK canonical `TabularFrameResponse` contract for the endpoint that directly feeds the Command Center tabular workspace.
- Add stable `operation_id` values for both endpoints.
- Add rich FastAPI parameter metadata with `Query(...)`, bounds, and descriptions for filters, `limit`, and `offset`.
- Keep route handlers thin: validate inputs, call service helpers, return typed response models.
- Keep catalog read/composition logic in service helpers that consume existing governed data; do not duplicate producer logic in the route.
- Avoid adding request-user middleware unless a route actually reads request-local user context.
- If the endpoint is intended to be usable from Command Center now, state that the FastAPI project resource and a FastAPI `ResourceRelease` must exist and be verified.
- Validate OpenAPI output, including that the widget-facing route advertises the tabular contract and resolves to the expected response schema.

Important non-goals:

- Do not propose Flask, ad hoc scripts, or notebook endpoints.
- Do not return loose dictionaries for the widget-facing full-frame endpoint.
- Do not claim local route code is sufficient for platform usability before resource and release verification.
- Do not move producer-side DataNode or MetaTable design into the API route.
