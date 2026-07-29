"""Gera contratos fictícios e o histórico detalhado de seus aditamentos."""

from datetime import date, timedelta
from pathlib import Path
import random

import pandas as pd
from dateutil.relativedelta import relativedelta


RAW_DIR = Path(__file__).resolve().parents[2] / "1.data" / "1.raw"
PROBABILIDADE_OUTLIER = 0.10
PROBABILIDADE_APORTE = 0.35

ESCOPOS_GERAIS = [
    "Aquisição de Equipamentos",
    "Consultoria",
    "Licença de Software",
    "Manutenção e Suporte",
    "Outsourcing de TI",
    "Serviços de Logística",
    "Treinamento e Capacitação",
    "Serviços de Infraestrutura",
]
ESCOPOS_POR_ATIVIDADE = {
    "Tecnologia": ["Outsourcing de TI", "Licença de Software", "Manutenção e Suporte", "Serviços de Infraestrutura"],
    "Inteligência": ["Consultoria", "Treinamento e Capacitação", "Serviços de Infraestrutura"],
    "Consultoria": ["Consultoria", "Treinamento e Capacitação", "Serviços de Infraestrutura"],
    "Logística": ["Serviços de Logística", "Aquisição de Equipamentos", "Manutenção e Suporte"],
    "Engenharia": ["Serviços de Infraestrutura", "Aquisição de Equipamentos", "Manutenção e Suporte"],
    "Comércio": ["Aquisição de Equipamentos", "Serviços de Logística"],
    "Serviços": ["Consultoria", "Treinamento e Capacitação", "Manutenção e Suporte"],
}
COLUNAS_ADITAMENTOS = [
    "Cód_Contrato",
    "Tipo_Aditamento",
    "Vigência_Inicio",
    "Vigência_Fim",
    "Valor",
    "Sequencia_Aditamento",
]


def quantidade_contratos(porte, hierarquia):
    """Define a quantidade de contratos conforme porte e posição societária."""
    if hierarquia == "Filial":
        return random.randint(1, 3) if porte in {"Médio", "Grande"} else 1

    faixas_matriz = {
        "Grande": (1, 5),
        "Médio": (1, 4),
        "Pequeno": (1, 3),
        "Microempresa": (1, 1),
    }
    return random.randint(*faixas_matriz[porte])


def selecionar_escopo(razao_social):
    """Seleciona um escopo coerente com a atividade da razão social."""
    for atividade, escopos in ESCOPOS_POR_ATIVIDADE.items():
        if atividade.lower() in razao_social.lower():
            return random.choice(escopos)
    return random.choice(ESCOPOS_GERAIS)


def distribuir_valor(valor_total, quantidade):
    """Distribui um valor em parcelas positivas, preservando o total por centavos."""
    pesos = [random.uniform(0.3, 1.0) for _ in range(quantidade)]
    soma_pesos = sum(pesos)
    valores = [round(valor_total * peso / soma_pesos, 2) for peso in pesos[:-1]]
    valores.append(round(valor_total - sum(valores), 2))
    return valores


def gerar_aportes(codigo_contrato, inicio_ciclo, fim_ciclo, valor_renovacao, sequencia, eh_outlier):
    """Cria aportes pontuais dentro de um ciclo de renovação."""
    if not eh_outlier and random.random() >= PROBABILIDADE_APORTE:
        return [], 0.0, sequencia

    fator_aporte = (
        random.uniform(1.01, 1.50)
        if eh_outlier
        else random.uniform(0.01, 0.30)
    )
    valor_total_aportado = round(valor_renovacao * fator_aporte, 2)
    qtd_aportes = random.randint(1, 3) if eh_outlier else random.randint(1, 2)
    valores = distribuir_valor(valor_total_aportado, qtd_aportes)
    dias_ciclo = max((fim_ciclo - inicio_ciclo).days, 1)
    dias_aporte = sorted(
        random.randint(round(dias_ciclo * 0.25), round(dias_ciclo * 0.75))
        for _ in range(qtd_aportes)
    )

    aportes = []
    for valor, dias in zip(valores, dias_aporte):
        sequencia += 1
        aportes.append({
            "Cód_Contrato": codigo_contrato,
            "Tipo_Aditamento": "Aporte",
            "Vigência_Inicio": (inicio_ciclo + timedelta(days=dias)).isoformat(),
            "Vigência_Fim": fim_ciclo.isoformat(),
            "Valor": valor,
            "Sequencia_Aditamento": sequencia,
        })
    return aportes, valor_total_aportado, sequencia


def gerar_aditamentos(codigo_contrato, valor_original, vigencia_inicio, vigencia_fim, duracao_meses, renovado):
    """Gera ciclos anuais de renovação e seus aportes eventuais."""
    if not renovado:
        return [], 0.0, 0.0

    qtd_renovacoes = max(1, (duracao_meses - 1) // 12)
    ultimo_valor_anualizado = valor_original
    valor_renovado = 0.0
    valor_aportado = 0.0
    aditamentos = []
    sequencia = 0

    for numero_ciclo in range(1, qtd_renovacoes + 1):
        inicio_ciclo = vigencia_inicio + relativedelta(months=12 * numero_ciclo)
        fim_ciclo = min(
            vigencia_inicio + relativedelta(months=12 * (numero_ciclo + 1)) - timedelta(days=1),
            vigencia_fim,
        )
        ultimo_valor_anualizado = round(
            ultimo_valor_anualizado * random.uniform(0.85, 1.15),
            2,
        )
        valor_renovado += ultimo_valor_anualizado
        sequencia += 1
        aditamentos.append({
            "Cód_Contrato": codigo_contrato,
            "Tipo_Aditamento": "Renovação",
            "Vigência_Inicio": inicio_ciclo.isoformat(),
            "Vigência_Fim": fim_ciclo.isoformat(),
            "Valor": ultimo_valor_anualizado,
            "Sequencia_Aditamento": sequencia,
        })

        eh_outlier = random.random() < PROBABILIDADE_OUTLIER
        aportes, valor_ciclo_aportado, sequencia = gerar_aportes(
            codigo_contrato,
            inicio_ciclo,
            fim_ciclo,
            ultimo_valor_anualizado,
            sequencia,
            eh_outlier,
        )
        aditamentos.extend(aportes)
        valor_aportado += valor_ciclo_aportado

    return aditamentos, round(valor_renovado, 2), round(valor_aportado, 2)


def calcular_saldo(valor_total, valor_disponivel, vigencia_inicio, vigencia_fim, data_referencia, eh_outlier_consumo):
    """Calcula saldo sem consumir ciclos de renovação ou aporte ainda futuros."""
    if vigencia_fim < data_referencia:
        percentual_saldo = (
            random.uniform(0.20, 0.70)
            if eh_outlier_consumo
            else random.uniform(0.00, 0.10)
        )
        return round(valor_total * percentual_saldo, 2), "Vencido"

    total_dias = max((vigencia_fim - vigencia_inicio).days, 1)
    dias_decorridos = min(max((data_referencia - vigencia_inicio).days, 0), total_dias)
    percentual_saldo_esperado = 1 - dias_decorridos / total_dias
    if eh_outlier_consumo:
        percentual_saldo = random.uniform(0.00, 0.10) if random.choice([True, False]) else random.uniform(0.85, 0.98)
    else:
        percentual_saldo = min(max(percentual_saldo_esperado + random.uniform(-0.08, 0.08), 0.02), 0.98)
    valor_consumido = round(valor_disponivel * (1 - percentual_saldo), 2)
    return round(valor_total - valor_consumido, 2), "Ativo"


def gerar_tabelas_contratos(df_empresas, data_referencia=None):
    """Gera tabelas de contratos e de aditamentos detalhados."""
    data_referencia = data_referencia or date.today()
    contratos = []
    aditamentos = []
    codigo_counter = 1
    colunas_faturamento = [coluna for coluna in df_empresas if coluna.startswith("Faturamento_")]

    for _, empresa in df_empresas.iterrows():
        media_faturamento = empresa[colunas_faturamento].astype(float).mean()
        for _ in range(quantidade_contratos(empresa["Porte_Empresa"], empresa["Hierarquia"])):
            codigo_contrato = f"CS{codigo_counter:08d}"
            codigo_counter += 1
            duracao_meses = random.randint(6, 120)
            inicio_minimo = date(data_referencia.year - 6, 1, 1)
            inicio_maximo = data_referencia - timedelta(days=26)
            vigencia_inicio = inicio_minimo + timedelta(days=random.randint(0, (inicio_maximo - inicio_minimo).days))
            vigencia_fim = vigencia_inicio + relativedelta(months=duracao_meses) - timedelta(days=1)
            valor_original = round(media_faturamento * random.uniform(0.01, 0.35), 2)
            renovado = duracao_meses >= 24 and random.choice([True, False])
            aditamentos_contrato, valor_renovado, valor_aportado = gerar_aditamentos(
                codigo_contrato,
                valor_original,
                vigencia_inicio,
                vigencia_fim,
                duracao_meses,
                renovado,
            )
            aditamentos.extend(aditamentos_contrato)
            valor_total = round(valor_original + valor_renovado + valor_aportado, 2)
            valor_disponivel = round(
                valor_original + sum(
                    aditamento["Valor"]
                    for aditamento in aditamentos_contrato
                    if date.fromisoformat(aditamento["Vigência_Inicio"]) <= data_referencia
                ),
                2,
            )
            saldo, status = calcular_saldo(
                valor_total,
                valor_disponivel,
                vigencia_inicio,
                vigencia_fim,
                data_referencia,
                random.random() < PROBABILIDADE_OUTLIER,
            )
            escopo = selecionar_escopo(empresa["Razao_Social"])
            contratos.append({
                "Cód_Contrato": codigo_contrato,
                "Nome_Contrato": f"Contrato de {escopo} - {empresa['Razao_Social'].split()[0]}",
                "CNPJ": empresa["CNPJ"],
                "Fornecedor": empresa["Razao_Social"],
                "Escopo": escopo,
                "Vigência Inicio": vigencia_inicio.isoformat(),
                "Vigência Fim": vigencia_fim.isoformat(),
                "Valor_Original": valor_original,
                "Valor_Total": valor_total,
                "Saldo": saldo,
                "Tipo_Contrato": "Contrato Renovado" if renovado else "Novo Contrato",
                "Status": status,
            })

    return pd.DataFrame(contratos), pd.DataFrame(aditamentos, columns=COLUNAS_ADITAMENTOS)


def localizar_arquivo_empresas():
    """Retorna o arquivo versionado de empresas mais recente."""
    arquivos = sorted(RAW_DIR.glob("empresas_*.csv"))
    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo no padrão empresas_YYYYMMDD.csv foi encontrado em data/raw.")
    return arquivos[-1]


if __name__ == "__main__":
    arquivo_empresas = localizar_arquivo_empresas()
    df_empresas = pd.read_csv(arquivo_empresas, dtype={"CNPJ": "string"})
    df_contratos, df_aditamentos = gerar_tabelas_contratos(df_empresas)
    data_execucao = date.today().strftime("%Y%m%d")
    arquivo_contratos = RAW_DIR / f"contratos_ficticios_{data_execucao}.csv"
    arquivo_aditamentos = RAW_DIR / f"aditamentos_{data_execucao}.csv"
    df_contratos.to_csv(arquivo_contratos, index=False, encoding="utf-8-sig")
    df_aditamentos.to_csv(arquivo_aditamentos, index=False, encoding="utf-8-sig")

    print(f"Arquivo de contratos gerado: {arquivo_contratos}")
    print(f"Arquivo de aditamentos gerado: {arquivo_aditamentos}")
    print(f"Total de contratos: {len(df_contratos)}")
    print(f"Total de aditamentos: {len(df_aditamentos)}")
