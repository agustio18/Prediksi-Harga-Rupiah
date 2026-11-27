import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion import validasi


KOLOM = ["tanggal", "open", "high", "low", "close"]


def _df(baris):
    return pd.DataFrame(baris, columns=KOLOM)


class TestValidasi(unittest.TestCase):

    def test_luar_rentang_jadi_periksa(self):
        df = _df([("2020-01-06", 14000, 14100, 13900, 60000)])
        hasil, _ = validasi(df)
        self.assertEqual(len(hasil), 1)
        self.assertEqual(hasil.iloc[0]["status"], "PERIKSA")

    def test_close_kosong_dibuang(self):
        df = _df([
            ("2020-01-06", 14000, 14100, 13900, None),
            ("2020-01-07", 14000, 14100, 13900, 14050),
        ])
        hasil, _ = validasi(df)
        self.assertEqual(len(hasil), 1)

    def test_tanggal_duplikat_dibuang(self):
        df = _df([
            ("2020-01-06", 14000, 14100, 13900, 14050),
            ("2020-01-06", 14010, 14110, 13910, 14100),
        ])
        hasil, _ = validasi(df)
        self.assertEqual(len(hasil), 1)

    def test_high_lebih_rendah_dari_low(self):
        df = _df([("2020-01-06", 14000, 13800, 13900, 14050)])
        hasil, _ = validasi(df)
        self.assertEqual(hasil.iloc[0]["status"], "PERIKSA")

    def test_perubahan_di_atas_3_persen(self):
        df = _df([
            ("2020-01-06", 14000, 14100, 13900, 14000),
            ("2020-01-07", 15000, 15100, 14900, 15000),
        ])
        hasil, _ = validasi(df)
        self.assertEqual(hasil.iloc[1]["status"], "PERIKSA")

    def test_jeda_lebih_7_hari(self):
        df = _df([
            ("2020-01-06", 14000, 14100, 13900, 14050),
            ("2020-01-20", 14000, 14100, 13900, 14050),
        ])
        hasil, _ = validasi(df)
        self.assertEqual(hasil.iloc[1]["status"], "PERIKSA")

    def test_valid_tetap_valid(self):
        df = _df([("2020-01-06", 14000, 14100, 13900, 14050)])
        hasil, _ = validasi(df)
        self.assertEqual(hasil.iloc[0]["status"], "VALID")


if __name__ == "__main__":
    unittest.main()