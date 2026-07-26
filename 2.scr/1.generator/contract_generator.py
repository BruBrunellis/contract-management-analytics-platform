from datetime import datetime, timedelta
import random
import numpy as np
import pandas as pd

# Define a semente para reprodutibilidade dos dados aleatórios
random.seed(42)
np.random.seed(42)

# 1. Carregamento do arquivo base
df_empresas = pd.read_csv('C:\\Users\\bvbbr\\OneDrive\\Portfolio\\Contract Management Platform\\1.data\\1.raw\\empresas.csv')

# 2. Cálculo do faturamento médio por fornecedor (usando as colunas de faturamento disponíveis)
fatu_cols = [c for c in df_empresas.columns if c.startswith('Faturamento_')]
df_empresas['Media_Faturamento'] = df_empresas[fatu_cols].mean(axis=1)

# Lista de escopos para distribuição aleatória
escopos = [
    'Aquisição de Equipamentos',
    'Consultoria',
    'Licença de Software',
    'Manutenção e Suporte',
    'Outsourcing de TI',
    'Serviços de Logística',
    'Treinamento e Capacitação',
    'Serviços de Infraestrutura',
]


def gerar_tabela_contratos(df_base, data_referencia=datetime(2026, 7, 24)):
  contratos = []
  codigo_counter = 1

  for _, row in df_base.iterrows():
    cnpj = row['CNPJ']
    fornecedor = row['Razao_Social']
    media_fat = row['Media_Faturamento']

    # Premissa: Quantidade de 1 a 5 contratos por fornecedor
    qtd_contratos = random.randint(1, 5)

    for _ in range(qtd_contratos):
      # Cód_Contrato: CS######## único
      cod_contrato = f'CS{codigo_counter:08d}'
      codigo_counter += 1

      # Escopo e Nome do Contrato
      escopo = random.choice(escopos)
      nome_contrato = f'Contrato de {escopo} - {fornecedor.split()[0]}'

      # Vigência: 6 meses a 10 anos (6 a 120 meses)
      duracao_meses = random.randint(6, 120)
      duracao_anos = duracao_meses / 12.0

      # Data inicial aleatória entre 2020 e 2026
      data_inicio_ord = random.randint(
          datetime(2020, 1, 1).toordinal(), datetime(2026, 6, 30).toordinal()
      )
      vigencia_inicio = datetime.fromordinal(data_inicio_ord)
      vigencia_fim = vigencia_inicio + timedelta(
          days=int(duracao_meses * 30.4375)
      )

      # Valor Original: Média Faturamento * (0.01, 0.35)
      fator_orig = random.uniform(0.01, 0.35)
      valor_original = round(media_fat * fator_orig, 2)

      # Lógica de Renovação e Valor Total
      anos_inteiros = int(duracao_anos)

      if anos_inteiros >= 2:
        renovado = random.choice([0, 1])
      else:
        renovado = 0

      if renovado == 1:
        tipo_contrato = 'Contrato Renovado'
        baseline = valor_original
        valor_total_acumulado = valor_original

        # Aplica a regra de renovação ano a ano a partir do 2º ano
        for ano in range(2, anos_inteiros + 1):
          multiplicador = random.uniform(0.5, 2.5)
          novo_valor_ciclo = baseline * multiplicador
          valor_total_acumulado += novo_valor_ciclo
          baseline = novo_valor_ciclo  # Atualiza o baseline para o próximo ciclo

        valor_total = round(valor_total_acumulado, 2)
      else:
        tipo_contrato = 'Novo Contrato'
        valor_total = valor_original

      # Saldo: Valor_Total * (0, 0.9)
      saldo = round(valor_total * random.uniform(0.0, 0.9), 2)

      # Status: Ativo ou Vencido com base na Vigência Fim
      status = 'Vencido' if vigencia_fim < data_referencia else 'Ativo'

      contratos.append({
          'Cód_Contrato': cod_contrato,
          'Nome_Contrato': nome_contrato,
          'CNPJ': cnpj,
          'Fornecedor': fornecedor,
          'Escopo': escopo,
          'Vigência Inicio': vigencia_inicio.strftime('%Y-%m-%d'),
          'Vigência Fim': vigencia_fim.strftime('%Y-%m-%d'),
          'Valor_Original': valor_original,
          'Valor_Total': valor_total,
          'Saldo': saldo,
          'Tipo_Contrato': tipo_contrato,
          'Status': status,
      })

  return pd.DataFrame(contratos)


# Execução do gerador e salvamento em arquivo CSV
df_contratos = gerar_tabela_contratos(df_empresas)
df_contratos.to_csv(r'C:\Users\bvbbr\OneDrive\Portfolio\Contract Management Platform\1.data\1.raw\contratos_ficticios.csv', index=False, encoding='utf-8-sig')

print(f'Tabela gerada com sucesso! Total de contratos: {len(df_contratos)}')
print(df_contratos.head())