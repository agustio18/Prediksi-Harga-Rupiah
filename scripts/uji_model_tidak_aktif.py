
from unittest.mock import patch

import pandas as pd

from src.siklus import buat_prediksi_baru


def uji_model_tidak_aktif():
    print("=== UJI MODEL TIDAK AKTIF ===")

    # Simulasi kondisi tidak ada model aktif.
    with patch(
        "src.siklus.ambil_model_aktif",
        return_value=None
    ) as mock_model:

        try:
            # Tidak memerlukan koneksi database karena
            # fungsi seharusnya berhenti sebelum mengaksesnya.
            buat_prediksi_baru(
                engine=None,
                mingguan=pd.DataFrame()
            )

        except RuntimeError as error:

            pesan = str(error)

            pesan_diharapkan = (
                "Tidak ada model SVR aktif di database."
            )

            if pesan_diharapkan not in pesan:
                raise AssertionError(
                    f"Pesan error tidak sesuai: {pesan}"
                ) from error

            print("Pesan kesalahan:", pesan)
            print("\nPENGUJIAN BERHASIL")
            print(
                "Sistem menolak prediksi karena "
                "model aktif tidak tersedia."
            )

        else:
            raise AssertionError(
                "Sistem seharusnya menolak prediksi "
                "ketika model aktif tidak tersedia."
            )

        assert mock_model.call_count == 1

    print("\nTidak ada perubahan pada database.")
    print("Semua pengujian berhasil.")


if __name__ == "__main__":
    uji_model_tidak_aktif()
