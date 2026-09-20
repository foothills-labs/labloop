# labloop: lab context

An experiment loop that retains changes only when a measured objective improves.

Lifecycle status and artifact locations are authoritative in [project.yaml](project.yaml). The [project README](../README.md) explains usage and the [agent instructions](../AGENTS.md) define scope and constraints. Start with `make setup` and `make check` at the repository root.

Code, protocols, measured evidence, and reproduction instructions stay in their existing project directories. Link to those files rather than copying their changing contents here.

Record significant decisions under `decisions/` using a dated file with context, decision, and consequences. Later decisions supersede earlier records. Exploratory notes may live under `notes/`, with dates and limitations; neither directory is required until it has content.

Metadata is descriptive, not a claim that experiments are complete or scientifically validated. Routine code changes require no central board update. Existing dated notes and historical decision logs remain evidence of what was believed at the time.
