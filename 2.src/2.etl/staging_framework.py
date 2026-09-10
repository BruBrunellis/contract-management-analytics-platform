"""Utilitários e convenções compartilhados para transformações RAW → STAGING."""

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pyarrow.parquet as pq

TIMEZONE = ZoneInfo("America/Sao_Paulo")
CONTRACT_VERSION = "1.0"
LINEAGE_COLUMNS = ["source_file", "source_row_number", "load_date", "batch_id"]


class SchemaContractError(ValueError):
    """Indica que uma fonte não atende ao contrato estrutural mínimo."""


def localizar_arquivo_versionado(raw_dir, padrao, descricao):
    """Retorna a versão mais recente de uma fonte RAW pelo padrão informado."""
    arquivos = sorted(Path(raw_dir).glob(padrao))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum arquivo no padrão {padrao} foi encontrado para {descricao}.")
    return arquivos[-1]


def extrair_identificador_lote(arquivo_origem):
    """Extrai ``YYYYMMDD_HHMMSS`` de um arquivo RAW versionado."""
    correspondencia = re.search(r"_(\d{8}_\d{6})\.csv$", Path(arquivo_origem).name)
    if not correspondencia:
        raise SchemaContractError(
            f"Não foi possível extrair o identificador de lote de {Path(arquivo_origem).name}."
        )
    return correspondencia.group(1)


def validar_colunas_obrigatorias(colunas, colunas_obrigatorias, descricao):
    """Falha cedo quando a fonte não possui o contrato estrutural esperado."""
    ausentes = sorted(set(colunas_obrigatorias).difference(colunas))
    if ausentes:
        raise SchemaContractError(f"Fonte {descricao} sem colunas obrigatórias: {', '.join(ausentes)}.")


def adicionar_linhagem(df, arquivo_origem, data_carga=None, identificador_lote=None):
    """Inclui metadados que permitem rastrear cada linha até a fonte RAW."""
    arquivo_origem = Path(arquivo_origem)
    lote = identificador_lote or extrair_identificador_lote(arquivo_origem)
    resultado = df.copy()
    resultado["source_file"] = arquivo_origem.name
    resultado["source_row_number"] = pd.Series(range(2, len(resultado) + 2), dtype="Int64")
    resultado["load_date"] = pd.Timestamp(data_carga or datetime.now(TIMEZONE).date())
    resultado["batch_id"] = pd.Series(lote, index=resultado.index, dtype="string")
    return resultado


def adicionar_erro(erros, mascara, mensagem):
    """Acumula mensagens de validação sem ocultar erros anteriores da mesma linha."""
    erros.loc[mascara] = erros.loc[mascara].map(
        lambda atual: f"{atual}; {mensagem}" if atual else mensagem
    )


def contar_erros(erros):
    """Conta cada regra violada; uma linha pode contribuir para mais de uma regra."""
    contador = Counter()
    for erro in erros.dropna():
        contador.update(mensagem.strip() for mensagem in str(erro).split(";") if mensagem.strip())
    return dict(sorted(contador.items()))


def escrever_parquet(df, arquivo_destino, schema=None):
    """Grava Parquet criando os diretórios necessários e retorna o schema físico."""
    arquivo_destino = Path(arquivo_destino)
    arquivo_destino.parent.mkdir(parents=True, exist_ok=True)
    if schema is None:
        df.to_parquet(arquivo_destino, index=False, engine="pyarrow")
    else:
        import pyarrow as pa

        tabela = pa.Table.from_pandas(df, schema=schema, preserve_index=False, safe=False)
        pq.write_table(tabela, arquivo_destino)
    return [
        {"name": campo.name, "type": str(campo.type), "nullable": campo.nullable}
        for campo in pq.read_schema(arquivo_destino)
    ]


def construir_resultado_staging(
    *,
    tabela,
    arquivo_origem,
    arquivo_staging,
    arquivo_excecoes,
    total_origem,
    total_validos,
    total_invalidos,
    schema,
    erros,
):
    """Devolve o resultado padronizado usado pelo orquestrador e pelo manifesto."""
    return {
        "arquivo_staging": Path(arquivo_staging),
        "arquivo_excecoes": Path(arquivo_excecoes),
        "registros_origem": total_origem,
        "registros_validos": total_validos,
        "registros_invalidos": total_invalidos,
        "manifesto": {
            "table": tabela,
            "contract_version": CONTRACT_VERSION,
            "source_file": Path(arquivo_origem).name,
            "batch_id": extrair_identificador_lote(arquivo_origem),
            "row_counts": {
                "source": total_origem,
                "valid": total_validos,
                "invalid": total_invalidos,
            },
            "schema": schema,
            "validation_error_counts": contar_erros(erros),
        },
    }
