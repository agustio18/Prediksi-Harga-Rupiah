import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import (
    get_engine,
    buat_tabel,
    ambil_harian_tersimpan,
    simpan_harian,
)
from src.ingestion import validasi


def main():
    engine = get_engine()
    buat_tabel(engine)

    harian = ambil_harian_tersimpan(engine)

    if harian.empty:
        print("Tabel harga_harian masih kosong.")
        return

    data, catatan = validasi(harian)

    jumlah = simpan_harian(data, engine)

    print(f"Baris divalidasi ulang: {jumlah}")
    print(f"Catatan PERIKSA: {len(catatan)}")

    for c in catatan:
        print(f"  - {c}")


if __name__ == "__main__":
    main()