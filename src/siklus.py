import pandas as pd

from config import TICKER, TANGGAL_MULAI

from src.db import (
    get_engine,
    buat_tabel,
    tanggal_terakhir,
    ambil_harian_tersimpan,
    simpan_harian,
    catat_log,
    ambil_prediksi_belum_aktual,
    cek_prediksi_ada,
    simpan_prediksi,
    perbarui_prediksi,
)

from src.ingestion import (
    ambil_data_harian,
    validasi,
    ke_mingguan,
)

from src.features import (
    hitung_fitur,
    KOLOM_FITUR,
)

from src.model import (
    ambil_model_aktif,
    muat_model,
    prediksi_return,
    konversi_ke_harga,
)


# ============================================================
# 1. MEMERIKSA KELENGKAPAN DATA MINGGUAN
# ============================================================

def periksa_data_mingguan(mingguan):
    """
    Memastikan data mingguan terakhir merupakan
    data dari Jumat terakhir yang sudah selesai.
    """

    if mingguan is None or mingguan.empty:
        raise ValueError(
            "Data mingguan tidak tersedia."
        )

    hari_ini = pd.Timestamp.now().normalize()

    # Mencari Jumat terakhir yang sudah selesai.
    jarak_hari = (hari_ini.weekday() - 4) % 7

    if jarak_hari == 0:
        jarak_hari = 7

    jumat_terakhir = (
        hari_ini - pd.Timedelta(days=jarak_hari)
    ).date()

    tanggal_data = pd.Timestamp(
        mingguan.iloc[-1]["tanggal"]
    ).date()

    if tanggal_data != jumat_terakhir:
        raise RuntimeError(
            "Data mingguan belum mencapai Jumat terakhir "
            f"yang seharusnya ({jumat_terakhir}). "
            f"Data terakhir tersedia: {tanggal_data}. "
            "Prediksi baru tidak dibuat."
        )

    return tanggal_data


# ============================================================
# 2. MEMPERBARUI PREDIKSI SEBELUMNYA
# ============================================================

def perbarui_prediksi_lama(engine, mingguan):
    """
    Mengambil prediksi yang belum memiliki harga aktual,
    kemudian memperbaruinya jika data aktual sudah tersedia.
    """

    prediksi_lama = ambil_prediksi_belum_aktual(engine)

    if prediksi_lama.empty:
        print("Tidak ada prediksi lama yang perlu diperbarui.")
        return 0

    # Membuat data harga aktual berdasarkan tanggal mingguan.
    data_aktual = mingguan.copy()

    data_aktual["tanggal"] = pd.to_datetime(
        data_aktual["tanggal"]
    ).dt.normalize()

    data_aktual = data_aktual.set_index("tanggal")

    jumlah_diperbarui = 0

    for row in prediksi_lama.itertuples(index=False):

        tanggal_target = pd.Timestamp(
            row.tanggal_target
        ).normalize()

        # Lewati jika harga aktual belum tersedia.
        if tanggal_target not in data_aktual.index:
            continue

        harga_aktual = float(
            data_aktual.loc[tanggal_target, "close"]
        )

        berhasil = perbarui_prediksi(
            engine,
            row.id,
            harga_aktual
        )

        if berhasil:
            jumlah_diperbarui += 1

            print(
                f"Prediksi ID {row.id} berhasil diperbarui."
            )

    return jumlah_diperbarui


# ============================================================
# 3. MEMBUAT PREDIKSI BARU
# ============================================================

def buat_prediksi_baru(engine, mingguan):
    """
    Membuat prediksi return dan harga kurs
    menggunakan model SVR yang aktif.
    """

    # Mengambil model aktif dari PostgreSQL.
    model_info = ambil_model_aktif(engine)

    if model_info is None:
        raise RuntimeError(
            "Tidak ada model SVR aktif di database. "
            "Silakan latih model terlebih dahulu."
        )

    # Memastikan nama file model tersedia.
    nama_file = model_info["file_model"]

    if not nama_file:
        raise RuntimeError(
            "Informasi file model tidak tersedia di database."
        )

    # Memuat model .joblib.
    isi_model = muat_model(nama_file)

    model = isi_model["pipeline"]

    # Menghitung lima fitur teknikal.
    dataset_fitur = hitung_fitur(mingguan)

    if dataset_fitur.empty:
        raise ValueError(
            "Dataset fitur tidak tersedia."
        )

    # Menggunakan baris terakhir, bukan baris lama
    # yang kebetulan masih memiliki fitur lengkap.
    data_terbaru = dataset_fitur.iloc[-1]

    # Memastikan semua fitur terbaru tersedia.
    if data_terbaru[KOLOM_FITUR].isna().any():
        raise ValueError(
            "Fitur terbaru belum lengkap. "
            "Prediksi tidak dapat dibuat."
        )

    X_prediksi = dataset_fitur[
        KOLOM_FITUR
    ].iloc[[-1]]

    tanggal_acuan = pd.Timestamp(
        data_terbaru["tanggal"]
    ).date()

    harga_acuan = float(
        data_terbaru["close"]
    )

    # Target prediksi adalah Jumat minggu berikutnya.
    tanggal_target = (
        pd.Timestamp(tanggal_acuan)
        + pd.Timedelta(days=7)
    ).date()

    model_id = model_info["id"]

    # Memeriksa apakah prediksi sudah pernah dibuat.
    if cek_prediksi_ada(
        engine,
        tanggal_acuan,
        model_id
    ):
        print(
            "Prediksi sudah tersedia. "
            "Tidak membuat prediksi ganda."
        )

        return None

    # Menghitung prediksi return.
    hasil_return = prediksi_return(
        model,
        X_prediksi
    )

    # Mengubah return menjadi perkiraan harga.
    harga_prediksi = konversi_ke_harga(
        hasil_return,
        harga_acuan
    )

    # Menyimpan prediksi ke PostgreSQL.
    prediksi_id = simpan_prediksi(
        engine=engine,
        tanggal_acuan=tanggal_acuan,
        tanggal_target=tanggal_target,
        harga_acuan=harga_acuan,
        return_persen=hasil_return,
        harga_prediksi=harga_prediksi,
        model_id=model_id
    )

    if prediksi_id is None:
        print(
            "Prediksi tidak disimpan karena terdeteksi duplikat."
        )

        return None

    print("\n=== PREDIKSI BARU ===")
    print("ID prediksi:", prediksi_id)
    print("Model ID:", model_id)
    print("Tanggal acuan:", tanggal_acuan)
    print("Tanggal target:", tanggal_target)
    print(f"Harga acuan: Rp {harga_acuan:,.2f}")
    print(f"Prediksi return: {hasil_return:.6f}%")
    print(f"Harga prediksi: Rp {harga_prediksi:,.2f}")

    return prediksi_id


# ============================================================
# 4. MENJALANKAN SELURUH SIKLUS
# ============================================================

def jalankan_siklus():
    """
    Mengatur proses pengambilan data,
    pembaruan prediksi lama, dan prediksi baru.
    """

    engine = get_engine()

    jumlah_data = 0
    jumlah_update = 0
    prediksi_id = None

    try:
        print("=== MEMULAI SIKLUS PREDIKSI ===")

        # Memastikan tabel tersedia.
        buat_tabel(engine)

        # ----------------------------------------------------
        # A. MENGAMBIL DATA TERBARU DARI YAHOO FINANCE
        # ----------------------------------------------------

        terakhir = tanggal_terakhir(engine)

        if terakhir is None:
            mulai = TANGGAL_MULAI
        else:
            mulai = (
                pd.Timestamp(terakhir)
                - pd.Timedelta(days=14)
            ).date()

        print(
            f"Mengambil data {TICKER} sejak {mulai}..."
        )

        data_yahoo = ambil_data_harian(
            TICKER,
            mulai=mulai
        )

        # Tidak menggunakan data lama jika Yahoo gagal.
        if data_yahoo is None or data_yahoo.empty:
            raise RuntimeError(
                "Yahoo Finance tidak mengembalikan data. "
                "Prediksi baru tidak dibuat."
            )

        # ----------------------------------------------------
        # B. VALIDASI DATA
        # ----------------------------------------------------

        data_bersih, catatan = validasi(data_yahoo)

        if data_bersih is None or data_bersih.empty:
            raise RuntimeError(
                "Tidak ada data valid dari Yahoo Finance."
            )

        # ----------------------------------------------------
        # C. MENYIMPAN DATA HARIAN
        # ----------------------------------------------------

        jumlah_data = simpan_harian(
            data_bersih,
            engine
        )

        print(
            "Jumlah baris data yang diproses:",
            jumlah_data
        )

        # ----------------------------------------------------
        # D. MENGAMBIL DATA HISTORIS DARI DATABASE
        # ----------------------------------------------------

        harian = ambil_harian_tersimpan(engine)

        if harian.empty:
            raise RuntimeError(
                "Data historis di database masih kosong."
            )

        # Mengubah data harian menjadi mingguan.
        mingguan = ke_mingguan(harian)

        # Memastikan data mingguan sudah lengkap
        # dan bukan data yang kedaluwarsa.
        tanggal_terakhir_mingguan = periksa_data_mingguan(
            mingguan
        )

        print(
            "Data mingguan terakhir:",
            tanggal_terakhir_mingguan
        )

        # ----------------------------------------------------
        # E. MEMPERBARUI PREDIKSI SEBELUMNYA
        # ----------------------------------------------------

        jumlah_update = perbarui_prediksi_lama(
            engine,
            mingguan
        )

        print(
            "Jumlah prediksi lama diperbarui:",
            jumlah_update
        )

        # ----------------------------------------------------
        # F. MEMBUAT PREDIKSI BARU
        # ----------------------------------------------------

        prediksi_id = buat_prediksi_baru(
            engine,
            mingguan
        )

        # ----------------------------------------------------
        # G. MENCATAT KEBERHASILAN SIKLUS
        # ----------------------------------------------------

        pesan = (
            f"Siklus berhasil. "
            f"Data harian diproses: {jumlah_data}. "
            f"Prediksi lama diperbarui: {jumlah_update}. "
            f"ID prediksi baru: {prediksi_id}."
        )

        if catatan:
            pesan += (
                " Catatan validasi: "
                + "; ".join(catatan)
            )

        catat_log(
            engine,
            status="SUKSES",
            baris_diproses=jumlah_data,
            pesan=pesan,
            sumber="siklus"
        )

        print("\n=== SIKLUS BERHASIL ===")

        return {
            "status": "SUKSES",
            "data_diproses": jumlah_data,
            "prediksi_diperbarui": jumlah_update,
            "prediksi_baru": prediksi_id,
        }

    except Exception as e:

        # Mencatat kegagalan tanpa menghapus data lama.
        try:
            catat_log(
                engine,
                status="GAGAL",
                baris_diproses=jumlah_data,
                pesan=str(e),
                sumber="siklus"
            )

        except Exception as error_log:
            print(
                "Gagal mencatat log:",
                error_log
            )

        print("\n=== SIKLUS GAGAL ===")
        print("Penyebab:", e)

        raise

    finally:
        engine.dispose()


# ============================================================
# 5. MENJALANKAN FILE SECARA LANGSUNG
# ============================================================

if __name__ == "__main__":
    jalankan_siklus()
