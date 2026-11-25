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


def ambil_harian_tersimpan(engine):
    """
    Mengambil seluruh data harian dari PostgreSQL,
    termasuk status VALID dan PERIKSA.
    """

    query = text("""
        SELECT
            tanggal,
            open,
            high,
            low,
            close,
            status
        FROM harga_harian
        ORDER BY tanggal ASC
    """)

    with engine.connect() as conn:
        data = pd.read_sql_query(query, conn)

    if data.empty:
        return pd.DataFrame(
            columns=[
                "tanggal",
                "open",
                "high",
                "low",
                "close",
                "status",
            ]
        )

    data["tanggal"] = pd.to_datetime(data["tanggal"])

    kolom_harga = ["open", "high", "low", "close"]

    for kolom in kolom_harga:
        data[kolom] = pd.to_numeric(
            data[kolom],
            errors="coerce"
        )

    data["status"] = (
        data["status"]
        .fillna("VALID")
        .astype(str)
        .str.upper()
    )

    return data



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
                "status": getattr(row, "status", "VALID"),
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
            "status": stmt.excluded.status,
            "diperbarui": text("NOW()"),
        },
    )

    with engine.begin() as conn:
        conn.execute(stmt)

    return len(baris)



def catat_log(
    engine,
    status,
    baris_diproses=0,
    pesan=None,
    sumber="yahoo"
):
    stmt = text(
        "INSERT INTO log_update "
        "(sumber, baris_diproses, status, pesan) "
        "VALUES (:sumber, :baris_diproses, :status, :pesan)"
    )

    with engine.begin() as conn:
        conn.execute(
            stmt,
            {
                "sumber": sumber,
                "baris_diproses": baris_diproses,
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


def ambil_prediksi_belum_aktual(engine):
    """
    Mengambil seluruh prediksi yang belum memiliki harga aktual.
    """

    sql = text("""
        SELECT
            id,
            tanggal_acuan,
            tanggal_target,
            harga_acuan,
            return_persen,
            harga_prediksi,
            model_id
        FROM prediksi
        WHERE harga_aktual IS NULL
        ORDER BY tanggal_target ASC
    """)

    with engine.connect() as conn:
        data = pd.read_sql_query(sql, conn)

    return data


def cek_prediksi_ada(engine, tanggal_acuan, model_id):
    """
    Memeriksa apakah prediksi untuk tanggal acuan dan model
    tertentu sudah pernah disimpan.
    """

    sql = text("""
        SELECT EXISTS (
            SELECT 1
            FROM prediksi
            WHERE tanggal_acuan = :tanggal_acuan
              AND model_id = :model_id
        )
    """)

    with engine.connect() as conn:
        hasil = conn.execute(sql, {
            "tanggal_acuan": _ke_date(tanggal_acuan),
            "model_id": model_id,
        }).scalar()

    return bool(hasil)


def simpan_prediksi(
    engine,
    tanggal_acuan,
    tanggal_target,
    harga_acuan,
    return_persen,
    harga_prediksi,
    model_id
):
    """
    Menyimpan prediksi baru.

    Jika prediksi dengan tanggal acuan dan model yang sama
    sudah ada, data tidak akan dimasukkan kembali.

    Mengembalikan ID jika berhasil, atau None jika duplikat.
    """

    sql = text("""
        INSERT INTO prediksi (
            tanggal_acuan,
            tanggal_target,
            harga_acuan,
            return_persen,
            harga_prediksi,
            model_id
        )
        VALUES (
            :tanggal_acuan,
            :tanggal_target,
            :harga_acuan,
            :return_persen,
            :harga_prediksi,
            :model_id
        )
        ON CONFLICT (tanggal_acuan, model_id)
        DO NOTHING
        RETURNING id
    """)

    with engine.begin() as conn:
        hasil = conn.execute(sql, {
            "tanggal_acuan": _ke_date(tanggal_acuan),
            "tanggal_target": _ke_date(tanggal_target),
            "harga_acuan": float(harga_acuan),
            "return_persen": float(return_persen),
            "harga_prediksi": float(harga_prediksi),
            "model_id": model_id,
        }).scalar()

    return int(hasil) if hasil is not None else None


def perbarui_prediksi(engine, prediksi_id, harga_aktual):
    """
    Memperbarui prediksi lama setelah harga aktual tersedia.

    Menghitung:
    - Selisih harga aktual dengan prediksi.
    - Persentase galat absolut.
    - Kebenaran arah pergerakan.
    """

    harga_aktual = float(harga_aktual)

    if harga_aktual <= 0:
        raise ValueError("Harga aktual harus lebih besar dari 0.")

    sql = text("""
        SELECT
            harga_acuan,
            harga_prediksi,
            harga_aktual
        FROM prediksi
        WHERE id = :prediksi_id
    """)

    with engine.begin() as conn:

        data = conn.execute(sql, {
            "prediksi_id": prediksi_id
        }).mappings().first()

        if data is None:
            raise ValueError(
                f"Prediksi dengan ID {prediksi_id} tidak ditemukan."
            )

        if data["harga_aktual"] is not None:
            return False

        harga_acuan = float(data["harga_acuan"])
        harga_prediksi = float(data["harga_prediksi"])

        # Selisih bertanda: aktual dikurangi prediksi.
        selisih = harga_aktual - harga_prediksi

        # Persentase galat absolut.
        galat_persen = (
            abs(selisih) / harga_aktual
        ) * 100

        # Membandingkan arah perubahan terhadap harga acuan.
        arah_prediksi = (
            harga_prediksi > harga_acuan
        ) - (
            harga_prediksi < harga_acuan
        )

        arah_aktual = (
            harga_aktual > harga_acuan
        ) - (
            harga_aktual < harga_acuan
        )

        arah_benar = arah_prediksi == arah_aktual

        update = text("""
            UPDATE prediksi
            SET
                harga_aktual = :harga_aktual,
                selisih = :selisih,
                galat_persen = :galat_persen,
                arah_benar = :arah_benar
            WHERE id = :prediksi_id
              AND harga_aktual IS NULL
        """)

        hasil = conn.execute(update, {
            "harga_aktual": harga_aktual,
            "selisih": selisih,
            "galat_persen": galat_persen,
            "arah_benar": arah_benar,
            "prediksi_id": prediksi_id,
        })

        return hasil.rowcount == 1
