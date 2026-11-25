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



def periksa_data_mingguan(
    mingguan,
    hari_ini=None,
    toleransi_hari=2
):
    """
    Memeriksa kelengkapan data mingguan dan memberikan
    peringatan jika terdapat data berstatus PERIKSA.

    Data PERIKSA tidak dibuang dan tidak otomatis
    menghentikan proses prediksi.
    """

    if mingguan is None or mingguan.empty:
        raise ValueError(
            "Data mingguan tidak tersedia."
        )

    kolom_wajib = [
        "tanggal",
        "tanggal_data_terakhir",
        "status",
        "jumlah_periksa",
    ]

    for kolom in kolom_wajib:
        if kolom not in mingguan.columns:
            raise ValueError(
                f"Kolom {kolom} tidak tersedia pada data mingguan."
            )

    data = mingguan.sort_values(
        "tanggal"
    ).reset_index(drop=True)

    if hari_ini is None:
        hari_ini = pd.Timestamp.now().normalize()

    hari_ini = pd.Timestamp(hari_ini).normalize()

    # Menentukan Jumat terakhir yang sudah selesai.
    jarak_hari = (hari_ini.weekday() - 4) % 7

    if jarak_hari == 0:
        jarak_hari = 7

    jumat_terakhir = (
        hari_ini - pd.Timedelta(days=jarak_hari)
    ).normalize()

    baris_terakhir = data.iloc[-1]

    tanggal_mingguan = pd.Timestamp(
        baris_terakhir["tanggal"]
    ).normalize()

    tanggal_observasi = pd.Timestamp(
        baris_terakhir["tanggal_data_terakhir"]
    ).normalize()

    # Memastikan label minggu sesuai Jumat terakhir.
    if tanggal_mingguan != jumat_terakhir:
        raise RuntimeError(
            "Data mingguan belum mencapai Jumat terakhir "
            f"yang seharusnya ({jumat_terakhir.date()}). "
            f"Data terakhir tersedia: {tanggal_mingguan.date()}. "
            "Prediksi baru tidak dibuat."
        )

    # Observasi tidak boleh melewati batas minggu.
    if tanggal_observasi > tanggal_mingguan:
        raise RuntimeError(
            "Tanggal observasi terakhir melewati batas minggu."
        )

    # Memeriksa jarak observasi terhadap Jumat.
    selisih_hari = (
        tanggal_mingguan - tanggal_observasi
    ).days

    if selisih_hari > toleransi_hari:
        raise RuntimeError(
            "Data mingguan terindikasi belum lengkap atau kedaluwarsa. "
            f"Jumat terakhir: {tanggal_mingguan.date()}, "
            f"observasi terakhir: {tanggal_observasi.date()}, "
            f"selisih: {selisih_hari} hari. "
            "Prediksi baru tidak dibuat."
        )

    # Menghitung total data harian berstatus PERIKSA.
    total_periksa = int(data["jumlah_periksa"].sum())

    # Memeriksa apakah minggu terakhir memiliki data PERIKSA.
    status_terakhir = baris_terakhir["status"]
    periksa_minggu_terakhir = int(
        baris_terakhir["jumlah_periksa"]
    )

    print(
        "Observasi terakhir minggu tersebut:",
        tanggal_observasi.date()
    )

    print(
        "Total data harian PERIKSA pada data mingguan:",
        total_periksa
    )

    if periksa_minggu_terakhir > 0:
        print(
            "PERINGATAN: Minggu terakhir memiliki",
            periksa_minggu_terakhir,
            "data harian berstatus PERIKSA."
        )

    if total_periksa > 0 and periksa_minggu_terakhir == 0:
        print(
            "PERINGATAN: Terdapat data PERIKSA pada minggu-minggu "
            "sebelumnya."
        )

    return tanggal_mingguan.date()



# ============================================================
# 2. MEMPERBARUI PREDIKSI SEBELUMNYA
# ============================================================


def perbarui_prediksi_lama(
    engine,
    mingguan,
    prediksi_ids=None
):
    """
    Memperbarui prediksi yang harga aktualnya sudah tersedia.

    prediksi_ids:
        None  -> memperbarui seluruh prediksi yang belum aktual.
        List  -> hanya memperbarui prediksi dengan ID tertentu.
    """

    prediksi_lama = ambil_prediksi_belum_aktual(engine)

    # Membatasi data yang diperbarui jika ID diberikan.
    if prediksi_ids is not None:
        prediksi_lama = prediksi_lama[
            prediksi_lama["id"].isin(prediksi_ids)
        ].copy()

    if prediksi_lama.empty:
        print("Tidak ada prediksi lama yang perlu diperbarui.")
        return 0

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

        # Menggunakan tanggal akhir eksplisit.
        # Parameter end pada yfinance bersifat eksklusif.
        akhir = (
            pd.Timestamp.now().normalize()
            + pd.Timedelta(days=1)
        ).date()

        print(
            f"Mengambil data {TICKER} "
            f"sejak {mulai} sampai sebelum {akhir}..."
        )

        data_yahoo = ambil_data_harian(
            TICKER,
            mulai=mulai,
            akhir=akhir
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
