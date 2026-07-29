"""Gera pagamentos fictícios a partir de contratos e seus aditamentos."""

from datetime import date, datetime, timedelta
from pathlib import Path
import random
import re

import pandas as pd
from dateutil.relativedelta import relativedelta


RAW_DIR = Path(__file__).resolve().parents[2] / "1.data" / "1.raw"
MODELOS_PAGAMENTO = ("Mensal variável", "One-shot", "Concentrado")
PESOS_MODELOS = (0.75, 0.10, 0.15)


def data_arquivo_versionado(caminho):
    """Extrai a data YYYYMMDD de um arquivo versionado."""
    correspondencia = re.search(r"_(\d{8})(?:_\d{6})?\.csv$", caminho.name)
    if not correspondencia:
        raise ValueError(f"Nome de arquivo sem data de versão: {caminho.name}")
    return datetime.strptime(correspondencia.group(1), "%Y%m%d").date()


def identificador_arquivo_versionado(caminho):
    """Extrai o identificador de lote YYYYMMDD ou YYYYMMDD_HHMMSS."""
    correspondencia = re.search(r"_(\d{8}(?:_\d{6})?)\.csv$", caminho.name)
    if not correspondencia:
        raise ValueError(f"Nome de arquivo sem identificador de versão: {caminho.name}")
    return correspondencia.group(1)


def localizar_arquivos_origem():
    """Localiza o contrato mais recente e seus aditamentos da mesma versão."""
    contratos = sorted(RAW_DIR.glob("contratos_ficticios_*.csv"))
    if not contratos:
        raise FileNotFoundError("Nenhum arquivo no padrão contratos_ficticios_YYYYMMDD.csv foi encontrado.")

    arquivo_contratos = contratos[-1]
    data_snapshot = data_arquivo_versionado(arquivo_contratos)
    identificador_lote = identificador_arquivo_versionado(arquivo_contratos)
    arquivo_aditamentos = RAW_DIR / f"aditamentos_{identificador_lote}.csv"
    if not arquivo_aditamentos.exists():
        raise FileNotFoundError(
            f"Não foi encontrado o arquivo de aditamentos correspondente a {arquivo_contratos.name}."
        )
    return arquivo_contratos, arquivo_aditamentos, data_snapshot


def datas_mensais(inicio, fim):
    """Retorna datas mensais dentro de uma janela de pagamento."""
    datas = []
    data_pagamento = inicio
    while data_pagamento <= fim:
        datas.append(data_pagamento)
        data_pagamento += relativedelta(months=1)
    return datas or [inicio]


def distribuir_valor(valor_total, quantidade, variacao=True):
    """Divide um valor, preservando o total após o arredondamento."""
    pesos = [random.uniform(0.70, 1.30) if variacao else 1.0 for _ in range(quantidade)]
    soma_pesos = sum(pesos)
    valores = [round(valor_total * peso / soma_pesos, 2) for peso in pesos[:-1]]
    valores.append(round(valor_total - sum(valores), 2))
    return valores


def gerar_pagamentos_janela(valor, inicio, fim, modelo):
    """Cria pagamentos variáveis, únicos ou concentrados em uma janela."""
    if valor <= 0 or inicio > fim:
        return []

    if modelo == "One-shot":
        return [(inicio + timedelta(days=random.randint(0, max((fim - inicio).days, 0))), round(valor, 2))]

    datas = datas_mensais(inicio, fim)
    if modelo == "Concentrado" and len(datas) > 1:
        valor_concentrado = round(valor * random.uniform(0.35, 0.65), 2)
        indice_concentrado = random.randrange(len(datas))
        valores_restantes = distribuir_valor(valor - valor_concentrado, len(datas) - 1)
        valores = []
        indice_restante = 0
        for indice in range(len(datas)):
            if indice == indice_concentrado:
                valores.append(valor_concentrado)
            else:
                valores.append(valores_restantes[indice_restante])
                indice_restante += 1
        return list(zip(datas, valores))

    return list(zip(datas, distribuir_valor(valor, len(datas))))


def construir_ciclos(contrato, aditamentos_contrato):
    """Monta os valores disponíveis por ciclo original, renovação e aporte."""
    inicio_contrato = pd.to_datetime(contrato["Vigência Inicio"]).date()
    fim_contrato = pd.to_datetime(contrato["Vigência Fim"]).date()
    renovacoes = aditamentos_contrato[aditamentos_contrato["Tipo_Aditamento"] == "Renovação"].copy()
    renovacoes["Vigência_Inicio"] = pd.to_datetime(renovacoes["Vigência_Inicio"]).dt.date
    renovacoes["Vigência_Fim"] = pd.to_datetime(renovacoes["Vigência_Fim"]).dt.date

    fim_ciclo_original = (
        min(renovacoes["Vigência_Inicio"]) - timedelta(days=1)
        if not renovacoes.empty
        else fim_contrato
    )
    ciclos = [{
        "inicio": inicio_contrato,
        "fim": fim_ciclo_original,
        "valor": float(contrato["Valor_Original"]),
    }]

    for _, aditamento in aditamentos_contrato.iterrows():
        ciclos.append({
            "inicio": pd.to_datetime(aditamento["Vigência_Inicio"]).date(),
            "fim": pd.to_datetime(aditamento["Vigência_Fim"]).date(),
            "valor": float(aditamento["Valor"]),
        })
    return ciclos


def alocar_valor(valor_total, ciclos, data_limite, capacidades=None):
    """Aloca valor proporcionalmente aos ciclos já iniciados até uma data."""
    elegiveis = [ciclo for ciclo in ciclos if ciclo["inicio"] <= data_limite]
    capacidades = capacidades or [ciclo["valor"] for ciclo in ciclos]
    capacidade = round(
        sum(capacidades[indice] for indice, ciclo in enumerate(ciclos) if ciclo["inicio"] <= data_limite),
        2,
    )
    if valor_total > capacidade + 0.01:
        raise ValueError("O consumo solicitado excede o valor já disponível até a data de referência.")
    if not elegiveis or valor_total <= 0:
        return [0.0] * len(ciclos)

    pesos = [
        capacidades[indice]
        for indice, ciclo in enumerate(ciclos)
        if ciclo["inicio"] <= data_limite
    ]
    soma_pesos = sum(pesos)
    valores_elegiveis = [round(valor_total * peso / soma_pesos, 2) for peso in pesos[:-1]]
    valores_elegiveis.append(round(valor_total - sum(valores_elegiveis), 2))

    alocacao = []
    indice = 0
    for ciclo in ciclos:
        if ciclo["inicio"] <= data_limite:
            alocacao.append(valores_elegiveis[indice])
            indice += 1
        else:
            alocacao.append(0.0)
    return alocacao


def calcular_incremento(ciclos, consumo_base, data_snapshot, data_referencia):
    """Simula consumo adicional após a data do snapshot contratual."""
    if data_referencia <= data_snapshot:
        return 0.0

    capacidade_base = sum(ciclo["valor"] for ciclo in ciclos if ciclo["inicio"] <= data_snapshot)
    capacidade_referencia = sum(ciclo["valor"] for ciclo in ciclos if ciclo["inicio"] <= data_referencia)
    capacidade_restante = max(0.0, capacidade_referencia - consumo_base)
    if capacidade_restante == 0:
        return 0.0

    dias_posteriores = (data_referencia - data_snapshot).days
    ciclos_ativos = [
        ciclo for ciclo in ciclos
        if ciclo["inicio"] <= data_referencia and ciclo["fim"] > data_snapshot
    ]
    taxa_diaria = sum(
        ciclo["valor"] / max((ciclo["fim"] - ciclo["inicio"]).days + 1, 1)
        for ciclo in ciclos_ativos
    )
    incremento = taxa_diaria * dias_posteriores * random.uniform(0.80, 1.20)
    return round(min(incremento, capacidade_restante), 2)


def gerar_tabela_spending(df_contratos, df_aditamentos, data_snapshot, data_referencia=None):
    """Gera pagamentos até a data de referência, respeitando os ciclos financeiros."""
    data_referencia = data_referencia or date.today()
    if data_referencia < data_snapshot:
        raise ValueError("A data de referência não pode ser anterior à data do snapshot de contratos.")

    pagamentos = []
    pagamento_id = 1
    for _, contrato in df_contratos.iterrows():
        codigo_contrato = contrato["Cód_Contrato"]
        aditamentos_contrato = df_aditamentos[df_aditamentos["Cód_Contrato"] == codigo_contrato]
        ciclos = construir_ciclos(contrato, aditamentos_contrato)
        consumo_snapshot = round(float(contrato["Valor_Total"]) - float(contrato["Saldo"]), 2)
        alocacao_base = alocar_valor(consumo_snapshot, ciclos, data_snapshot)
        incremento = 0.0 if contrato["Status"] == "Vencido" else calcular_incremento(
            ciclos,
            consumo_snapshot,
            data_snapshot,
            data_referencia,
        )
        capacidades_incremento = [
            round(ciclo["valor"] - alocacao_base[indice], 2)
            for indice, ciclo in enumerate(ciclos)
        ]
        alocacao_incremento = alocar_valor(
            incremento,
            ciclos,
            data_referencia,
            capacidades=capacidades_incremento,
        )
        modelo = random.choices(MODELOS_PAGAMENTO, weights=PESOS_MODELOS, k=1)[0]

        for indice, ciclo in enumerate(ciclos):
            fim_base = min(ciclo["fim"], data_snapshot)
            for data_pagamento, valor_pago in gerar_pagamentos_janela(
                alocacao_base[indice],
                ciclo["inicio"],
                fim_base,
                modelo,
            ):
                pagamentos.append({
                    "Cód_Contrato": codigo_contrato,
                    "CNPJ": contrato["CNPJ"],
                    "Fornecedor": contrato["Fornecedor"],
                    "Cód_Pagamento": f"PAG{pagamento_id:08d}",
                    "Data_Pagamento": data_pagamento.isoformat(),
                    "Valor_Pago": valor_pago,
                })
                pagamento_id += 1

            if incremento > 0:
                inicio_incremento = max(ciclo["inicio"], data_snapshot + timedelta(days=1))
                fim_incremento = min(ciclo["fim"], data_referencia)
                for data_pagamento, valor_pago in gerar_pagamentos_janela(
                    alocacao_incremento[indice],
                    inicio_incremento,
                    fim_incremento,
                    modelo,
                ):
                    pagamentos.append({
                        "Cód_Contrato": codigo_contrato,
                        "CNPJ": contrato["CNPJ"],
                        "Fornecedor": contrato["Fornecedor"],
                        "Cód_Pagamento": f"PAG{pagamento_id:08d}",
                        "Data_Pagamento": data_pagamento.isoformat(),
                        "Valor_Pago": valor_pago,
                    })
                    pagamento_id += 1
    return pd.DataFrame(pagamentos)


if __name__ == "__main__":
    arquivo_contratos, arquivo_aditamentos, data_snapshot = localizar_arquivos_origem()
    df_contratos = pd.read_csv(arquivo_contratos, dtype={"CNPJ": "string"})
    df_aditamentos = pd.read_csv(arquivo_aditamentos)
    data_referencia = date.today()
    df_spending = gerar_tabela_spending(
        df_contratos,
        df_aditamentos,
        data_snapshot,
        data_referencia,
    )
    identificador_lote = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_saida = RAW_DIR / f"spending_ficticio_{identificador_lote}.csv"
    df_spending.to_csv(arquivo_saida, index=False, encoding="utf-8-sig")
    print(f"Arquivo de spending gerado: {arquivo_saida}")
    print(f"Data do snapshot de contratos: {data_snapshot:%Y-%m-%d}")
    print(f"Data de referência do spending: {data_referencia:%Y-%m-%d}")
    print(f"Total de pagamentos: {len(df_spending)}")
