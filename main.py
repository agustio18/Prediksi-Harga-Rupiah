"""
Titik masuk program prediksi USD/IDR (Fase 1).

Alur Fase 1:
ambil data historis dari Yahoo Finance -> validasi kualitas ->
simpan ke PostgreSQL -> tampilkan laporan pemeriksaan.

Jalankan dari folder utama proyek:  python main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    try:
        from scripts.tarik_data import main as tarik_data
        from scripts.periksa_data import main as periksa_data

        tarik_data()
        print()
        periksa_data()
    except RuntimeError as e:
        # Biasanya DATABASE_URL belum diisi di file .env
        print("Gagal:", e)
        sys.exit(1)
    except Exception as e:
        print(f"Terjadi kesalahan: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()