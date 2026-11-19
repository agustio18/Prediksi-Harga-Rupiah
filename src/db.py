from datetime import date

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert

from config import BASE_DIR, DATABASE_URL

SCHEMA_FILE = BASE_DIR / "database" / "schema.sql"


def get_engine():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL belum diset. Salin .env.example menjadi .env."
        )
    return create_engine(DATABASE_URL, future=True)


def buat_tabel(engine):
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql))


def tanggal_terakhir(engine):
    with engine.connect() as conn:
        hasil = conn.execute(text("SELECT MAX(tanggal) FROM harga_harian")).scalar()
    return hasil


def simpan_harian(df, engine):
    if df is None or df.empty:
        return 0

    baris = []
    for row in df.itertuples(index=False):
        baris.append(
            {
                "tanggal": _ke_date(row.tanggal),
                "open": _angka(row.open),
                "high": _angka(row.high),
                "low": _angka(row.low),
                "close": _angka(row.close),
                "sumber": "yahoo",
            }
        )

    from sqlalchemy import MetaData, Table

    meta = MetaData()
    tabel = Table("harga_harian", meta, autoload_with=engine)
    stmt = insert(tabel).values(baris)
    stmt = stmt.on_conflict_do_update(
        index_elements=["tanggal"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "sumber": stmt.excluded.sumber,
            "diperbarui": text("NOW()"),
        },
    )

    with engine.begin() as conn:
        conn.execute(stmt)
    return len(baris)


def catat_log(engine, status, baris_baru=0, pesan=None, sumber="yahoo"):
  
    stmt = text(
        "INSERT INTO log_update (sumber, baris_baru, status, pesan) "
        "VALUES (:sumber, :baris_baru, :status, :pesan)"
    )
    with engine.begin() as conn:
        conn.execute(
            stmt,
            {
                "sumber": sumber,
                "baris_baru": baris_baru,
                "status": status,
                "pesan": pesan,
            },
        )


def _ke_date(nilai):
    if isinstance(nilai, date):
        return nilai
    return pd.Timestamp(nilai).date()


def _angka(nilai):
    if nilai is None or (isinstance(nilai, float) and pd.isna(nilai)):
        return None
    return float(nilai)
