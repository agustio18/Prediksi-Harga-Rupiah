import pandas as pd

from config import HARGA_MAX, HARGA_MIN


def ambil_data_harian(ticker, mulai, akhir=None):
    import yfinance as yf

    data = yf.Ticker(ticker).history(
        start=mulai, end=akhir, interval="1d", auto_adjust=False
    )
    if data.empty:
        return pd.DataFrame(columns=["tanggal", "open", "high", "low", "close"])

    data = data.reset_index()
    data.columns = [str(kolom).lower() for kolom in data.columns]

    kolom_tanggal = "date" if "date" in data.columns else "datetime"
    data = data.rename(columns={kolom_tanggal: "tanggal"})
    data["tanggal"] = (
        pd.to_datetime(data["tanggal"]).dt.tz_localize(None).dt.normalize()
    )
    return data[["tanggal", "open", "high", "low", "close"]].copy()


def validasi(df):
    if df is None or df.empty:
        return df, []

    data = df.copy()

    # Memastikan tipe data benar
    data["tanggal"] = pd.to_datetime(
        data["tanggal"], errors="coerce"
    ).dt.normalize()

    for kolom in ["open", "high", "low", "close"]:
        data[kolom] = pd.to_numeric(
            data[kolom], errors="coerce"
        )

    catatan = []

    # 1. Buang tanggal dan Close kosong
    jumlah_awal = len(data)

    data = data.dropna(subset=["tanggal", "close"])

    jumlah_dibuang = jumlah_awal - len(data)

    if jumlah_dibuang > 0:
        catatan.append(
            f"DIBUANG {jumlah_dibuang} baris karena tanggal/Close kosong"
        )

    # 2. Buang Close di luar rentang harga
    harga_wajar = data["close"].between(
        HARGA_MIN, HARGA_MAX
    )

    jumlah_harga_aneh = (~harga_wajar).sum()

    if jumlah_harga_aneh > 0:
        catatan.append(
            f"DIBUANG {jumlah_harga_aneh} baris karena Close di luar rentang"
        )

    data = data[harga_wajar].copy()

    # 3. Urutkan tanggal dan hapus duplikat
    data = data.sort_values("tanggal")
    data = data.drop_duplicates("tanggal", keep="last")
    data = data.reset_index(drop=True)

    # Semua data dianggap VALID terlebih dahulu
    data["status"] = "VALID"

    def tandai_periksa(mask, alasan):
        mask = mask.fillna(False)

        data.loc[mask, "status"] = "PERIKSA"

        for i in data.index[mask]:
            tanggal = data.loc[i, "tanggal"].date()

            catatan.append(
                f"PERIKSA {alasan} pada {tanggal}"
            )

    # 4. Periksa kelengkapan OHLC
    ohlc_kosong = data[
        ["open", "high", "low", "close"]
    ].isna().any(axis=1)

    tandai_periksa(
        ohlc_kosong,
        "OHLC tidak lengkap"
    )

    # 5. Periksa High lebih rendah daripada Low
    high_low_aneh = (
        data["high"].notna()
        & data["low"].notna()
        & (data["high"] < data["low"])
    )

    tandai_periksa(
        high_low_aneh,
        "High lebih rendah dari Low"
    )

    # 6. Periksa Open di luar rentang Low-High
    open_aneh = (
        data["open"].notna()
        & data["low"].notna()
        & data["high"].notna()
        & (
            (data["open"] < data["low"])
            | (data["open"] > data["high"])
        )
    )

    tandai_periksa(
        open_aneh,
        "Open di luar rentang Low-High"
    )

    # 7. Periksa Close di luar rentang Low-High
    close_aneh = (
        data["close"].notna()
        & data["low"].notna()
        & data["high"].notna()
        & (
            (data["close"] < data["low"])
            | (data["close"] > data["high"])
        )
    )

    tandai_periksa(
        close_aneh,
        "Close di luar rentang Low-High"
    )

    # 8. Perubahan harga harian lebih dari 3%
    perubahan = data["close"].pct_change(fill_method=None) * 100

    perubahan_aneh = perubahan.abs() > 3

    for i in data.index[perubahan_aneh.fillna(False)]:
        data.loc[i, "status"] = "PERIKSA"

        tanggal = data.loc[i, "tanggal"].date()

        catatan.append(
            f"PERIKSA perubahan {perubahan.loc[i]:.2f}% pada {tanggal}"
        )

    # 9. Jarak antartanggal lebih dari 7 hari
    jarak = data["tanggal"].diff().dt.days

    celah_aneh = jarak > 7

    for i in data.index[celah_aneh.fillna(False)]:
        data.loc[i, "status"] = "PERIKSA"

        tanggal = data.loc[i, "tanggal"].date()

        catatan.append(
            f"PERIKSA celah {int(jarak.loc[i])} hari sebelum {tanggal}"
        )

    return data, catatan


def ke_mingguan(df, hari_ini=None):
    """
    Mengubah data harian menjadi mingguan W-FRI.

    Menyimpan tanggal observasi terakhir dan status
    pemeriksaan setiap kelompok minggu.
    """

    kolom_hasil = [
        "tanggal",
        "open",
        "high",
        "low",
        "close",
        "tanggal_data_terakhir",
        "status",
        "jumlah_periksa",
    ]

    if df is None or df.empty:
        return pd.DataFrame(columns=kolom_hasil)

    data = df.copy()

    # Memastikan tipe data dan urutan tanggal.
    data["tanggal"] = pd.to_datetime(
        data["tanggal"]
    ).dt.normalize()

    data = data.sort_values("tanggal").reset_index(drop=True)

    # Jika status tidak tersedia, anggap VALID.
    if "status" not in data.columns:
        data["status"] = "VALID"
    else:
        data["status"] = (
            data["status"]
            .fillna("VALID")
            .astype(str)
            .str.upper()
        )

    # Menentukan tanggal Jumat untuk setiap observasi.
    tambahan_hari = (
        4 - data["tanggal"].dt.weekday
    ) % 7

    data["tanggal_mingguan"] = (
        data["tanggal"]
        + pd.to_timedelta(tambahan_hari, unit="D")
    )

    # Menggabungkan data harian menjadi mingguan.
    mingguan = (
        data.groupby("tanggal_mingguan", as_index=False)
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            tanggal_data_terakhir=("tanggal", "last"),
            status=(
                "status",
                lambda nilai: (
                    "PERIKSA"
                    if (nilai == "PERIKSA").any()
                    else "VALID"
                )
            ),
            jumlah_periksa=(
                "status",
                lambda nilai: int(
                    (nilai == "PERIKSA").sum()
                )
            ),
        )
        .rename(columns={
            "tanggal_mingguan": "tanggal"
        })
    )

    # Menentukan Jumat terakhir yang sudah selesai.
    if hari_ini is None:
        hari_ini = pd.Timestamp.today().normalize()

    hari_ini = pd.Timestamp(hari_ini).normalize()

    jarak_hari = (hari_ini.weekday() - 4) % 7

    # Jika hari ini Jumat, Jumat hari ini belum selesai.
    if jarak_hari == 0:
        jarak_hari = 7

    jumat_terakhir = (
        hari_ini - pd.Timedelta(days=jarak_hari)
    )

    # Menghilangkan minggu yang belum selesai.
    mingguan = mingguan[
        mingguan["tanggal"] <= jumat_terakhir
    ].reset_index(drop=True)

    return mingguan
