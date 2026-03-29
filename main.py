import tkinter as tk
from tkinter import messagebox
import pandas as pd


def tablo_hazirla():
    dosya = "kaba_kesif_yem_ornek.csv"
    df = pd.read_csv(dosya, encoding="utf-8")
    df.columns = df.columns.str.strip()

    for kolon in ["KM_%", "CP_%", "ME_kcal_kg"]:
        df[kolon] = pd.to_numeric(df[kolon], errors="coerce")

    df[["KM_%", "CP_%", "ME_kcal_kg"]] = df[["KM_%", "CP_%", "ME_kcal_kg"]].fillna(0)

    df["Yem_Adi"] = df["Yem_Adi"].astype(str).str.strip()

    df["KM_oran"] = df["KM_%"] / 100
    df["CP_oran"] = df["CP_%"] / 100

    df["KM_kg"] = df["KM_oran"]
    df["CP_kg"] = df["KM_oran"] * df["CP_oran"]
    df["ME"] = df["ME_kcal_kg"] * df["KM_oran"]
    return df


def ihtiyac_hesapla(hayvan_tipi, agirlik, sut=0, artis=0):
    """KM, ham protein (CP) ve metabolize enerji (ME) ihtiyaçları."""
    if hayvan_tipi == "sut":
        km_ihtiyac = agirlik * 0.03
        cp_ihtiyac = (agirlik * 0.0025) + (sut * 0.085)
        me_ihtiyac = (agirlik * 30) + (sut * 500)
    elif hayvan_tipi == "besi":
        km_ihtiyac = agirlik * 0.025
        cp_ihtiyac = (agirlik * 0.0020) + (artis * 0.50)
        me_ihtiyac = (agirlik * 25) + (artis * 4000)
    else:
        raise ValueError("Hayvan tipi 'sut' veya 'besi' olmalı.")

    return km_ihtiyac, cp_ihtiyac, me_ihtiyac


def secili_yem_getir(df, secili_yem):
    return df[df["Yem_Adi"].isin(secili_yem)].copy()


def puan_hesapla(df_secili, km_ihtiyac, cp_ihtiyac, me_ihtiyac):
    eps = 1e-9
    if km_ihtiyac > eps:
        hedef_cp_dm = cp_ihtiyac / km_ihtiyac
        hedef_me_dm = me_ihtiyac / km_ihtiyac
    else:
        hedef_cp_dm = 0.0
        hedef_me_dm = 0.0

    puanlar = []
    for _, satir in df_secili.iterrows():
        km = float(satir["KM_kg"])
        if km <= eps:
            puanlar.append(0.0)
            continue

        cp_dm = float(satir["CP_kg"]) / km
        me_dm = float(satir["ME"])

        if km_ihtiyac > eps and hedef_cp_dm > eps:
            cp_uyum = 1.0 / (1.0 + abs(cp_dm - hedef_cp_dm) / hedef_cp_dm)
        else:
            cp_uyum = 0.5

        if km_ihtiyac > eps and hedef_me_dm > eps:
            me_uyum = 1.0 / (1.0 + abs(me_dm - hedef_me_dm) / hedef_me_dm)
        else:
            me_uyum = 0.5

        puan = 0.2 * km + 0.4 * cp_uyum + 0.4 * me_uyum
        puanlar.append(puan)

    df_secili = df_secili.copy()
    df_secili["puan"] = puanlar
    return df_secili


def oranlari_hesapla(df_secili):
    toplam_puan = df_secili["puan"].sum()

    if toplam_puan == 0:
        df_secili["oran"] = 0
    else:
        df_secili["oran"] = df_secili["puan"] / toplam_puan

    return df_secili


def rasyon_hesapla(df_secili, km_ihtiyac):
    rasyon = {}

    for _, satir in df_secili.iterrows():
        oran = satir["oran"]
        km_kg = satir["KM_kg"]

        if km_kg <= 0:
            miktar = 0
        else:
            miktar = (km_ihtiyac * oran) / km_kg

        yem_adi = satir["Yem_Adi"]
        rasyon[yem_adi] = round(miktar, 2)

    return rasyon


def rasyon_olustur(df_secili, km_ihtiyac, cp_ihtiyac, me_ihtiyac):
    df_work = df_secili.copy()
    df_work = puan_hesapla(df_work, km_ihtiyac, cp_ihtiyac, me_ihtiyac)
    df_work = oranlari_hesapla(df_work)
    rasyon = rasyon_hesapla(df_work, km_ihtiyac)

    toplam_km = 0.0
    toplam_cp = 0.0
    toplam_enerji = 0.0
    for _, satir in df_work.iterrows():
        yem_adi = satir["Yem_Adi"]
        kg = rasyon.get(yem_adi, 0.0)
        km_kg = float(satir["KM_kg"])
        cp_kg = float(satir["CP_kg"])
        me_dm = float(satir["ME"])
        dm = kg * km_kg
        toplam_km += dm
        toplam_cp += kg * cp_kg
        toplam_enerji += dm * me_dm

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

        for entry in (self.agirlik_entry, self.sut_entry, self.artis_entry):
            entry.bind("<FocusOut>", self._giris_degisti_odak)

    def _giris_degisti_odak(self, event=None):
        # Checkbox tıklanınca önce FocusOut gelir; seçim henüz güncellenmemiş olabilir.
        self.after_idle(self._giris_sonrasi_sessiz_hesap)

    def _giris_sonrasi_sessiz_hesap(self):
        try:
            if not self.agirlik_entry.get().strip():
                return
            self.update_idletasks()
            if not any(var.get() for var in self.yem_vars.values()):
                return
            self.hesapla(sessiz=True)
        except Exception:
            pass

    def ust_frame_olustur(self):
        self.ust_frame = tk.LabelFrame(self, text="Hayvan Bilgileri", padx=10, pady=10)
        self.ust_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(self.ust_frame, text="Hayvan Tipi:").grid(row=0, column=0, padx=5, pady=5, sticky="e")

        self.hayvan_tipi_var = tk.StringVar(value="sut")

        tk.Radiobutton(self.ust_frame, text="Süt", variable=self.hayvan_tipi_var, value="sut",
                       command=self.giris_guncelle, ).grid(row=0, column=1, padx=5, pady=5)

        tk.Radiobutton(self.ust_frame, text="Besi", variable=self.hayvan_tipi_var, value="besi",
                       command=self.giris_guncelle, ).grid(row=0, column=2, padx=5, pady=5)

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
            self.artis_entry.config(state="normal")
            self.artis_entry.delete(0, tk.END)
            self.artis_label.grid_forget()
            self.artis_entry.grid_forget()
            self.artis_entry.config(state="disabled")
            self.sut_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
            self.sut_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
            self.sut_entry.config(state="normal")
        else:
            self.sut_entry.config(state="normal")
            self.sut_entry.delete(0, tk.END)
            self.sut_label.grid_forget()
            self.sut_entry.grid_forget()
            self.sut_entry.config(state="disabled")
            self.artis_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
            self.artis_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
            self.artis_entry.config(state="normal")

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
            width=20,
        )

    def yem_listesini_guncelle(self):
        for widget in self.orta_frame.winfo_children():
            if isinstance(widget, tk.Checkbutton):
                widget.destroy()

        self.yem_vars = {}

        secim = self.hayvan_tipi_var.get()
        tip_seri = self.df["Yem_Tipi"].astype(str).str.lower().str.strip()

        if secim == "sut":
            maske = tip_seri.str.contains("kaba|süt|sut|protein|kesif|enerji|besi", na=False)
        else:
            maske = tip_seri.str.contains("kaba|besi|protein|kesif|enerji", na=False)

        df_filtre = self.df[maske].copy()

        idx = 0
        for _, yem in enumerate(df_filtre["Yem_Adi"]):
            yem_etiket = str(yem).strip()
            if not yem_etiket or yem_etiket.lower() == "nan":
                continue
            var = tk.IntVar(master=self, value=0)
            chk = tk.Checkbutton(
                self.orta_frame,
                text=yem_etiket,
                variable=var,
                onvalue=1,
                offvalue=0,
            )
            chk.grid(row=idx // 3, column=idx % 3, padx=10, pady=4, sticky="w")
            self.yem_vars[yem_etiket] = var
            idx += 1

        satir_no = (idx - 1) // 3 + 2 if idx else 1
        self.hesapla_btn.grid(row=satir_no, column=0, padx=10, pady=10, sticky="w")

    def alt_frame_olustur(self):
        self.alt_frame = tk.LabelFrame(self, text="Sonuçlar", padx=10, pady=10)
        self.alt_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.sonuc_text = tk.Text(self.alt_frame, wrap="word")
        self.sonuc_text.pack(fill="both", expand=True)

    def hesapla(self, sessiz=False):
        try:
            self.update_idletasks()
            hayvan_tipi = self.hayvan_tipi_var.get()
            agirlik = float(self.agirlik_entry.get().strip().replace(",", ".") or 0)

            if hayvan_tipi == "sut":
                sut = float(self.sut_entry.get().strip().replace(",", ".") or 0)
                artis = 0
            else:
                artis = float(self.artis_entry.get().strip().replace(",", ".") or 0)
                sut = 0

            secilen_yemler = [yem for yem, var in self.yem_vars.items() if var.get()]

            if not secilen_yemler:
                if not sessiz:
                    messagebox.showwarning("Uyarı", "En az bir yem seç.")
                return

            df_secili = self.df[self.df["Yem_Adi"].isin(secilen_yemler)].copy()

            km_ihtiyac, cp_ihtiyac, me_ihtiyac = ihtiyac_hesapla(hayvan_tipi, agirlik, sut, artis)

            rasyon, toplam_km, toplam_cp, toplam_enerji = rasyon_olustur(
                df_secili, km_ihtiyac, cp_ihtiyac, me_ihtiyac
            )

            self.sonuc_text.delete("1.0", tk.END)
            self.sonuc_text.insert(tk.END, "=== HAYVAN İHTİYAÇLARI ===\n")
            self.sonuc_text.insert(tk.END, f"KM ihtiyacı: {km_ihtiyac:.2f} kg\n")
            self.sonuc_text.insert(tk.END, f"CP ihtiyacı: {cp_ihtiyac:.2f} kg\n")
            self.sonuc_text.insert(tk.END, f"ME ihtiyacı: {me_ihtiyac:.2f} kcal\n\n")

            self.sonuc_text.insert(tk.END, "=== ÖNERİLEN RASYON ===\n")
            if rasyon:
                for yem, kg in sorted(rasyon.items()):
                    self.sonuc_text.insert(tk.END, f"{yem}: {kg:.2f} kg\n")
            else:
                self.sonuc_text.insert(tk.END, "Uygun rasyon oluşturulamadı.\n")

            self.sonuc_text.insert(tk.END, "\n=== RASYON TOPLAMI ===\n")
            self.sonuc_text.insert(tk.END, f"Toplam KM: {toplam_km:.2f} kg\n")
            self.sonuc_text.insert(tk.END, f"Toplam CP: {toplam_cp:.2f} kg\n")
            self.sonuc_text.insert(tk.END, f"Toplam ME: {toplam_enerji:.2f} kcal\n")
            self.sonuc_text.insert(tk.END, "\n=== İHTİYAÇLA KARŞILAŞTIRMA ===\n")
            self.sonuc_text.insert(
                tk.END,
                f"CP: ihtiyaç {cp_ihtiyac:.2f} kg, rasyon {toplam_cp:.2f} kg\n",
            )
            self.sonuc_text.insert(
                tk.END,
                f"ME: ihtiyaç {me_ihtiyac:.2f} kcal, rasyon {toplam_enerji:.2f} kcal\n",
            )

        except ValueError:
            if not sessiz:
                messagebox.showerror("Hata", "Ağırlık, süt veya artış alanına geçerli sayı gir.")
        except Exception as e:
            if not sessiz:
                messagebox.showerror("Hata", str(e))


if __name__ == "__main__":
    df3 = tablo_hazirla()
    print(df3["Yem_Tipi"].unique())
    uygulama = App(df3)
    uygulama.mainloop()