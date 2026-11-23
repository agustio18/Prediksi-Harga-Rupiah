from unittest.mock import patch

from src.db import (
    get_engine,
    ambil_harian_tersimpan,
)

from src.ingestion import ke_mingguan
from src.siklus import buat_prediksi_baru


def uji_model_tidak_aktif():
    engine = get_engine()

    try:
        print("=== UJI MODEL TIDAK AKTIF ===")

        harian = ambil_harian_tersimpan(engine)
        mingguan = ke_mingguan(harian)

        jumlah_awal = len(mingguan)

        # Simulasi tidak ada model aktif.
        with patch(
            "src.siklus.ambil_model_aktif",
            return_value=None
        ):
            try:
                buat_prediksi_baru(engine, mingguan)
                print("PENGUJIAN GAGAL")
                print("Sistem seharusnya menolak proses prediksi.")

            except Exception as error:
                print("Pesan kesalahan:", error)
                print("\nPENGUJIAN BERHASIL")
                print("Sistem menolak prediksi tanpa model aktif.")

        print("\nJumlah data mingguan:", jumlah_awal)

    finally:
        engine.dispose()


if __name__ == "__main__":
    uji_model_tidak_aktif()
