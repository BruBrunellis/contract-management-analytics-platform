# Contratos técnicos de Staging

## Convenções comuns

Cada transformação RAW → STAGING recebe um CSV versionado, conserva a fonte e produz dois arquivos Parquet: uma saída válida em `1.data/2.staging` e uma saída de exceções em `1.data/2.staging/exceptions`.

Todos os processos aplicam o mesmo contrato de linhagem:

| Campo | Descrição |
|---|---|
| `source_file` | Nome do arquivo RAW consumido. |
| `source_row_number` | Linha física da fonte CSV, incluindo o cabeçalho. |
| `load_date` | Data de execução da carga. |
| `batch_id` | Identificador `YYYYMMDD_HHMMSS` do lote. |

O arquivo de exceções preserva as colunas transformadas e inclui `validation_errors`. Uma linha pode ter vários erros separados por `;`. Erros estruturais — arquivo ausente, CSV ilegível ou coluna obrigatória ausente — interrompem a execução; erros de conteúdo são isolados por registro.

O manifesto registra, por tabela, versão do contrato, arquivo de origem, lote, contagens, schema Parquet e quantidade de violações por regra. As contagens por regra não são mutuamente exclusivas.

## `stg_empresas`

Mantém o contrato de campos existente, agora com a linhagem comum e o resumo de manifesto padronizado. A saída é `stg_empresas_<lote>.parquet` e as exceções são `stg_empresas_invalidas_<lote>.parquet`.

## `stg_contratos`

Grão: um contrato por `contract_id`.

| Campo | Tipo Parquet | Regra principal |
|---|---|---|
| `contract_id` | string | Único; padrão `CS########`. |
| `supplier_cnpj` | string | Obrigatório; 14 dígitos. |
| `contract_name`, `supplier_name` | string | Obrigatórios. |
| `contract_category` | string | Categoria técnica normalizada. |
| `validity_start_date`, `validity_end_date` | date32 | Início não posterior ao fim. |
| `original_value`, `total_value`, `balance_value` | decimal(18,2) | Obrigatórios, não negativos; saldo não supera total. |
| `contract_type` | string | `novo_contrato` ou `contrato_renovado`. |
| `contract_status` | string | `ativo`, `vencido` ou `encerrado`. |
| `risk_evaluation_date` | date32 | Obrigatória para encerrados. |
| `final_risk` | string | Obrigatório. |
| `closure_reason` | string | Obrigatório para encerrados e nulo nos demais. |

A saída é `stg_contratos_<lote>.parquet` e as exceções são `stg_contratos_invalidos_<lote>.parquet`. A validação de referência contra fornecedor será executada na camada curated, para que o staging continue sendo uma representação rastreável e independente de cada fonte.

## `stg_homologacoes_risco`

Grão: uma avaliação anual de risco por `risk_assessment_id`. A staging deriva `supplier_cnpj8` do CNPJ e mantém os campos de homologação, risco, rating e score com nomes técnicos normalizados.

| Campo | Tipo Parquet | Regra principal |
|---|---|---|
| `risk_assessment_id` | string | Único; padrão `RSK#########`. |
| `supplier_cnpj`, `supplier_cnpj8` | string | CNPJ de 14 dígitos e prefixo de 8 dígitos. |
| `assessment_date` | date32 | Obrigatória e válida. |
| `last_approval_date`, `expiration_date` | date32 | Exigidas para homologações aprovadas. |
| `homologation_result` | string | `aprovada` ou `reprovada`. |
| `homologation_status` | string | `ativa`, `expirada` ou `negada`. |
| `financial_risk`, `labor_risk`, `final_risk` | string | `final_risk` é o maior risco componente. |
| `credit_rating` | string | Rating permitido pelo contrato. |
| Campos de score | float64 | Numéricos; índices não negativos quando aplicável. |

Uma homologação aprovada não pode ter risco final alto e precisa de datas de aprovação e expiração. Uma reprovada deve estar negada, com risco alto e sem essas datas. A saída é `stg_homologacoes_risco_<lote>.parquet`; as exceções são `stg_homologacoes_risco_invalidas_<lote>.parquet`.

## `stg_pagamentos`

Grão: um pagamento por `payment_id`. A fonte RAW publica `Centro_Custo` e `Categoria`, definidos deterministicamente pelo escopo do contrato no gerador. A staging deriva `supplier_cnpj8` a partir do CNPJ completo e valida `contract_id` contra os contratos válidos de `stg_contratos` do mesmo lote.

| Campo | Tipo Parquet | Regra principal |
|---|---|---|
| `payment_id` | string | Único; padrão `PAG########`. |
| `contract_id` | string | Obrigatório; deve existir em `stg_contratos`. |
| `supplier_cnpj`, `supplier_cnpj8` | string | CNPJ de 14 dígitos e prefixo de 8 dígitos. |
| `supplier_name` | string | Obrigatório. |
| `payment_date` | date32 | Obrigatória e válida. |
| `payment_value` | decimal(18,2) | Obrigatório e estritamente positivo. |
| `cost_center` | string | Padrão `CC-999`. |
| `payment_category` | string | Obrigatória e normalizada. |

A saída é `stg_pagamentos_<lote>.parquet` e as exceções são `stg_pagamentos_invalidos_<lote>.parquet`.
