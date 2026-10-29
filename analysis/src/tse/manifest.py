from __future__ import annotations
import hashlib, json, platform, sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from .config import load_config

LIBS = ["duckdb", "polars", "pandas", "pyarrow", "numpy", "scipy", "statsmodels", "plotly"]


def sha256_of(path: Path, chunk_size: int = 1 << 24) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest() -> dict:
    config = load_config()
    zips = sorted(config["downloads_dir"].rglob("*.zip"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "seed": config["seed"],
        "libraries": {lib: version(lib) for lib in LIBS},
        "inputs": [
            {"path": str(z.relative_to(config["downloads_dir"].parent)), "bytes": z.stat().st_size, "sha256": sha256_of(z)}
            for z in zips
        ],
    }


def main() -> None:
    config = load_config()
    out = config["outputs_dir"] / "run_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_manifest(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
