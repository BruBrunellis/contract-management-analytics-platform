"""Gera avaliações anuais de risco e homologação para fornecedores fictícios."""

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from dateutil.relativedelta import relativedelta

RAW_DIR = Path(__file__).resolve().parents[2] / "1.data" / "1.raw"
ANOS_AVALIACAO = range(2022, 2027)
TIMEZONE = ZoneInfo("America/Sao_Paulo")


def localizar_arquivo_empresas():
    arquivos = sorted(RAW_DIR.glob("empresas_*.csv"))
    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo versionado de empresas foi encontrado.")
    return arquivos[-1]


def classificar_risco_financeiro(juros_sobre_receita, tendencia_faturamento, margem_liquida, cenario):
    pontos = 0
    pontos += 2 if juros_sobre_receita >= 0.045 else 1 if juros_sobre_receita >= 0.025 else 0
    pontos += 2 if tendencia_faturamento <= -0.08 else 1 if tendencia_faturamento <= 0 else 0
    pontos += 2 if margem_liquida <= 0.03 else 1 if margem_liquida <= 0.08 else 0
    pontos += 1 if cenario == "Em decadência" else 0
    return "Alto" if pontos >= 4 else "Médio" if pontos >= 2 else "Baixo", pontos


def classificar_risco_trabalhista(processos_por_100_funcionarios):
    if processos_por_100_funcionarios > 8:
        return "Alto", 3
    if processos_por_100_funcionarios > 3:
        return "Médio", 2
    return "Baixo", 1


def definir_rating(pontos_financeiros):
    ratings = {0: "AAA", 1: "AA", 2: "A", 3: "BBB", 4: "BB", 5: "B", 6: "CCC", 7: "CC"}
    return ratings.get(min(pontos_financeiros, 7), "D")


def maior_risco(risco_financeiro, risco_trabalhista):
    ordem = {"Baixo": 1, "Médio": 2, "Alto": 3}
    return max((risco_financeiro, risco_trabalhista), key=ordem.get)


def gerar_homologacoes_risco(df_empresas, data_referencia=None):
    """Cria uma avaliação anual por empresa, usando os indicadores daquele ano."""
    data_referencia = data_referencia or datetime.now(TIMEZONE).date()
    registros = []
    identificador = 1
    for _, empresa in df_empresas.iterrows():
        for ano in ANOS_AVALIACAO:
            faturamento = float(empresa[f"Faturamento_{ano}"])
            juros = float(empresa[f"Juros_Divida_{ano}"])
            lucro_liquido = float(empresa[f"Lucro_Liquido_{ano}"])
            faturamento_anterior = float(empresa.get(f"Faturamento_{ano - 1}", faturamento))
            tendencia = 0.0 if ano == 2022 else faturamento / faturamento_anterior - 1
            juros_sobre_receita = juros / faturamento
            margem_liquida = lucro_liquido / faturamento
            processos_por_100 = float(empresa["Processos_Trabalhistas"]) / max(float(empresa["Num_Total_Func"]), 1) * 100
            risco_financeiro, pontos_financeiros = classificar_risco_financeiro(
                juros_sobre_receita, tendencia, margem_liquida, empresa["Cenario_Financeiro"]
            )
            risco_trabalhista, _ = classificar_risco_trabalhista(processos_por_100)
            risco_final = maior_risco(risco_financeiro, risco_trabalhista)
            data_avaliacao = date(ano, 1, 1)
            aprovado = risco_final != "Alto"
            data_expiracao = data_avaliacao + relativedelta(years=4) - timedelta(days=1) if aprovado else pd.NaT
            status = "Negada" if not aprovado else "Expirada" if data_expiracao < data_referencia else "Ativa"
            registros.append({
                "Id_Avaliacao_Risco": f"RSK{identificador:09d}",
                "CNPJ": empresa["CNPJ"],
                "Data_Avaliacao": data_avaliacao.isoformat(),
                "Data_Ultima_Homologacao": data_avaliacao.isoformat() if aprovado else "",
                "Data_Expiracao": data_expiracao.isoformat() if aprovado else "",
                "Resultado_Homologacao": "Aprovada" if aprovado else "Reprovada",
                "Status_Homologacao": status,
                "Risco_Financeiro": risco_financeiro,
                "Risco_Trabalhista": risco_trabalhista,
                "Rating_Credito": definir_rating(pontos_financeiros),
                "Risco_Final": risco_final,
                "Indice_Juros_Sobre_Receita": round(juros_sobre_receita, 4),
                "Tendencia_Faturamento": round(tendencia, 4),
                "Margem_Liquida": round(margem_liquida, 4),
                "Indice_Processos_Trabalhistas": round(processos_por_100, 4),
            })
            identificador += 1
    return pd.DataFrame(registros)


if __name__ == "__main__":
    arquivo_empresas = localizar_arquivo_empresas()
    df_empresas = pd.read_csv(arquivo_empresas, dtype={"CNPJ": "string"})
    df_riscos = gerar_homologacoes_risco(df_empresas)
    identificador_lote = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    arquivo_saida = RAW_DIR / f"homologacoes_risco_{identificador_lote}.csv"
    df_riscos.to_csv(arquivo_saida, index=False, encoding="utf-8-sig")
    print(f"Arquivo de risco gerado: {arquivo_saida}")
    print(f"Avaliações: {len(df_riscos)}")
    print(f"Homologações aprovadas: {(df_riscos['Resultado_Homologacao'] == 'Aprovada').sum()}")
