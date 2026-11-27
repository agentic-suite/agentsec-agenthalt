# Developing agenthalt

## Setup

```sh
make setup                 # .venv with the package (editable) + dev extras
make setup BOOTSTRAP=python3.12   # pick the interpreter used to create the venv
```

Python 3.10–3.13 are supported. The runtime is **stdlib-only** (plus `tomli` on 3.10); dev tools are `pytest`,
`pytest-cov`, `ruff` and `mypy`.

## The gate

| Target | What it runs |
|---|---|
| `make lint` | `ruff check` + `ruff format --check` — zero violations |
| `make typecheck` | `mypy --strict` over `src` and `tests` |
| `make test` | `pytest` |
| `make cov` | `pytest` with coverage; fails under 95% |
| `make gate` | all of the above — the standing milestone gate |

CI ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) runs the same gate on Python 3.10–3.13 × Linux
and macOS, plus a fresh `pip install .` smoke test. Every commit needs a DCO `Signed-off-by` (`git commit -s`).

## Working a ticket

The WBS ([index](../wbs/v0.1.0/wbs-v0.1.0-index.md)) fixes the order:

1. **Design first** — the milestone's `.D0` design doc ([design index](../design/README.md)) is reviewed
   before code.
2. **One ticket at a time, test first** — write the failing test (RED), implement (GREEN), move on. Run only that
   ticket's tests between tickets.
3. **Gate once at milestone end** — `make gate`, code review in
   [`codereview-log.md`](../wbs/v0.1.0/codereview-log.md), docs, commit, WBS checkpoint.

## Invariants every change keeps

- **Fail closed.** No error path silently continues; a broken config, store or chain stops, loudly, with a
  distinct reason.
- **Exit codes are Tier-0.** Usage errors exit 5, never argparse's 2. Precedence lives only in `exit_codes.py`.
- **No secrets anywhere.** Free text going to the journal or logs passes through `agenthalt.redact`.
- **Additive formats.** Journal fields and actions are only ever added.
- **Docs move with code.** A behaviour change updates its reference page and, if it touches a requirement,
  the PRD and WBS ([design index](../design/README.md) rules).

## Layout

```
src/agenthalt/   cli · config · exit_codes · ids · journal · redact · logs · doctor
tests/           one test module per ticket area (see PRD 12 for the map)
docs/            prd · adr · design · wbs · reference · guides
```
