# Roadmap da evolução arquitetural

Criado em 10/09/2026 a partir de [architecture_review.md](architecture_review.md). As cinco etapas são milestones do repositório GitHub, seguindo o padrão do planejamento original. O milestone Evolucao - AWS permanece separado.

## Fluxo por issue

1. O usuário chama uma issue no chat; verificar o escopo e as dependências antes de iniciar.
2. Criar branch dedicada com prefixo `codex/`, número da issue e descrição curta.
3. Implementar, validar e apresentar o resultado para avaliação local do usuário.
4. Enviar a PR somente após solicitação explícita do usuário; vincular a issue. Criar o planejamento não autoriza implementação, PR ou merge.

Entrada recomendada: [#55 — Inventariar métricas SQL/DAX e versionar o contrato da evolução](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/55). A [#57](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/57) também não possui dependências novas bloqueadoras.

## Etapas e issues

### [Evolução 1 - Contratos e baseline](https://github.com/BruBrunellis/contract-management-analytics-platform/milestone/6)

Consolidar os contratos de métricas e de evolução dos dados antes de substituir o dashboard. Entregas: inventário SQL/DAX, métricas reconciliadas, regras de snapshots e onboarding atual corrigido. Base: architecture_review.md, etapa 1. Concluir quando casos conhecidos validarem carteira ativa, exposição anual, filtros e transições temporais.

| Issue | Entrega | Depende de |
|---|---|---|
| [#55](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/55) | Inventariar métricas SQL/DAX e versionar o contrato da evolução | Nenhuma nova |
| [#56](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/56) | Consolidar métricas SQL e reconciliar carteira ativa, períodos e filtros | [#55](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/55) |
| [#57](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/57) | Definir contrato de atualização de cenários e corrigir o quickstart atual | Nenhuma nova |

### [Evolução 2 - Orquestração e publicação](https://github.com/BruBrunellis/contract-management-analytics-platform/milestone/7)

Entregar operação unificada: pacote Python, atualização de cenários, horizonte financeiro, catálogo e jobs, execução por dependências, publicação DuckDB consistente e menu mestre. Base: architecture_review.md, etapa 2. Concluir quando criar, atualizar e reprocessar chegarem ao DuckDB sem alterar históricos e falhas preservarem a publicação anterior.

| Issue | Entrega | Depende de |
|---|---|---|
| [#58](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/58) | Estruturar pacote Python e configuração reproduzível da plataforma | [#55](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/55), [#57](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/57) |
| [#59](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/59) | Implementar atualização temporal consistente de fornecedores e contratos | [#57](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/57), [#58](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/58) |
| [#60](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/60) | Parametrizar horizonte financeiro em geração, staging e curated | [#57](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/57), [#58](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/58) |
| [#61](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/61) | Criar catálogo de cenários e jobs com exclusão mútua e recuperação | [#58](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/58) |
| [#62](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/62) | Refatorar pipeline em etapas com dependências e reuso rastreável | [#58](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/58), [#61](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/61) |
| [#63](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/63) | Publicar DuckDB versionado com promoção atômica e exportação portátil | [#56](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/56), [#61](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/61), [#62](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/62) |
| [#64](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/64) | Entregar orquestrador mestre com menu e subcomandos de operação | [#59](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/59), [#60](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/60), [#61](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/61), [#62](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/62), [#63](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/63) |

### [Evolução 3 - API e portal inicial](https://github.com/BruBrunellis/contract-management-analytics-platform/milestone/8)

Entregar API Python e portal React/TypeScript com navegação, Visão de Categoria e Dados e execuções. Base: architecture_review.md, etapa 3. Concluir quando o usuário puder consultar e operar o pipeline pelo navegador local, com contexto de publicação e sem ODBC.

| Issue | Entrega | Depende de |
|---|---|---|
| [#65](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/65) | Implementar API Python para consulta analítica e controle de jobs | [#56](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/56), [#61](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/61), [#63](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/63), [#64](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/64) |
| [#66](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/66) | Construir portal TypeScript com navegação e Visão de Categoria | [#65](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/65) |
| [#67](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/67) | Implementar menu de Dados e execuções no portal | [#64](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/64), [#65](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/65), [#66](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/66) |

### [Evolução 4 - Domínios e validação](https://github.com/BruBrunellis/contract-management-analytics-platform/milestone/9)

Migrar Contratos, Spending, Fornecedores e Qualidade e validar o portal integrado. Base: architecture_review.md, etapa 4. Concluir com métricas reconciliadas por filtro, navegação acessível, qualidade das diferentes camadas e recuperação de falhas comprovadas.

| Issue | Entrega | Depende de |
|---|---|---|
| [#68](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/68) | Migrar Contratos e Renovações para o portal | [#56](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/56), [#65](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/65), [#66](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/66) |
| [#69](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/69) | Migrar Spending e concentração de gastos para o portal | [#56](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/56), [#65](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/65), [#66](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/66) |
| [#70](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/70) | Migrar Fornecedores, risco e dependência financeira para o portal | [#56](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/56), [#65](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/65), [#66](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/66) |
| [#71](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/71) | Consolidar qualidade RAW–STAGING–CURATED e criar página de investigação | [#62](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/62), [#63](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/63), [#65](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/65), [#66](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/66) |
| [#72](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/72) | Validar portal integrado, equivalência de métricas e recuperação de falhas | [#67](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/67), [#68](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/68), [#69](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/69), [#70](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/70), [#71](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/71) |

### [Evolução 5 - Distribuição e demonstração](https://github.com/BruBrunellis/contract-management-analytics-platform/milestone/10)

Distribuir release local com frontend compilado, launcher, demonstração pública somente de consulta e documentação final, mantendo Power BI opcional. Base: architecture_review.md, etapa 5. Concluir com teste em ambiente limpo e experiência de consulta sem instalação.

| Issue | Entrega | Depende de |
|---|---|---|
| [#73](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/73) | Empacotar portal local e launcher para instalação em ambiente limpo | [#58](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/58), [#64](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/64), [#67](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/67), [#72](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/72) |
| [#74](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/74) | Preparar demonstração pública somente de consulta com cenário reproduzível | [#63](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/63), [#72](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/72), [#73](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/73) |
| [#75](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/75) | Finalizar onboarding, documentação de operação e Power BI opcional | [#72](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/72), [#73](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/73), [#74](https://github.com/BruBrunellis/contract-management-analytics-platform/issues/74) |

As dependências também estão registradas como referências de issues nos corpos publicados no GitHub. A ordem respeita os pré-requisitos técnicos; issues sem dependência entre si podem ser implementadas em sequência escolhida pelo usuário.

Cada issue contém objetivo, escopo, critérios de aceite, referências e fluxo de trabalho. O arquivo [implementation_backlog.json](implementation_backlog.json) preserva o detalhamento e os IDs remotos para manutenção do planejamento.
