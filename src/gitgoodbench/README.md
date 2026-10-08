# GitGoodBench → Harbor Adapter

## Overview

This adapter converts the 60 deterministic `merge` rows of
[`JetBrains/git_good_bench-lite`](https://huggingface.co/datasets/JetBrains/git_good_bench-lite)
into offline Harbor Git-resolution tasks. The other 60 `file_commit_chain` rows are
excluded because their history-quality judge cannot be replaced by exact tree comparison.
This is the reference-validation variant migrated from
[harbor#2292](https://github.com/harbor-framework/harbor/pull/2292).
Migration review: [adapters#20](https://github.com/harbor-framework/adapters/pull/20).

## What is GitGoodBench?

[GitGoodBench](https://github.com/JetBrains-Research/git-good-bench) evaluates agents on
real version-control workflows. The adapted merge split uses the maintainer's final
merge tree as a deterministic target. This package retains the existing strict verifier:
the repository must be committed, clean, free of unresolved index entries, and match that
target tree exactly. Upstream data and source retain their original license terms.

## Adapter Features

- Generates all 60 merge rows, with stable `jetbrains/gitgoodbench__<id>` task names.
- Reconstructs each merge from an agent-visible parent-only Git bundle.
- Keeps the target commit in hidden solution and verifier assets.
- Uses the existing `no-network` agent and verifier policies.
- Provides a local bare-repository cache and selected-task generation.
- Preserves historical oracle and model evidence without counting one execution twice.

## Generated Task Structure

```text
datasets/gitgoodbench/<task-directory>/
├── task.toml
├── instruction.md
├── environment/
│   ├── Dockerfile
│   └── parent.bundle
├── solution/
│   ├── solve.sh
│   └── target.bundle
└── tests/
    ├── test.sh
    ├── target.bundle
    └── metadata.json
```

The standalone package is under `src/gitgoodbench/`; its templates live in
`src/gitgoodbench/src/gitgoodbench/task-template/`.

## Run Evaluation / Harness

### Running with Datasets Registry

After maintainers publish the dataset from
[dataset discussion #66](https://huggingface.co/datasets/harborframework/harbor-datasets/discussions/66):

```bash
harbor run -d jetbrains/gitgoodbench -a oracle
```

Registry publication is separate from this code migration. Before publication, use local
generated tasks. Harbor is installed separately; this repository does not supply its CLI.

### Using Job Configurations

From the adapters repository root:

```bash
harbor run -c src/gitgoodbench/run_gitgoodbench.yaml
harbor run -p datasets/gitgoodbench -a oracle
```

The config defaults to Oracle. Use `-a <agent> -m <model>` for an authorized model run.
It is a development config, not a replay of the historical budget.

### Running Individual Trial

```bash
harbor trial start -p datasets/gitgoodbench/<task-directory> -a oracle
```

## Usage: Create Task Directories

From the adapters repository root:

```bash
uv run --project src/gitgoodbench gitgoodbench \
  --split merge --output-dir datasets/gitgoodbench
```

- `--output-dir`: defaults to `datasets/gitgoodbench` relative to the current directory,
  including when installed outside a source checkout.
- `--limit N`: generate at most N rows; omit to generate all 60.
- `--overwrite`: replace existing generated tasks.
- `--task-ids <id> ...`: select upstream IDs or generated directory names.
- `--split merge`: the only supported split.

## Comparison with Original Benchmark (Parity)

**Independent original-versus-Harbor parity is pending. No exception has been approved.**
These historical results were carried forward from the old PR, not rerun after migration.

| Agent | Model | Metric | Runs | Dataset Size | Original | Harbor |
| --- | --- | --- | --- | --- | --- | --- |
| Codex 0.144.1 | gpt-5.4, xhigh | exact-tree solve rate | 1 Harbor run | 60 | Not run | 22/60 = 0.3667; SEM undefined |

The pinned upstream
[README](https://github.com/JetBrains-Research/git-good-bench/blob/b11ae6cd92be2b8b96e237d379427e04ad59c455/README.md#L39-L42)
states that proprietary code was removed; the published entrypoint still relies on an
internal dataset location and leaves its client/runner incomplete. This explains the old
reference-validation approach but does not establish its acceptance. The
[migration review](https://github.com/harbor-framework/harbor/pull/2292#issuecomment-6004945859)
asks for team agreement on a matched harness or a policy exception before further runs.

`parity_experiment.json` is deliberately `[]`: no independent pair is available.
[`reference_validation.json`](reference_validation.json) records the single model run
once, alongside the oracle. The old comparison-shaped JSON is preserved in
[`historical_evidence/`](historical_evidence/README.md), outside parity aggregation.
The non-empty-parity validation requirement remains an explicit review blocker.

### Historical full oracle verification

On 2026-07-16, Harbor 0.18.0 with Oracle 1.0.0 completed all 60 tasks with one attempt per
task, concurrency 3, and the shipped no-network policies in the standard Docker environment.
Recorded platform: Docker Engine 29.5.2, Linux 6.8.0-117-generic, Colima 0.10.3.

| Tasks | Passed | Mean reward | Trial exceptions | Retries | Duration |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 60 | 60 | 1.0000 | 0 | 0 | 12m 6s |

Hub job:
[`86f53ee7-a969-4ad3-b933-69da7a915599`](https://hub.harborframework.com/jobs/86f53ee7-a969-4ad3-b933-69da7a915599)
(private, shared with the reviewer). An extra `git diff --check` style gate was removed
before this run: official target trees containing whitespace errors remain valid. The
existing regression fixture is retained.

A new Harbor-side oracle run can use the config above. Reproducing the historical run
also requires its recorded Harbor version and concurrency; it is not an independent
original-versus-Harbor model experiment.

```bash
harbor run -c src/gitgoodbench/run_gitgoodbench.yaml -a oracle --n-concurrent 3
```

### Historical full model reference run

The 2026-07-10 run used Codex 0.144.1, `gpt-5.4`, reasoning effort `xhigh`, one attempt per
task, and concurrency 4. It achieved 22/60 with zero trial errors or retries in 1h 39m,
at an estimated $42.69. Job ID: `65744320-2874-467f-84c3-dadf27fc6277` (private).
Reported tokens: 66,350,885 input, 59,247,872 cached input, 674,422 output.
These are historical measurements, not a claim about a newly installed harness version.

## Notes & Caveats

- Migration source: `harbor#2292` at `a007cb51577e62e9de7f8fe39947722b145b8492`.
  Task instructions, verifier, templates, and bundle construction are preserved. Changes
  concern package paths, local test discovery, and evidence classification.
- Generation needs host network access; generated tasks run offline. Target objects are
  excluded from parent bundles. Keep solution/verifier assets outside agent inputs.
- The additional clean, committed repository checks reject incomplete merges without
  imposing style rules beyond the target tree.
- Related proposals:
  [harbor#1519](https://github.com/harbor-framework/harbor/pull/1519) (merge subset with a
  ported reference runner) and
  [harbor#3327](https://github.com/harbor-framework/harbor/pull/3327) (reconstructed harness).
  Their results are not imported into this variant. Agree a shared reference harness with
  maintainers before new parity runs.
- Historical links:
  [old adapter PR](https://github.com/harbor-framework/harbor/pull/2292),
  [dataset #66](https://huggingface.co/datasets/harborframework/harbor-datasets/discussions/66),
  [evidence #264](https://huggingface.co/datasets/harborframework/parity-experiments/discussions/264).

## Installation / Prerequisites

Python 3.12+, uv, Git, and Docker are required. Install Harbor independently and record
its version for any new evaluation:

```bash
uv tool install harbor
uv sync --project src/gitgoodbench --locked
harbor --version
```

The adapter has its own project and lockfile. Existing local regression tests do not
require the upstream dataset:

```bash
uv run --project src/gitgoodbench pytest -q src/gitgoodbench/tests
```

## Troubleshooting

- If generation cannot fetch a repository, check host Git access. Docker builds use the
  generated bundles rather than fetching the task repository.
- Set `HARBOR_GITGOOD_CACHE` to relocate the local bare-repository cache.
- Use `--overwrite` after changing the adapter.
- Empty-parity validation remains expected until methodology is agreed. Do not duplicate
  the reference result across the comparison arrays to satisfy it.

## Citation

```bibtex
@inproceedings{lindenbauer2025gitgoodbench,
  title = {GitGoodBench: A Novel Benchmark For Evaluating Agentic Performance On Git},
  author = {Tobias Lindenbauer and Egor Bogomolov and Yaroslav Zharov},
  year = {2025},
  doi = {10.18653/v1/2025.realm-1.19}
}
```

## Authors & Contributions

Original benchmark: Tobias Lindenbauer, Egor Bogomolov, and Yaroslav Zharov.
Adapter builder: Lingbei Meng (`225085001@link.cuhk.edu.cn`).

## Acknowledgement

The upstream benchmark and published evaluator are credited above. No new API evaluation
was performed for this migration.
