from datetime import datetime

import joblib
import pandas as pd
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from sqlalchemy import text

from config import MODEL_DIR
from src.features import KOLOM_FITUR, siapkan_dataset

# Ruang pencarian hiperparameter (PRD: kernel linear dan RBF)
PARAM_GRID = [
    {
        "svr__kernel": ["linear"],
        "svr__C": [0.01, 0.1, 1, 10],
        "svr__epsilon": [0.01, 0.1, 0.5],
    },
    {
        "svr__kernel": ["rbf"],
        "svr__C": [0.1, 1, 10, 100],
        "svr__epsilon": [0.01, 0.1, 0.5],
        "svr__gamma": ["scale", 0.01, 0.1],
    },
]


def buat_model_svr(kernel="rbf", C=1.0, epsilon=0.1, gamma="scale"):
    """
    Membuat pipeline StandardScaler dan SVR.
    Scaler berada di dalam Pipeline agar mean dan std hanya
    dipelajari dari data latih (mencegah data leakage).
    """

    return Pipeline([
        ("scaler", StandardScaler()),
        ("svr", SVR(kernel=kernel, C=C, epsilon=epsilon, gamma=gamma)),
    ])


def cari_parameter_terbaik(X, y, n_splits=5):
    """
    Grid Search dengan TimeSeriesSplit (data latih selalu
    berada sebelum data validasi secara kronologis).
    """

    pencarian = GridSearchCV(
        estimator=buat_model_svr(),
        param_grid=PARAM_GRID,
        cv=TimeSeriesSplit(n_splits=n_splits),
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
        refit=True,
    )

    pencarian.fit(X, y)

    hasil_cv = pd.DataFrame(pencarian.cv_results_)

    return pencarian, hasil_cv


def ringkas_per_kernel(hasil_cv):
    """
    Mengambil kombinasi terbaik tiap kernel untuk dibandingkan.
    """

    baris = []

    for kernel in ["linear", "rbf"]:
        bagian = hasil_cv[hasil_cv["param_svr__kernel"] == kernel]

        if bagian.empty:
            continue

        terbaik = bagian.sort_values("rank_test_score").iloc[0]

        baris.append({
            "kernel": kernel,
            "C": terbaik["param_svr__C"],
            "epsilon": terbaik["param_svr__epsilon"],
            "gamma": terbaik.get("param_svr__gamma"),
            "mae_cv": -terbaik["mean_test_score"],
        })

    return pd.DataFrame(baris)


def latih_model(dataset, tuning=True, parameter=None):
    """
    Melatih SVR menggunakan seluruh data berlabel.

    tuning=True  : mencari parameter dengan Grid Search + TimeSeriesSplit
    tuning=False : memakai `parameter` (dict kernel, C, epsilon, gamma)
                   atau default bila parameter kosong
    """

    paket = siapkan_dataset(dataset)

    if tuning:
        pencarian, hasil_cv = cari_parameter_terbaik(
            paket["X_train"], paket["y_train"]
        )
        model = pencarian.best_estimator_
        paket["hasil_cv"] = hasil_cv
        paket["mae_cv"] = float(-pencarian.best_score_)
    else:
        model = buat_model_svr(**(parameter or {}))
        model.fit(paket["X_train"], paket["y_train"])

    paket["parameter"] = ambil_parameter(model)

    return model, paket


def ambil_parameter(model):
    """
    Membaca hiperparameter SVR dari pipeline yang sudah dilatih.
    """

    svr = model.named_steps["svr"]

    return {
        "kernel": svr.kernel,
        "C": float(svr.C),
        "epsilon": float(svr.epsilon),
        "gamma": str(svr.gamma),
        "jumlah_support_vector": int(len(svr.support_)),
    }


def prediksi_return(model, X_prediksi):
    """
    Memprediksi return untuk minggu berikutnya.
    """

    hasil = model.predict(X_prediksi)

    return float(hasil[0])


def konversi_ke_harga(return_prediksi, harga_acuan):
    """
    Mengubah prediksi return menjadi prediksi harga kurs.
    """

    harga_prediksi = harga_acuan * (
        1 + return_prediksi / 100
    )

    return float(harga_prediksi)


# ---------------------------------------------------------------
# Penyimpanan model
# ---------------------------------------------------------------

def simpan_model(model, paket, nama=None):
    """
    Menyimpan pipeline (scaler + SVR) ke file .joblib beserta
    metadata, lalu mengembalikan nama file.
    """

    waktu = datetime.now()

    if nama is None:
        nama = f"svr_{waktu:%Y%m%d_%H%M%S}"

    nama_file = f"{nama}.joblib"

    isi = {
        "pipeline": model,
        "fitur": list(KOLOM_FITUR),
        "parameter": paket["parameter"],
        "dibuat_pada": waktu.isoformat(timespec="seconds"),
    }

    joblib.dump(isi, MODEL_DIR / nama_file)

    return nama_file


def muat_model(nama_file):
    """
    Memuat model dari folder models. Mengembalikan dict berisi
    pipeline, fitur, parameter, dan dibuat_pada.
    """

    lokasi = MODEL_DIR / nama_file

    if not lokasi.exists():
        raise FileNotFoundError(f"File model tidak ditemukan: {lokasi}")

    isi = joblib.load(lokasi)

    if list(isi["fitur"]) != list(KOLOM_FITUR):
        raise ValueError(
            "Fitur model berbeda dengan KOLOM_FITUR saat ini. "
            "Latih ulang model."
        )

    return isi



# ---------------------------------------------------------------
# Pencatatan dan seleksi versi model di PostgreSQL
# ---------------------------------------------------------------

def ambil_model_aktif(engine):
    """
    Mengambil model aktif beserta parameter dan metrik evaluasinya.
    """

    sql = text("""
        SELECT
            id,
            nama,
            file_model,
            kernel,
            c,
            epsilon,
            gamma,
            tanggal_data_awal,
            tanggal_data_akhir,
            mae_persen,
            rmse_persen,
            akurasi_arah,
            mae_baseline_persen,
            tanggal_uji_awal,
            tanggal_uji_akhir
        FROM model_versi
        WHERE aktif = TRUE
        ORDER BY id DESC
        LIMIT 1
    """)

    with engine.connect() as conn:
        baris = conn.execute(sql).mappings().first()

    return dict(baris) if baris else None


def perbarui_evaluasi_model(engine, model_id, ringkasan):
    """
    Memperbarui metrik evaluasi model aktif pada periode pengujian
    terbaru agar dapat dibandingkan secara adil dengan calon model.
    """

    sql = text("""
        UPDATE model_versi
        SET
            mae_persen = :mae,
            rmse_persen = :rmse,
            akurasi_arah = :akurasi,
            mae_baseline_persen = :mae_baseline,
            tanggal_uji_awal = :tanggal_uji_awal,
            tanggal_uji_akhir = :tanggal_uji_akhir
        WHERE id = :model_id
          AND aktif = TRUE
    """)

    with engine.begin() as conn:
        hasil = conn.execute(sql, {
            "mae": ringkasan["mae_svr"],
            "rmse": ringkasan["rmse_svr"],
            "akurasi": ringkasan["akurasi_arah_svr"],
            "mae_baseline": ringkasan["mae_baseline"],
            "tanggal_uji_awal": ringkasan["tanggal_uji_awal"],
            "tanggal_uji_akhir": ringkasan["tanggal_uji_akhir"],
            "model_id": model_id,
        })

        if hasil.rowcount != 1:
            raise RuntimeError(
                "Metrik model aktif gagal diperbarui."
            )


def bandingkan_model(ringkasan_baru, ringkasan_aktif):
    """
    Menentukan apakah calon model layak menjadi model aktif.

    Syarat:
    1. MAE harus lebih kecil daripada naive baseline.
    2. RMSE tidak boleh lebih besar daripada naive baseline.
    3. Jika ada model aktif, MAE harus lebih kecil
       daripada model aktif dan RMSE tidak boleh lebih besar.
    4. Periode pengujian harus sama.
    """

    mae_baru = ringkasan_baru["mae_svr"]
    rmse_baru = ringkasan_baru["rmse_svr"]

    mae_baseline = ringkasan_baru["mae_baseline"]
    rmse_baseline = ringkasan_baru["rmse_baseline"]

    # Setiap calon wajib mengungguli naive baseline.
    if not (
        mae_baru < mae_baseline
        and rmse_baru <= rmse_baseline
    ):
        return False, (
            "Model baru tidak mengungguli naive baseline."
        )

    # Jika belum ada model aktif.
    if ringkasan_aktif is None:
        return True, (
            "Model pertama berhasil mengungguli naive baseline."
        )

    # Memastikan periode evaluasi sama.
    tanggal_baru = (
        ringkasan_baru["tanggal_uji_awal"],
        ringkasan_baru["tanggal_uji_akhir"],
    )

    tanggal_aktif = (
        ringkasan_aktif["tanggal_uji_awal"],
        ringkasan_aktif["tanggal_uji_akhir"],
    )

    if tanggal_baru != tanggal_aktif:
        raise ValueError(
            "Periode pengujian kedua model berbeda. "
            "Perbandingan tidak dapat dilakukan."
        )

    nilai_mae_aktif = ringkasan_aktif["mae_persen"]
    nilai_rmse_aktif = ringkasan_aktif["rmse_persen"]

    if (
        nilai_mae_aktif is None
        or pd.isna(nilai_mae_aktif)
        or nilai_rmse_aktif is None
        or pd.isna(nilai_rmse_aktif)
    ):
        raise ValueError(
            "Model aktif belum memiliki metrik evaluasi."
        )

    mae_aktif = float(nilai_mae_aktif)
    rmse_aktif = float(nilai_rmse_aktif)

    if mae_baru < mae_aktif and rmse_baru <= rmse_aktif:
        return True, (
            "Model baru mengungguli baseline dan memenuhi "
            "kriteria dibandingkan model aktif."
        )

    return False, (
        "Model baru tidak lebih baik daripada model aktif. "
        "Model aktif sebelumnya tetap dipertahankan."
    )


def daftarkan_model(
    engine,
    model,
    paket,
    dataset,
    nama_file,
    hasil_evaluasi,
    aktif=False,
    nama=None
):
    """
    Mencatat model dan hasil evaluasinya ke tabel model_versi.

    Model hanya diaktifkan jika parameter aktif=True.
    Keputusan tersebut harus berasal dari hasil bandingkan_model().
    """

    ringkasan = hasil_evaluasi["ringkasan"]
    param = paket["parameter"]

    tanggal = pd.to_datetime(dataset["tanggal"])
    tanggal_awal = tanggal.min().date()
    tanggal_akhir = pd.to_datetime(
        paket["tanggal_acuan"]
    ).date()

    sql_nonaktif = text("""
        UPDATE model_versi
        SET aktif = FALSE
        WHERE aktif = TRUE
    """)

    sql_insert = text("""
        INSERT INTO model_versi (
            nama,
            dibuat_pada,
            fitur,
            kernel,
            c,
            epsilon,
            gamma,
            tanggal_data_awal,
            tanggal_data_akhir,
            mae_persen,
            rmse_persen,
            akurasi_arah,
            mae_baseline_persen,
            tanggal_uji_awal,
            tanggal_uji_akhir,
            file_model,
            aktif
        )
        VALUES (
            :nama,
            :dibuat_pada,
            :fitur,
            :kernel,
            :c,
            :epsilon,
            :gamma,
            :tanggal_awal,
            :tanggal_akhir,
            :mae,
            :rmse,
            :akurasi,
            :mae_baseline,
            :tanggal_uji_awal,
            :tanggal_uji_akhir,
            :file_model,
            :aktif
        )
        RETURNING id
    """)

    with engine.begin() as conn:

        # Nonaktifkan model lama hanya jika model baru disetujui.
        if aktif:
            conn.execute(sql_nonaktif)

        model_id = conn.execute(sql_insert, {
            "nama": nama or nama_file.replace(".joblib", ""),
            "dibuat_pada": datetime.now(),
            "fitur": ",".join(KOLOM_FITUR),
            "kernel": param["kernel"],
            "c": param["C"],
            "epsilon": param["epsilon"],
            "gamma": param["gamma"],
            "tanggal_awal": tanggal_awal,
            "tanggal_akhir": tanggal_akhir,
            "mae": ringkasan["mae_svr"],
            "rmse": ringkasan["rmse_svr"],
            "akurasi": ringkasan["akurasi_arah_svr"],
            "mae_baseline": ringkasan["mae_baseline"],
            "tanggal_uji_awal": ringkasan["tanggal_uji_awal"],
            "tanggal_uji_akhir": ringkasan["tanggal_uji_akhir"],
            "file_model": nama_file,
            "aktif": aktif,
        }).scalar()

    return int(model_id)
