
import pandas as pd
from sqlalchemy import text

from src.db import get_engine
from src.model import (
    ambil_model_aktif,
    bandingkan_model,
    daftarkan_model,
)


NAMA_UJI = "__uji_pendaftaran_model_tidak_aktif__"
FILE_UJI = "__uji_pendaftaran_model_tidak_aktif__.joblib"


def main():
    engine = get_engine()
    model_id_uji = None

    try:
        # Menghapus sisa pengujian sebelumnya jika pernah terhenti.
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM model_versi WHERE nama = :nama"),
                {"nama": NAMA_UJI},
            )

        # Mengambil model aktif yang sebenarnya.
        model_aktif = ambil_model_aktif(engine)

        if model_aktif is None:
            raise RuntimeError("Model aktif tidak ditemukan.")

        mae_aktif = float(model_aktif["mae_persen"])
        rmse_aktif = float(model_aktif["rmse_persen"])

        if (
            model_aktif["tanggal_uji_awal"] is None
            or model_aktif["tanggal_uji_akhir"] is None
        ):
            raise RuntimeError(
                "Periode pengujian model aktif belum tersedia."
            )

        print("=== PENGUJIAN PENDAFTARAN MODEL ===")
        print("ID model aktif sebelum pengujian:", model_aktif["id"])

        # Membuat calon model yang lebih buruk daripada model aktif,
        # tetapi tetap lebih baik daripada baseline simulasi.
        ringkasan = {
            "mae_svr": mae_aktif + 0.01,
            "rmse_svr": rmse_aktif + 0.01,
            "akurasi_arah_svr": 50.0,
            "mae_baseline": mae_aktif + 0.10,
            "rmse_baseline": rmse_aktif + 0.10,
            "tanggal_uji_awal": model_aktif["tanggal_uji_awal"],
            "tanggal_uji_akhir": model_aktif["tanggal_uji_akhir"],
        }

        # Memastikan calon model ditolak.
        diterima, alasan = bandingkan_model(
            ringkasan,
            model_aktif
        )

        print("\nKeputusan seleksi:", "DITERIMA" if diterima else "DITOLAK")
        print("Alasan:", alasan)

        assert diterima is False, (
            "Calon model buruk seharusnya ditolak."
        )

        # Data contoh hanya untuk menguji fungsi pendaftaran.
        paket = {
            "parameter": {
                "kernel": model_aktif["kernel"],
                "C": float(model_aktif["c"]),
                "epsilon": float(model_aktif["epsilon"]),
                "gamma": model_aktif["gamma"],
            },
            "tanggal_acuan": model_aktif["tanggal_data_akhir"],
        }

        dataset = pd.DataFrame({
            "tanggal": [model_aktif["tanggal_data_awal"]]
        })

        # Daftarkan sebagai tidak aktif.
        model_id_uji = daftarkan_model(
            engine=engine,
            model=None,
            paket=paket,
            dataset=dataset,
            nama_file=FILE_UJI,
            hasil_evaluasi={"ringkasan": ringkasan},
            aktif=False,
            nama=NAMA_UJI,
        )

        # Periksa status calon model di database.
        with engine.connect() as conn:
            status_uji = conn.execute(
                text("""
                    SELECT aktif
                    FROM model_versi
                    WHERE id = :id
                """),
                {"id": model_id_uji},
            ).scalar_one()

        # Periksa model aktif setelah pendaftaran.
        model_aktif_setelah = ambil_model_aktif(engine)

        with engine.connect() as conn:
            jumlah_aktif = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM model_versi
                    WHERE aktif = TRUE
                """)
            ).scalar_one()

        print("\n=== HASIL PENDAFTARAN ===")
        print("ID calon model:", model_id_uji)
        print("Status calon model:", status_uji)
        print("ID model aktif setelah pengujian:",
              model_aktif_setelah["id"])
        print("Jumlah model aktif:", jumlah_aktif)

        assert status_uji is False, (
            "Calon model seharusnya tersimpan sebagai tidak aktif."
        )

        assert model_aktif_setelah["id"] == model_aktif["id"], (
            "Model aktif lama berubah."
        )

        assert jumlah_aktif == 1, (
            "Jumlah model aktif seharusnya tetap satu."
        )

        print("\nSemua pengujian pendaftaran berhasil.")

    finally:
        # Menghapus baris sementara agar database kembali seperti semula.
        if model_id_uji is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("DELETE FROM model_versi WHERE id = :id"),
                    {"id": model_id_uji},
                )

            print("\nData pengujian sementara sudah dibersihkan.")


if __name__ == "__main__":
    main()
