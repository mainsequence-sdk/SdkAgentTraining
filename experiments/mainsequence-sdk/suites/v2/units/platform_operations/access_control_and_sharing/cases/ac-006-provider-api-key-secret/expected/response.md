The answer should treat the provider API key as a security boundary.

Expected decisions:

- Use a Main Sequence `Secret`, not a `Constant`, because the value is a credential.
- Treat the secret name as the unique configuration identity.
- Before creating it, check whether that name already exists.
- Use the current CLI workaround for lookup when relevant: name-filtered secret list.
- Create only missing secrets; do not blindly create duplicates.
- Read from Python with the SDK `Secret.get(name=...)`.
- Extract the value safely, including support for secret-value wrappers when applicable.
- Raise or return a clear configuration error when the secret is missing, has no value, or is blank.
- Do not hardcode the key in source files, examples, tests, environment defaults, prompts, logs, error bodies, cache keys, connection JSON, or API responses.
- If teams or jobs need to consume the secret, verify access to the actual `Secret` resource, not just project code access.
- Keep provider request construction separate from access policy; the access-control decision is about the secret resource.

Important non-goals:

- Do not store the API key in a `Constant`.
- Do not put the raw key in a Command Center connection public config field.
- Do not expose the value through a health route or settings route.
- Do not claim idempotency without first resolving by name.
