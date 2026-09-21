# Documentation standard

Repository standard for research documentation and evidence layout.

## Placement rules

- Put narrative findings, caveats, and conclusions in `docs/wiki/`.
- Keep raw evidence (logs, JSON outputs, command transcripts) in tool artifact paths
  such as `tools/sandbox/campaign_results/<timestamp>/`.
- Do not add unlinked narrative markdown under tool directories.

## Linking rules

- Any new research page must be linked from `docs/wiki/Home.md`.
- Pages with related content should add a `See also` link to the new page.
- Artifact directories referenced by wiki pages must use repository-relative paths.

## Content rules

- Use concise, factual language with explicit confidence labels:
  - **mock-confirmed**
  - **unverified-on-real**
  - **static-only**
- Keep hostnames/secrets redacted.
- Do not publish process/tool-provenance guidance or model-orchestration notes.

## Review checklist

Before merging docs updates:

1. No orphan narrative markdown outside `docs/wiki/`.
2. Artifact directories contain evidence files only.
3. New wiki pages are linked from `Home.md` and relevant `See also` sections.
