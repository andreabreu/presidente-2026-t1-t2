from __future__ import annotations

from .build import build


def main() -> int:
    path = build()
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
