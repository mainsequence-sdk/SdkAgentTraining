You are working on a FastAPI API in a Main Sequence project.

The API already has several business endpoints: some are read-only queries, some mutate project records, and a few return full tabular payloads that should be consumed directly by generic Command Center table or chart widgets. Other endpoints return provider-native JSON that may be useful later but is not itself a widget-ready table.

The user asks:

"Make this API discoverable by Command Center through Adapter from API. I need the contract approach, the health check, how operations should be exposed, how query and mutation operations should be treated, and how to represent tabular versus provider-native responses without lying to the workspace."
