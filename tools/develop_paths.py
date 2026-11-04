"""Where the shot tools find local material: a footage index and a material folder.
No machine's folders are written in the code. Each value comes from an environment variable, else from
develop.local.json at the repo root (git-ignored, one per machine), else it is None and the tool says what to set.

develop.local.json:  {"material_root": "D:/Footage/Project", "catalog": "D:/Footage/index.csv",
                      "depth_pass_dir": "D:/Depth passes"}   (all optional)
Environment:         DEVELOP_CATALOG, DEVELOP_MATERIAL_ROOT,
                     DEVELOP_DEPTH_PASS_DIR, DEVELOP_LOCAL (another settings file in place of develop.local.json,
                     for tests)

A footage index is a CSV with idx and path columns: a tool given a clip number reads that clip's path from it.
Without its own "catalog", the index is <material_root>/catalog.csv.
"""
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _local():
    p = os.environ.get("DEVELOP_LOCAL") or os.path.join(REPO, "develop.local.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _env_root():
    return os.environ.get("DEVELOP_MATERIAL_ROOT") or None


def material_root():
    """The folder holding the local footage and sound material, or None."""
    return _env_root() or _local().get("material_root") or None


def broll_catalog():
    """The footage index CSV, or None."""
    if os.environ.get("DEVELOP_CATALOG"):
        return os.environ["DEVELOP_CATALOG"]
    loc = _local()
    root = _env_root() or (None if loc.get("catalog") else loc.get("material_root"))
    if root:
        return os.path.join(root, "catalog.csv")
    return loc.get("catalog") or None


def setting(key, env):
    """Any other local setting: the environment variable env, else develop.local.json's key, else None."""
    return os.environ.get(env) or _local().get(key) or None


def need(value, what):
    """value, or stop with what to set."""
    if not value:
        sys.exit(f"{what} is not set: put it in develop.local.json at the repo root, or set it in the environment "
                 f"(see tools/develop_paths.py), or pass a file path instead of a number")
    return value


def clip_from_index(idx):
    """The path of footage index row idx."""
    import csv
    cat = need(broll_catalog(), "the footage index (catalog)")
    try:
        with open(cat, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if int(r["idx"]) == int(idx):
                    return r["path"]
    except OSError as e:
        sys.exit(f"cannot read the footage index {cat}: {e}")
    except KeyError:
        sys.exit(f"the footage index {cat} needs idx and path columns")
    sys.exit(f"no row {idx} in {cat}")
