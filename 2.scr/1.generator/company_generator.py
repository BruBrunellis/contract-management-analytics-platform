import pandas as pd
import random

def gerar_cnpj_ficticio():
    """Gera uma string no formato padronizado de CNPJ."""
    n = [random.randint(0, 9) for _ in range(8)]
    digitos = f"{random.randint(10, 99)}"
    return f"{n[0]}{n[1]}.{n[2]}{n[3]}{n[4]}.{n[5]}{n[6]}{n[7]}/0001-{digitos}"

def gerar_razao_social():
    """Combina termos para criar nomes de empresas verossímeis."""
    prefixos = ["Alpha", "Beta", "Nexus", "Inovação", "Global", "Vanguarda", "Horizonte", "Prime", "Apex", "Eco", 
    "Quantum", "Nova", "Orion", "Zenith", "Spectra", 
    "Integra", "Altus", "Matrix", "Summit", "Synapse", 
    "Stellar", "Omega", "Vertex", "Titan", "Atlas", 
    "Infinity", "Synergy", "Pulse", "Aegis", "Vektor", "Luanda", "Camargo", "Mendes", "Castelo Brando", "Brado",
    "Cubo", "Equinox", "Vitta", "Estratta", "Safra", "Insper", "Positivo", "Avante", "Ascenty", "Kyndryl", "Sonda"]
    meios = ["Tecnologia", "Serviços", "Comércio", "Inteligência", "Rede", "Logística", "Soluções", "Engenharia", "Consultoria"]
    sufixos = ["Ltda.", "S.A."]
    return f"{random.choice(prefixos)} {random.choice(meios)} {random.choice(sufixos)}"

def gerar_tabela_empresas(qtd=300):
    dados = []
    
    for _ in range(qtd):
        capital = round(random.uniform(50000, 2000000), 2)
        
        # Simula evolução de faturamento ano a ano com variação realista
        fat_2022 = round(capital * random.uniform(1.2, 50.5), 2)
        fat_2023 = round(fat_2022 * random.uniform(0.9, 1.3), 2)
        fat_2024 = round(fat_2023 * random.uniform(0.95, 1.35), 2)
        fat_2025 = round(fat_2024 * random.uniform(0.95, 1.4), 2)
        fat_2026 = round(fat_2025 * random.uniform(0.9, 1.25), 2)

        #Gera custos
        custo_2022 = round(fat_2022 * random.uniform(0.5, 1.5), 2)
        custo_2023 = round(fat_2023 * random.uniform(0.5, 0.8), 2)
        custo_2024 = round(fat_2024 * random.uniform(0.5, 0.8), 2)
        custo_2025 = round(fat_2025 * random.uniform(0.5, 0.8), 2)
        custo_2026 = round(fat_2026 * random.uniform(0.5, 0.8), 2)

        #Gera Lucro Bruto
        lucro_bruto_2022 = round(fat_2022 - custo_2022, 2)
        lucro_bruto_2023 = round(fat_2023 - custo_2023, 2)
        lucro_bruto_2024 = round(fat_2024 - custo_2024, 2)
        lucro_bruto_2025 = round(fat_2025 - custo_2025, 2)
        lucro_bruto_2026 = round(fat_2026 - custo_2026, 2)

        #Gera Dívida
        juros_divida_2022 = round(random.uniform(0.01, 0.05) * fat_2022, 2)
        juros_divida_2023 = round(random.uniform(0.01, 0.05) * fat_2023, 2)
        juros_divida_2024 = round(random.uniform(0.01, 0.05) * fat_2024, 2)
        juros_divida_2025 = round(random.uniform(0.01, 0.05) * fat_2025, 2)
        juros_divida_2026 = round(random.uniform(0.01, 0.05) * fat_2026, 2)

        #Gera Lucro Líquido
        lucro_liquido_2022 = round(lucro_bruto_2022 - juros_divida_2022, 2)
        lucro_liquido_2023 = round(lucro_bruto_2023 - juros_divida_2023, 2)
        lucro_liquido_2024 = round(lucro_bruto_2024 - juros_divida_2024, 2)
        lucro_liquido_2025 = round(lucro_bruto_2025 - juros_divida_2025, 2)
        lucro_liquido_2026 = round(lucro_bruto_2026 - juros_divida_2026, 2)

        #Determina o porte da empresa com base no faturamento
        if fat_2022 < 360000:
            porte = "Microempresa"
        elif fat_2022 < 3600000:
            porte = "Pequeno"
        elif fat_2022 < 10000000:
            porte = "Médio"
        else:
            porte = "Grande"

        #Determina a quantidade de funcionários com base no porte da empresa
        if porte == "Microempresa":
            num_funcionarios = random.randint(1, 9)
        elif porte == "Pequeno":
            num_funcionarios = random.randint(10, 99)
        elif porte == "Médio":
            num_funcionarios = random.randint(100, 999)
        else:
            num_funcionarios = random.randint(1000, 99999)

        num_func_CLT = round(num_funcionarios * random.uniform(0.0, 1.0))
        num_func_PJ = num_funcionarios - num_func_CLT
        num_tot_func = num_func_CLT + num_func_PJ
        num_processos = round(num_funcionarios * random.uniform(0.0, 0.45))

        #Adiciona os dados
        dados.append({
                "CNPJ": gerar_cnpj_ficticio(),
                "Razao_Social": gerar_razao_social(),
                "Capital_Social": capital,
                "Faturamento_2022": fat_2022,
                "Faturamento_2023": fat_2023,
                "Faturamento_2024": fat_2024,
                "Faturamento_2025": fat_2025,
                "Faturamento_2026": fat_2026,
                "Custo_2022": custo_2022,
                "Custo_2023": custo_2023,
                "Custo_2024": custo_2024,
                "Custo_2025": custo_2025,
                "Custo_2026": custo_2026,
                "Lucro_Bruto_2022": lucro_bruto_2022,
                "Lucro_Bruto_2023": lucro_bruto_2023,
                "Lucro_Bruto_2024": lucro_bruto_2024,
                "Lucro_Bruto_2025": lucro_bruto_2025,
                "Lucro_Bruto_2026": lucro_bruto_2026,
                "Juros_Divida_2022": juros_divida_2022,
                "Juros_Divida_2023": juros_divida_2023,
                "Juros_Divida_2024": juros_divida_2024,
                "Juros_Divida_2025": juros_divida_2025,
                "Juros_Divida_2026": juros_divida_2026,
                "Lucro_Liquido_2022": lucro_liquido_2022,
                "Lucro_Liquido_2023": lucro_liquido_2023,
                "Lucro_Liquido_2024": lucro_liquido_2024,
                "Lucro_Liquido_2025": lucro_liquido_2025,
                "Lucro_Liquido_2026": lucro_liquido_2026,
                "Porte_Empresa": porte,
                "Num_Func_CLT": num_func_CLT,
                "Num_Func_PJ": num_func_PJ,
                "Num_Total_Func": num_tot_func,
                "Processos_Trabalhistas": num_processos
                })

    return pd.DataFrame(dados)

# 1. Gerar 300 empresas fictícias
df_empresas = gerar_tabela_empresas(qtd=300)

# Exporta CSV
df_empresas.to_csv(
    r"C:\Users\bvbbr\OneDrive\Portfolio\Contract Management Platform\1.data\1.raw\empresas.csv",
    index=False,
    encoding="utf-8-sig"
)

print(df_empresas.head())