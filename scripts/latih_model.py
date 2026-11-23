
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.db import (
    get_engine,
    ambil_harian_tersimpan,
    buat_tabel,
    catat_log,
)

from src.ingestion import ke_mingguan
from src.features import hitung_fitur

from src.evaluasi import evaluasi_walk_forward

from src.model import (
    latih_model,
    ringkas_per_kernel,
    prediksi_return,
    konversi_ke_harga,
    simpan_model,
    daftarkan_model,
    ambil_model_aktif,
    perbarui_evaluasi_model,
    bandingkan_model,
)


def main():
    engine = get_engine()
    buat_tabel(engine)

    # -------------------------------------------------------
    # 1. Mengambil data dan menghitung fitur
    # -------------------------------------------------------

    harian = ambil_harian_tersimpan(engine)
    mingguan = ke_mingguan(harian)
    dataset = hitung_fitur(mingguan)

    print("=== PELATIHAN DAN SELEKSI MODEL SVR ===")
    print("Jumlah data mingguan:", len(mingguan))

    # -------------------------------------------------------
    # 2. Evaluasi calon model dengan tuning
    # -------------------------------------------------------

    print("\n=== EVALUASI CALON MODEL ===")
    print("Mencari parameter dengan GridSearchCV...")
    print("Melakukan walk-forward validation 52 minggu...")

    hasil_calon = evaluasi_walk_forward(
        dataset,
        jumlah_minggu=52,
        n_splits=5
    )

    ringkasan_baru = hasil_calon["ringkasan"]

    print("\nPerbandingan kernel (MAE validasi silang):")
    print(
        ringkas_per_kernel(
            hasil_calon["hasil_cv"]
        ).to_string(index=False)
    )

    print("\nParameter calon model:")
    for nama, nilai in ringkasan_baru["parameter"].items():
        print(f"  {nama}: {nilai}")

    print("\nMetrik calon model:")
    print(f"  MAE: {ringkasan_baru['mae_svr']:.6f}")
    print(f"  RMSE: {ringkasan_baru['rmse_svr']:.6f}")
    print(
        f"  Directional Accuracy: "
        f"{ringkasan_baru['akurasi_arah_svr']:.2f}%"
    )

    # -------------------------------------------------------
    # 3. Mengambil model aktif
    # -------------------------------------------------------

    model_aktif = ambil_model_aktif(engine)

    if model_aktif is not None:

        print("\n=== EVALUASI MODEL AKTIF ===")
        print("Model aktif:", model_aktif["nama"])

        # Memastikan parameter model aktif tersedia.
        if any(
            model_aktif[kunci] is None
            for kunci in ["kernel", "c", "epsilon"]
        ):
            raise ValueError(
                "Parameter model aktif tidak lengkap. "
                "Model tidak dapat dibandingkan."
            )

        parameter_aktif = {
            "kernel": model_aktif["kernel"],
            "C": float(model_aktif["c"]),
            "epsilon": float(model_aktif["epsilon"]),
            "gamma": model_aktif["gamma"] or "scale",
        }

        # Menggunakan parameter lama tanpa tuning ulang.
        hasil_model_aktif = evaluasi_walk_forward(
            dataset,
            jumlah_minggu=52,
            n_splits=5,
            parameter=parameter_aktif
        )

        # Memperbarui metrik model aktif pada periode pengujian sama.
        perbarui_evaluasi_model(
            engine,
            model_aktif["id"],
            hasil_model_aktif["ringkasan"]
        )

        # Membaca kembali metrik terbaru dari database.
        model_aktif = ambil_model_aktif(engine)

        print(
            f"  MAE model aktif: "
            f"{model_aktif['mae_persen']:.6f}"
        )
        print(
            f"  RMSE model aktif: "
            f"{model_aktif['rmse_persen']:.6f}"
        )

    else:
        print("\nBelum ada model aktif.")

    # -------------------------------------------------------
    # 4. Membandingkan calon model dengan model aktif
    # -------------------------------------------------------

    layak_aktif, alasan = bandingkan_model(
        ringkasan_baru,
        model_aktif
    )

    print("\n=== KEPUTUSAN SELEKSI MODEL ===")
    print("Keputusan:", "DITERIMA" if layak_aktif else "DITOLAK")
    print("Alasan:", alasan)

    # -------------------------------------------------------
    # 5. Melatih model final menggunakan parameter terpilih
    # -------------------------------------------------------

    print("\n=== PELATIHAN MODEL FINAL ===")

    model, paket = latih_model(
        dataset,
        tuning=False,
        parameter=ringkasan_baru["parameter"]
    )

    print("Jumlah data training:", len(paket["X_train"]))
    print("Kernel:", paket["parameter"]["kernel"])

    # -------------------------------------------------------
    # 6. Menyimpan model dan mendaftarkan versinya
    # -------------------------------------------------------

    nama_file = simpan_model(model, paket)

    model_id = daftarkan_model(
        engine=engine,
        model=model,
        paket=paket,
        dataset=dataset,
        nama_file=nama_file,
        hasil_evaluasi=hasil_calon,
        aktif=layak_aktif,
    )

    # -------------------------------------------------------
    # 7. Mencatat proses ke log
    # -------------------------------------------------------

    status_model = (
        "AKTIF" if layak_aktif else "TIDAK AKTIF"
    )

    pesan = (
        f"Model {nama_file} berhasil dilatih dan disimpan. "
        f"ID={model_id}, status={status_model}. "
        f"MAE={ringkasan_baru['mae_svr']:.6f}, "
        f"RMSE={ringkasan_baru['rmse_svr']:.6f}. "
        f"{alasan}"
    )

    catat_log(
        engine,
        status="SUKSES",
        baris_diproses=len(paket["X_train"]),
        pesan=pesan,
        sumber="latih_model",
    )

    print("\n=== HASIL PENDAFTARAN MODEL ===")
    print("File model:", nama_file)
    print("ID model:", model_id)
    print("Status:", status_model)

    # -------------------------------------------------------
    # 8. Prediksi contoh untuk minggu berikutnya
    # -------------------------------------------------------

    r = prediksi_return(
        model,
        paket["X_prediksi"]
    )

    harga = konversi_ke_harga(
        r,
        paket["harga_acuan"]
    )

    target = (
        pd.to_datetime(paket["tanggal_acuan"])
        + pd.Timedelta(days=7)
    )

    if r > 0:
        arah = "Rupiah melemah"
    elif r < 0:
        arah = "Rupiah menguat"
    else:
        arah = "Relatif stabil"

    print("\n=== CONTOH PREDIKSI ===")
    print(
        "Tanggal acuan:",
        pd.to_datetime(paket["tanggal_acuan"]).date()
    )
    print("Tanggal target:", target.date())
    print(f"Harga acuan: Rp {paket['harga_acuan']:,.2f}")
    print(f"Prediksi return: {r:.6f}%")
    print(f"Harga prediksi: Rp {harga:,.2f}")
    print("Arah:", arah)

    print("\nProses pelatihan dan seleksi selesai.")


if __name__ == "__main__":
    main()
