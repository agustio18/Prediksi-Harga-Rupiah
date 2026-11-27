import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.db import get_engine, buat_tabel


def main():
    engine = get_engine()
    buat_tabel(engine)

    df = pd.read_sql_query(
        "SELECT tanggal, close, status "
        "FROM harga_harian ORDER BY tanggal ASC",
        engine,
    )

    if df.empty:
        print("Tabel harga_harian masih kosong.")
        return

    df["tanggal"] = pd.to_datetime(df["tanggal"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    total = len(df)
    tanggal_duplikat = int(df["tanggal"].duplicated().sum())
    close_kosong = int(df["close"].isna().sum())

    perubahan = df["close"].pct_change(fill_method=None) * 100
    perubahan_di_atas_3 = int((perubahan.abs() > 3).sum())

    jarak = df["tanggal"].diff().dt.days
    jeda_lebih_7 = int((jarak > 7).sum())

    status = df["status"].fillna("VALID").astype(str).str.upper()
    jumlah_valid = int((status == "VALID").sum())
    jumlah_periksa = int((status == "PERIKSA").sum())

    print("=== PEMERIKSAAN DATA HARIAN (FASE 1) ===")
    print(f"Jumlah data: {total}")
    print(f"Tanggal awal: {df['tanggal'].min().date()}")
    print(f"Tanggal akhir: {df['tanggal'].max().date()}")
    print(f"Status VALID: {jumlah_valid}")
    print(f"Status PERIKSA: {jumlah_periksa}")
    print(f"Nilai Close kosong: {close_kosong}")
    print(f"Tanggal duplikat: {tanggal_duplikat}")
    print(f"Perubahan harian di atas 3%: {perubahan_di_atas_3}")
    print(f"Jeda tanggal lebih dari 7 hari: {jeda_lebih_7}")


if __name__ == "__main__":
    main()