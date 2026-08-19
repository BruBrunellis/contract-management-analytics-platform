"""Contratos e utilitários para snapshots RAW versionados por cenário."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

TIMEZONE = ZoneInfo("America/Sao_Paulo")
MANIFEST_VERSION = "1.0"
SOURCE_FILENAMES = {
    "empresas": "empresas_{snapshot_id}.csv",
    "homologacoes_risco": "homologacoes_risco_{snapshot_id}.csv",
    "contratos": "contratos_ficticios_{snapshot_id}.csv",
    "aditamentos": "aditamentos_{snapshot_id}.csv",
    "pagamentos": "spending_ficticio_{snapshot_id}.csv",
}


class RawSnapshotError(ValueError):
    """Indica manifesto ou transição RAW inválidos."""


def novo_snapshot_id(valor=None):
    """Normaliza ou cria um identificador temporal de snapshot."""
    if valor:
        return str(valor)
    return datetime.now(TIMEZONE).strftime("%Y%m%d_%H%M%S")


def diretorio_snapshot(raw_dir, scenario_id, snapshot_id):
    return Path(raw_dir) / str(scenario_id) / str(snapshot_id)


def sha256_arquivo(arquivo):
    digest = hashlib.sha256()
    with Path(arquivo).open("rb") as origem:
        for bloco in iter(lambda: origem.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _data_iso(valor):
    return valor.isoformat() if isinstance(valor, (date, datetime)) else str(valor)


def gravar_snapshot(
    fontes,
    *,
    raw_dir,
    scenario_id,
    snapshot_id,
    data_referencia,
    parent_snapshot_id=None,
    parametros=None,
    tipo="initial",
):
    """Materializa fontes completas e o manifesto imutável de um snapshot."""
    snapshot_dir = diretorio_snapshot(raw_dir, scenario_id, snapshot_id)
    if snapshot_dir.exists():
        raise RawSnapshotError(f"O snapshot já existe e não pode ser sobrescrito: {snapshot_dir}.")
    snapshot_dir.mkdir(parents=True)

    arquivos = {}
    for nome, padrao in SOURCE_FILENAMES.items():
        if nome not in fontes:
            raise RawSnapshotError(f"Fonte obrigatória ausente no snapshot: {nome}.")
        arquivo = snapshot_dir / padrao.format(snapshot_id=snapshot_id)
        fontes[nome].to_csv(arquivo, index=False, encoding="utf-8-sig")
        arquivos[nome] = {
            "path": arquivo.name,
            "row_count": len(fontes[nome]),
            "sha256": sha256_arquivo(arquivo),
        }

    manifesto = {
        "manifest_version": MANIFEST_VERSION,
        "scenario_id": str(scenario_id),
        "snapshot_id": str(snapshot_id),
        "parent_snapshot_id": parent_snapshot_id,
        "snapshot_type": tipo,
        "as_of_date": _data_iso(data_referencia),
        "created_at": datetime.now(TIMEZONE).isoformat(),
        "parameters": parametros or {},
        "sources": arquivos,
    }
    arquivo_manifesto = snapshot_dir / "raw_manifest.json"
    arquivo_manifesto.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")
    return arquivo_manifesto, manifesto


def carregar_manifesto(caminho_manifesto, validar_hash=True):
    """Carrega e valida os artefatos declarados, sem procurar arquivos por glob."""
    caminho_manifesto = Path(caminho_manifesto)
    dados = json.loads(caminho_manifesto.read_text(encoding="utf-8"))
    campos = {"scenario_id", "snapshot_id", "as_of_date", "sources"}
    ausentes = campos.difference(dados)
    if ausentes:
        raise RawSnapshotError(f"Manifesto sem campos obrigatórios: {', '.join(sorted(ausentes))}.")
    for nome in SOURCE_FILENAMES:
        if nome not in dados["sources"]:
            raise RawSnapshotError(f"Manifesto sem a fonte obrigatória: {nome}.")
        arquivo = caminho_manifesto.parent / dados["sources"][nome]["path"]
        if not arquivo.exists():
            raise RawSnapshotError(f"Arquivo declarado não encontrado: {arquivo}.")
        if validar_hash and dados["sources"][nome].get("sha256") != sha256_arquivo(arquivo):
            raise RawSnapshotError(f"Checksum divergente para a fonte {nome}: {arquivo}.")
    return dados


def carregar_fontes(manifesto, diretorio_manifesto):
    """Lê todas as fontes completas declaradas por um manifesto validado."""
    diretorio_manifesto = Path(diretorio_manifesto)
    dtypes = {
        "empresas": {"CNPJ": "string", "CNPJ8": "string", "CNPJ_Matriz": "string"},
        "homologacoes_risco": {"Id_Avaliacao_Risco": "string", "CNPJ": "string"},
        "contratos": {"Cód_Contrato": "string", "CNPJ": "string"},
        "aditamentos": {"Cód_Contrato": "string"},
        "pagamentos": {"Cód_Pagamento": "string", "Cód_Contrato": "string", "CNPJ": "string"},
    }
    return {
        nome: pd.read_csv(diretorio_manifesto / metadados["path"], dtype=dtypes.get(nome))
        for nome, metadados in manifesto["sources"].items()
    }
