
import numpy as np
import pandas as pd

from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.features import KOLOM_FITUR
from src.model import buat_model_svr, cari_parameter_terbaik


def evaluasi_walk_forward(
    dataset,
    jumlah_minggu=52,
    n_splits=5,
    parameter=None
    ):    
    """
    Mengevaluasi SVR dengan expanding walk-forward validation.

    Parameter SVR dipilih hanya dari data sebelum periode pengujian.
    Setiap minggu, model dilatih ulang menggunakan data yang sudah tersedia.
    """

    if dataset is None or dataset.empty:
        raise ValueError("Dataset evaluasi kosong.")

    kolom_wajib = ["tanggal", "target"] + KOLOM_FITUR
    kolom_hilang = [
        kolom for kolom in kolom_wajib
        if kolom not in dataset.columns
    ]

    if kolom_hilang:
        raise ValueError(
            f"Kolom dataset tidak ditemukan: {kolom_hilang}"
        )

    data = dataset.copy()
    data["tanggal"] = pd.to_datetime(data["tanggal"])
    data = data.sort_values("tanggal").reset_index(drop=True)

    # Target pada suatu baris adalah return pada minggu berikutnya.
    # Simpan tanggal minggu target agar tidak mengasumsikan
    # selalu terdapat jarak tepat tujuh hari.
    data["tanggal_target"] = data["tanggal"].shift(-1)

    # Hanya gunakan baris dengan lima fitur dan target lengkap.
    data = data.dropna(
        subset=KOLOM_FITUR + ["target", "tanggal_target"]
    ).reset_index(drop=True)

    if len(data) <= jumlah_minggu:
        raise ValueError(
            "Jumlah data tidak cukup untuk periode pengujian "
            f"{jumlah_minggu} minggu."
        )

    # Membagi data awal dan 52 minggu pengujian.
    posisi_awal_uji = len(data) - jumlah_minggu

    data_awal = data.iloc[:posisi_awal_uji].copy()

    if len(data_awal) <= n_splits:
        raise ValueError(
            "Data awal tidak cukup untuk TimeSeriesSplit."
        )


    # ---------------------------------------------------------
    # 1. Menentukan parameter model
    # ---------------------------------------------------------

    if parameter is None:
        # Calon model: mencari parameter terbaik
        pencarian, hasil_cv = cari_parameter_terbaik(
            data_awal[KOLOM_FITUR],
            data_awal["target"],
            n_splits=n_splits
        )

        parameter_terpilih = pencarian.best_params_

        parameter_model = {
            "kernel": parameter_terpilih["svr__kernel"],
            "C": float(parameter_terpilih["svr__C"]),
            "epsilon": float(parameter_terpilih["svr__epsilon"]),
            "gamma": parameter_terpilih.get(
                "svr__gamma", "scale"
            ),
        }

        mae_cv_awal = float(-pencarian.best_score_)

    else:
        # Model aktif: menggunakan parameter yang sudah tersimpan
        gamma = parameter.get("gamma", "scale")

        # PostgreSQL menyimpan gamma sebagai VARCHAR.
        # Ubah kembali menjadi angka jika nilainya bukan scale/auto.
        if isinstance(gamma, str) and gamma not in ("scale", "auto"):
            gamma = float(gamma)

        parameter_model = {
            "kernel": parameter["kernel"],
            "C": float(parameter["C"]),
            "epsilon": float(parameter["epsilon"]),
            "gamma": gamma,
        }

        hasil_cv = pd.DataFrame()
        mae_cv_awal = None

    # ---------------------------------------------------------
    # 2. Walk-forward validation
    # ---------------------------------------------------------

    hasil_prediksi = []

    for posisi in range(posisi_awal_uji, len(data)):
        # Data training hanya sampai minggu sebelum data uji.
        data_latih = data.iloc[:posisi]
        data_uji = data.iloc[[posisi]]

        X_train = data_latih[KOLOM_FITUR]
        y_train = data_latih["target"]

        X_test = data_uji[KOLOM_FITUR]

        # Membuat dan melatih ulang model setiap minggu.
        model = buat_model_svr(**parameter_model)
        model.fit(X_train, y_train)

        prediksi_svr = float(model.predict(X_test)[0])
        aktual = float(data_uji["target"].iloc[0])

        hasil_prediksi.append({
            "tanggal_acuan": data_uji["tanggal"].iloc[0],
            "tanggal_target": data_uji["tanggal_target"].iloc[0],
            "aktual": aktual,
            "prediksi_svr": prediksi_svr,
            "prediksi_baseline": 0.0,
            "arah_benar": (
                np.sign(aktual) == np.sign(prediksi_svr)
            ),
        })

    hasil = pd.DataFrame(hasil_prediksi)

    # ---------------------------------------------------------
    # 3. Menghitung metrik evaluasi
    # ---------------------------------------------------------

    y_aktual = hasil["aktual"]
    y_svr = hasil["prediksi_svr"]
    y_baseline = hasil["prediksi_baseline"]

    mae_svr = mean_absolute_error(y_aktual, y_svr)
    rmse_svr = np.sqrt(mean_squared_error(y_aktual, y_svr))

    mae_baseline = mean_absolute_error(
        y_aktual, y_baseline
    )
    rmse_baseline = np.sqrt(
        mean_squared_error(y_aktual, y_baseline)
    )

    akurasi_arah = (
        np.mean(np.sign(y_aktual) == np.sign(y_svr)) * 100
    )

    ringkasan = {
        "jumlah_data_training_awal": len(data_awal),
        "jumlah_data_uji": len(hasil),
        "mae_svr": float(mae_svr),
        "rmse_svr": float(rmse_svr),
        "akurasi_arah_svr": float(akurasi_arah),
        "mae_baseline": float(mae_baseline),
        "rmse_baseline": float(rmse_baseline),
        "svr_lebih_baik_mae": bool(mae_svr < mae_baseline),
        "svr_lebih_baik_rmse": bool(rmse_svr < rmse_baseline),
        "mae_cv_awal": mae_cv_awal,
        "parameter": parameter_model,
        "tanggal_uji_awal": pd.to_datetime(hasil["tanggal_target"].iloc[0]).date(),
        "tanggal_uji_akhir": pd.to_datetime(hasil["tanggal_target"].iloc[-1]).date(),
    }

    return {
        "ringkasan": ringkasan,
        "hasil_prediksi": hasil,
        "hasil_cv": hasil_cv,
    }


def eksperimen_panjang_data(
    dataset,
    daftar_tahun=(5, 8, 10),
    jumlah_minggu=52,
    n_splits=5
):
    """
    Membandingkan SVR dengan panjang data training 5, 8, dan 10 tahun.

    Ketiga eksperimen menggunakan 52 minggu pengujian yang sama.
    Training menggunakan rolling window sesuai panjang tahun.
    """

    if dataset is None or dataset.empty:
        raise ValueError("Dataset eksperimen kosong.")

    data = dataset.copy()
    data["tanggal"] = pd.to_datetime(data["tanggal"])
    data = data.sort_values("tanggal").reset_index(drop=True)

    # Menentukan tanggal target sebelum menghapus data tidak lengkap
    data["tanggal_target"] = data["tanggal"].shift(-1)

    # Mengambil data dengan fitur dan target lengkap
    data = data.dropna(
        subset=KOLOM_FITUR + ["target", "tanggal_target"]
    ).reset_index(drop=True)

    if len(data) <= jumlah_minggu:
        raise ValueError("Data tidak cukup untuk periode pengujian.")

    # Menentukan satu periode pengujian yang sama
    posisi_awal_uji = len(data) - jumlah_minggu

    hasil_eksperimen = []

    for tahun in daftar_tahun:

        # Data training awal dibatasi berdasarkan tanggal
        tanggal_uji_pertama = data.iloc[posisi_awal_uji]["tanggal"]
        batas_awal = tanggal_uji_pertama - pd.DateOffset(
            years=tahun
        )

        data_latih_awal = data.iloc[:posisi_awal_uji].copy()
        data_latih_awal = data_latih_awal[
            data_latih_awal["tanggal"] >= batas_awal
        ]

        if len(data_latih_awal) <= n_splits:
            raise ValueError(
                f"Data training {tahun} tahun tidak cukup."
            )

        # Tuning dilakukan hanya pada data training awal
        pencarian, hasil_cv = cari_parameter_terbaik(
            data_latih_awal[KOLOM_FITUR],
            data_latih_awal["target"],
            n_splits=n_splits
        )

        parameter_terpilih = pencarian.best_params_

        parameter_model = {
            "kernel": parameter_terpilih["svr__kernel"],
            "C": float(parameter_terpilih["svr__C"]),
            "epsilon": float(parameter_terpilih["svr__epsilon"]),
            "gamma": parameter_terpilih.get("svr__gamma", "scale"),
        }

        hasil_prediksi = []
        jumlah_training = []

        # Walk-forward menggunakan periode pengujian yang sama
        for posisi in range(posisi_awal_uji, len(data)):

            data_uji = data.iloc[[posisi]]
            tanggal_sekarang = data_uji["tanggal"].iloc[0]

            # Batas awal training bergeser setiap minggu
            batas_training = tanggal_sekarang - pd.DateOffset(
                years=tahun
            )

            data_latih = data.iloc[:posisi].copy()
            data_latih = data_latih[
                data_latih["tanggal"] >= batas_training
            ]

            if data_latih.empty:
                raise ValueError(
                    f"Training kosong pada eksperimen {tahun} tahun."
                )

            model = buat_model_svr(**parameter_model)

            model.fit(
                data_latih[KOLOM_FITUR],
                data_latih["target"]
            )

            prediksi = float(
                model.predict(data_uji[KOLOM_FITUR])[0]
            )

            aktual = float(data_uji["target"].iloc[0])

            hasil_prediksi.append({
                "aktual": aktual,
                "prediksi_svr": prediksi,
            })

            jumlah_training.append(len(data_latih))

        hasil = pd.DataFrame(hasil_prediksi)

        y_aktual = hasil["aktual"]
        y_svr = hasil["prediksi_svr"]
        y_baseline = np.zeros(len(y_aktual))

        # Menghitung metrik SVR
        mae_svr = mean_absolute_error(y_aktual, y_svr)
        rmse_svr = np.sqrt(
            mean_squared_error(y_aktual, y_svr)
        )

        # Menghitung metrik baseline
        mae_baseline = mean_absolute_error(
            y_aktual, y_baseline
        )
        rmse_baseline = np.sqrt(
            mean_squared_error(y_aktual, y_baseline)
        )

        akurasi_arah = (
            np.mean(
                np.sign(y_aktual) == np.sign(y_svr)
            ) * 100
        )

        rentang_data = (
            data_latih_awal["tanggal"].max()
            - data_latih_awal["tanggal"].min()
        ).days / 365.25

        hasil_eksperimen.append({
            "tahun_training": tahun,
            "jumlah_minggu_uji": len(hasil),
            "jumlah_training_awal": len(data_latih_awal),
            "jumlah_training_min": min(jumlah_training),
            "jumlah_training_max": max(jumlah_training),
            "tanggal_training_awal": (
                data_latih_awal["tanggal"].min().date()),
            "tanggal_training_akhir": (
                data_latih_awal["tanggal"].max().date()
            ),
            "rentang_training_tahun": round(rentang_data, 2),
            "kernel": parameter_model["kernel"],
            "C": parameter_model["C"],
            "epsilon": parameter_model["epsilon"],
            "gamma": parameter_model["gamma"],
            "mae_cv_awal": float(-pencarian.best_score_),
            "mae_svr": float(mae_svr),
            "rmse_svr": float(rmse_svr),
            "akurasi_arah_svr": float(akurasi_arah),
            "mae_baseline": float(mae_baseline),
            "rmse_baseline": float(rmse_baseline),
            "svr_lebih_baik_mae": bool(
                mae_svr < mae_baseline
            ),
            "svr_lebih_baik_rmse": bool(
                rmse_svr < rmse_baseline
            ),
        })

    return pd.DataFrame(hasil_eksperimen)
