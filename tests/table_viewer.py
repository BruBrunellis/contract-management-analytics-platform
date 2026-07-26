import pandas as pd

#Leitura da base
print("Rodando script table_viewer.py...")

df = pd.read_csv(
    r"C:\Users\bvbbr\OneDrive\Portfolio\Contract Management Platform\1.data\1.raw\CNPJs\RAW_CNPJ_K3241.K03200Y0.D60711.CSV",
    sep=";",
    encoding="latin1",
    header=None
)