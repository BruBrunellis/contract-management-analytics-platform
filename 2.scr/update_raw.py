"""Evolui um snapshot RAW sem modificar o snapshot-pai."""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
GENERATOR_DIR = SCRIPT_DIR / "1.generator"
sys.path.insert(0, str(GENERATOR_DIR))

import company_generator
import contract_generator
import risk_generator
from raw_snapshot_framework import (
    RawSnapshotError,
    carregar_fontes,
    carregar_manifesto,
    gravar_snapshot,
    novo_snapshot_id,
)


@dataclass
class RawUpdateConfig:
    data_referencia: date
    seed: int | None = None
    probabilidade_novos_fornecedores: float = 0.10
    probabilidade_novos_contratos: float = 0.50
    probabilidade_novos_pagamentos: float = 0.75
    probabilidade_reavaliacao_risco: float = 0.50
    percentual_matrizes_grandes_com_filiais: float = 0.50


def validar_config(config, data_pai):
    if config.data_referencia <= data_pai:
        raise RawSnapshotError("A nova data de referência deve ser posterior ao snapshot-pai.")
    for nome in [
        "probabilidade_novos_fornecedores",
        "probabilidade_novos_contratos",
        "probabilidade_novos_pagamentos",
        "probabilidade_reavaliacao_risco",
        "percentual_matrizes_grandes_com_filiais",
    ]:
        if not 0 <= getattr(config, nome) <= 1:
            raise ValueError(f"{nome} deve estar entre 0 e 1.")


def _proximo_numero(df, coluna, prefixo):
    valores = df[coluna].fillna("").astype(str).str.extract(r"(\d+)$", expand=False)
    numeros = pd.to_numeric(valores, errors="coerce").dropna()
    return int(numeros.max()) + 1 if not numeros.empty else 1


def _empresas_novas(quantidade, existentes):
    novas = []
    for _ in range(quantidade):
        matriz = company_generator.gerar_empresa_matriz(existentes)
        novas.append(matriz)
        novas.extend(company_generator.gerar_filiais(matriz))
    return pd.DataFrame(novas) if novas else pd.DataFrame()


def _atualizar_riscos(riscos, empresas_novas, config):
    resultado = riscos.copy()
    expiracao = pd.to_datetime(resultado["Data_Expiracao"], errors="coerce").dt.date
    aprovadas = resultado["Resultado_Homologacao"].eq("Aprovada")
    resultado.loc[aprovadas & expiracao.lt(config.data_referencia), "Status_Homologacao"] = "Expirada"
    novas_avaliacoes = []
    proximo_id = _proximo_numero(resultado, "Id_Avaliacao_Risco", "RSK")
    candidatos = resultado.loc[
        resultado["Resultado_Homologacao"].eq("Aprovada")
        & resultado["Status_Homologacao"].eq("Expirada")
    ].sort_values("Data_Avaliacao").groupby("CNPJ", as_index=False).tail(1)
    for _, avaliacao in candidatos.iterrows():
        if random.random() > config.probabilidade_reavaliacao_risco:
            continue
        nova = avaliacao.copy()
        nova["Id_Avaliacao_Risco"] = f"RSK{proximo_id:09d}"
        proximo_id += 1
        nova["Data_Avaliacao"] = config.data_referencia.isoformat()
        nova["Data_Ultima_Homologacao"] = config.data_referencia.isoformat()
        nova["Data_Expiracao"] = (config.data_referencia + timedelta(days=1461)).isoformat()
        nova["Status_Homologacao"] = "Ativa"
        novas_avaliacoes.append(nova)
    if not empresas_novas.empty:
        riscos_novos = risk_generator.gerar_homologacoes_risco(empresas_novas, config.data_referencia)
        for indice in riscos_novos.index:
            riscos_novos.loc[indice, "Id_Avaliacao_Risco"] = f"RSK{proximo_id:09d}"
            proximo_id += 1
        novas_avaliacoes.extend(registro for _, registro in riscos_novos.iterrows())
    if novas_avaliacoes:
        resultado = pd.concat([resultado, pd.DataFrame(novas_avaliacoes)], ignore_index=True)
    return resultado


def _anexar_contratos_novos(contratos, aditamentos, empresas_novas, riscos, config):
    if empresas_novas.empty or random.random() > config.probabilidade_novos_contratos:
        return contratos, aditamentos
    novos_contratos, novos_aditamentos = contract_generator.gerar_tabelas_contratos(
        empresas_novas, riscos, config.data_referencia
    )
    if novos_contratos.empty:
        return contratos, aditamentos
    proximo_id = _proximo_numero(contratos, "Cód_Contrato", "CS")
    mapa_ids = {}
    for indice, contrato_id in novos_contratos["Cód_Contrato"].items():
        novo_id = f"CS{proximo_id:08d}"
        proximo_id += 1
        mapa_ids[contrato_id] = novo_id
        novos_contratos.loc[indice, "Cód_Contrato"] = novo_id
    novos_aditamentos = novos_aditamentos.copy()
    if not novos_aditamentos.empty:
        novos_aditamentos["Cód_Contrato"] = novos_aditamentos["Cód_Contrato"].map(mapa_ids)
    return (
        pd.concat([contratos, novos_contratos], ignore_index=True),
        pd.concat([aditamentos, novos_aditamentos], ignore_index=True),
    )


def _atualizar_contratos_e_pagamentos(contratos, pagamentos, data_anterior, config):
    resultado = contratos.copy()
    fim = pd.to_datetime(resultado["Vigência Fim"], errors="coerce").dt.date
    ativos_vencidos = resultado["Status"].eq("Ativo") & fim.lt(config.data_referencia)
    resultado.loc[ativos_vencidos, "Status"] = "Vencido"
    proximo_id = _proximo_numero(pagamentos, "Cód_Pagamento", "PAG")
    eventos = []
    for indice, contrato in resultado.iterrows():
        if contrato["Status"] != "Ativo" or random.random() > config.probabilidade_novos_pagamentos:
            continue
        saldo = round(float(contrato["Saldo"]), 2)
        if saldo <= 0:
            continue
        valor = round(min(saldo, max(float(contrato["Valor_Total"]) * random.uniform(0.02, 0.10), 0.01)), 2)
        if valor <= 0:
            continue
        resultado.loc[indice, "Saldo"] = round(saldo - valor, 2)
        eventos.append(
            {
                "Cód_Contrato": contrato["Cód_Contrato"],
                "CNPJ": contrato["CNPJ"],
                "Fornecedor": contrato["Fornecedor"],
                "Cód_Pagamento": f"PAG{proximo_id:08d}",
                "Data_Pagamento": config.data_referencia.isoformat(),
                "Valor_Pago": valor,
                "Centro_Custo": "CC-001",
                "Categoria": contrato["Escopo"],
            }
        )
        proximo_id += 1
    if eventos:
        pagamentos = pd.concat([pagamentos, pd.DataFrame(eventos)], ignore_index=True)
    return resultado, pagamentos


def atualizar_snapshot(caminho_manifesto, config, raw_dir=None, snapshot_id=None):
    """Cria um snapshot filho completo, preservando todo o RAW do pai."""
    caminho_manifesto = Path(caminho_manifesto)
    pai = carregar_manifesto(caminho_manifesto)
    data_pai = date.fromisoformat(pai["as_of_date"])
    validar_config(config, data_pai)
    if config.seed is not None:
        random.seed(config.seed)
    fontes = carregar_fontes(pai, caminho_manifesto.parent)
    existentes = set(fontes["empresas"]["CNPJ"].astype(str))
    quantidade_nova = round(len(fontes["empresas"]) * config.probabilidade_novos_fornecedores)
    empresas_novas = _empresas_novas(quantidade_nova, existentes)
    if not empresas_novas.empty:
        fontes["empresas"] = pd.concat([fontes["empresas"], empresas_novas], ignore_index=True)
    fontes["homologacoes_risco"] = _atualizar_riscos(
        fontes["homologacoes_risco"], empresas_novas, config
    )
    fontes["contratos"], fontes["aditamentos"] = _anexar_contratos_novos(
        fontes["contratos"], fontes["aditamentos"], empresas_novas,
        fontes["homologacoes_risco"], config
    )
    fontes["contratos"], fontes["pagamentos"] = _atualizar_contratos_e_pagamentos(
        fontes["contratos"], fontes["pagamentos"], data_pai, config
    )
    _validar_integridade(fontes)
    snapshot_id = novo_snapshot_id(snapshot_id)
    raw_dir = raw_dir or caminho_manifesto.parents[2]
    parametros = asdict(config)
    parametros["data_referencia"] = config.data_referencia.isoformat()
    arquivo, manifesto = gravar_snapshot(
        fontes,
        raw_dir=raw_dir,
        scenario_id=pai["scenario_id"],
        snapshot_id=snapshot_id,
        data_referencia=config.data_referencia,
        parent_snapshot_id=pai["snapshot_id"],
        parametros=parametros,
        tipo="update",
    )
    return {"arquivo_manifesto": arquivo, "manifesto": manifesto}


def _validar_integridade(fontes):
    contratos = set(fontes["contratos"]["Cód_Contrato"])
    empresas = set(fontes["empresas"]["CNPJ"].astype(str))
    if not set(fontes["contratos"]["CNPJ"].astype(str)).issubset(empresas):
        raise RawSnapshotError("Há contratos sem fornecedor no snapshot.")
    for nome, coluna in [("aditamentos", "Cód_Contrato"), ("pagamentos", "Cód_Contrato")]:
        if not set(fontes[nome][coluna]).issubset(contratos):
            raise RawSnapshotError(f"Há {nome} sem contrato no snapshot.")
    for nome, coluna in [("empresas", "CNPJ"), ("contratos", "Cód_Contrato"), ("pagamentos", "Cód_Pagamento")]:
        if fontes[nome][coluna].duplicated().any():
            raise RawSnapshotError(f"Há identificadores duplicados em {nome}: {coluna}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-manifest", required=True)
    parser.add_argument("--data-referencia", required=True, type=date.fromisoformat)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--probabilidade-novos-fornecedores", type=float, default=0.10)
    parser.add_argument("--probabilidade-novos-contratos", type=float, default=0.50)
    parser.add_argument("--probabilidade-novos-pagamentos", type=float, default=0.75)
    parser.add_argument("--probabilidade-reavaliacao-risco", type=float, default=0.50)
    argumentos = parser.parse_args()
    resultado = atualizar_snapshot(
        argumentos.from_manifest,
        RawUpdateConfig(
            data_referencia=argumentos.data_referencia,
            seed=argumentos.seed,
            probabilidade_novos_fornecedores=argumentos.probabilidade_novos_fornecedores,
            probabilidade_novos_contratos=argumentos.probabilidade_novos_contratos,
            probabilidade_novos_pagamentos=argumentos.probabilidade_novos_pagamentos,
            probabilidade_reavaliacao_risco=argumentos.probabilidade_reavaliacao_risco,
        ),
    )
    print(f"Manifesto RAW: {resultado['arquivo_manifesto']}")


if __name__ == "__main__":
    main()
