# Public local edition

- This directory is the public source-available local edition of ATTENTION.
- Keep all runtime data, credentials, personal documents, server deployment files and private repository history out of commits.
- Preserve the PolyForm Noncommercial license and NOTICE. Do not replace them with a permissive license.
- Test with temporary databases and mocked model responses. Never call paid APIs or modify a user's real data during tests.
- The application binds to loopback only. Do not expose it to the network or add cloud deployment details as a routine change.
- Document changes to local API behavior in docs/API.md. External Agent imports currently go to the archive, not directly into an edition.
