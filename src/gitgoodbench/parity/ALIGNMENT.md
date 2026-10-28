# Reference preparation and parity alignment

Status: source preparation only; **not approved for model execution**. Updated 2026-10-28.
No peer result is imported into this adapter's `parity_experiment.json`.

## Pinned sources

- Upstream: `JetBrains-Research/git-good-bench@b11ae6cd92be2b8b96e237d379427e04ad59c455`.
- Candidate reconstruction: [Yang Wenting's harbor#3327](https://github.com/harbor-framework/harbor/pull/3327),
  `YanggWendy/harbor@097e646d450c84868ee4345f2ee664561fc78e96`,
  `adapters/gitgoodbench/parity/reference-harness.patch`.
- Our migration: [adapters#20](https://github.com/harbor-framework/adapters/pull/20).

Prepare a fresh review checkout from the adapters repository root:

```bash
uv run --project src/gitgoodbench python src/gitgoodbench/parity/prepare_reference.py \
  --output-dir /tmp/gitgoodbench-reference-review
```

The command fetches pinned source, checks and applies the patch, and records provenance.
It refuses to overwrite an existing directory. It does not install reference dependencies,
build Docker, start an agent, or call a model. Read the patch before running its entrypoint.
The upstream benchmark and reconstruction retain their respective attribution/licenses.

## Decisions required before execution

| Dimension | Current difference or unresolved item | Required evidence |
| --- | --- | --- |
| Prompt | Our concise merge prompt differs from the reconstruction's original contextual prompt and conflict hunks. | Freeze the same expanded prompt and public context for both sides, or explicitly evaluate distinct adaptations. |
| Metric | Upstream merge evaluator compares trees; our existing profile also requires a clean, committed, conflict-free repository. Peer Harbor grading also checks parent ancestry. | Agree one scored contract. Do not silently add ancestry checks or relabel old scores. |
| Git safety | Our new verifier uses private Git metadata and a separate target store. It rejects linked metadata, alternates, worktree gitfiles and initialized submodules; agent filters/config are not used. | Review these offline-profile restrictions. Run current-version representative Linux runtime checks; the historical 60/60 oracle does not validate the new verifier. |
| Reference cleanup | The candidate reconstruction restores gold into the task repository before final leftover-process cleanup. | Stop all actor processes before exposing private assets; grade in protected context. |
| Reference artifacts | Artifact copy uses ordinary host file-copy operations; the CLI does not enforce separation between results and the shared work directory. | Reject links/special files and prove that gold/results cannot enter the actor bind mount. |
| Network | Reconstruction hides gold only with an opt-in flag and relies on a host-side agent to retain API access while task networking is disabled. | Freeze enforced actor isolation and authenticated model transport for the chosen agent on both sides; do not assume in-container Codex works under that policy. |
| Agent/budget | Peer measurements use mini-swe-agent; our archived run used Codex 0.144.1. | Agree agent/version, model, effort, prompt, step/time/token limits, retries and fresh-container policy. |
| Dataset | The public dataset name alone is not an immutable sample manifest. | Record the dataset revision and exact ordered 60 merge IDs on both sides. |
| Statistics | Current Harbor spec asks for sample SEM and overlapping run ranges; peer report uses standard deviation. | Use at least two independent runs per side, preferably three; report run counts, mean, sample SEM, ranges, exceptions, retries and cost. |

The reference's resume/error flags are not evidence of same-session continuation. Freeze
trial identity and retry handling before execution; service exceptions remain visible.
A maintainer's willingness to review reconstruction is not final methodology approval.

## Current local changes

The generator now stages output before replacement and restores the previous task on an
installation failure. Qualified Harbor IDs are accepted; unknown requested IDs fail before
generation. The verifier does not import gold into the actor repository, load actor Git
configuration/hooks/replace refs, or trust pre-existing rewards. It rebuilds index stat
information to expose dirty files hidden by index flags, and compares recursive tree
entries with the independent target store as well as tree IDs.

These checks assume a stopped actor and protected verifier executables, mounts and results.
They do not establish an OS isolation boundary against an actor still running as verifier
root. The committed/clean/exact-tree criterion is retained for the generated ordinary Git
repositories; nonstandard layouts need an explicitly reviewed extension. This is a security
revision of our offline adaptation, not a claim of strict upstream scoring equivalence.

Historical July oracle/model evidence remains unchanged and belongs to the old verifier.
Only a new matched experiment can populate formal parity; preparing this source cannot.
