## Agent skills

### Issue tracker

Issues and specs live in GitHub Issues for `quanzhan-zzz/policy-rag-studio`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the seven default triage labels without overrides. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout with `GLOSSARY.md` and ADRs in `docs/adr/`. See `docs/agents/domain.md`.

### External peers

Use `auto` mode with Claude and Codex effort set to `high`. See `docs/agents/cross-model.json`.

## Testing

Environment verification and E2E acceptance must use the real PostgreSQL/Redis stack and the
configured real Embedding and LLM providers. Do not substitute a self-built mock server or
deterministic demo provider for acceptance evidence. Isolated unit tests may use test doubles for
internal control flow, but they never count as environment verification.

## Development planning

Read `docs/development-roadmap.md` before choosing or starting the next milestone.
It is the source of truth for milestone order, acceptance criteria, and current scope.

## Git commits

Use Chinese Conventional Commits: `<type>(<scope>): <中文摘要>`.
Keep one concern per commit, run the relevant checks first, and commit only runnable states.
See `docs/git-commit-convention.md` for allowed types, scopes, and examples.
