"""Gera contratos fictícios e o histórico detalhado de seus aditamentos."""

import random
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from dateutil.relativedelta import relativedelta

RAW_DIR = Path(__file__).resolve().parents[2] / "1.data" / "1.raw"
PROBABILIDADE_OUTLIER = 0.10
PROBABILIDADE_APORTE = 0.35
PROBABILIDADE_OUTLIER_QTD_CONTRATOS = 0.12
LIMITE_EXPOSICAO_NORMAL = (0.20, 0.45)
LIMITE_EXPOSICAO_OUTLIER = (0.45, 0.90)
FAIXA_CONTRATOS_GRANDE_OUTLIER = (6, 12)
TIMEZONE = ZoneInfo("America/Sao_Paulo")

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


def quantidade_contratos(
    porte,
    hierarquia,
    probabilidade_outlier=PROBABILIDADE_OUTLIER_QTD_CONTRATOS,
):
    """Define a quantidade de contratos conforme porte e posição societária."""
    if hierarquia == "Filial":
        return random.randint(1, 3) if porte in {"Médio", "Grande"} else 1

    if porte == "Grande" and random.random() < probabilidade_outlier:
        return random.randint(*FAIXA_CONTRATOS_GRANDE_OUTLIER)

    faixas_matriz = {
        "Grande": (1, 5),
        "Médio": (1, 4),
        "Pequeno": (1, 3),
        "Microempresa": (1, 1),
    }
    return random.randint(*faixas_matriz[porte])


def faturamento_base_contrato(empresa, vigencia_inicio):
    """Retorna o faturamento do ano de início, limitado ao primeiro ano disponível."""
    ano_base = max(vigencia_inicio.year, 2022)
    return float(empresa[f"Faturamento_{ano_base}"]), ano_base


def calcular_limites_exposicao(empresa, fator_limite):
    """Define a capacidade anual de contratos do fornecedor com este comprador."""
    return {
        ano: round(float(empresa[f"Faturamento_{ano}"]) * fator_limite, 2)
        for ano in range(2022, 2027)
    }


def calcular_valor_original(
    empresa,
    vigencia_inicio,
    quantidade_planejada,
    exposicao_anual,
    limites_exposicao,
):
    """Calcula um valor anualizado sem exceder a exposição anual do fornecedor."""
    faturamento, ano_base = faturamento_base_contrato(empresa, vigencia_inicio)
    capacidade_disponivel = round(limites_exposicao[ano_base] - exposicao_anual[ano_base], 2)
    if capacidade_disponivel <= 0:
        return 0.0

    fator_maximo = min(0.35, limites_exposicao[ano_base] / faturamento / quantidade_planejada * 1.5)
    fator_minimo = min(0.01, fator_maximo / 4)
    valor_sugerido = faturamento * random.uniform(fator_minimo, fator_maximo)
    valor_original = round(min(valor_sugerido, capacidade_disponivel), 2)
    exposicao_anual[ano_base] = round(exposicao_anual[ano_base] + valor_original, 2)
    return valor_original


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


def gerar_aportes(
    codigo_contrato,
    inicio_ciclo,
    fim_ciclo,
    valor_renovacao,
    sequencia,
    eh_outlier,
    probabilidade_aporte=PROBABILIDADE_APORTE,
):
    """Cria aportes pontuais dentro de um ciclo de renovação."""
    if not eh_outlier and random.random() >= probabilidade_aporte:
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


def obter_avaliacao_risco(df_riscos, cnpj, data_evento):
    """Busca a avaliação anual disponível para a data de um ciclo contratual."""
    avaliacoes = df_riscos[df_riscos["CNPJ"].eq(cnpj)].copy()
    avaliacoes["Data_Avaliacao"] = pd.to_datetime(avaliacoes["Data_Avaliacao"])
    ano = data_evento.year
    candidatas = avaliacoes[avaliacoes["Data_Avaliacao"].dt.year.eq(ano)]
    if candidatas.empty:
        candidatas = avaliacoes[avaliacoes["Data_Avaliacao"] <= pd.Timestamp(data_evento)]
    if candidatas.empty:
        return None
    return candidatas.sort_values("Data_Avaliacao").iloc[-1]


def gerar_aditamentos(
    codigo_contrato,
    cnpj,
    valor_original,
    vigencia_inicio,
    vigencia_fim,
    duracao_meses,
    renovado,
    df_riscos,
    data_referencia,
    probabilidade_outlier=PROBABILIDADE_OUTLIER,
    probabilidade_aporte=PROBABILIDADE_APORTE,
):
    """Gera renovação apenas quando a avaliação de risco anual é aprovada."""
    if not renovado:
        return [], 0.0, 0.0, False, None, None

    qtd_renovacoes = max(1, (duracao_meses - 1) // 12)
    ultimo_valor_anualizado = valor_original
    valor_renovado = 0.0
    valor_aportado = 0.0
    aditamentos = []
    sequencia = 0

    for numero_ciclo in range(1, qtd_renovacoes + 1):
        inicio_ciclo = vigencia_inicio + relativedelta(months=12 * numero_ciclo)
        if inicio_ciclo > data_referencia:
            break
        fim_ciclo = min(
            vigencia_inicio + relativedelta(months=12 * (numero_ciclo + 1)) - timedelta(days=1),
            vigencia_fim,
        )
        avaliacao = obter_avaliacao_risco(df_riscos, cnpj, inicio_ciclo)
        if avaliacao is None or avaliacao["Resultado_Homologacao"] != "Aprovada":
            return aditamentos, round(valor_renovado, 2), round(valor_aportado, 2), True, inicio_ciclo, avaliacao
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

        eh_outlier = random.random() < probabilidade_outlier
        aportes, valor_ciclo_aportado, sequencia = gerar_aportes(
            codigo_contrato,
            inicio_ciclo,
            fim_ciclo,
            ultimo_valor_anualizado,
            sequencia,
            eh_outlier,
            probabilidade_aporte,
        )
        aditamentos.extend(aportes)
        valor_aportado += valor_ciclo_aportado

    return aditamentos, round(valor_renovado, 2), round(valor_aportado, 2), False, None, None


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


def gerar_tabelas_contratos(
    df_empresas,
    df_riscos,
    data_referencia=None,
    probabilidade_outlier=PROBABILIDADE_OUTLIER,
    probabilidade_aporte=PROBABILIDADE_APORTE,
    probabilidade_outlier_qtd_contratos=PROBABILIDADE_OUTLIER_QTD_CONTRATOS,
    limite_exposicao_normal=LIMITE_EXPOSICAO_NORMAL,
    limite_exposicao_outlier=LIMITE_EXPOSICAO_OUTLIER,
):
    """Gera tabelas de contratos e de aditamentos detalhados."""
    data_referencia = data_referencia or datetime.now(TIMEZONE).date()
    contratos = []
    aditamentos = []
    codigo_counter = 1
    for _, empresa in df_empresas.iterrows():
        quantidade_planejada = quantidade_contratos(
            empresa["Porte_Empresa"],
            empresa["Hierarquia"],
            probabilidade_outlier_qtd_contratos,
        )
        carteira_outlier = empresa["Porte_Empresa"] == "Grande" and quantidade_planejada > 5
        faixa_limite = limite_exposicao_outlier if carteira_outlier else limite_exposicao_normal
        fator_limite = random.uniform(*faixa_limite)
        limites_exposicao = calcular_limites_exposicao(empresa, fator_limite)
        exposicao_anual = dict.fromkeys(limites_exposicao, 0.0)

        for _ in range(quantidade_planejada):
            duracao_meses = random.randint(6, 120)
            inicio_minimo = date(2022, 1, 1)
            inicio_maximo = data_referencia - timedelta(days=26)
            vigencia_inicio = inicio_minimo + timedelta(days=random.randint(0, (inicio_maximo - inicio_minimo).days))
            vigencia_fim = vigencia_inicio + relativedelta(months=duracao_meses) - timedelta(days=1)
            avaliacao_inicial = obter_avaliacao_risco(df_riscos, empresa["CNPJ"], vigencia_inicio)
            if avaliacao_inicial is None or avaliacao_inicial["Resultado_Homologacao"] != "Aprovada":
                continue
            valor_original = calcular_valor_original(
                empresa,
                vigencia_inicio,
                quantidade_planejada,
                exposicao_anual,
                limites_exposicao,
            )
            if valor_original <= 0:
                continue
            codigo_contrato = f"CS{codigo_counter:08d}"
            codigo_counter += 1
            renovado = duracao_meses >= 24 and random.choice([True, False])
            aditamentos_contrato, valor_renovado, valor_aportado, encerrado_por_risco, data_encerramento, avaliacao_encerramento = gerar_aditamentos(
                codigo_contrato,
                empresa["CNPJ"],
                valor_original,
                vigencia_inicio,
                vigencia_fim,
                duracao_meses,
                renovado,
                df_riscos,
                data_referencia,
                probabilidade_outlier,
                probabilidade_aporte,
            )
            if encerrado_por_risco:
                vigencia_fim = data_encerramento - timedelta(days=1)
            avaliacao_atual = obter_avaliacao_risco(df_riscos, empresa["CNPJ"], data_referencia)
            if (
                not encerrado_por_risco
                and vigencia_fim >= data_referencia
                and (avaliacao_atual is None or avaliacao_atual["Resultado_Homologacao"] != "Aprovada")
            ):
                encerrado_por_risco = True
                data_encerramento = data_referencia
                avaliacao_encerramento = avaliacao_atual
                vigencia_fim = data_encerramento - timedelta(days=1)
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
                random.random() < probabilidade_outlier,
            )
            if encerrado_por_risco:
                status = "Encerrado"
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
                "Data_Avaliacao_Risco": avaliacao_encerramento["Data_Avaliacao"] if encerrado_por_risco else "",
                "Risco_Final": avaliacao_encerramento["Risco_Final"] if encerrado_por_risco else avaliacao_inicial["Risco_Final"],
                "Motivo_Encerramento": "Homologação negada por risco final alto" if encerrado_por_risco else "",
            })

    return pd.DataFrame(contratos), pd.DataFrame(aditamentos, columns=COLUNAS_ADITAMENTOS)


def localizar_arquivo_empresas():
    """Retorna o arquivo versionado de empresas mais recente."""
    arquivos = sorted(RAW_DIR.glob("empresas_*.csv"))
    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo no padrão empresas_YYYYMMDD.csv foi encontrado em data/raw.")
    return arquivos[-1]


def localizar_arquivo_riscos():
    arquivos = sorted(RAW_DIR.glob("homologacoes_risco_*.csv"))
    if not arquivos:
        raise FileNotFoundError("Execute risk_generator.py antes de gerar contratos.")
    return arquivos[-1]


if __name__ == "__main__":
    arquivo_empresas = localizar_arquivo_empresas()
    arquivo_riscos = localizar_arquivo_riscos()
    df_empresas = pd.read_csv(arquivo_empresas, dtype={"CNPJ": "string"})
    df_riscos = pd.read_csv(arquivo_riscos, dtype={"CNPJ": "string"})
    df_contratos, df_aditamentos = gerar_tabelas_contratos(df_empresas, df_riscos)
    identificador_lote = datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")
    arquivo_contratos = RAW_DIR / f"contratos_ficticios_{identificador_lote}.csv"
    arquivo_aditamentos = RAW_DIR / f"aditamentos_{identificador_lote}.csv"
    df_contratos.to_csv(arquivo_contratos, index=False, encoding="utf-8-sig")
    df_aditamentos.to_csv(arquivo_aditamentos, index=False, encoding="utf-8-sig")

    print(f"Arquivo de contratos gerado: {arquivo_contratos}")
    print(f"Arquivo de aditamentos gerado: {arquivo_aditamentos}")
    print(f"Total de contratos: {len(df_contratos)}")
    print(f"Total de aditamentos: {len(df_aditamentos)}")
