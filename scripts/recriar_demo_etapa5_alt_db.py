"""Recria .data/demo-etapa5-alt/newport_app.db a partir do original (VACUUM INTO + ANALYZE)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / ".data" / "newport_app.db"
DST_DIR = ROOT / ".data" / "demo-etapa5-alt"
DST = DST_DIR / "newport_app.db"


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"Origem inexistente: {SRC}")
    DST_DIR.mkdir(parents=True, exist_ok=True)
    for extra in (DST, DST.with_suffix(DST.suffix + "-wal"), DST.with_suffix(DST.suffix + "-shm")):
        if extra.is_file():
            extra.unlink()
    with sqlite3.connect(SRC) as conn:
        conn.execute("VACUUM INTO ?", (str(DST),))
    with sqlite3.connect(DST) as conn:
        conn.execute("ANALYZE")
        conn.commit()
        freelist = conn.execute("pragma freelist_count").fetchone()[0]
    print(f"OK: {DST} ({DST.stat().st_size} bytes, freelist={freelist})")


if __name__ == "__main__":
    main()
