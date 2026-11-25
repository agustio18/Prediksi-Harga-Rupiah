
from datetime import timedelta

from sqlalchemy import text

from src.db import (
    get_engine,
    ambil_harian_tersimpan,
    cek_prediksi_ada,
    simpan_prediksi,
)

from src.ingestion import ke_mingguan
from src.siklus import perbarui_prediksi_lama
from src.model import ambil_model_aktif


def uji_pencocokan_aktual():
    engine = get_engine()
    prediksi_id = None

    try:
        print("=== UJI PENCOCOKAN HARGA AKTUAL ===")

        # Mengambil model aktif yang sebenarnya.
        model_info = ambil_model_aktif(engine)

        if model_info is None:
            raise RuntimeError(
                "Tidak ada model aktif untuk pengujian."
            )

        model_id = model_info["id"]

        # Mengambil data mingguan.
        harian = ambil_harian_tersimpan(engine)
        mingguan = ke_mingguan(harian)

        if mingguan.empty:
            raise ValueError("Data mingguan tidak tersedia.")

        baris_terakhir = mingguan.iloc[-1]

        tanggal_target = baris_terakhir["tanggal"].date()
        harga_aktual = float(baris_terakhir["close"])

        tanggal_acuan = tanggal_target - timedelta(days=7)

        # Memastikan prediksi sementara tidak bentrok.
        if cek_prediksi_ada(engine, tanggal_acuan, model_id):
            raise ValueError(
                "Tanggal acuan sudah memiliki prediksi "
                "untuk model aktif. Pengujian dibatalkan."
            )

        # Membuat prediksi sementara.
        harga_acuan = harga_aktual * 0.999
        harga_prediksi = harga_aktual * 1.001

        return_persen = (
            (harga_prediksi / harga_acuan) - 1
        ) * 100

        prediksi_id = simpan_prediksi(
            engine=engine,
            tanggal_acuan=tanggal_acuan,
            tanggal_target=tanggal_target,
            harga_acuan=harga_acuan,
            return_persen=return_persen,
            harga_prediksi=harga_prediksi,
            model_id=model_id,
        )

        if prediksi_id is None:
            raise RuntimeError(
                "Prediksi sementara gagal disimpan."
            )

        print("Prediksi sementara berhasil dibuat.")
        print("ID:", prediksi_id)
        print("Tanggal target:", tanggal_target)

        # Hanya memperbarui ID pengujian ini.
        jumlah = perbarui_prediksi_lama(
            engine,
            mingguan,
            prediksi_ids=[prediksi_id],
        )

        if jumlah != 1:
            raise AssertionError(
                "Prediksi sementara tidak berhasil diperbarui."
            )

        # Memeriksa hasil pembaruan.
        with engine.connect() as conn:
            hasil = conn.execute(
                text("""
                    SELECT
                        harga_aktual,
                        selisih,
                        galat_persen,
                        arah_benar
                    FROM prediksi
                    WHERE id = :id
                """),
                {"id": prediksi_id},
            ).mappings().first()

        if hasil is None:
            raise RuntimeError(
                "Hasil prediksi sementara tidak ditemukan."
            )

        print("\n=== HASIL PENGUJIAN ===")
        print("Harga aktual:", hasil["harga_aktual"])
        print("Selisih:", hasil["selisih"])
        print("Galat (%):", hasil["galat_persen"])
        print("Arah benar:", hasil["arah_benar"])

        assert hasil["harga_aktual"] is not None

        print("\nPENGUJIAN BERHASIL")

    finally:
        # Hanya menghapus prediksi sementara milik pengujian.
        if prediksi_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        DELETE FROM prediksi
                        WHERE id = :id
                    """),
                    {"id": prediksi_id},
                )

            print("\nPrediksi sementara sudah dihapus.")

        engine.dispose()


if __name__ == "__main__":
    uji_pencocokan_aktual()
