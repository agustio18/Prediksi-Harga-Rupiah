
from src.db import get_engine, ambil_harian_tersimpan
from src.ingestion import ke_mingguan
from src.features import hitung_fitur
from src.evaluasi import (
    evaluasi_walk_forward,
    eksperimen_panjang_data,
)

def main():
    engine = get_engine()

    # Mengambil seluruh data historis dari PostgreSQL
    harian = ambil_harian_tersimpan(engine)

    # Membentuk data mingguan dan menghitung fitur
    mingguan = ke_mingguan(harian)
    dataset = hitung_fitur(mingguan)

    print("=== EVALUASI MODEL SVR ===")
    print("\nMenjalankan walk-forward validation 52 minggu...")

    hasil_evaluasi = evaluasi_walk_forward(
        dataset,
        jumlah_minggu=52,
        n_splits=5
    )

    ringkasan = hasil_evaluasi["ringkasan"]
    hasil_prediksi = hasil_evaluasi["hasil_prediksi"]

    print("\n=== INFORMASI DATA ===")
    print("Total data mingguan:", len(mingguan))
    print(
        "Data training awal:",
        ringkasan["jumlah_data_training_awal"]
    )
    print("Data pengujian:", ringkasan["jumlah_data_uji"])

    print("\n=== PARAMETER MODEL TERPILIH ===")
    for nama, nilai in ringkasan["parameter"].items():
        print(f"{nama}: {nilai}")

    print("\n=== HASIL EVALUASI SVR ===")
    print(
        f"MAE SVR: {ringkasan['mae_svr']:.6f} "
        "poin persentase"
    )
    print(
        f"RMSE SVR: {ringkasan['rmse_svr']:.6f} "
        "poin persentase"
    )
    print(
        f"Directional Accuracy SVR: "
        f"{ringkasan['akurasi_arah_svr']:.2f}%"
    )

    print("\n=== HASIL NAIVE BASELINE ===")
    print(
        f"MAE Baseline: {ringkasan['mae_baseline']:.6f} "
        "poin persentase"
    )
    print(
        f"RMSE Baseline: {ringkasan['rmse_baseline']:.6f} "
        "poin persentase"
    )

    print("\n=== PERBANDINGAN ===")
    print(
        "SVR lebih baik berdasarkan MAE:",
        "YA" if ringkasan["svr_lebih_baik_mae"] else "TIDAK"
    )
    print(
        "SVR lebih baik berdasarkan RMSE:",
        "YA" if ringkasan["svr_lebih_baik_rmse"] else "TIDAK"
    )

    print("\n=== LIMA HASIL PREDIKSI TERAKHIR ===")
    print(
        hasil_prediksi.tail(5).to_string(index=False)
    )


    # Eksperimen perbandingan panjang data training
    print("\n=== EKSPERIMEN PANJANG DATA TRAINING ===")
    print("Membandingkan training 5, 8, dan 10 tahun...")

    hasil_eksperimen = eksperimen_panjang_data(
        dataset,
        daftar_tahun=(5, 8, 10),
        jumlah_minggu=52,
        n_splits=5
    )

    kolom_tampil = [
        "tahun_training",
        "jumlah_minggu_uji",
        "jumlah_training_awal",
        "rentang_training_tahun",
        "kernel",
        "mae_svr",
        "rmse_svr",
        "akurasi_arah_svr",
        "mae_baseline",
        "rmse_baseline",
        "svr_lebih_baik_mae",
        "svr_lebih_baik_rmse",
    ]

    print(
        hasil_eksperimen[kolom_tampil].to_string(index=False)
    )

    print("\nRentang tanggal training awal:")
    print(
        hasil_eksperimen[
            [
                "tahun_training",
                "tanggal_training_awal",
                "tanggal_training_akhir",
            ]
        ].to_string(index=False)
    )

    print("\nEvaluasi selesai.")


if __name__ == "__main__":
    main()
