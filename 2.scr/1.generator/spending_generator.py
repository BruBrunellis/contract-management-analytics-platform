from datetime import datetime
import pandas as pd
from dateutil.relativedelta import relativedelta

# 1. Carregar a tabela de contratos fictícios gerada na etapa anterior
df_contratos = pd.read_csv(r'C:\Users\bvbbr\OneDrive\Portfolio\Contract Management Platform\1.data\1.raw\contratos_ficticios.csv')
df_contratos['Vigência Inicio'] = pd.to_datetime(
    df_contratos['Vigência Inicio']
)
df_contratos['Vigência Fim'] = pd.to_datetime(df_contratos['Vigência Fim'])

# Data limite de corte para pagamentos (hoje)
HOJE = datetime(2026, 7, 24)

spending_rows = []
pagamento_id = 1

for _, row in df_contratos.iterrows():
  cod_contrato = row['Cód_Contrato']
  cnpj = row['CNPJ']
  fornecedor = row['Fornecedor']
  valor_total = float(row['Valor_Total'])
  saldo = float(row['Saldo'])
  status = row['Status']
  inicio = row['Vigência Inicio']
  fim = row['Vigência Fim']

  # 2. Mapeamento das datas mensais de vigência do contrato
  i = 0
  datas_vigencia = []
  while True:
    p_date = inicio + relativedelta(months=i)
    if p_date > fim:
      break
    datas_vigencia.append(p_date)
    i += 1

  n_total_meses = len(datas_vigencia)
  if n_total_meses == 0:
    n_total_meses = 1
    datas_vigencia = [inicio]

  # 3. Lógica para Contratos VENCIDOS
  if status == 'Vencido':
    payment_dates = datas_vigencia
    n_pagamentos = len(payment_dates)

    # Total consumido é estritamente Valor_Total - Saldo
    valor_consumido = max(0.0, round(valor_total - saldo, 2))
    parcela_media = round(valor_consumido / n_pagamentos, 2)

    valores = [parcela_media] * n_pagamentos
    # Ajuste do último pagamento para eliminar diferenças de arredondamento de centavos
    diferenca = round(valor_consumido - sum(valores), 2)
    valores[-1] = round(valores[-1] + diferenca, 2)

    for p_date, p_valor in zip(payment_dates, valores):
      cod_pag = f'PAG{pagamento_id:08d}'
      pagamento_id += 1
      spending_rows.append({
          'Cód_Contrato': cod_contrato,
          'CNPJ': cnpj,
          'Fornecedor': fornecedor,
          'Cód_Pagamento': cod_pag,
          'Data_Pagamento': p_date.strftime('%Y-%m-%d'),
          'Valor_Pago': p_valor,
      })

  # 4. Lógica para Contratos ATIVOS
  else:
    # Pagamentos realizados apenas até HOJE (24/07/2026)
    payment_dates = [d for d in datas_vigencia if d <= HOJE]

    if len(payment_dates) > 0:
      # Parcela base calculada pela divisão do Valor_Total pelos meses totais previstos
      parcela_base = round(valor_total / n_total_meses, 2)

      for p_date in payment_dates:
        cod_pag = f'PAG{pagamento_id:08d}'
        pagamento_id += 1
        spending_rows.append({
            'Cód_Contrato': cod_contrato,
            'CNPJ': cnpj,
            'Fornecedor': fornecedor,
            'Cód_Pagamento': cod_pag,
            'Data_Pagamento': p_date.strftime('%Y-%m-%d'),
            'Valor_Pago': parcela_base,
        })

# 5. Criação do DataFrame e exportação
df_spending = pd.DataFrame(spending_rows)
df_spending.to_csv(r'C:\Users\bvbbr\OneDrive\Portfolio\Contract Management Platform\1.data\1.raw\spending_ficticio.csv', index=False, encoding='utf-8-sig')

print(f'Tabela gerada com {len(df_spending)} lançamentos de pagamentos.')