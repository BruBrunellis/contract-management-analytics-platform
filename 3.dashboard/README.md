# Dashboard Power BI

Esta pasta contém os artefatos versionáveis da issue #29 para o dashboard de
gestão de contratos. O arquivo de trabalho será salvo pelo Power BI Desktop
como um Power BI Project (PBIP) nesta pasta, para que o modelo e o relatório
possam ser acompanhados pelo Git.

> O Power BI Desktop é a ferramenta de autoria dos visuais. Não edite
> manualmente os arquivos internos de um PBIP enquanto o relatório estiver
> aberto; use os arquivos desta pasta como fonte das consultas, medidas e
> checklist de validação.

## Pré-requisitos

- Power BI Desktop 64 bits;
- DuckDB ODBC Driver 64 bits instalado;
- DSN de sistema `Contract_analytics`, configurado para o arquivo
  `contract_analytics.duckdb` produzido por `build_analytics.py`;
- parâmetro ODBC `access_mode` configurado como `READ_ONLY` no DSN. Isso permite
  que os processos paralelos de carregamento do Power BI leiam o mesmo banco;
- uma execução analítica construída a partir de um `etl_manifest.json` com
  quality gate aprovado.

Para reduzir o caminho do arquivo em instalações Windows, pode-se usar o
junction local `C:\Users\bvbbr\duckdb` apontando para a pasta do lote
analítico. Esse junction não é parte do repositório.

Para criar o parâmetro de somente leitura em um **DSN de Sistema**, abra o
PowerShell como administrador e execute:

```powershell
reg add "HKLM\SOFTWARE\ODBC\ODBC.INI\Contract_analytics" `
  /v access_mode /t REG_SZ /d READ_ONLY /f
```

Feche o Power BI antes de executar `build_analytics.py`, pois `READ_ONLY`
impede que outro processo regrave o banco enquanto o relatório estiver aberto.

## Criar e salvar o projeto

1. No Power BI Desktop, acesse **Arquivo > Opções e configurações > Opções >
   Recursos de visualização** e habilite **Salvar projeto do Power BI (.pbip)**.
2. Crie um relatório em branco e salve-o como
   `3.dashboard/contract_management_analytics.pbip`.
3. Em **Obter dados > ODBC**, selecione o DSN `Contract_analytics`.
4. No **Navigator**, marque exclusivamente `analytics_run_context` e as views
   `vw_*` listadas no contrato de consumo abaixo. Não marque nenhuma tabela
   `src_*`. Nesta primeira carga, clique em **Carregar**; o arquivo
   `queries/power_query.m` é uma referência versionada das consultas e não
   precisa ser copiado manualmente no Power Query.
5. Modele relacionamentos, crie as medidas em `measures/dashboard_measures.dax`
   e implemente as páginas descritas em `docs/dashboard_specification.md`.
6. Salve o projeto e confirme que os diretórios `.Report` e `.SemanticModel`
   foram criados dentro desta pasta.

O diretório `.pbi` e os arquivos de cache criados pelo Desktop são locais e
ignorados pelo Git.

## Atualizar a fonte

```powershell
python .\2.scr\generate_raw.py
python .\2.scr\run_etl.py
python .\2.scr\4.analytics\build_analytics.py `
  --etl-manifest .\1.data\3.curated\<pipeline_run_id>\etl_manifest.json
```

Em seguida, ajuste o DSN `Contract_analytics` para o novo
`contract_analytics.duckdb` (ou atualize o junction para a nova pasta) e use
**Atualizar** no Power BI Desktop. Valide os resultados com
`validation/dashboard_validation.md` antes de distribuir o relatório.

## Contrato de consumo

O relatório só pode importar:

- `analytics_run_context`;
- `vw_suppliers`, `vw_contracts`, `vw_spending`, `vw_renewals`, `vw_rfi`;
- `vw_supplier_financials`, `vw_quality_reconciliation` e
  `vw_quality_exceptions`.

Não importe Parquets, tabelas `src_*` ou camadas RAW, STAGING e CURATED. As
regras de negócio pertencem às views e aos KPIs SQL; medidas DAX apenas
apresentam agregações compatíveis com elas.
