
from datetime import timedelta

import pandas as pd
from sqlalchemy import text

from src.db import get_engine, ambil_harian_tersimpan
from src.ingestion import ke_mingguan
from src.model import ambil_model_aktif
from src.siklus import buat_prediksi_baru


def main():
    engine = get_engine()
    prediksi_id = None

    try:
        print("=== PENGUJIAN IDEMPOTENSI PREDIKSI ===")

        # Mengambil model aktif.
        model_info = ambil_model_aktif(engine)

        if model_info is None:
            raise RuntimeError("Model aktif tidak ditemukan.")

        model_id = model_info["id"]

        # Mengambil seluruh data historis.
        harian = ambil_harian_tersimpan(engine)
        mingguan = ke_mingguan(harian)

        if mingguan.empty:
            raise ValueError("Data mingguan tidak tersedia.")

        # Membuat tanggal acuan sintetis untuk pengujian.
        tanggal_terakhir = pd.Timestamp(
            mingguan.iloc[-1]["tanggal"]
        )

        tanggal_uji = tanggal_terakhir + pd.Timedelta(days=7)

        # Pastikan belum ada prediksi sungguhan pada tanggal ini.
        with engine.connect() as conn:
            sudah_ada = conn.execute(
                text("""
                    SELECT id
                    FROM prediksi
                    WHERE tanggal_acuan = :tanggal
                      AND model_id = :model_id
                """),
                {
                    "tanggal": tanggal_uji.date(),
                    "model_id": model_id,
                }
            ).scalar_one_or_none()

        if sudah_ada is not None:
            raise RuntimeError(
                "Tanggal pengujian sudah memiliki prediksi. "
                "Pengujian dibatalkan agar data lama tidak terganggu."
            )

        # Menambahkan satu baris sintetis untuk pengujian.
        baris_uji = mingguan.iloc[-1].copy()

        baris_uji["tanggal"] = tanggal_uji
        baris_uji["tanggal_data_terakhir"] = tanggal_uji
        baris_uji["status"] = "VALID"
        baris_uji["jumlah_periksa"] = 0

        mingguan_uji = pd.concat(
            [
                mingguan,
                pd.DataFrame([baris_uji])
            ],
            ignore_index=True
        )

        print("Model aktif:", model_id)
        print("Tanggal acuan pengujian:", tanggal_uji.date())

        # PEMANGGILAN PERTAMA
        print("\n=== PEMANGGILAN PERTAMA ===")

        prediksi_id = buat_prediksi_baru(
            engine,
            mingguan_uji
        )

        if prediksi_id is None:
            raise AssertionError(
                "Prediksi pertama seharusnya berhasil dibuat."
            )

        print("Prediksi pertama berhasil disimpan.")

        # PEMANGGILAN KEDUA
        print("\n=== PEMANGGILAN KEDUA ===")

        hasil_kedua = buat_prediksi_baru(
            engine,
            mingguan_uji
        )

        if hasil_kedua is not None:
            raise AssertionError(
                "Pemanggilan kedua seharusnya tidak membuat prediksi baru."
            )

        print("Prediksi kedua berhasil dilewati.")

        # Memeriksa jumlah baris di database.
        with engine.connect() as conn:
            jumlah = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM prediksi
                    WHERE tanggal_acuan = :tanggal
                      AND model_id = :model_id
                """),
                {
                    "tanggal": tanggal_uji.date(),
                    "model_id": model_id,
                }
            ).scalar_one()

        print("\n=== HASIL PEMERIKSAAN ===")
        print("Jumlah prediksi pada tanggal tersebut:", jumlah)

        assert jumlah == 1, (
            "Ditemukan prediksi duplikat."
        )

        print("\nSEMUA PENGUJIAN IDEMPOTENSI BERHASIL.")

    finally:
        # Menghapus hanya prediksi sintetis yang dibuat pengujian.
        if prediksi_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM prediksi WHERE id = :id"),
                    {"id": prediksi_id},
                )

            print("\nPrediksi sementara sudah dibersihkan.")

        engine.dispose()


if __name__ == "__main__":
    main()
