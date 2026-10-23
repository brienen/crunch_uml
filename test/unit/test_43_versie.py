"""Version metadata (0.7.0): one source, reported truthfully.

0.6.0 run markers said '0.4.11' - importlib.metadata of an editable install -
while setup.py said 0.6.0. A minimum-version gate on the marker was therefore
unreliable.
"""

import re
import sqlite3

import pytest

import crunch_uml
import crunch_uml.db as db
from crunch_uml import _version, cli


def _dispose_singleton():
    inst = db.Database._instance
    if inst is not None:
        try:
            inst.session.close()
        except Exception:  # noqa: S110 - best-effort teardown
            pass
        try:
            inst.engine.dispose()
        except Exception:  # noqa: S110 - best-effort teardown
            pass
        db.Database._instance = None


def test_versie_is_070_en_komt_uit_een_bron():
    assert crunch_uml.__version__ == "0.7.0"
    with open("setup.py", encoding="utf-8") as f:
        setup = f.read()
    assert "crunch_uml/_version.py" in setup
    assert not re.search(r"version=['\"]\d", setup), "setup.py must not hardcode the version"


def test_run_marker_meldt_de_pakketversie(tmp_path):
    path = tmp_path / "versie.db"
    _dispose_singleton()
    try:
        rc = cli.main(
            ["-db_url", f"sqlite:///{path}", "import", "-f", "./test/data/MiniM4.qea", "-t", "qea", "-db_create"]
        )
    finally:
        _dispose_singleton()
    assert rc == 0
    con = sqlite3.connect(path)
    try:
        assert con.execute("SELECT crunch_version FROM crunch_uml_runs").fetchone()[0] == crunch_uml.__version__
    finally:
        con.close()


@pytest.mark.parametrize("layout", ["loose-ref", "packed-ref", "detached", "worktree"])
def test_producer_build_leest_git_zonder_subprocess(tmp_path, layout):
    sha = "0123456789abcdef0123456789abcdef01234567"
    repo = tmp_path / "repo"
    git = repo / ".git"
    git.mkdir(parents=True)
    if layout == "loose-ref":
        (git / "HEAD").write_text("ref: refs/heads/main\n")
        (git / "refs" / "heads").mkdir(parents=True)
        (git / "refs" / "heads" / "main").write_text(sha + "\n")
    elif layout == "packed-ref":
        (git / "HEAD").write_text("ref: refs/heads/main\n")
        (git / "packed-refs").write_text(f"# pack-refs with: peeled\n{sha} refs/heads/main\n")
    elif layout == "detached":
        (git / "HEAD").write_text(sha + "\n")
    else:
        worktree_git = git / "worktrees" / "wt"
        worktree_git.mkdir(parents=True)
        (worktree_git / "HEAD").write_text("ref: refs/heads/feature\n")
        (worktree_git / "commondir").write_text("../..\n")
        (git / "packed-refs").write_text(f"{sha} refs/heads/feature\n")
        checkout = tmp_path / "checkout"
        checkout.mkdir()
        (checkout / ".git").write_text(f"gitdir: {worktree_git}\n")
        repo = checkout
    assert _version.producer_build(str(repo)) == sha


def test_producer_build_zonder_git_is_pypi(tmp_path):
    assert _version.producer_build(str(tmp_path)) == "pypi"
