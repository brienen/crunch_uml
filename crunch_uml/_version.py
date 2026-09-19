"""Single source of the crunch_uml version.

``setup.py`` reads ``__version__`` from this file, and the import-run marker and
the ``pack`` artifact report it. ``importlib.metadata`` is deliberately not used:
an editable install keeps reporting the version it was installed with.
"""

import os

__version__ = "0.7.0"


def producer_build(repo=None):
    """The git commit this code runs from, or ``'pypi'`` for an installed release.

    Read from the ``.git`` metadata next to the package (no subprocess), so a
    source checkout or an editable install reports the exact commit.
    """
    if repo is None:
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git = os.path.join(repo, ".git")
    try:
        if os.path.isfile(git):  # worktree or submodule: "gitdir: <path>"
            with open(git, encoding="utf-8") as f:
                content = f.read().strip()
            if not content.startswith("gitdir:"):
                return "pypi"
            git = os.path.normpath(os.path.join(repo, content.split(":", 1)[1].strip()))
        with open(os.path.join(git, "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
        if not head.startswith("ref:"):
            return head or "pypi"
        ref = head.split(":", 1)[1].strip()
        for base in (git, _common_dir(git)):
            ref_path = os.path.join(base, ref)
            if os.path.isfile(ref_path):
                with open(ref_path, encoding="utf-8") as f:
                    return f.read().strip()
            packed = os.path.join(base, "packed-refs")
            if os.path.isfile(packed):
                with open(packed, encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split(" ")
                        if len(parts) == 2 and parts[1] == ref:
                            return parts[0]
    except OSError:
        pass
    return "pypi"


def _common_dir(git):
    """The shared git directory of a worktree (its ``commondir`` file), else ``git`` itself."""
    commondir = os.path.join(git, "commondir")
    if os.path.isfile(commondir):
        with open(commondir, encoding="utf-8") as f:
            return os.path.normpath(os.path.join(git, f.read().strip()))
    return git
