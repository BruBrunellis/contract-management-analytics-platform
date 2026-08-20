"""Recria as views DuckDB a partir de um manifesto ETL aprovado."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
from analytics_framework import (
    caminho_banco_padrao,
    carregar_entrada,
    criar_views_de_fonte,
    registrar_contexto,
)

SQL_DIR = Path(__file__).resolve().parent / "sql"
VIEWS_ESPERADAS = {
    "vw_suppliers",
    "vw_contracts",
    "vw_spending",
    "vw_rfi",
    "vw_renewals",
    "vw_supplier_financials",
    "vw_quality_reconciliation",
    "vw_quality_exceptions",
}


def recriar_views(caminho_manifesto, database_path=None):
    """Cria um banco local e publica todas as views SQL versionadas."""
    entrada = carregar_entrada(caminho_manifesto)
    database_path = Path(database_path) if database_path else caminho_banco_padrao(entrada)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database_path)) as conexao:
        criar_views_de_fonte(conexao, entrada)
        registrar_contexto(conexao, entrada)
        for arquivo_sql in sorted(SQL_DIR.glob("*.sql")):
            conexao.execute(arquivo_sql.read_text(encoding="utf-8"))
        views = {
            linha[0]
            for linha in conexao.execute(
                "SELECT table_name FROM information_schema.views WHERE table_schema = 'main'"
            ).fetchall()
        }
        ausentes = VIEWS_ESPERADAS.difference(views)
        if ausentes:
            raise RuntimeError(f"Views analíticas não publicadas: {', '.join(sorted(ausentes))}.")
    return {"database_path": database_path, "input": entrada, "views": sorted(VIEWS_ESPERADAS)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etl-manifest", required=True)
    parser.add_argument("--database", help="Caminho opcional para o arquivo .duckdb.")
    argumentos = parser.parse_args()
    resultado = recriar_views(argumentos.etl_manifest, argumentos.database)
    print(f"Banco DuckDB: {resultado['database_path']}")
    print(f"Views: {', '.join(resultado['views'])}")


if __name__ == "__main__":
    main()
