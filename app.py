import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="Controle TRE - GOE", page_icon="🎟️", layout="wide")
st.title("🎟️ Sistema Web - Controle de Folgas TRE (Método PEPS)")

from funcoes import inicializar_bancos, salvar_dados, gerar_pdf_certidao, gerar_pdf_lista_geral

df_servidores, df_declaracoes, df_folgas = inicializar_bancos()

if not df_servidores.empty:
    df_servidores['Nome'] = df_servidores['Nome'].astype(str).str.upper()

opcao = st.sidebar.selectbox("Menu Principal", ["Painel de Saldos", "Gerenciar Servidores", "Lançar Declaração (Crédito)", "Registrar Folga (Débito)", "Ajustes do Sistema ⚙️"])

# 1. PAINEL DE SALDOS
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
        
        # AJUSTE DA NUMERAÇÃO: Força o índice da tabela a começar em 1 em vez de 0
        df_resumo.index = df_resumo.index + 1
        
        busca = st.text_input("Buscar Servidor pelo Nome ou CPF").strip().upper()
        if busca:
            df_resumo = df_resumo[df_resumo['Nome'].str.contains(busca, case=False) | df_resumo['CPF'].str.contains(busca)]
        st.dataframe(df_resumo, use_container_width=True)
        
        st.write("#### 💾 Exportar Relação de Todos os Saldos")
        col_btn1, col_btn2, _ = st.columns(3)
        
        with col_btn1:
            csv_data = df_resumo.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="📊 Baixar Lista para Excel (CSV)", data=csv_data, file_name="Lista_Saldos_TRE.csv", mime="text/csv")
            
        with col_btn2:
            if st.button("🖨️ Criar Relatório em PDF"):
                pdf_lista_path = gerar_pdf_lista_geral(df_resumo)
                with open(pdf_lista_path, "rb") as f_lista:
                    st.download_button(label="⬇️ Baixar Lista em PDF", data=f_lista, file_name="Relatorio_Saldos_Geral.pdf", mime="application/pdf")
        
        st.markdown("---")
        st.subheader("🖨️ Emitir Declaração Oficial de Saldo Individual")
        
        col1, col2 = st.columns(2)
        with col1:
            assinante_opcoes = ["Jacques Bras da Silva", "Outro Funcionário / Agente"]
            sel_assinante = st.selectbox("Quem está emitindo este documento?", assinante_opcoes)
            
            if sel_assinante == "Jacques Bras da Silva":
                nome_responsavel = "Jacques Bras da Silva"
                cargo_responsavel = "Gerente de Organização Escolar"
                st.text_input("Cargo do Emissor", value=cargo_responsavel, disabled=True)
            else:
                nome_responsavel = st.text_input("Nome Completo do Emissor").strip().upper()
                cargo_responsavel = st.selectbox("Cargo do Emissor", ["Gerente de Organização Escolar", "Agente de Organização Escolar", "Diretor de Escola"])
        
        with col2:
            servidores_ativos = df_servidores[df_servidores['Status'] == 'Ativo']['Nome'].unique().tolist()
            if servidores_ativos:
                sel_certidao = st.selectbox("Escolha o servidor para gerar a folha em PDF", servidores_ativos)
                cpf_certidao = df_servidores[df_servidores['Nome'] == sel_certidao]['CPF'].values[0]
                saldo_certidao = df_declaracoes[df_declaracoes['CPF'] == cpf_certidao]['Saldo'].sum()
                historico_contrib = df_declaracoes[df_declaracoes['CPF'] == cpf_certidao]
                
                if st.button("Gerar Certidão em PDF"):
                    if not nome_responsavel:
                        st.error("Por favor, preencha o nome do emissor.")
                    else:
                        pdf_path = gerar_pdf_certidao(sel_certidao, cpf_certidao, saldo_certidao, historico_contrib, nome_responsavel, cargo_responsavel)
                        with open(pdf_path, "rb") as pdf_file:
                            st.download_button(label="⬇️ Baixar Declaração para Imprimir", data=pdf_file, file_name=f"Certidao_TRE_{cpf_certidao}.pdf", mime="application/pdf")
            else:
                st.warning("Nenhum funcionário ativo disponível.")

# 2. GERENCIAR SERVIDORES
elif opcao == "Gerenciar Servidores":
    st.subheader("👥 Rotatividade de Funcionários")
    with st.expander("➕ Cadastrar Novo Servidor"):
        n_cpf = st.text_input("CPF (Apenas números)").strip()
        n_nome = st.text_input("Nome Completo").strip().upper()
        if st.button("Salvar Registro"):
            if n_cpf and n_nome:
                if n_cpf in df_servidores['CPF'].values:
                    st.error("Este CPF já está cadastrado!")
                else:
                    nova = pd.DataFrame([{'CPF': n_cpf, 'Nome': n_nome, 'Status': 'Ativo'}])
                    df_servidores = pd.concat([df_servidores, nova], ignore_index=True)
                    salvar_dados(df_servidores, df_declaracoes, df_folgas)
                    st.success(f"{n_nome} cadastrado com sucesso!")
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
        func_opcoes = ativos['Nome'].unique().tolist()
        func = st.selectbox("Selecione o Servidor", func_opcoes)
        cpf_func = ativos[ativos['Nome'] == func]['CPF'].values[0]
        data_e = st.date_input("Data da Eleição")
        qtd = st.selectbox("Dias de Direito", [2, 4])
        if st.button("Gravar Crédito"):
            data_formatada = data_e.strftime("%d/%m/%Y")
            nova = pd.DataFrame([{'CPF': cpf_func, 'Data_Eleicao': data_formatada, 'Direito': int(qtd), 'Saldo': int(qtd)}])
            df_declaracoes = pd.concat([df_declaracoes, nova], ignore_index=True)
            salvar_dados(df_servidores, df_declaracoes, df_folgas)
            st.success("Crédito gravado!")

# 4. REGISTRAR FOLGA
elif opcao == "Registrar Folga (Débito)":
    st.subheader("➖ Registro de Usufruto de Folga")
    ativos = df_servidores[df_servidores['Status'] == 'Ativo']
    if ativos.empty:
        st.warning("Não há funcionários ativos.")
    else:
        func_opcoes = ativos['Nome'].unique().tolist()
        func = st.selectbox("Selecione o Servidor", func_opcoes)
        cpf_func = ativos[ativos['Nome'] == func]['CPF'].values[0]
        data_f = st.date_input("Data da folga gozada")
        if st.button("Confirmar Baixa de 1 Dia"):
            indices = df_declaracoes[(df_declaracoes['CPF'] == cpf_func) & (df_declaracoes['Saldo'] > 0)].index
            if len(indices) > 0:
                idx_alvo = indices[0]
                df_declaracoes.at[idx_alvo, 'Saldo'] -= 1
                data_formatada = data_f.strftime("%d/%m/%Y")
                nova = pd.DataFrame([{'CPF': cpf_func, 'Data_Folga': data_formatada}])
                df_folgas = pd.concat([df_folgas, nova], ignore_index=True)
                salvar_dados(df_servidores, df_declaracoes, df_folgas)
                st.success("Folga debitada do direito mais antigo!")
                st.rerun()
            else:
                st.error("Este servidor não possui saldo disponível.")

# 5. AJUSTES DO SISTEMA
elif opcao == "Ajustes do Sistema ⚙️":
    st.subheader("🛠️ Área Administrativa (Edição de Lançamentos)")
    senha = st.text_input("Digite a senha master para liberar as tabelas", type="password")
    
    if senha == "clovis":
        st.success("Acesso Liberado! Use o formato DD/MM/AAAA para alterar as datas.")
        
        config_colunas_dec = {"Data_Eleicao": st.column_config.TextColumn("Data_Eleicao")}
        config_colunas_fol = {"Data_Folga": st.column_config.TextColumn("Data_Folga")}
        
        edt_s = st.data_editor(df_servidores, num_rows="dynamic", key="ed_s")
        edt_d = st.data_editor(df_declaracoes, num_rows="dynamic", column_config=config_colunas_dec, key="ed_d")
        edt_f = st.data_editor(df_folgas, num_rows="dynamic", column_config=config_colunas_fol, key="ed_f")
        
        if st.button("💾 Salvar Todas as Alterações"):
            if not edt_s.empty:
                edt_s['Nome'] = edt_s['Nome'].astype(str).str.upper()
                
            salvar_dados(edt_s, edt_d, edt_f)
            st.success("Todos os arquivos foram updated com sucesso!")
            st.rerun()
    elif senha != "":
        st.error("Senha incorreta. Acesso negado.")
# 5. AJUSTES DO SISTEMA
elif opcao == "Ajustes do Sistema ⚙️":
    st.subheader("🛠️ Área Administrativa (Edição de Lançamentos)")
    senha = st.text_input("Digite a senha master para liberar as tabelas", type="password")
    
    if senha == "clovis":
        st.success("Acesso Liberado! Use o formato DD/MM/AAAA para alterar as datas.")
        
        config_colunas_dec = {"Data_Eleicao": st.column_config.TextColumn("Data_Eleicao")}
        config_colunas_fol = {"Data_Folga": st.column_config.TextColumn("Data_Folga")}
        
        edt_s = st.data_editor(df_servidores, num_rows="dynamic", key="ed_s")
        edt_d = st.data_editor(df_declaracoes, num_rows="dynamic", column_config=config_colunas_dec, key="ed_d")
        edt_f = st.data_editor(df_folgas, num_rows="dynamic", column_config=config_colunas_fol, key="ed_f")
        
        if st.button("💾 Salvar Todas as Alterações"):
            if not edt_s.empty:
                edt_s['Nome'] = edt_s['Nome'].astype(str).str.upper()
                
            salvar_dados(edt_s, edt_d, edt_f)
            st.success("Todos os arquivos foram atualizados com sucesso!")
            st.rerun()
    elif senha != "":
        st.error("Senha incorreta. Acesso negado.")

# --- INFORMAÇÕES DE VERSÃO E AUTORIA (RODAPÉ DA BARRA LATERAL) ---
st.sidebar.markdown("---")
st.sidebar.caption("🌐 **Informações do Sistema**")
st.sidebar.caption("• **Versão:** 1.1.0 (LGPD Protegida)")
st.sidebar.caption("• **Ano de Lançamento:** 2026")
st.sidebar.caption("• **Idealização e Gestão:** Jacques Bras da Silva")
st.sidebar.caption("• **Unidade:** E.E. Clovis de Lucca")

# Botão de Logoff na barra lateral para fechar o sistema após o uso
if st.sidebar.button("Sair do Sistema 🔒"):
    st.session_state.autenticado = False
    st.rerun()

