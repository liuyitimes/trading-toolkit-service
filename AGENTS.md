## Specification Workflow

The repository-level `openspec/` directory is the source of truth for current supported Service behavior. Before changing Service behavior, read the relevant baseline specification and follow `openspec/README.md`.

Service changes that also affect the Vue application SHALL have a same-named companion OpenSpec change in the independently versioned `trading-toolkit-web` repository. Keep HTTP contracts consistent, but record only Service implementation work here.
