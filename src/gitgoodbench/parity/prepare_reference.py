"""Prepare pinned reference source for review; never build or run an agent."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

UPSTREAM = "https://github.com/JetBrains-Research/git-good-bench.git"
UPSTREAM_REVISION = "b11ae6cd92be2b8b96e237d379427e04ad59c455"
PATCH_REVISION = "097e646d450c84868ee4345f2ee664561fc78e96"
PATCH_URL = (
    f"https://raw.githubusercontent.com/YanggWendy/harbor/{PATCH_REVISION}/"
    "adapters/gitgoodbench/parity/reference-harness.patch"
)


def prepare(output: Path) -> None:
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(
            f"Output already exists; choose a new review directory: {output}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".gitgood-reference-", dir=output.parent
    ) as root:
        root = Path(root)
        checkout = root / "reference"
        checkout.mkdir()
        commands = [
            ["init", "--template="],
            ["remote", "add", "origin", UPSTREAM],
            ["fetch", "--depth=1", "origin", UPSTREAM_REVISION],
            ["checkout", "--detach", "FETCH_HEAD"],
        ]
        for command in commands:
            subprocess.run(
                ["git", "-C", str(checkout), *command], check=True, timeout=180
            )
        patch = root / "reference-harness.patch"
        with (
            urllib.request.urlopen(PATCH_URL, timeout=60) as response,
            patch.open("wb") as stream,
        ):
            shutil.copyfileobj(response, stream)
        for args in (["--check"], []):
            subprocess.run(
                ["git", "-C", str(checkout), "apply", *args, str(patch)],
                check=True,
                timeout=60,
            )
        shutil.copyfile(patch, checkout / "REVIEWED_REFERENCE.patch")
        (checkout / "PREPARATION.json").write_text(
            json.dumps(
                {
                    "upstream": UPSTREAM,
                    "upstream_revision": UPSTREAM_REVISION,
                    "patch_url": PATCH_URL,
                    "patch_revision": PATCH_REVISION,
                    "purpose": "source_review_only",
                    "model_execution_approved": False,
                    "docker_built": False,
                    "parity_results_imported": False,
                    "required_followup": "Resolve ALIGNMENT.md gates before any model execution.",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        checkout.rename(output)
    print(f"Prepared source only: {output}. No model or Docker execution.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    prepare(parser.parse_args().output_dir)
