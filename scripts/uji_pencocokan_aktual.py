from datetime import timedelta

from sqlalchemy import text

from src.db import (
    get_engine,
    buat_tabel,
    ambil_harian_tersimpan,
    cek_prediksi_ada,
    simpan_prediksi,
)

from src.ingestion import ke_mingguan
from src.siklus import perbarui_prediksi_lama


def uji_pencocokan_aktual():
    engine = get_engine()
    prediksi_id = None

    try:
        print("=== UJI PENCOCOKAN HARGA AKTUAL ===")

        buat_tabel(engine)

        # Mengambil data mingguan dari database.
        harian = ambil_harian_tersimpan(engine)
        mingguan = ke_mingguan(harian)

        if mingguan.empty:
            raise ValueError("Data mingguan tidak tersedia.")

        # Menggunakan tanggal mingguan terakhir yang sudah tersedia.
        tanggal_target = mingguan.iloc[-1]["tanggal"].date()

        harga_aktual = float(
            mingguan.iloc[-1]["close"]
        )

        tanggal_acuan = tanggal_target - timedelta(days=7)

        # Memastikan prediksi sementara tidak bentrok.
        if cek_prediksi_ada(engine, tanggal_acuan, 1):
            raise ValueError(
                "Tanggal acuan sudah memiliki prediksi "
                "untuk model ID 1. Pengujian dibatalkan."
            )

        # Membuat data prediksi sementara.
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
            model_id=1,
        )

        if prediksi_id is None:
            raise RuntimeError(
                "Prediksi sementara gagal disimpan."
            )

        print("Prediksi sementara berhasil dibuat.")
        print("ID:", prediksi_id)
        print("Tanggal target:", tanggal_target)
        print("Harga aktual:", harga_aktual)

        # Menjalankan fungsi pencocokan yang sebenarnya.
        jumlah = perbarui_prediksi_lama(
            engine,
            mingguan
        )

        print("\nJumlah prediksi diperbarui:", jumlah)

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
                {"id": prediksi_id}
            ).mappings().first()

        print("\n=== HASIL PENGUJIAN ===")
        print("Harga aktual:", hasil["harga_aktual"])
        print("Selisih:", hasil["selisih"])
        print("Galat (%):", hasil["galat_persen"])
        print("Arah benar:", hasil["arah_benar"])

        if hasil["harga_aktual"] is not None:
            print("\nPENGUJIAN BERHASIL")
        else:
            print("\nPENGUJIAN GAGAL")

    finally:
        # Menghapus baris sementara agar database tetap bersih.
        if prediksi_id is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        DELETE FROM prediksi
                        WHERE id = :id
                    """),
                    {"id": prediksi_id}
                )

            print("\nData pengujian sementara sudah dihapus.")

        engine.dispose()


if __name__ == "__main__":
    uji_pencocokan_aktual()
