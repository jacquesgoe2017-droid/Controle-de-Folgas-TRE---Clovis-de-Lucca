import streamlit as st
import pandas as pd
import os
from datetime import datetime

# Configuração inicial da página
st.set_page_config(page_title="Controle TRE - GOE", page_icon="🎟️", layout="wide")
st.title("🎟️ Sistema Web - Controle de Folgas TRE (Método PEPS)")

# Importando as funções do outro arquivo
from funcoes import inicializar_bancos, salvar_dados, gerar_pdf_certidao

# Inicializa os arquivos de dados (CSV)
df_servidores, df_declaracoes, df_folgas = inicializar_bancos()

# Menu de navegação lateral
opcao = st.sidebar.selectbox("Menu Principal", ["Painel de Saldos", "Gerenciar Servidores", "Lançar Declaração (Crédito)", "Registrar Folga (Débito)"])

# 1. PAINEL DE SALDOS E CERTIDÕES
if opcao == "Painel de Saldos":
    st.subheader("📊 Extrato Geral e Emissão de Documentos")
    if df_servidores.empty:
        st.info("Nenhum servidor cadastrado ainda. Vá no menu 'Gerenciar Servidores'.")
    else:
        resumo = []
        for idx, s in df_servidores.iterrows():
            creditos_totais = df_declaracoes[df_declaracoes['CPF'] == s['CPF']]['Direito'].sum()
            saldo_atual = df_declaracoes[df_declaracoes['CPF'] == s['CPF']]['Saldo'].sum()
            debitos_totais = df_folgas[df_folgas['CPF'] == s['CPF']].shape[0]
            resumo.append({
                'CPF': s['CPF'], 'Nome': s['Nome'], 'Status': s['Status'],
                'Total Conquistado': creditos_totais, 'Total Usufruído': debitos_totais, 'Saldo Disponível': saldo_atual
            })
        df_resumo = pd.DataFrame(resumo)
        busca = st.text_input("Buscar Servidor pelo Nome ou CPF")
        if busca:
            df_resumo = df_resumo[df_resumo['Nome'].str.contains(busca, case=False) | df_resumo['CPF'].str.contains(busca)]
        st.dataframe(df_resumo, use_container_width=True)
        
        st.markdown("---")
        st.subheader("🖨️ Emitir Declaração Oficial de Saldo")
        servidores_ativos = df_servidores[df_servidores['Status'] == 'Ativo']['Nome'].tolist()
        if servidores_ativos:
            sel_certidao = st.selectbox("Escolha o servidor para gerar a folha em PDF", servidores_ativos)
            cpf_certidao = df_servidores[df_servidores['Nome'] == sel_certidao]['CPF'].values[0]
            saldo_certidao = df_declaracoes[df_declaracoes['CPF'] == cpf_certidao]['Saldo'].sum()
            historico_contrib = df_declaracoes[df_declaracoes['CPF'] == cpf_certidao]
            if st.button("Gerar Certidão em PDF"):
                pdf_path = gerar_pdf_certidao(sel_certidao, cpf_certidao, saldo_certidao, historico_contrib)
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(label="⬇️ Baixar Declaração para Imprimir", data=pdf_file, file_name=f"Certidao_TRE_{cpf_certidao}.pdf", mime="application/pdf")
        else:
            st.warning("Nenhum funcionário ativo disponível.")

# 2. GERENCIAR SERVIDORES
elif opcao == "Gerenciar Servidores":
    st.subheader("👥 Rotatividade de Funcionários")
    with st.expander("➕ Cadastrar Novo Servidor"):
        n_cpf = st.text_input("CPF (Apenas números)").strip()
        n_nome = st.text_input("Nome Completo").strip()
        if st.button("Salvar Registro"):
            if n_cpf and n_nome:
                if n_cpf in df_servidores['CPF'].values:
                    st.error("Este CPF já está cadastrado!")
                else:
                    nova = pd.DataFrame([{'CPF': n_cpf, 'Nome': n_nome, 'Status': 'Ativo'}])
                    df_servidores = pd.concat([df_servidores, nova], ignore_index=True)
                    salvar_dados(df_servidores, df_declaracoes, df_folgas)
                    st.success(f"{n_nome} cadastrado!")
                    st.rerun()
            else:
                st.error("Preencha todos os campos.")
                
    st.write("### Painel de Movimentação de Status")
    for idx, row in df_servidores.iterrows():
        c1, c2, c3 = st.columns(3)
        c1.write(f"🏷️ **{row['Nome']}** (CPF: {row['CPF']})")
        c2.write("🟢 Ativo" if row['Status'] == 'Ativo' else "💤 Inativo")
        if row['Status'] == 'Ativo':
            if c3.button("Dormir 💤", key=f"d_{idx}"):
                df_servidores.at[idx, 'Status'] = 'Inativo'
                salvar_dados(df_servidores, df_declaracoes, df_folgas)
                st.rerun()
        else:
            if c3.button("Reativar 🟢", key=f"a_{idx}"):
                df_servidores.at[idx, 'Status'] = 'Ativo'
                salvar_dados(df_servidores, df_declaracoes, df_folgas)
                st.rerun()

# 3. LANÇAR CRÉDITO
elif opcao == "Lançar Declaração (Crédito)":
    st.subheader("➕ Entrada de Novas Declarações")
    ativos = df_servidores[df_servidores['Status'] == 'Ativo']
    if ativos.empty:
        st.warning("Não há funcionários ativos.")
    else:
        func = st.selectbox("Selecione o Servidor", ativos['Nome'].tolist())
        cpf_func = ativos[ativos['Nome'] == func]['CPF'].values[0]
        data_e = st.date_input("Data da Eleição")
        qtd = st.selectbox("Dias de Direito", [2, 4])
        if st.button("Gravar Crédito"):
            nova = pd.DataFrame([{'CPF': cpf_func, 'Data_Eleicao': str(data_e), 'Direito': int(qtd), 'Saldo': int(qtd)}])
            df_declaracoes = pd.concat([df_declaracoes, nova], ignore_index=True).sort_values(by='Data_Eleicao').reset_index(drop=True)
            salvar_dados(df_servidores, df_declaracoes, df_folgas)
            st.success("Crédito gravado!")

# 4. REGISTRAR FOLGA (DÉBITO PEPS)
elif opcao == "Registrar Folga (Débito)":
    st.subheader("➖ Registro de Usufruto de Folga")
    ativos = df_servidores[df_servidores['Status'] == 'Ativo']
    if ativos.empty:
        st.warning("Não há funcionários ativos.")
    else:
        func = st.selectbox("Selecione o Servidor", ativos['Nome'].tolist())
        cpf_func = ativos[ativos['Nome'] == func]['CPF'].values[0]
        data_f = st.date_input("Data da folga gozada")
        if st.button("Confirmar Baixa de 1 Dia"):
            indices = df_declaracoes[(df_declaracoes['CPF'] == cpf_func) & (df_declaracoes['Saldo'] > 0)].index
            if len(indices) > 0:
                df_declaracoes.at[indices[0], 'Saldo'] -= 1
                nova = pd.DataFrame([{'CPF': cpf_func, 'Data_Folga': str(data_f)}])
                df_folgas = pd.concat([df_folgas, nova], ignore_index=True)
                salvar_dados(df_servidores, df_declaracoes, df_folgas)
                st.success("Folga debitada do direito mais antigo!")
                st.rerun()
            else:
                st.error("Este servidor não possui saldo disponível.")
