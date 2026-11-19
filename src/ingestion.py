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
    data["tanggal"] = pd.to_datetime(data["tanggal"]).dt.normalize()

    #Buang tanggal/close kosong
    data = data.dropna(subset=["tanggal", "close"])

    #Buang close di luar rentang wajar
    data = data[(data["close"] >= HARGA_MIN) & (data["close"] <= HARGA_MAX)]

    #Duplikat tanggal ambil data terakhir
    data = data.sort_values("tanggal").drop_duplicates("tanggal", keep="last")
    data = data.reset_index(drop=True)

    catatan = []

    #Perubahan harga > 3%
    selisih = data["close"].pct_change() * 100
    for i in selisih[selisih.abs() > 3].index:
        tanggal = data.loc[i, "tanggal"].date()
        catatan.append(
            f"PERIKSA perubahan {selisih.loc[i]:.2f}% pada {tanggal}"
        )

    #Celah tanggal > 7 hari
    jarak = data["tanggal"].diff().dt.days
    for i in jarak[jarak > 7].index:
        tanggal = data.loc[i, "tanggal"].date()
        catatan.append(f"PERIKSA celah {int(jarak.loc[i])} hari sebelum {tanggal}")

    return data, catatan


def ke_mingguan(df, hari_ini=None):
    if df is None or df.empty:
        return pd.DataFrame(columns=["tanggal", "open", "high", "low", "close"])

    data = df.copy()
    data["tanggal"] = pd.to_datetime(data["tanggal"]).dt.normalize()
    data = data.set_index("tanggal")

    mingguan = data.resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}
    )
    mingguan = mingguan.dropna(subset=["close"])

    if hari_ini is None:
        hari_ini = pd.Timestamp.today().normalize()
    hari_ini = pd.Timestamp(hari_ini).normalize()

    if not mingguan.empty and mingguan.index[-1] >= hari_ini:
        mingguan = mingguan.iloc[:-1]

    return mingguan.reset_index()
