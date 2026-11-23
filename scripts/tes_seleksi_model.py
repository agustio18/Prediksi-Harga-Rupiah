
from sqlalchemy import text

from src.db import get_engine
from src.model import ambil_model_aktif, bandingkan_model


def main():
    engine = get_engine()

    # Mengambil model aktif dari PostgreSQL
    model_aktif = ambil_model_aktif(engine)

    if model_aktif is None:
        raise RuntimeError("Tidak ditemukan model aktif.")

    mae_aktif = float(model_aktif["mae_persen"])
    rmse_aktif = float(model_aktif["rmse_persen"])

    print("=== PENGUJIAN SELEKSI MODEL ===")
    print("ID model aktif:", model_aktif["id"])
    print("MAE model aktif:", mae_aktif)
    print("RMSE model aktif:", rmse_aktif)

    # Membuat ringkasan calon model yang lebih baik
    calon_baik = {
        "mae_svr": mae_aktif * 0.90,
        "rmse_svr": rmse_aktif * 0.90,
        "mae_baseline": mae_aktif + 0.10,
        "rmse_baseline": rmse_aktif + 0.10,
        "tanggal_uji_awal": model_aktif["tanggal_uji_awal"],
        "tanggal_uji_akhir": model_aktif["tanggal_uji_akhir"],
    }

    diterima, alasan = bandingkan_model(
        calon_baik,
        model_aktif
    )

    print("\n=== SKENARIO 1: CALON MODEL LEBIH BAIK ===")
    print("Keputusan:", "DITERIMA" if diterima else "DITOLAK")
    print("Alasan:", alasan)

    # Membuat ringkasan calon model yang lebih buruk
    calon_buruk = {
        "mae_svr": mae_aktif + 0.01,
        "rmse_svr": rmse_aktif + 0.01,
        "mae_baseline": mae_aktif + 0.10,
        "rmse_baseline": rmse_aktif + 0.10,
        "tanggal_uji_awal": model_aktif["tanggal_uji_awal"],
        "tanggal_uji_akhir": model_aktif["tanggal_uji_akhir"],
    }

    diterima, alasan = bandingkan_model(
        calon_buruk,
        model_aktif
    )

    print("\n=== SKENARIO 2: CALON MODEL LEBIH BURUK ===")
    print("Keputusan:", "DITERIMA" if diterima else "DITOLAK")
    print("Alasan:", alasan)

    # Memastikan database tidak berubah
    with engine.connect() as conn:
        id_aktif = conn.execute(
            text("""
                SELECT id
                FROM model_versi
                WHERE aktif = TRUE
            """)
        ).scalar_one_or_none()

        jumlah_aktif = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM model_versi
                WHERE aktif = TRUE
            """)
        ).scalar_one()

    print("\n=== PEMERIKSAAN DATABASE ===")
    print("ID model aktif setelah pengujian:", id_aktif)
    print("Jumlah model aktif:", jumlah_aktif)

    assert diterima is False, (
        "Calon model buruk seharusnya ditolak."
    )

    assert id_aktif == model_aktif["id"], (
        "ID model aktif berubah."
    )

    assert jumlah_aktif == 1, (
        "Jumlah model aktif seharusnya tetap satu."
    )

    print("\nSemua pengujian seleksi model berhasil.")


if __name__ == "__main__":
    main()
