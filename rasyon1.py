import  tkinter as tk
from tkinter import messagebox
import pandas as pd





dosya="kaba_kesif_yem_ornek.csv"
df=pd.read_csv(dosya, encoding="utf-8")
print(df)
