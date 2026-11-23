from unittest.mock import patch

from sqlalchemy import text

from src.db import get_engine
from src.siklus import jalankan_siklus


def hitung_prediksi(engine):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT COUNT(*) FROM prediksi")
        ).scalar()


def uji_kegagalan_yahoo():
    engine = get_engine()

    try:
        print("=== UJI KEGAGALAN YAHOO FINANCE ===")

        jumlah_awal = hitung_prediksi(engine)

        # Simulasi Yahoo Finance tidak mengembalikan data.
        with patch(
            "src.siklus.ambil_data_harian",
            return_value=None
        ):
            try:
                jalankan_siklus()
            except RuntimeError as error:
                print("\nPesan kegagalan:", error)

        jumlah_akhir = hitung_prediksi(engine)

        # Memeriksa catatan log terbaru.
        with engine.connect() as conn:
            log = conn.execute(
                text("""
                    SELECT status, pesan
                    FROM log_update
                    ORDER BY waktu DESC
                    LIMIT 1
                """)
            ).mappings().first()

        print("\n=== HASIL PENGUJIAN ===")
        print("Jumlah prediksi sebelum:", jumlah_awal)
        print("Jumlah prediksi sesudah:", jumlah_akhir)
        print("Status log:", log["status"])
        print("Pesan log:", log["pesan"])

        if (
            jumlah_awal == jumlah_akhir
            and log["status"] == "GAGAL"
        ):
            print("\nPENGUJIAN BERHASIL")
        else:
            print("\nPENGUJIAN GAGAL")

    finally:
        engine.dispose()


if __name__ == "__main__":
    uji_kegagalan_yahoo()
