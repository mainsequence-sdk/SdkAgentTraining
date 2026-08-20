You are working in a Main Sequence project that integrates with an external reference-data provider.

Several project surfaces need the provider API key: a service module, an API route, and a scheduled job. A teammate suggests storing the key as a plain runtime value because it is "just configuration."

The user asks:

"Design the safe configuration workflow for this provider key. Explain which platform object should hold it, how to avoid duplicate configuration names, how Python code should read it, how missing or empty values should fail, and what should never expose the secret."
