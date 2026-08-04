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
