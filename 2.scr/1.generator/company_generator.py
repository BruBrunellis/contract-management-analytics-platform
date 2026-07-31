"""Gera empresas fictícias com relações coerentes entre receita, custos e equipe."""

import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[2] / "1.data" / "1.raw"
ANO_REFERENCIA = 2026
TIMEZONE = ZoneInfo("America/Sao_Paulo")
ATIVIDADES = [
    "Tecnologia", "Serviços", "Comércio", "Inteligência", "Rede", "Logística",
    "Soluções", "Engenharia", "Consultoria",
]
PERFIS_ATIVIDADE = {
    "Tecnologia": {"receita_func": (450_000, 1_300_000), "custo_func": (105_000, 250_000), "custo_operacional": (0.15, 0.32), "clt": (0.65, 0.90)},
    "Serviços": {"receita_func": (260_000, 650_000), "custo_func": (65_000, 155_000), "custo_operacional": (0.12, 0.28), "clt": (0.55, 0.85)},
    "Comércio": {"receita_func": (550_000, 1_800_000), "custo_func": (55_000, 135_000), "custo_operacional": (0.30, 0.60), "clt": (0.50, 0.80)},
    "Inteligência": {"receita_func": (350_000, 900_000), "custo_func": (100_000, 240_000), "custo_operacional": (0.10, 0.24), "clt": (0.65, 0.92)},
    "Rede": {"receita_func": (350_000, 1_000_000), "custo_func": (75_000, 180_000), "custo_operacional": (0.18, 0.38), "clt": (0.55, 0.85)},
    "Logística": {"receita_func": (300_000, 850_000), "custo_func": (55_000, 135_000), "custo_operacional": (0.25, 0.50), "clt": (0.60, 0.90)},
    "Soluções": {"receita_func": (350_000, 950_000), "custo_func": (80_000, 190_000), "custo_operacional": (0.15, 0.35), "clt": (0.55, 0.88)},
    "Engenharia": {"receita_func": (320_000, 900_000), "custo_func": (85_000, 200_000), "custo_operacional": (0.20, 0.42), "clt": (0.60, 0.90)},
    "Consultoria": {"receita_func": (300_000, 800_000), "custo_func": (95_000, 220_000), "custo_operacional": (0.10, 0.25), "clt": (0.65, 0.92)},
}
PREFIXOS = [
    "Alpha", "Beta", "Nexus", "Inovação", "Global", "Vanguarda", "Horizonte", "Prime",
    "Apex", "Eco", "Quantum", "Nova", "Orion", "Zenith", "Spectra", "Integra", "Altus",
    "Matrix", "Summit", "Synapse", "Stellar", "Omega", "Vertex", "Titan", "Atlas", "Infinity",
    "Synergy", "Pulse", "Aegis", "Vektor", "Luanda", "Camargo", "Mendes", "Castelo Brando",
    "Brado", "Cubo", "Equinox", "Vitta", "Estratta", "Safra", "Insper", "Positivo", "Avante",
    "Ascenty", "Kyndryl", "Sonda", "Lumina", "Helios", "Aether", "Paradigm", "Sentinel",
    "Stratos", "Chronos", "Prisma", "Genesis", "Optima", "Helix", "Solstice", "Astral",
    "Hyperion", "Kinetic", "Synthex", "Veloce", "Aeterna", "Valora", "Momentum", "Alvorada",
    "Pinnacle", "Beacon", "Dominium", "Virtus", "Crest", "Venture", "Ignite", "Conecta",
    "Prossiga", "Andrade", "Magalhães", "Pinheiro", "Faria", "Algar", "Stefanini", "Tivit", "Locaweb",
]


def gerar_cnpj_ficticio():
    """Gera um CNPJ fictício no formato de matriz."""
    raiz = "".join(str(random.randint(0, 9)) for _ in range(8))
    return f"{raiz[:2]}.{raiz[2:5]}.{raiz[5:]}/0001-{random.randint(10, 99):02d}"


def gerar_cnpj_filial(cnpj_matriz, numero_filial):
    """Gera uma filial que preserva a raiz econômica da matriz."""
    digitos = "".join(filter(str.isdigit, cnpj_matriz))
    raiz, verificadores = digitos[:8], digitos[-2:]
    return f"{raiz[:2]}.{raiz[2:5]}.{raiz[5:]}/{numero_filial:04d}-{verificadores}"


def gerar_razao_social(atividade):
    return f"{random.choice(PREFIXOS)} {atividade} {random.choice(['Ltda.', 'S.A.'])}"


def classificar_porte(faturamento):
    if faturamento < 360_000:
        return "Microempresa"
    if faturamento < 3_600_000:
        return "Pequeno"
    if faturamento < 10_000_000:
        return "Médio"
    return "Grande"


def definir_estagio(idade):
    if idade <= 7:
        return "Jovem"
    if idade <= 15:
        return "Em crescimento"
    if idade <= 35:
        return "Madura"
    return "Consolidada"


def definir_cenario(idade):
    """Define um cenário financeiro; unicórnios são restritos a empresas jovens."""
    sorteio = random.random()
    if idade <= 12 and sorteio < 0.03:
        return "Unicórnio"
    if sorteio < 0.15:
        return "Expansão"
    if sorteio < 0.23:
        return "Estagnada"
    if sorteio < 0.30:
        return "Em decadência"
    return "Normal"


def fator_faturamento_inicial(estagio, cenario):
    faixas_estagio = {
        "Jovem": (0.8, 8.0),
        "Em crescimento": (3.0, 18.0),
        "Madura": (8.0, 45.0),
        "Consolidada": (15.0, 90.0),
    }
    fator = random.uniform(*faixas_estagio[estagio])
    if cenario == "Unicórnio":
        fator *= random.uniform(4.0, 10.0)
    elif cenario == "Expansão":
        fator *= random.uniform(1.2, 2.0)
    elif cenario == "Em decadência":
        fator *= random.uniform(0.5, 0.9)
    return fator


def taxa_crescimento(cenario, estagio):
    if cenario == "Unicórnio":
        return random.uniform(0.35, 0.80)
    if cenario == "Expansão":
        return random.uniform(0.12, 0.35)
    if cenario == "Estagnada":
        return random.uniform(-0.03, 0.03)
    if cenario == "Em decadência":
        return random.uniform(-0.18, -0.05)
    if estagio == "Jovem":
        return random.uniform(0.05, 0.18)
    if estagio == "Em crescimento":
        return random.uniform(0.03, 0.12)
    return random.uniform(-0.02, 0.08)


def gerar_indicadores_financeiros(capital, perfil, estagio, cenario):
    """Gera receita, custos e lucro conectando produtividade e estrutura de pessoal."""
    faturamentos = [round(capital * fator_faturamento_inicial(estagio, cenario), 2)]
    for _ in range(4):
        crescimento = taxa_crescimento(cenario, estagio) + random.uniform(-0.025, 0.025)
        faturamentos.append(round(max(faturamentos[-1] * (1 + crescimento), 50_000), 2))

    receita_por_funcionario = random.uniform(*perfil["receita_func"])
    custo_anual_funcionario = random.uniform(*perfil["custo_func"])
    custos, folhas, lucros_brutos, juros, lucros_liquidos = [], [], [], [], []
    for faturamento in faturamentos:
        funcionarios_ano = max(1, round(faturamento / receita_por_funcionario))
        folha = round(funcionarios_ano * custo_anual_funcionario, 2)
        custo_operacional = faturamento * random.uniform(*perfil["custo_operacional"])
        custo_total = round(min(folha + custo_operacional, faturamento * 0.98), 2)
        lucro_bruto = round(faturamento - custo_total, 2)
        juros_divida = round(min(faturamento * random.uniform(0.01, 0.05), lucro_bruto * 0.65), 2)
        custos.append(custo_total)
        folhas.append(folha)
        lucros_brutos.append(lucro_bruto)
        juros.append(juros_divida)
        lucros_liquidos.append(round(lucro_bruto - juros_divida, 2))
    return faturamentos, custos, folhas, lucros_brutos, juros, lucros_liquidos, receita_por_funcionario


def gerar_empresa_matriz(cnpjs_existentes):
    """Gera uma matriz com dimensões operacionais derivadas da receita."""
    cnpj = gerar_cnpj_ficticio()
    while cnpj in cnpjs_existentes:
        cnpj = gerar_cnpj_ficticio()
    cnpjs_existentes.add(cnpj)

    atividade = random.choice(ATIVIDADES)
    perfil = PERFIS_ATIVIDADE[atividade]
    ano_fundacao = random.randint(1970, ANO_REFERENCIA - 2)
    idade = ANO_REFERENCIA - ano_fundacao
    estagio = definir_estagio(idade)
    cenario = definir_cenario(idade)
    capital = round(random.uniform(50_000, 8_000_000), 2)
    faturamentos, custos, folhas, lucros_brutos, juros, lucros_liquidos, receita_por_funcionario = gerar_indicadores_financeiros(
        capital, perfil, estagio, cenario
    )
    total_funcionarios = max(1, round(faturamentos[-1] / receita_por_funcionario))
    funcionarios_clt = round(total_funcionarios * random.uniform(*perfil["clt"]))

    empresa = {
        "CNPJ": cnpj,
        "CNPJ8": "".join(filter(str.isdigit, cnpj))[:8],
        "CNPJ_Matriz": cnpj,
        "Razao_Social": gerar_razao_social(atividade),
        "Atividade_Economica": atividade,
        "Ano_Fundacao": ano_fundacao,
        "Idade_Empresa": idade,
        "Estagio_Empresa": estagio,
        "Cenario_Financeiro": cenario,
        "Hierarquia": "Matriz",
        "Capital_Social": capital,
        "Porte_Empresa": classificar_porte(faturamentos[-1]),
        "Receita_Por_Funcionario": round(faturamentos[-1] / total_funcionarios, 2),
        "Num_Func_CLT": funcionarios_clt,
        "Num_Func_PJ": total_funcionarios - funcionarios_clt,
        "Num_Total_Func": total_funcionarios,
        "Processos_Trabalhistas": round(total_funcionarios * random.uniform(0.0, 0.12)),
    }
    for ano, faturamento, custo, folha, lucro_bruto, juros_divida, lucro_liquido in zip(
        range(2022, 2027), faturamentos, custos, folhas, lucros_brutos, juros, lucros_liquidos
    ):
        empresa[f"Faturamento_{ano}"] = faturamento
        empresa[f"Custo_{ano}"] = custo
        empresa[f"Custo_Folha_{ano}"] = folha
        empresa[f"Lucro_Bruto_{ano}"] = lucro_bruto
        empresa[f"Juros_Divida_{ano}"] = juros_divida
        empresa[f"Lucro_Liquido_{ano}"] = lucro_liquido
    return empresa


def gerar_filiais(matriz):
    """Gera de uma a três filiais, sempre menores que sua matriz."""
    campos_monetarios = [
        "Capital_Social",
        *[
            f"{indicador}_{ano}"
            for indicador in ("Faturamento", "Custo", "Custo_Folha", "Lucro_Bruto", "Juros_Divida", "Lucro_Liquido")
            for ano in range(2022, 2027)
        ],
    ]
    filiais = []
    for numero_filial in range(2, random.randint(2, 4) + 1):
        fator = random.uniform(0.10, 0.40)
        total_funcionarios = max(1, round(matriz["Num_Total_Func"] * fator))
        funcionarios_clt = min(total_funcionarios, round(matriz["Num_Func_CLT"] * fator))
        filial = {
            "CNPJ": gerar_cnpj_filial(matriz["CNPJ"], numero_filial),
            "CNPJ8": matriz["CNPJ8"],
            "CNPJ_Matriz": matriz["CNPJ"],
            "Razao_Social": f"{matriz['Razao_Social']} - Filial {numero_filial:04d}",
            "Atividade_Economica": matriz["Atividade_Economica"],
            "Ano_Fundacao": matriz["Ano_Fundacao"],
            "Idade_Empresa": matriz["Idade_Empresa"],
            "Estagio_Empresa": matriz["Estagio_Empresa"],
            "Cenario_Financeiro": matriz["Cenario_Financeiro"],
            "Hierarquia": "Filial",
            "Porte_Empresa": classificar_porte(matriz["Faturamento_2026"] * fator),
            "Receita_Por_Funcionario": matriz["Receita_Por_Funcionario"],
            "Num_Func_CLT": funcionarios_clt,
            "Num_Func_PJ": total_funcionarios - funcionarios_clt,
            "Num_Total_Func": total_funcionarios,
            "Processos_Trabalhistas": round(matriz["Processos_Trabalhistas"] * fator),
        }
        filial.update({campo: round(matriz[campo] * fator, 2) for campo in campos_monetarios})
        filiais.append(filial)
    return filiais


def gerar_tabela_empresas(qtd=300):
    cnpjs_existentes = set()
    matrizes = [gerar_empresa_matriz(cnpjs_existentes) for _ in range(qtd)]
    matrizes_grandes = [matriz for matriz in matrizes if matriz["Porte_Empresa"] == "Grande"]
    selecionadas = random.sample(matrizes_grandes, len(matrizes_grandes) // 2)
    filiais = [filial for matriz in selecionadas for filial in gerar_filiais(matriz)]
    return pd.DataFrame([*matrizes, *filiais])


if __name__ == "__main__":
    df_empresas = gerar_tabela_empresas(qtd=300)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    identificador_lote = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    arquivo_saida = RAW_DIR / f"empresas_{identificador_lote}.csv"
    df_empresas.to_csv(arquivo_saida, index=False, encoding="utf-8-sig")
    print(f"Arquivo gerado: {arquivo_saida}")
    print(f"Matrizes: {(df_empresas['Hierarquia'] == 'Matriz').sum()}")
    print(f"Filiais: {(df_empresas['Hierarquia'] == 'Filial').sum()}")
