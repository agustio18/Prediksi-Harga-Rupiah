import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

PALET = {
    "bg": "#000000",
    "border_kotak": "#0b2cb1",
    "teks": "#ffffff",
    "tombol": "#3781fc",
    "border_tombol": "#03195b",
}
FONT = "Verdana"


def _kotak_tumpul(canvas, x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


class TombolTumpul(tk.Canvas):
    def __init__(self, parent, teks, perintah, lebar=155, tinggi=38):
        super().__init__(parent, width=lebar, height=tinggi, bg=parent["bg"], highlightthickness=0, cursor="hand2")
        self.teks, self.perintah = teks, perintah
        self._gambar()
        self.bind("<Button-1>", lambda e: self.perintah())

    def _gambar(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        r = h // 2
        fill, out = PALET["tombol"], PALET["border_tombol"]
        self.create_oval(1, 1, h - 1, h - 1, fill=fill, outline=out, width=2)
        self.create_oval(w - h + 1, 1, w - 1, h - 1, fill=fill, outline=out, width=2)
        self.create_rectangle(r, 1, w - r, h - 1, fill=fill, outline=fill)
        self.create_line(r, 1, w - r, 1, fill=out, width=2)
        self.create_line(r, h - 1, w - r, h - 1, fill=out, width=2)
        self.create_text(w // 2, h // 2, text=self.teks, fill=PALET["teks"], font=(FONT, 9, "bold"))


class KartuTumpul(tk.Canvas):
    def __init__(self, parent, judul, nilai, tinggi=76):
        super().__init__(parent, height=tinggi, bg=parent["bg"], highlightthickness=0)
        self.judul, self.nilai = judul, nilai
        self.bind("<Configure>", self._gambar)

    def set_nilai(self, nilai):
        self.nilai = nilai
        self._gambar()

    def _gambar(self, _=None):
        self.delete("all")
        w, h = max(self.winfo_width(), 120), int(self["height"])
        _kotak_tumpul(self, 2, 2, w - 2, h - 2, 16, fill=PALET["bg"], outline=PALET["border_kotak"], width=2)
        self.create_text(16, 22, text=self.judul, anchor="w", fill=PALET["teks"], font=(FONT, 8, "bold"))
        self.create_text(16, 48, text=self.nilai, anchor="w", fill=PALET["teks"], font=(FONT, 12, "bold"))


class DashboardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dashboard Prediksi USD/IDR")
        self.geometry("1060x700")
        self.configure(bg=PALET["bg"])

        nav = tk.Frame(self, bg=PALET["bg"], padx=16, pady=12)
        nav.pack(fill="x")
        for nama in ["Dashboard", "Riwayat Kurs", "Evaluasi Model"]:
            TombolTumpul(nav, nama, lambda n=nama: self.pindah(n), 155, 38).pack(side="left", padx=(0, 8))

        self.area = tk.Frame(self, bg=PALET["bg"], padx=16, pady=4)
        self.area.pack(fill="both", expand=True)
        self.halaman = {
            "Dashboard": self._buat_dashboard(self.area),
            "Riwayat Kurs": tk.Frame(self.area, bg=PALET["bg"]),
            "Evaluasi Model": tk.Frame(self.area, bg=PALET["bg"]),
        }
        self.pindah("Dashboard")

    def pindah(self, nama):
        for f in self.halaman.values():
            f.pack_forget()
        self.halaman[nama].pack(fill="both", expand=True)

    def _buat_dashboard(self, parent):
        f = tk.Frame(parent, bg=PALET["bg"])

        top = tk.Frame(f, bg=PALET["bg"])
        top.pack(fill="x", pady=(0, 12))
        tk.Label(top, text="Dashboard Prediksi USD/IDR", bg=PALET["bg"], fg=PALET["teks"], font=(FONT, 15, "bold")).pack(side="left")
        TombolTumpul(top, "Perbarui Data & Prediksi", self._aksi_perbarui, 205, 38).pack(side="right")

        g1 = tk.Frame(f, bg=PALET["bg"])
        g1.pack(fill="x", pady=(0, 10))
        for i in range(3):
            g1.columnconfigure(i, weight=1, uniform="a")
        self.k_kurs = KartuTumpul(g1, "Kurs Terakhir", "Rp 15.850,00")
        self.k_pred = KartuTumpul(g1, "Prediksi Minggu Depan", "Rp 15.910,00")
        self.k_ubah = KartuTumpul(g1, "Perubahan Diprediksi", "+0,38%")
        self.k_kurs.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.k_pred.grid(row=0, column=1, padx=6, sticky="ew")
        self.k_ubah.grid(row=0, column=2, padx=(6, 0), sticky="ew")

        g2 = tk.Frame(f, bg=PALET["bg"])
        g2.pack(fill="x", pady=(0, 12))
        for i in range(2):
            g2.columnconfigure(i, weight=1, uniform="b")
        self.k_model = KartuTumpul(g2, "Model SVR Aktif", "RBF  |  C=10, eps=0.1")
        self.k_status = KartuTumpul(g2, "Status Update", "Siap (Data Contoh)")
        self.k_model.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.k_status.grid(row=0, column=1, padx=(6, 0), sticky="ew")

        box = tk.Frame(f, bg=PALET["bg"], highlightbackground=PALET["border_kotak"], highlightthickness=2, padx=12, pady=10)
        box.pack(fill="both", expand=True)

        fig = Figure(figsize=(8, 3.5), dpi=100, facecolor=PALET["bg"])
        ax = fig.add_subplot(111, facecolor=PALET["bg"])
        x = ["W1", "W2", "W3", "W4", "W5", "W6", "Prediksi"]
        y = [15680, 15720, 15700, 15790, 15820, 15850, 15910]
        ax.plot(x[:-1], y[:-1], marker="o", lw=2.2, color=PALET["tombol"], label="Aktual")
        ax.plot(x[-2:], y[-2:], marker="o", lw=2.2, ls="--", color=PALET["teks"], label="Prediksi")
        ax.set_title("Perkembangan Kurs USD/IDR", color=PALET["teks"], fontsize=10, fontfamily=FONT)
        ax.tick_params(colors=PALET["teks"])
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontfamily(FONT)
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
        for s in ["bottom", "left"]:
            ax.spines[s].set_color(PALET["border_kotak"])
        ax.grid(True, ls=":", alpha=0.4, color=PALET["border_kotak"])
        ax.legend(facecolor=PALET["bg"], edgecolor=PALET["border_kotak"], labelcolor=PALET["teks"])
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=box)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        return f

    def _aksi_perbarui(self):
        self.k_status.set_nilai("Klik diterima — siap ke jalankan_siklus()")


if __name__ == "__main__":
    DashboardApp().mainloop()