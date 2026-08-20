# Contratos técnicos da camada Curated

## `dim_supplier`

Grão: um fornecedor legal por CNPJ válido da `stg_empresas`.

| Campo | Regra |
|---|---|
| `supplier_key` | Chave substituta determinística: `SUP-<cnpj>`. |
| `supplier_cnpj` | Chave natural legal, com 14 dígitos. |
| `supplier_cnpj8`, `economic_group_key` | Relacionamento com o grupo econômico. |
| `parent_supplier_key` | Nulo para matriz e chave da matriz para filial. |
| `parent_supplier_cnpj` | CNPJ legal da matriz declarada na fonte. |
| Atributos descritivos | Razão social, hierarquia, porte, atividade e perfil corporativo. |

## `dim_economic_group`

Grão: um grupo econômico por raiz CNPJ8 válida.

| Campo | Regra |
|---|---|
| `economic_group_key` | Chave substituta determinística: `GRP-<cnpj8>`. |
| `economic_group_cnpj8` | Raiz econômica de oito dígitos. |
| `matrix_supplier_key` | Fornecedor legal da matriz que representa o grupo. |
| `economic_group_legal_name` | Razão social da matriz. |

Os registros que não permitem resolver uma matriz única, uma relação filial/matriz ou as chaves CNPJ/CNPJ8 são gravados em `1.data/3.curated/exceptions/dim_supplier_resolution_exceptions_<lote>.parquet`, com `curated_validation_errors`. As dimensões contêm somente registros resolvidos e preservam a linhagem da staging de origem.

## `dim_calendar`

Grão: um dia por linha, entre a menor e a maior data de negócio encontrada nas stagings de contratos, aditamentos, pagamentos e homologações do lote. As datas de carga também participam da cobertura.

| Campo | Regra |
|---|---|
| `calendar_key` | Chave substituta determinística no formato `AAAAMMDD`. |
| `calendar_date` | Data civil correspondente à chave. |
| Atributos temporais | Ano, semestre, trimestre, mês, semana ISO e dia. |
| Atributos de agregação | `year_month`, `year_quarter`, nomes de mês e dia. |
| Indicadores | Fim de semana, início/fim de mês e início/fim de ano. |

As futuras fatos devem referenciar `calendar_key` para cada uma de suas datas de evento.

## `dim_category`

Grão: uma categoria técnica distinta de `contract_category` ou `payment_category`.

| Campo | Regra |
|---|---|
| `category_key` | Chave substituta determinística: `CAT-<category_code>`. |
| `category_code` | Código técnico normalizado presente no staging. |
| `category_name` | Rótulo legível da categoria. |
| `category_macro_group` | Nível mais macro: `capex_focused`, `opex_focused` ou `nao_classificada`. |
| `category_group`, `category_family` | Segundo e terceiro níveis da taxonomia. |
| `is_taxonomy_mapped` | Indica se a categoria foi classificada pela taxonomia conhecida. |

Contratos e pagamentos que tenham o mesmo código técnico devem usar a mesma `category_key`. Categorias fora da taxonomia permanecem publicadas, mas recebem `nao_classificada` nos três níveis hierárquicos.

## `dim_contract`

Grão: um contrato resolvido por `contract_id` da `stg_contratos`.

| Campo | Regra |
|---|---|
| `contract_key` | Chave substituta determinística: `CON-<contract_id>`. |
| `supplier_key`, `economic_group_key`, `category_key` | Chaves obrigatórias das dimensões de referência. |
| Chaves de vigência e risco | Referências a `dim_calendar`; a avaliação de risco pode ser nula. |
| Valores contratuais | Valores original, total e saldo em precisão decimal. |

Contratos sem fornecedor, categoria ou data resolvida são gravados em `dim_contract_resolution_exceptions_<lote>.parquet` e não integram a dimensão.

## `fact_spending`

Grão: um pagamento por `payment_id` da `stg_pagamentos`.

| Campo | Regra |
|---|---|
| `spending_key` | Chave determinística: `SPN-<payment_id>`. |
| `contract_key`, `supplier_key`, `economic_group_key`, `category_key` | Chaves obrigatórias e validadas contra o contrato e dimensões. |
| `payment_calendar_key` | Referência obrigatória à data do pagamento. |
| `cost_center`, `payment_value` | Dimensão degenerada e medida monetária decimal. |

Pagamentos sem contrato publicado ou sem outra chave obrigatória são gravados em `fact_spending_exceptions_<lote>.parquet`, com `curated_validation_errors`. O manifesto reconcilia contagem e valor entre staging, fato e exceções.

## `fact_rfi`

Grão: um evento de homologação e risco por `risk_assessment_id`.

| Campo | Regra |
|---|---|
| `rfi_key` | Chave determinística: `RFI-<risk_assessment_id>`. |
| `supplier_key`, `economic_group_key` | Referências obrigatórias ao fornecedor avaliado. |
| Chaves de calendário | Avaliação obrigatória; aprovação e expiração podem ser nulas. |
| Atributos de risco | Resultado/status de homologação, riscos, rating e indicadores. |

Eventos sem fornecedor ou data de avaliação resolvida são gravados em `fact_rfi_exceptions_<lote>.parquet`.

## `fact_supplier_financial`

Grão: um fornecedor legal por ano fiscal disponível na `stg_empresas`.

| Campo | Regra |
|---|---|
| `financial_snapshot_key` | Chave determinística: `FIN-<cnpj>-<ano>`. |
| `supplier_key`, `economic_group_key` | Referências obrigatórias à entidade legal e ao grupo econômico. |
| `financial_period_calendar_key` | Referência ao encerramento do ano fiscal. |
| Medidas financeiras | Faturamento, custos, folha, lucro bruto, juros da dívida e lucro líquido. |

Cada combinação fornecedor-ano é publicada ou isolada em
`fact_supplier_financial_exceptions_<lote>.parquet`. A fato não agrega matriz e
filiais: suas medidas são analisadas no CNPJ legal de origem.

## `fact_renewal`

Grão: um evento de aditamento por `amendment_id`, incluindo renovações e aportes.

| Campo | Regra |
|---|---|
| `renewal_key` | Chave determinística: `RNL-<amendment_id>`. |
| `is_renewal` | Verdadeiro somente para `amendment_type = renovacao`. |
| Chaves de contrato | `contract_key`, fornecedor, grupo e categoria resolvidos por `dim_contract`. |
| Chaves de calendário | Vigência inicial e final do evento. |
| `amendment_value` | Valor monetário decimal do evento. |

Eventos sem contrato ou datas resolvidas são gravados em `fact_renewal_exceptions_<lote>.parquet`. O manifesto confirma que cada registro staging foi publicado ou isolado em exceção.
