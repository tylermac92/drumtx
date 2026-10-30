# 0001 — Personal use only (resolves Q1)

- **Status:** Accepted, 2026-10-30
- **Task:** M0-2

## Decision

DrumTx is a personal tool for its author. There is no commercial intent, no other users, and no distribution: no PyPI package, no public release, no beta testers.

## Consequences

- Components under non-commercial licenses (for example madmom's model files) are allowed. Other terms still apply and are checked per item in M0-2: research-only clauses, registration, and no-redistribution clauses. Anything with unclear terms is excluded.
- Third-party datasets and model weights are never committed to the git repository. They are downloaded or kept locally.
- The project needs no LICENSE file while it stays personal.
- Work aimed at other people is dropped from the plan: PyPI publishing, the external beta, outside documentation review, and contributor docs. CI on Linux, macOS, and Windows stays.
- If the project is ever shared, this decision must be revisited and every non-commercial component replaced or re-checked.
