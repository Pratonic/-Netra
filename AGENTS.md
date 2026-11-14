# Repository instructions

## Explicit permission for remote changes

- Keep work local unless the user explicitly asks to push or publish that work.
- Never automatically push to GitHub or any other Git remote.
- Never run a Sites source synchronization helper that commits/pushes source, or publish/deploy a Site, without explicit user authorization for that operation.
- Authorization for one push or publication does not authorize future pushes or publications.
- An explicit user request to push authorizes only the requested destination and scope. Do not force-push or overwrite unrelated remote work without separate authorization.

## Credentials and generated files

- Never commit credentials, session tokens, runtime secrets, biometric enrollment data, or local databases.
- Keep dependency directories, local environment files and temporary build/runtime data out of commits according to `.gitignore`.
- Preserve the working AWS resource identifiers and storage keys when making visual branding changes; the product name is **त्रिNetra**.
