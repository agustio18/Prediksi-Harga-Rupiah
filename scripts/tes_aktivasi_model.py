
import pandas as pd
from sqlalchemy import text

from src.db import get_engine
from src.model import (
    ambil_model_aktif,
    bandingkan_model,
    daftarkan_model,
)


NAMA_UJI = "__uji_aktivasi_model__"
FILE_UJI = "__uji_aktivasi_model__.joblib"


def main():
    engine = get_engine()
    model_id_uji = None
    model_id_lama = None

    try:
        model_lama = ambil_model_aktif(engine)

        if model_lama is None:
            raise RuntimeError("Model aktif tidak ditemukan.")

        model_id_lama = model_lama["id"]

        mae = float(model_lama["mae_persen"])
        rmse = float(model_lama["rmse_persen"])

        # Calon model simulasi yang lebih baik.
        ringkasan = {
            "mae_svr": mae * 0.90,
            "rmse_svr": rmse * 0.90,
            "akurasi_arah_svr": 60.0,
            "mae_baseline": mae + 0.10,
            "rmse_baseline": rmse + 0.10,
            "tanggal_uji_awal": model_lama["tanggal_uji_awal"],
            "tanggal_uji_akhir": model_lama["tanggal_uji_akhir"],
        }

        diterima, alasan = bandingkan_model(
            ringkasan,
            model_lama
        )

        print("=== PENGUJIAN AKTIVASI MODEL BARU ===")
        print("Model lama:", model_id_lama)
        print("Keputusan:", "DITERIMA" if diterima else "DITOLAK")
        print("Alasan:", alasan)

        assert diterima is True

        paket = {
            "parameter": {
                "kernel": model_lama["kernel"],
                "C": float(model_lama["c"]),
                "epsilon": float(model_lama["epsilon"]),
                "gamma": model_lama["gamma"],
            },
            "tanggal_acuan": model_lama["tanggal_data_akhir"],
        }

        dataset = pd.DataFrame({
            "tanggal": [model_lama["tanggal_data_awal"]]
        })

        # Model simulasi didaftarkan sebagai aktif.
        model_id_uji = daftarkan_model(
            engine=engine,
            model=None,
            paket=paket,
            dataset=dataset,
            nama_file=FILE_UJI,
            hasil_evaluasi={"ringkasan": ringkasan},
            aktif=True,
            nama=NAMA_UJI,
        )

        with engine.connect() as conn:
            status_lama = conn.execute(
                text("""
                    SELECT aktif FROM model_versi
                    WHERE id = :id
                """),
                {"id": model_id_lama},
            ).scalar_one()

            status_baru = conn.execute(
                text("""
                    SELECT aktif FROM model_versi
                    WHERE id = :id
                """),
                {"id": model_id_uji},
            ).scalar_one()

            jumlah_aktif = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM model_versi
                    WHERE aktif = TRUE
                """)
            ).scalar_one()

        print("\n=== HASIL PENGUJIAN ===")
        print("ID model baru:", model_id_uji)
        print("Status model lama:", status_lama)
        print("Status model baru:", status_baru)
        print("Jumlah model aktif:", jumlah_aktif)

        assert status_lama is False
        assert status_baru is True
        assert jumlah_aktif == 1

        print("\nPengujian aktivasi berhasil.")

    finally:
        # Menghapus model simulasi dan mengaktifkan kembali model lama.
        if model_id_uji is not None:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        DELETE FROM model_versi
                        WHERE id = :id
                    """),
                    {"id": model_id_uji},
                )

                conn.execute(
                    text("""
                        UPDATE model_versi
                        SET aktif = TRUE
                        WHERE id = :id
                    """),
                    {"id": model_id_lama},
                )

            print("Model simulasi dihapus.")
            print("Model aktif lama dipulihkan.")


if __name__ == "__main__":
    main()
