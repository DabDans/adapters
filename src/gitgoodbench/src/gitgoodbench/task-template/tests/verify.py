"""Grade without loading the actor's Git config or exposing the hidden bundle.

The harness must stop the actor and protect verifier assets and results. This
script is not an OS sandbox for a concurrently running or privileged actor.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
SAFE_PATH = "/usr/local/bin:/usr/bin:/bin"
GIT = shutil.which("git", path=SAFE_PATH)


class InvalidRepository(Exception):
    pass


def regular_file(path: Path) -> None:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise InvalidRepository("Repository metadata must be regular files.")


def read_metadata(root: Path, relative: str) -> str:
    parts = Path(relative).parts
    if (
        not parts
        or any(part in ("..", ".") for part in parts)
        or Path(relative).is_absolute()
    ):
        raise InvalidRepository("Invalid repository metadata path.")
    current = root
    for part in parts[:-1]:
        current /= part
        if not stat.S_ISDIR(current.lstat().st_mode):
            raise InvalidRepository("Linked repository metadata is unsupported.")
    path = root / relative
    regular_file(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise InvalidRepository("Repository metadata is too large.")
    return path.read_text(encoding="utf-8")


def read_head(git_dir: Path) -> str:
    head = read_metadata(git_dir, "HEAD").strip()
    if head.startswith("ref: "):
        ref = head[5:]
        if not ref.startswith("refs/heads/"):
            raise InvalidRepository("HEAD must name a local branch or commit.")
        try:
            head = read_metadata(git_dir, ref).strip()
        except FileNotFoundError:
            head = ""
            for line in read_metadata(git_dir, "packed-refs").splitlines():
                fields = line.split()
                if len(fields) == 2 and fields[1] == ref:
                    head = fields[0]
                    break
    if OID.fullmatch(head) is None:
        raise InvalidRepository("HEAD is not a valid commit reference.")
    return head


def copy_regular_tree(source: Path, destination: Path) -> None:
    # The actor must be stopped before this snapshot. Metadata symlinks and
    # special files are rejected; config/hooks/refs are not imported.
    if not stat.S_ISDIR(source.lstat().st_mode):
        raise InvalidRepository("Git objects must be a real directory.")
    destination.mkdir(exist_ok=True)
    for entry in source.iterdir():
        mode = entry.lstat().st_mode
        if stat.S_ISDIR(mode):
            copy_regular_tree(entry, destination / entry.name)
        elif stat.S_ISREG(mode):
            shutil.copyfile(entry, destination / entry.name)
        else:
            raise InvalidRepository("Linked or special Git objects are unsupported.")


class NeutralGit:
    def __init__(self, root: Path, head: str) -> None:
        self.root = root
        self.env = {
            "PATH": SAFE_PATH,
            "HOME": str(root),
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }
        root.mkdir()
        self.run(
            "init",
            "--bare",
            "--template=",
            f"--object-format={'sha256' if len(head) == 64 else 'sha1'}",
            str(root),
        )

    def run(self, *args: str, worktree: Path | None = None) -> bytes:
        command = [GIT, "--no-replace-objects", f"--git-dir={self.root}"]
        if worktree is not None:
            command += [f"--work-tree={worktree}"]
        command += [
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.commitGraph=false",
        ]
        result = subprocess.run(
            command + list(args),
            env=self.env,
            cwd=self.root.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        if result.returncode:
            # Do not disclose private object IDs or paths in the diagnostic.
            raise InvalidRepository(f"Git {args[0]} failed during verification.")
        return result.stdout


def evaluate(repo: Path, bundle: Path, workspace: Path) -> None:
    source = repo / ".git"
    if repo.is_symlink() or not stat.S_ISDIR(source.lstat().st_mode):
        raise InvalidRepository(
            "An ordinary repository with a .git directory is required."
        )
    head = read_head(source)
    for relative in ("objects/info/alternates", "objects/info/http-alternates"):
        if (source / relative).exists() or (source / relative).is_symlink():
            raise InvalidRepository("External object stores are unsupported.")
    actual = NeutralGit(workspace / "actual", head)
    copy_regular_tree(source / "objects", actual.root / "objects")
    regular_file(source / "index")
    shutil.copyfile(source / "index", actual.root / "index")
    for shared in source.glob("sharedindex.*"):
        regular_file(shared)
        shutil.copyfile(shared, actual.root / shared.name)
    # Preserve ordinary ignore rules (data only), not executable configuration.
    try:
        excludes = read_metadata(source, "info/exclude")
    except FileNotFoundError:
        excludes = ""
    (actual.root / "info").mkdir(exist_ok=True)
    (actual.root / "info/exclude").write_text(excludes, encoding="utf-8")
    (actual.root / "HEAD").write_text(head + "\n", encoding="ascii")
    actual.run("rev-parse", "--verify", "HEAD^{commit}")
    if actual.run("ls-files", "--unmerged", worktree=repo):
        raise InvalidRepository("Repository still has unresolved merge entries.")
    actual.run(
        "diff-index",
        "--cached",
        "--quiet",
        "--no-ext-diff",
        "--no-textconv",
        "HEAD",
        "--",
        worktree=repo,
    )
    # Generated tasks never initialize submodules. Do not recurse into an
    # actor-controlled nested Git configuration or follow a nested gitfile.
    for record in actual.run("ls-tree", "-rz", "HEAD").split(b"\0"):
        if record.startswith(b"160000 "):
            submodule = repo / os.fsdecode(record.split(b"\t", 1)[1])
            if submodule.is_symlink() or (
                submodule.exists()
                and (not submodule.is_dir() or any(submodule.iterdir()))
            ):
                raise InvalidRepository(
                    "Initialized submodules need a separate verifier; leave them uninitialized."
                )
    # Check the real index first, then rebuild its stat cache from HEAD. Actor
    # assume-unchanged/skip-worktree/fsmonitor flags cannot conceal dirty files.
    (actual.root / "index").unlink()
    actual.run("read-tree", "HEAD", worktree=repo)
    if actual.run("status", "--porcelain", "--ignore-submodules=all", worktree=repo):
        raise InvalidRepository("Repository has uncommitted changes.")
    actual_tree = actual.run("rev-parse", "HEAD^{tree}").strip()

    expected = NeutralGit(workspace / "expected", head)
    expected.run(
        "fetch", "--no-tags", str(bundle), "refs/harbor/target:refs/harbor/target"
    )
    expected_tree = expected.run("rev-parse", "refs/harbor/target^{tree}").strip()
    if actual_tree != expected_tree:
        raise InvalidRepository("HEAD tree does not match the expected merge tree.")
    # Do not trust just an object filename supplied by the actor. Compare the
    # complete tree listing against the independent store as well; the fresh
    # index/status check above verifies tracked working files against blob IDs.
    if actual.run("ls-tree", "-rtz", "HEAD") != expected.run(
        "ls-tree", "-rtz", "refs/harbor/target"
    ):
        raise InvalidRepository(
            "Committed tree contents do not match the expected tree."
        )


def write_result(logs: Path, reward: float, reason: str) -> None:
    logs.mkdir(parents=True, exist_ok=True)
    if logs.is_symlink():
        raise InvalidRepository("Verifier log directory cannot be a symlink.")
    for name, content in {
        "reward.txt": f"{reward}\n",
        "reward.json": json.dumps({"reward": reward}) + "\n",
        "reason.txt": reason + "\n",
    }.items():
        fd, temporary = tempfile.mkstemp(prefix=".result-", dir=logs)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(content)
            os.replace(temporary, logs / name)
        finally:
            Path(temporary).unlink(missing_ok=True)


def main() -> None:
    repo, bundle, logs = (Path(arg).absolute() for arg in sys.argv[1:])
    write_result(logs, 0.0, "Verification did not complete.")
    try:
        with tempfile.TemporaryDirectory(
            prefix="gitgood-verifier-", dir="/tmp"
        ) as root:
            evaluate(repo, bundle, Path(root))
    except (InvalidRepository, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        reason = (
            str(exc)
            if isinstance(exc, InvalidRepository)
            else "Invalid or unreadable repository metadata."
        )
        write_result(logs, 0.0, reason)
    else:
        write_result(logs, 1.0, "Resolved tree matches the expected merge tree.")


if __name__ == "__main__":
    main()
