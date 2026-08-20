You are working in a Main Sequence project with a FastAPI API under `apps/v1`.

The project already has reusable service helpers that can read a governed catalog of domain objects. A Command Center workspace now needs to load a filtered tabular view of those objects from the API. The team also wants the same API area to keep a normal paginated browsing endpoint for non-widget clients.

The data itself is already produced elsewhere. The API must not rebuild producer logic or write new producer tables.

The user asks:

"Plan the API surface for this. Explain the route and service split, the response contracts, the request validation metadata, and what you would verify before saying this is ready for Command Center."
