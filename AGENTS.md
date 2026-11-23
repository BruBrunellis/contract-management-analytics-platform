# Condução do projeto

- Consulte a issue no [repositório remoto](https://github.com/BruBrunellis/contract-management-analytics-platform). Confira o objetivo, os critérios de aceite e as dependências antes de começar.
- Use uma branch dedicada por issue, a partir da base atualizada do repositório. Nomeie a branch como `codex/issue-<número>-<descrição-curta>` e reutilize a branch da issue se ela já existir. Preserve as alterações locais do usuário.
- Quando o usuário pedir um plano, divida-o em commits. Para cada commit, indique o objetivo, as mudanças e como validá-las. Agrupe mudanças relacionadas no menor número de commits que permita uma revisão clara. Um único commit é suficiente se a entrega for coesa.
- Ao implementar, mantenha o escopo da issue, execute as verificações pertinentes e apresente o resultado para avaliação local. Abra uma PR somente a pedido do usuário e vincule a issue na descrição.

## Onde buscar contexto

- [README](README.md) para visão geral, setup e comandos. O diretório [`docs/`](docs/) reúne os contratos técnicos e a documentação do projeto.
- [Revisão arquitetural](docs/architecture_review.md), [roadmap](docs/implementation_roadmap.md) e [backlog](docs/implementation_backlog.json) para decisões, etapas e dependências da evolução.
- [Contratos analíticos](docs/analytics_contracts.md) e [dicionário de métricas](docs/metric_dictionary.md) para semântica e fontes dos indicadores. O SQL fica em [`2.src/4.analytics/`](2.src/4.analytics/) e o projeto Power BI em [`3.dashboard/`](3.dashboard/).
