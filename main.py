import tkinter as tk
from tkinter import messagebox
import pandas as pd


def tablo_hazirla(dosya="kaba_kesif_yem_ornek.csv"):
    df = pd.read_csv(dosya, encoding="utf-8")
    df.columns = df.columns.str.strip()

    for kolon in ["KM_%", "CP_%", "ME_kcal_kg"]:
        df[kolon] = pd.to_numeric(df[kolon], errors="coerce")

    df[["KM_%", "CP_%", "ME_kcal_kg"]] = df[["KM_%", "CP_%", "ME_kcal_kg"]].fillna(0)

    df["KM_oran"] = df["KM_%"] / 100
    df["CP_oran"] = df["CP_%"] / 100

    df["KM_kg"] = df["KM_oran"]
    df["CP_kg"] = df["KM_oran"] * df["CP_oran"]
    df["ME"] = df["ME_kcal_kg"]

    return df


def ihtiyac_hesapla(hayvan_tipi, agirlik, sut=0, artis=0):
    if hayvan_tipi == "sut":
        km_ihtiyac = agirlik * 0.03
        cp_ihtiyac = (agirlik * 0.0025) + (sut * 0.085)
        enerji_ihtiyac = (agirlik * 30) + (sut * 500)
    elif hayvan_tipi == "besi":
        km_ihtiyac = agirlik * 0.025
        cp_ihtiyac = (agirlik * 0.0020) + (artis * 0.50)
        enerji_ihtiyac = (agirlik * 25) + (artis * 4000)
    else:
        raise ValueError("Hayvan tipi 'sut' veya 'besi' olmalı.")

    return km_ihtiyac, cp_ihtiyac, enerji_ihtiyac


def yem_katkisi(satir, miktar):
    km = miktar * satir["KM_kg"]
    cp = miktar * satir["CP_kg"]
    enerji = miktar * satir["ME"]
    return km, cp, enerji


def maksimum_miktar_belirle(yem_tipi):
    tip = str(yem_tipi).lower()

    if "kaba" in tip:
        return 25.0
    elif "protein" in tip:
        return 5.0
    else:
        return 10.0


def adim_miktari_belirle(yem_tipi):
    tip = str(yem_tipi).lower()

    if "kaba" in tip:
        return 1.0
    elif "protein" in tip:
        return 0.25
    else:
        return 0.5


def yem_puani_hesapla(satir, km_acik, cp_acik, enerji_acik):
    km_katki = satir["KM_kg"]
    cp_katki = satir["CP_kg"]
    enerji_katki = satir["ME"]

    km_oran = max(km_acik, 0)
    cp_oran = max(cp_acik, 0)
    enerji_oran = max(enerji_acik, 0)

    toplam_acik = km_oran + cp_oran + enerji_oran
    if toplam_acik == 0:
        return 0

    km_agirlik = km_oran / toplam_acik
    cp_agirlik = cp_oran / toplam_acik
    enerji_agirlik = enerji_oran / toplam_acik

    enerji_normalize = enerji_katki / 1000

    puan = (
        km_katki * km_agirlik +
        cp_katki * cp_agirlik * 5 +
        enerji_normalize * enerji_agirlik
    )

    return puan


def akilli_rasyon(df_secili, km_ihtiyac, cp_ihtiyac, enerji_ihtiyac):
    rasyon = {}
    toplam_km = 0.0
    toplam_cp = 0.0
    toplam_enerji = 0.0

    if df_secili.empty:
        return rasyon, toplam_km, toplam_cp, toplam_enerji

    max_iter = 300

    for _ in range(max_iter):
        km_acik = max(0, km_ihtiyac - toplam_km)
        cp_acik = max(0, cp_ihtiyac - toplam_cp)
        enerji_acik = max(0, enerji_ihtiyac - toplam_enerji)

        if km_acik <= 0 and cp_acik <= 0 and enerji_acik <= 0:
            break

        en_iyi_index = None
        en_iyi_puan = -1

        for idx, satir in df_secili.iterrows():
            yem_adi = satir["Yem_Adi"]
            mevcut = rasyon.get(yem_adi, 0.0)
            max_miktar = maksimum_miktar_belirle(satir["Yem_Tipi"])

            if mevcut >= max_miktar:
                continue

            puan = yem_puani_hesapla(satir, km_acik, cp_acik, enerji_acik)

            if puan > en_iyi_puan:
                en_iyi_puan = puan
                en_iyi_index = idx

        if en_iyi_index is None:
            break

        secilen = df_secili.loc[en_iyi_index]
        yem_adi = secilen["Yem_Adi"]
        adim = adim_miktari_belirle(secilen["Yem_Tipi"])
        max_miktar = maksimum_miktar_belirle(secilen["Yem_Tipi"])
        mevcut = rasyon.get(yem_adi, 0.0)

        if mevcut + adim > max_miktar:
            adim = max_miktar - mevcut

        if adim <= 0:
            break

        km, cp, enerji = yem_katkisi(secilen, adim)

        rasyon[yem_adi] = mevcut + adim
        toplam_km += km
        toplam_cp += cp
        toplam_enerji += enerji

    return rasyon, toplam_km, toplam_cp, toplam_enerji


class App(tk.Tk):
    def __init__(self, df):
        super().__init__()

        self.df = df

        self.title("Rasyon Programı")
        self.geometry("1000x800")

        self.ust_frame_olustur()
        self.orta_frame_olustur()
        self.alt_frame_olustur()
        self.yem_listesini_guncelle()

    def ust_frame_olustur(self):
        self.ust_frame = tk.LabelFrame(self, text="Hayvan Bilgileri", padx=10, pady=10)
        self.ust_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(self.ust_frame, text="Hayvan Tipi:").grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.hayvan_tipi_var = tk.StringVar(value="sut")

        tk.Radiobutton(
            self.ust_frame, text="Süt",variable=self.hayvan_tipi_var, value="sut",command=self.giris_guncelle).grid(row=0, column=1, padx=5, pady=5)

        tk.Radiobutton(self.ust_frame, text="Besi",variable=self.hayvan_tipi_var, value="besi",command=self.giris_guncelle).grid(row=0, column=2, padx=5, pady=5)

        tk.Label(self.ust_frame, text="Canlı Ağırlık (kg):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.agirlik_entry = tk.Entry(self.ust_frame, width=15)
        self.agirlik_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        self.sut_label = tk.Label(self.ust_frame, text="Günlük Süt (L):")
        self.sut_entry = tk.Entry(self.ust_frame, width=15)

        self.artis_label = tk.Label(self.ust_frame, text="Günlük Artış (kg):")
        self.artis_entry = tk.Entry(self.ust_frame, width=15)

        self.giris_guncelle()

    def giris_guncelle(self):
        secim = self.hayvan_tipi_var.get()

        if secim == "sut":
            self.sut_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
            self.sut_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
            self.artis_label.grid_forget()
            self.artis_entry.grid_forget()
        else:
            self.artis_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
            self.artis_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
            self.sut_label.grid_forget()
            self.sut_entry.grid_forget()

        if hasattr(self, "orta_frame"):
            self.yem_listesini_guncelle()

    def orta_frame_olustur(self):
        self.orta_frame = tk.LabelFrame(self, text="Elindeki Yemler", padx=10, pady=10)
        self.orta_frame.pack(fill="x", padx=10, pady=10)

        self.yem_vars = {}

        self.hesapla_btn = tk.Button(
            self.orta_frame,
            text="Rasyon Hesapla",
            command=self.hesapla,
            width=20
        )

    def yem_listesini_guncelle(self):

        for widget in self.orta_frame.winfo_children():
            if isinstance(widget, tk.Checkbutton):
                widget.destroy()

        self.yem_vars = {}

        secim = self.hayvan_tipi_var.get()
        tip_seri = self.df["Yem_Tipi"].astype(str).str.lower().str.strip()

        if secim == "sut":
            maske = tip_seri.str.contains("kaba|süt|sut|protein|kesif|enerji", na=False)
        else:
            maske = tip_seri.str.contains("kaba|besi|protein|kesif|enerji", na=False)

        df_filtre = self.df[maske].copy()

        for i, yem in enumerate(df_filtre["Yem_Adi"]):
            var = tk.IntVar()
            chk = tk.Checkbutton(self.orta_frame, text=yem, variable=var)
            chk.grid(row=i // 3, column=i % 3, padx=10, pady=4, sticky="w")
            self.yem_vars[yem] = var

        satir_no = (len(df_filtre) - 1) // 3 + 2
        self.hesapla_btn.grid(row=satir_no, column=0, padx=10, pady=10, sticky="w")

    def alt_frame_olustur(self):
        self.alt_frame = tk.LabelFrame(self, text="Sonuçlar", padx=10, pady=10)
        self.alt_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.sonuc_text = tk.Text(self.alt_frame, wrap="word")
        self.sonuc_text.pack(fill="both", expand=True)

    def hesapla(self):
        try:
            hayvan_tipi = self.hayvan_tipi_var.get()
            agirlik = float(self.agirlik_entry.get())

            sut = float(self.sut_entry.get() or 0)
            artis = float(self.artis_entry.get() or 0)

            secilen_yemler = [yem for yem, var in self.yem_vars.items() if var.get() == 1]

            if not secilen_yemler:
                messagebox.showwarning("Uyarı", "En az bir yem seç.")
                return

            df_secili = self.df[self.df["Yem_Adi"].isin(secilen_yemler)].copy()

            km_ihtiyac, cp_ihtiyac, enerji_ihtiyac = ihtiyac_hesapla(
                hayvan_tipi, agirlik, sut, artis
            )

            rasyon, toplam_km, toplam_cp, toplam_enerji = akilli_rasyon(
                df_secili, km_ihtiyac, cp_ihtiyac, enerji_ihtiyac
            )

            self.sonuc_text.delete("1.0", tk.END)

            self.sonuc_text.insert(tk.END, "=== HAYVAN İHTİYAÇLARI ===\n")
            self.sonuc_text.insert(tk.END, f"KM ihtiyacı: {km_ihtiyac:.2f} kg\n")
            self.sonuc_text.insert(tk.END, f"CP ihtiyacı: {cp_ihtiyac:.2f} kg\n")
            self.sonuc_text.insert(tk.END, f"Enerji ihtiyacı: {enerji_ihtiyac:.2f} kcal\n\n")

            self.sonuc_text.insert(tk.END, "=== ÖNERİLEN RASYON ===\n")
            if rasyon:
                for yem, kg in sorted(rasyon.items()):
                    self.sonuc_text.insert(tk.END, f"{yem}: {kg:.2f} kg\n")
            else:
                self.sonuc_text.insert(tk.END, "Uygun rasyon oluşturulamadı.\n")

            self.sonuc_text.insert(tk.END, "\n=== RASYON TOPLAMI ===\n")
            self.sonuc_text.insert(tk.END, f"Toplam KM: {toplam_km:.2f} kg\n")
            self.sonuc_text.insert(tk.END, f"Toplam CP: {toplam_cp:.2f} kg\n")
            self.sonuc_text.insert(tk.END, f"Toplam Enerji: {toplam_enerji:.2f} kcal\n")

            self.sonuc_text.insert(tk.END, "\n=== FARK ===\n")
            self.sonuc_text.insert(tk.END, f"KM farkı: {toplam_km - km_ihtiyac:.2f}\n")
            self.sonuc_text.insert(tk.END, f"CP farkı: {toplam_cp - cp_ihtiyac:.2f}\n")
            self.sonuc_text.insert(tk.END, f"Enerji farkı: {toplam_enerji - enerji_ihtiyac:.2f}\n")

        except ValueError:
            messagebox.showerror("Hata", "Sayısal alanları doğru gir.")
        except Exception as e:
            messagebox.showerror("Hata", str(e))


if __name__ == "__main__":
    df3 = tablo_hazirla("kaba_kesif_yem_ornek.csv")
    print(df3["Yem_Tipi"].unique())
    uygulama = App(df3)
    uygulama.mainloop()
