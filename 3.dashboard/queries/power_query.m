// Consultas Power Query aprovadas para o dashboard.
// Crie primeiro o parâmetro de texto AnalyticsDsn = "Contract_analytics".
// Cada expressão abaixo deve ser criada como uma consulta com o nome indicado.

// analytics_run_context
let
    Source = Odbc.DataSource("dsn=" & AnalyticsDsn, [HierarchicalNavigation = true]),
    Main = Source{[Name = "main", Kind = "Schema"]}[Data],
    Result = Main{[Name = "analytics_run_context", Kind = "Table"]}[Data]
in
    Result

// vw_suppliers
let
    Source = Odbc.DataSource("dsn=" & AnalyticsDsn, [HierarchicalNavigation = true]),
    Main = Source{[Name = "main", Kind = "Schema"]}[Data],
    Result = Main{[Name = "vw_suppliers", Kind = "View"]}[Data]
in
    Result

// vw_contracts
let
    Source = Odbc.DataSource("dsn=" & AnalyticsDsn, [HierarchicalNavigation = true]),
    Main = Source{[Name = "main", Kind = "Schema"]}[Data],
    Result = Main{[Name = "vw_contracts", Kind = "View"]}[Data]
in
    Result

// vw_spending
let
    Source = Odbc.DataSource("dsn=" & AnalyticsDsn, [HierarchicalNavigation = true]),
    Main = Source{[Name = "main", Kind = "Schema"]}[Data],
    Result = Main{[Name = "vw_spending", Kind = "View"]}[Data]
in
    Result

// vw_renewals
let
    Source = Odbc.DataSource("dsn=" & AnalyticsDsn, [HierarchicalNavigation = true]),
    Main = Source{[Name = "main", Kind = "Schema"]}[Data],
    Result = Main{[Name = "vw_renewals", Kind = "View"]}[Data]
in
    Result

// vw_rfi
let
    Source = Odbc.DataSource("dsn=" & AnalyticsDsn, [HierarchicalNavigation = true]),
    Main = Source{[Name = "main", Kind = "Schema"]}[Data],
    Result = Main{[Name = "vw_rfi", Kind = "View"]}[Data]
in
    Result

// vw_supplier_financials
let
    Source = Odbc.DataSource("dsn=" & AnalyticsDsn, [HierarchicalNavigation = true]),
    Main = Source{[Name = "main", Kind = "Schema"]}[Data],
    Result = Main{[Name = "vw_supplier_financials", Kind = "View"]}[Data]
in
    Result

// vw_quality_reconciliation
let
    Source = Odbc.DataSource("dsn=" & AnalyticsDsn, [HierarchicalNavigation = true]),
    Main = Source{[Name = "main", Kind = "Schema"]}[Data],
    Result = Main{[Name = "vw_quality_reconciliation", Kind = "View"]}[Data]
in
    Result

// vw_quality_exceptions
let
    Source = Odbc.DataSource("dsn=" & AnalyticsDsn, [HierarchicalNavigation = true]),
    Main = Source{[Name = "main", Kind = "Schema"]}[Data],
    Result = Main{[Name = "vw_quality_exceptions", Kind = "View"]}[Data]
in
    Result
