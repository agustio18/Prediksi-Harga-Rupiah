
from sqlalchemy import text

from src.db import get_engine
from src.siklus import jalankan_siklus


def hitung_prediksi():
    """Menghitung jumlah seluruh prediksi di PostgreSQL."""

    engine = get_engine()

    try:
        with engine.connect() as conn:
            jumlah = conn.execute(
                text("SELECT COUNT(*) FROM prediksi")
            ).scalar_one()

        return jumlah

    finally:
        engine.dispose()


def main():
    print("=== PENGUJIAN INTEGRASI SELURUH SIKLUS ===")

    jumlah_awal = hitung_prediksi()

    print("\nJumlah prediksi sebelum pengujian:", jumlah_awal)

    # Menjalankan siklus pertama.
    print("\n=== SIKLUS PERTAMA ===")

    hasil_pertama = jalankan_siklus()

    if hasil_pertama["status"] != "SUKSES":
        raise AssertionError("Siklus pertama gagal.")

    jumlah_setelah_pertama = hitung_prediksi()

    print(
        "\nJumlah prediksi setelah siklus pertama:",
        jumlah_setelah_pertama
    )

    # Menjalankan siklus kedua pada hari yang sama.
    print("\n=== SIKLUS KEDUA ===")

    hasil_kedua = jalankan_siklus()

    if hasil_kedua["status"] != "SUKSES":
        raise AssertionError("Siklus kedua gagal.")

    jumlah_setelah_kedua = hitung_prediksi()

    print(
        "\nJumlah prediksi setelah siklus kedua:",
        jumlah_setelah_kedua
    )

    # Memastikan pemanggilan kedua tidak membuat prediksi baru.
    assert hasil_kedua["prediksi_baru"] is None, (
        "Siklus kedua seharusnya melewati prediksi yang sudah ada."
    )

    assert jumlah_setelah_kedua == jumlah_setelah_pertama, (
        "Jumlah prediksi bertambah pada siklus kedua."
    )

    print("\n=== HASIL PENGUJIAN ===")
    print("Siklus pertama: SUKSES")
    print("Siklus kedua: SUKSES")
    print("Prediksi duplikat: Tidak ditemukan")

    print("\nPENGUJIAN INTEGRASI BERHASIL.")


if __name__ == "__main__":
    main()
