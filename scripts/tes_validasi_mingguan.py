
import pandas as pd

from src.ingestion import ke_mingguan
from src.siklus import periksa_data_mingguan


def buat_data(tanggal):
    jumlah = len(tanggal)

    harga = [17000 + (i * 10) for i in range(jumlah)]

    return pd.DataFrame({
        "tanggal": pd.to_datetime(tanggal),
        "open": harga,
        "high": [h + 20 for h in harga],
        "low": [h - 20 for h in harga],
        "close": harga,
    })


def main():
    print("=== PENGUJIAN VALIDASI DATA MINGGUAN ===")

    # SKENARIO 1: Data tersedia sampai Jumat.
    data_lengkap = buat_data([
        "2026-11-16",
        "2026-11-17",
        "2026-11-18",
        "2026-11-19",
        "2026-11-20",
    ])

    mingguan = ke_mingguan(
        data_lengkap,
        hari_ini="2026-11-21"
    )

    tanggal = periksa_data_mingguan(
        mingguan,
        hari_ini="2026-11-21"
    )

    assert str(tanggal) == "2026-11-20"

    print("\nSkenario 1: Data sampai Jumat")
    print(mingguan.tail(1).to_string(index=False))
    print("LULUS: data mingguan diterima.")

    # SKENARIO 2: Data hanya tersedia sampai Senin.
    data_tidak_lengkap = buat_data([
        "2026-11-16",
    ])

    mingguan = ke_mingguan(
        data_tidak_lengkap,
        hari_ini="2026-11-25"
    )

    try:
        periksa_data_mingguan(
            mingguan,
            hari_ini="2026-11-25"
        )

        raise AssertionError(
            "Data yang hanya sampai Senin seharusnya ditolak."
        )

    except RuntimeError as e:
        print("\nSkenario 2: Data hanya sampai Senin")
        print("LULUS: data ditolak.")
        print("Pesan:", e)

    # SKENARIO 3: Kamis dan Jumat tidak memiliki data.
    data_libur = buat_data([
        "2026-11-16",
        "2026-11-17",
        "2026-11-18",
    ])

    mingguan = ke_mingguan(
        data_libur,
        hari_ini="2026-11-21"
    )

    tanggal = periksa_data_mingguan(
        mingguan,
        hari_ini="2026-11-21"
    )

    assert str(tanggal) == "2026-11-20"

    print("\nSkenario 3: Observasi terakhir Rabu")
    print(mingguan.tail(1).to_string(index=False))
    print("LULUS: data diterima dalam toleransi 2 hari.")

    # SKENARIO 4: Hari ini masih Jumat.
    data_jumat = buat_data([
        "2026-11-09",
        "2026-11-10",
        "2026-11-11",
        "2026-11-12",
        "2026-11-13",
        "2026-11-16",
        "2026-11-17",
        "2026-11-18",
        "2026-11-19",
        "2026-11-20",
    ])

    mingguan = ke_mingguan(
        data_jumat,
        hari_ini="2026-11-20"
    )

    tanggal = periksa_data_mingguan(
        mingguan,
        hari_ini="2026-11-20"
    )

    assert str(tanggal) == "2026-11-13"

    print("\nSkenario 4: Hari ini masih Jumat")
    print("LULUS: minggu berjalan belum dimasukkan.")

    print("\nSemua pengujian validasi mingguan berhasil.")


if __name__ == "__main__":
    main()
