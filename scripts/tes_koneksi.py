import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from src.db import get_engine, buat_tabel


def main():
    engine = get_engine()
    buat_tabel(engine)

    with engine.connect() as conn:
        jumlah = conn.execute(
            text("SELECT COUNT(*) FROM harga_harian")
        ).scalar()

    print(f"Koneksi PostgreSQL berhasil. Baris harga_harian: {jumlah}")


if __name__ == "__main__":
    main()