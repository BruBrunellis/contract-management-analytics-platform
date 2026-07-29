"""Gera empresas matrizes e filiais fictícias para a camada RAW."""

from datetime import date
from pathlib import Path
import random

import pandas as pd


RAW_DIR = Path(__file__).resolve().parents[2] / "1.data" / "1.raw"


def gerar_cnpj_ficticio():
    """Gera um CNPJ fictício no formato de uma matriz (estabelecimento 0001)."""
    raiz = "".join(str(random.randint(0, 9)) for _ in range(8))
    digitos_verificadores = f"{random.randint(10, 99)}"
    return f"{raiz[:2]}.{raiz[2:5]}.{raiz[5:]}/0001-{digitos_verificadores}"


def gerar_cnpj_filial(cnpj_matriz, numero_filial):
    """Mantém a raiz do CNPJ da matriz e altera o número do estabelecimento."""
    raiz = "".join(filter(str.isdigit, cnpj_matriz))[:8]
    digitos_verificadores = "".join(filter(str.isdigit, cnpj_matriz))[-2:]
    return f"{raiz[:2]}.{raiz[2:5]}.{raiz[5:]}/{numero_filial:04d}-{digitos_verificadores}"


def gerar_razao_social():
    """Combina termos para criar nomes de empresas verossímeis."""
    prefixos = [
        "Alpha", "Beta", "Nexus", "Inovação", "Global", "Vanguarda", "Horizonte",
        "Prime", "Apex", "Eco", "Quantum", "Nova", "Orion", "Zenith", "Spectra",
        "Integra", "Altus", "Matrix", "Summit", "Synapse", "Stellar", "Omega",
        "Vertex", "Titan", "Atlas", "Infinity", "Synergy", "Pulse", "Aegis",
        "Vektor", "Luanda", "Camargo", "Mendes", "Castelo Brando", "Brado", "Cubo",
        "Equinox", "Vitta", "Estratta", "Safra", "Insper", "Positivo", "Avante",
        "Ascenty", "Kyndryl", "Sonda", "Lumina", "Helios", "Aether", "Paradigm", "Sentinel", "Stratos", "Chronos",
        "Prisma", "Genesis", "Optima", "Helix", "Solstice", "Astral", "Hyperion",
        "Kinetic", "Synthex", "Veloce", "Aeterna", "Valora", "Momentum", "Alvorada",
        "Pinnacle", "Beacon", "Dominium", "Virtus", "Crest", "Venture", "Ignite",
        "Conecta", "Prossiga", "Andrade", "Magalhães", "Pinheiro", "Faria", "Algar",
        "Stefanini", "Tivit", "Locaweb"
    ]
    meios = [
        "Tecnologia", "Serviços", "Comércio", "Inteligência", "Rede", "Logística",
        "Soluções", "Engenharia", "Consultoria",
    ]
    sufixos = ["Ltda.", "S.A."]
    return f"{random.choice(prefixos)} {random.choice(meios)} {random.choice(sufixos)}"


def classificar_porte(faturamento):
    """Classifica o porte a partir do faturamento anual de 2022."""
    if faturamento < 360_000:
        return "Microempresa"
    if faturamento < 3_600_000:
        return "Pequeno"
    if faturamento < 10_000_000:
        return "Médio"
    return "Grande"


def gerar_empresa_matriz(cnpjs_existentes):
    """Gera uma empresa matriz com seus indicadores financeiros e operacionais."""
    cnpj = gerar_cnpj_ficticio()
    while cnpj in cnpjs_existentes:
        cnpj = gerar_cnpj_ficticio()
    cnpjs_existentes.add(cnpj)

    capital = round(random.uniform(50_000, 2_000_000), 2)
    faturamentos = [round(capital * random.uniform(1.2, 50.5), 2)]
    faturamentos.extend(
        round(faturamentos[-1] * random.uniform(limite_inferior, limite_superior), 2)
        for limite_inferior, limite_superior in [(0.9, 1.3), (0.95, 1.35), (0.95, 1.4), (0.9, 1.25)]
    )
    custos = [round(faturamento * random.uniform(0.5, 0.8), 2) for faturamento in faturamentos]
    lucros_brutos = [round(faturamento - custo, 2) for faturamento, custo in zip(faturamentos, custos)]
    juros_divida = [round(random.uniform(0.01, 0.05) * faturamento, 2) for faturamento in faturamentos]
    lucros_liquidos = [
        round(lucro_bruto - juros, 2)
        for lucro_bruto, juros in zip(lucros_brutos, juros_divida)
    ]

    porte = classificar_porte(faturamentos[0])
    limites_funcionarios = {
        "Microempresa": (1, 9),
        "Pequeno": (10, 99),
        "Médio": (100, 999),
        "Grande": (1_000, 99_999),
    }
    num_funcionarios = random.randint(*limites_funcionarios[porte])
    num_func_clt = round(num_funcionarios * random.uniform(0.0, 1.0))

    empresa = {
        "CNPJ": cnpj,
        "CNPJ8": "".join(filter(str.isdigit, cnpj))[:8],
        "CNPJ_Matriz": cnpj,
        "Razao_Social": gerar_razao_social(),
        "Hierarquia": "Matriz",
        "Capital_Social": capital,
        "Porte_Empresa": porte,
        "Num_Func_CLT": num_func_clt,
        "Num_Func_PJ": num_funcionarios - num_func_clt,
        "Num_Total_Func": num_funcionarios,
        "Processos_Trabalhistas": round(num_funcionarios * random.uniform(0.0, 0.45)),
    }
    for ano, valor in zip(range(2022, 2027), faturamentos):
        empresa[f"Faturamento_{ano}"] = valor
    for ano, valor in zip(range(2022, 2027), custos):
        empresa[f"Custo_{ano}"] = valor
    for ano, valor in zip(range(2022, 2027), lucros_brutos):
        empresa[f"Lucro_Bruto_{ano}"] = valor
    for ano, valor in zip(range(2022, 2027), juros_divida):
        empresa[f"Juros_Divida_{ano}"] = valor
    for ano, valor in zip(range(2022, 2027), lucros_liquidos):
        empresa[f"Lucro_Liquido_{ano}"] = valor
    return empresa


def gerar_filiais(matriz):
    """Gera de uma a três filiais com 10% a 40% da escala da matriz."""
    filiais = []
    campos_monetarios = [
        "Capital_Social",
        *[f"{indicador}_{ano}" for indicador in ("Faturamento", "Custo", "Lucro_Bruto", "Juros_Divida", "Lucro_Liquido") for ano in range(2022, 2027)],
    ]

    for numero_filial in range(2, random.randint(2, 4) + 1):
        fator_escala = random.uniform(0.10, 0.40)
        total_funcionarios = max(1, round(matriz["Num_Total_Func"] * fator_escala))
        funcionarios_clt = min(
            total_funcionarios,
            round(matriz["Num_Func_CLT"] * fator_escala),
        )
        filial = {
            "CNPJ": gerar_cnpj_filial(matriz["CNPJ"], numero_filial),
            "CNPJ8": matriz["CNPJ8"],
            "CNPJ_Matriz": matriz["CNPJ"],
            "Razao_Social": f"{matriz['Razao_Social']} - Filial {numero_filial:04d}",
            "Hierarquia": "Filial",
            "Porte_Empresa": classificar_porte(matriz["Faturamento_2022"] * fator_escala),
            "Num_Func_CLT": funcionarios_clt,
            "Num_Func_PJ": total_funcionarios - funcionarios_clt,
            "Num_Total_Func": total_funcionarios,
            "Processos_Trabalhistas": round(matriz["Processos_Trabalhistas"] * fator_escala),
        }
        filial.update({campo: round(matriz[campo] * fator_escala, 2) for campo in campos_monetarios})
        filiais.append(filial)
    return filiais


def gerar_tabela_empresas(qtd=300):
    """Gera matrizes e filiais para 50% das matrizes classificadas como grandes."""
    cnpjs_existentes = set()
    matrizes = [gerar_empresa_matriz(cnpjs_existentes) for _ in range(qtd)]
    matrizes_grandes = [matriz for matriz in matrizes if matriz["Porte_Empresa"] == "Grande"]
    quantidade_com_filiais = len(matrizes_grandes) // 2
    matrizes_selecionadas = random.sample(matrizes_grandes, quantidade_com_filiais)
    filiais = [filial for matriz in matrizes_selecionadas for filial in gerar_filiais(matriz)]
    return pd.DataFrame([*matrizes, *filiais])


if __name__ == "__main__":
    df_empresas = gerar_tabela_empresas(qtd=300)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    arquivo_saida = RAW_DIR / f"empresas_{date.today():%Y%m%d}.csv"
    df_empresas.to_csv(arquivo_saida, index=False, encoding="utf-8-sig")

    print(f"Arquivo gerado: {arquivo_saida}")
    print(f"Matrizes: {(df_empresas['Hierarquia'] == 'Matriz').sum()}")
    print(f"Filiais: {(df_empresas['Hierarquia'] == 'Filial').sum()}")