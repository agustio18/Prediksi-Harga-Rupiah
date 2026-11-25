
import pandas as pd

from src.ingestion import ke_mingguan
from src.siklus import periksa_data_mingguan


def buat_data(tanggal, status):
    jumlah = len(tanggal)
    harga = [17000 + (i * 10) for i in range(jumlah)]

    return pd.DataFrame({
        "tanggal": pd.to_datetime(tanggal),
        "open": harga,
        "high": [h + 20 for h in harga],
        "low": [h - 20 for h in harga],
        "close": harga,
        "status": status,
    })


def main():
    print("=== PENGUJIAN PERIKSA DATA MINGGUAN ===")

    # SKENARIO 1: Data lengkap, tetapi memiliki PERIKSA.
    data = buat_data(
        [
            "2026-11-16",
            "2026-11-17",
            "2026-11-18",
            "2026-11-19",
            "2026-11-20",
        ],
        ["VALID", "PERIKSA", "VALID", "PERIKSA", "VALID"]
    )

    mingguan = ke_mingguan(data, hari_ini="2026-11-21")

    tanggal = periksa_data_mingguan(
        mingguan,
        hari_ini="2026-11-21"
    )

    assert str(tanggal) == "2026-11-20"
    assert mingguan.iloc[-1]["jumlah_periksa"] == 2

    print("LULUS: Data PERIKSA menghasilkan peringatan tanpa menghentikan proses.")

    # SKENARIO 2: Observasi terakhir Rabu, masih dalam toleransi.
    data = buat_data(
        ["2026-11-16", "2026-11-17", "2026-11-18"],
        ["VALID", "VALID", "VALID"]
    )

    mingguan = ke_mingguan(data, hari_ini="2026-11-21")

    tanggal = periksa_data_mingguan(
        mingguan,
        hari_ini="2026-11-21"
    )

    assert str(tanggal) == "2026-11-20"

    print("LULUS: Observasi Rabu diterima dalam toleransi.")

    # SKENARIO 3: Observasi hanya sampai Senin.
    data = buat_data(
        ["2026-11-16"],
        ["VALID"]
    )

    mingguan = ke_mingguan(data, hari_ini="2026-11-25")

    try:
        periksa_data_mingguan(
            mingguan,
            hari_ini="2026-11-25"
        )

        raise AssertionError(
            "Data yang hanya sampai Senin seharusnya ditolak."
        )

    except RuntimeError as error:
        print("LULUS: Data tidak lengkap ditolak.")
        print("Pesan:", error)

    print("\nSemua pengujian berhasil.")


if __name__ == "__main__":
    main()

