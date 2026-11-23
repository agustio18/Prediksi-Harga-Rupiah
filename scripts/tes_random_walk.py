
import numpy as np
import pandas as pd

from src.db import get_engine, ambil_harian_tersimpan
from src.ingestion import ke_mingguan
from src.features import hitung_fitur
from src.evaluasi import evaluasi_walk_forward


JUMLAH_SIMULASI = 10
SEED = 20261123


def buat_random_walk(tanggal, harga_awal, volatilitas, rng):
    """
    Membuat harga sintetis dengan return mingguan acak
    dan tidak memiliki pola prediktif.
    """

    jumlah_data = len(tanggal)

    # Return independen dengan rata-rata 0%
    return_acak = rng.normal(
        loc=0,
        scale=volatilitas,
        size=jumlah_data - 1
    )

    # Membentuk perjalanan harga dari return acak
    close = np.empty(jumlah_data)
    close[0] = harga_awal

    close[1:] = harga_awal * np.cumprod(
        1 + return_acak / 100
    )

    return pd.DataFrame({
        "tanggal": tanggal.to_numpy(),
        "close": close
    })


def main():
    print("=== RANDOM-WALK SANITY TEST ===")

    # Mengambil tanggal dan volatilitas historis
    engine = get_engine()
    harian = ambil_harian_tersimpan(engine)
    mingguan = ke_mingguan(harian)

    mingguan = mingguan.dropna(
        subset=["tanggal", "close"]
    ).reset_index(drop=True)

    return_historis = (
        mingguan["close"].pct_change(fill_method=None) * 100
    )

    volatilitas = float(return_historis.std())

    print("Jumlah data mingguan:", len(mingguan))
    print(f"Volatilitas simulasi: {volatilitas:.6f}%")
    print("Jumlah simulasi:", JUMLAH_SIMULASI)
    print("\nMemulai pengujian...\n")

    rng = np.random.default_rng(SEED)
    seluruh_hasil = []

    # Menjalankan 10 simulasi independen
    for nomor in range(1, JUMLAH_SIMULASI + 1):

        random_walk = buat_random_walk(
            tanggal=mingguan["tanggal"],
            harga_awal=float(mingguan["close"].iloc[0]),
            volatilitas=volatilitas,
            rng=rng
        )

        # Menghitung fitur dari data sintetis
        dataset = hitung_fitur(random_walk)

        # Evaluasi dengan metode yang sama seperti data asli
        hasil = evaluasi_walk_forward(
            dataset,
            jumlah_minggu=52,
            n_splits=5
        )

        ringkasan = hasil["ringkasan"]

        seluruh_hasil.append({
            "simulasi": nomor,
            "mae_svr": ringkasan["mae_svr"],
            "mae_baseline": ringkasan["mae_baseline"],
            "rmse_svr": ringkasan["rmse_svr"],
            "rmse_baseline": ringkasan["rmse_baseline"],
            "svr_unggul_mae": ringkasan["svr_lebih_baik_mae"],
            "svr_unggul_rmse": ringkasan["svr_lebih_baik_rmse"],
        })

        print(
            f"Simulasi {nomor:02d} | "
            f"MAE SVR: {ringkasan['mae_svr']:.6f} | "
            f"MAE Baseline: {ringkasan['mae_baseline']:.6f} | "
            f"RMSE SVR: {ringkasan['rmse_svr']:.6f} | "
            f"RMSE Baseline: {ringkasan['rmse_baseline']:.6f}"
        )

    # Menggabungkan hasil seluruh simulasi
    hasil_akhir = pd.DataFrame(seluruh_hasil)

    jumlah_unggul_mae = int(
        hasil_akhir["svr_unggul_mae"].sum()
    )

    jumlah_unggul_rmse = int(
        hasil_akhir["svr_unggul_rmse"].sum()
    )

    print("\n=== RINGKASAN RANDOM-WALK TEST ===")

    print(
        "Rata-rata MAE SVR:",
        f"{hasil_akhir['mae_svr'].mean():.6f}"
    )

    print(
        "Rata-rata MAE Baseline:",
        f"{hasil_akhir['mae_baseline'].mean():.6f}"
    )

    print(
        "Rata-rata RMSE SVR:",
        f"{hasil_akhir['rmse_svr'].mean():.6f}"
    )

    print(
        "Rata-rata RMSE Baseline:",
        f"{hasil_akhir['rmse_baseline'].mean():.6f}"
    )

    print(
        f"\nSVR unggul MAE: {jumlah_unggul_mae}/{JUMLAH_SIMULASI}"
    )

    print(
        f"SVR unggul RMSE: {jumlah_unggul_rmse}/{JUMLAH_SIMULASI}"
    )

    print("\nPengujian selesai.")


if __name__ == "__main__":
    main()

