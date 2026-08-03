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
