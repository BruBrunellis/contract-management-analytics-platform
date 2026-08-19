# Snapshots RAW e execuções ETL

## Conceitos

| Campo | Significado |
|---|---|
| `scenario_id` | Linha evolutiva de dados fictícios. |
| `snapshot_id` | Estado completo das fontes RAW em uma data de referência. |
| `pipeline_run_id` | Tentativa isolada de executar staging e curated para um snapshot. |

Cada snapshot fica em `1.data/1.raw/<scenario_id>/<snapshot_id>/` e possui um
`raw_manifest.json`. O manifesto declara os arquivos, contagens, hashes SHA-256,
parâmetros, data de referência e, quando aplicável, o snapshot-pai.

Snapshots são imutáveis: `update_raw.py` sempre escreve um novo diretório e nunca
altera o manifesto nem os CSVs de origem.

## Semântica das fontes

- Empresas, contratos e homologações são fotografias completas do estado atual.
- Aditamentos e pagamentos preservam o histórico acumulado de eventos.
- O atualizador mantém identificadores existentes, cria novos IDs sem colisão e
  verifica referências entre fornecedores, contratos, aditamentos e pagamentos.
- Um contrato novo somente é produzido a partir de fornecedores presentes nas
  fontes de risco aprovadas; pagamentos e aditamentos referenciam contratos do
  mesmo snapshot.

## Execução

`generate_raw.py` cria o primeiro snapshot. `update_raw.py` recebe o manifesto de
um snapshot existente e uma data posterior. `run_etl.py` exige `--raw-manifest` e
não usa seleção implícita do arquivo mais recente.

O ETL grava em `1.data/2.staging/<pipeline_run_id>/` e
`1.data/3.curated/<pipeline_run_id>/`. Os arquivos Parquet preservam o `batch_id`
como identificador do snapshot de origem; o `etl_manifest.json` e os relatórios de
qualidade registram também o `pipeline_run_id`.
