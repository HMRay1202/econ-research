# Documentation Index

Choose a document by the question it owns. Code is the implementation reference; historical
release records are not current operational status.

## Using the application

| Question | Main document |
| --- | --- |
| What is it, and how do I start? | [README](../README.md) |
| How do I configure GPU use, stop the server, inspect costs or troubleshoot? | [Runtime guide](runtime-guide.md) |
| Where is data, what needs backup, and which caches can be rebuilt? | [Data and backup](data-storage.md) |
| What is the project about without implementation detail? | [Project overview](../PROJECT_NARRATIVE.txt) |

## Developing and maintaining

| Responsibility | Main document |
| --- | --- |
| Scope and non-goals | [Project charter](../PROJECT_CHARTER.md) |
| Components and trust boundaries | [Architecture](../ARCHITECTURE.md) |
| Environment, checks and change discipline | [Development](../DEVELOPMENT.md) |
| Import, reparse, recovery and deletion behavior | [Workflows](workflows.md) |
| HTTP inputs, responses and errors | [API contracts](api-contracts.md) |
| Relations, lifecycle and persistence | [Data model](data-model.md) |
| Model output format and validation | [LLM output](llm-output-schema.md) |
| Browser interactions and safe rendering | [Frontend](frontend.md) |
| Instructions for coding agents | [AGENTS](../AGENTS.md) |

## Status and history

- [Current status](current-status.md): latest implementation baseline and verification boundaries.
- [Roadmap](../ROADMAP.md): remaining work, priorities and acceptance criteria, not implementation promises.
- [Change record](../CHANGELOG.md): delivered implementation changes.
- [Publication audit](release-readiness.md): historical evidence for one completed commit/push.

## Maintenance rules

All project documentation is maintained in English. Keep each detailed fact in its owning
document and link to it elsewhere. Check commands against launchers/CLI, contracts against routes
and Pydantic models, and state claims against the implementation.

Record dates and platforms for verification. Distinguish policy tests, local hardware smoke tests
and clean-install validation. After publication, record the commit and push result; do not leave a
pre-commit snapshot as the current status page.
