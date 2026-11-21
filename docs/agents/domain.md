# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

This repo is **single-context**: one glossary at `GLOSSARY.md`, and ADRs in `docs/adr/` once the first one is written.

## Before exploring, read these

- **`GLOSSARY.md`** for domain vocabulary.
- **`docs/adr/`**, once it exists: read ADRs that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill creates them lazily when terms or decisions actually get resolved.

## File structure example

```text
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-hybrid-retrieval.md
│   └── 0002-postgres-pgvector.md
└── app/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in the glossary. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, note it for `/domain-modeling`.

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding it.
