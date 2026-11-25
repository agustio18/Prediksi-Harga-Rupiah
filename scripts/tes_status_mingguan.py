
import pandas as pd

from src.ingestion import ke_mingguan


def main():
    print("=== PENGUJIAN STATUS DATA MINGGUAN ===")

    data = pd.DataFrame({
        "tanggal": pd.to_datetime([
            "2026-11-16",
            "2026-11-17",
            "2026-11-18",
            "2026-11-19",
            "2026-11-20",
        ]),
        "open": [17000, 17010, 17020, 17030, 17040],
        "high": [17020, 17030, 17040, 17050, 17060],
        "low": [16980, 16990, 17000, 17010, 17020],
        "close": [17010, 17020, 17030, 17040, 17050],
        "status": [
            "VALID",
            "PERIKSA",
            "VALID",
            "PERIKSA",
            "VALID",
        ],
    })

    mingguan = ke_mingguan(
        data,
        hari_ini="2026-11-21"
    )

    print("\nHasil agregasi:")
    print(mingguan.to_string(index=False))

    baris = mingguan.iloc[-1]

    assert baris["status"] == "PERIKSA"
    assert baris["jumlah_periksa"] == 2
    assert str(baris["tanggal_data_terakhir"].date()) == "2026-11-20"

    print("\nLULUS: Status PERIKSA berhasil dibawa ke data mingguan.")
    print("LULUS: Jumlah data PERIKSA berhasil dihitung.")
    print("\nSemua pengujian berhasil.")


if __name__ == "__main__":
    main()
