
"""Menjalankan siklus dan menampilkan hasil prediksi USD/IDR."""

from sqlalchemy import text

from src.siklus import jalankan_siklus
from src.db import get_engine


def format_rupiah(nilai):
    angka = f"{float(nilai):,.2f}"
    angka = angka.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"Rp{angka}"


def format_persen(nilai):
    return f"{float(nilai):.6f}".replace(".", ",") + "%"


def main():
    engine = None

    try:
        # Memperbarui data dan membuat prediksi.
        jalankan_siklus()

        # Mengambil prediksi terbaru dari database.
        engine = get_engine()

        sql = text("""
            SELECT
                tanggal_acuan,
                tanggal_target,
                harga_acuan,
                return_persen,
                harga_prediksi
            FROM prediksi
            ORDER BY tanggal_target DESC, tanggal_acuan DESC, id DESC
            LIMIT 1
        """)

        with engine.connect() as conn:
            prediksi = conn.execute(sql).mappings().first()

        if prediksi is None:
            print("\nBelum ada prediksi yang tersimpan.")
            return

        hasil_return = float(prediksi["return_persen"])

        if hasil_return < 0:
            kesimpulan = "Rupiah diprediksi MENGUAT"
        elif hasil_return > 0:
            kesimpulan = "Rupiah diprediksi MELEMAH"
        else:
            kesimpulan = "Kurs diprediksi TETAP"

        print("\n" + "=" * 40)
        print("       HASIL PREDIKSI USD/IDR")
        print("=" * 40)

        print("Tanggal acuan    :", prediksi["tanggal_acuan"])
        print("Tanggal target   :", prediksi["tanggal_target"])
        print("Harga acuan      :", format_rupiah(prediksi["harga_acuan"]))
        print("Prediksi return  :", format_persen(hasil_return))
        print("Prediksi harga   :", format_rupiah(prediksi["harga_prediksi"]))

        print("-" * 40)
        print("Kesimpulan       :", kesimpulan)
        print("=" * 40)

    except Exception as error:
        print("\nGagal menjalankan prediksi:", error)

    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
