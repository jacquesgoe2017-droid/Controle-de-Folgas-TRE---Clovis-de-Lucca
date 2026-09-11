import streamlit as st
import pandas as pd
from datetime import datetime
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

# Arquivos para salvar os dados permanentemente na nuvem
DB_SERVIDORES = "servidores.csv"
DB_DECLARACOES = "declaracoes.csv"
DB_FOLGAS = "folgas.csv"

# Inicialização e Carregamento dos dados
if not os.path.exists(DB_SERVIDORES):
    pd.DataFrame(columns=['CPF', 'Nome', 'Status']).to_csv(DB_SERVIDORES, index=False)
if not os.path.exists(DB_DECLARACOES):
    pd.DataFrame(columns=['CPF', 'Data_Eleicao', 'Direito', 'Saldo']).to_csv(DB_DECLARACOES, index=False)
if not os.path.exists(DB_FOLGAS):
    pd.DataFrame(columns=['CPF', 'Data_Folga']).to_csv(DB_FOLGAS, index=False)

df_servidores = pd.read_csv(DB_SERVIDORES, dtype={'CPF': str})
df_declaracoes = pd.read_csv(DB_DECLARACOES, dtype={'CPF': str})
df_folgas = pd.read_csv(DB_FOLGAS, dtype={'CPF': str})

# Função auxiliar para salvar alterações
def salvar_dados():
    df_servidores.to_csv(DB_SERVIDORES, index=False)
    df_declaracoes.to_csv(DB_DECLARACOES, index=False)
    df_folgas.to_csv(DB_FOLGAS, index=False)

# Função para Gerar o PDF da Certidão de Folgas
def gerar_pdf_certidao(nome, cpf, saldo, historico_creditos):
    filename = "certidao_folgas.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54, title="Certidão de Folgas TRE")
    styles = getSampleStyleSheet()
    
    style_titulo = ParagraphStyle('Titulo', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=18, alignment=TA_CENTER)
    style_corpo = ParagraphStyle('Corpo', parent=styles['Normal'], fontName='Helvetica', fontSize=11, leading=16, alignment=TA_JUSTIFY)
    style_assina = ParagraphStyle('Assina', parent=styles['Normal'], fontName='Helvetica', fontSize=11, leading=16, alignment=TA_CENTER)
    
    story = []
    
    story.append(Paragraph("<b>SECRETARIA DE ESTADO DA EDUCAÇÃO</b>", style_titulo))
    story.append(Paragraph("<b>DIRETORIA DE ENSINO - GESTÃO DE ORGANIZAÇÃO ESCOLAR</b>", style_titulo))
    story.append(Spacer(1, 30))
    
    story.append(Paragraph("<u><b>CERTIDÃO DE LIQUIDAÇÃO DE FOLGAS - TRE</b></u>", style_titulo))
    story.append(Spacer(1, 30))
    
    data_atual = datetime.now().strftime("%d/%m/%Y")
    texto = f"Certifico, para os devidos fins de direito e regularização de prontuário, que o(a) servidor(a) <b>{nome.upper()}</b>, inscrito(a) no CPF sob o nº <b>{cpf}</b>, em exercício nesta unidade escolar, possui nesta data (<b>{data_atual}</b>) o saldo acumulado de <b>{saldo} dia(s) de folga</b> pendente(s) de usufruto, decorrente(s) de convocações pela Justiça Eleitoral (TRE), conforme previsto na legislação vigente."
    story.append(Paragraph(texto, style_corpo))
    story.append(Spacer(1, 15))
    
    texto_detalhe = "O saldo acima descrito é composto pelas seguintes movimentações e direitos ainda disponíveis:"
    story.append(Paragraph(texto_detalhe, style_corpo))
    story.append(Spacer(1, 10))
    
    if len(historico_creditos) == 0 or saldo == 0:
        story.append(Paragraph("- Não há saldo ativo ou créditos pendentes registrados.", style_corpo))
    else:
        for _, row in historico_creditos.iterrows():
            if row['Saldo'] > 0:
                dt_formatada = datetime.strptime(str(row['Data_Eleicao']), "%Y-%m-%d").strftime("%d/%m/%Y") if "-" in str(row['Data_Eleicao']) else str(row['Data_Eleicao'])
                story.append(Paragraph(f"• Eleição em {dt_formatada}: Direito a {row['Direito']} dias | <b>Saldo Restante: {row['Saldo']} dia(s)</b>", style_corpo))
    
    story.append(Spacer(1, 40))
    story.append(Paragraph("Por ser a expressão da verdade, firmo a presente.", style_corpo))
    story.append(Spacer(1, 60))
    
    story.append(Paragraph("____________________________________________", style_assina))
    story.append(Paragraph("<b>Gerência de Organização Escolar</b>", style_assina))
    story.append(Paragraph("Responsável pelo Registro / Controle", style_assina))
    
    doc.build(story)
    return filename

# --- INTERFACE WEB DO STREAMLIT ---
st.set_page_config(page_title="Controle TRE - GOE", page_icon="🎟️", layout="wide")
st.title("🎟️ Sistema Web - Controle de Folgas TRE (Método PEPS)")

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
                'CPF': s['CPF'],
                'Nome': s['Nome'],
                'Status': s['Status'],
                'Total Conquistado': creditos_totais,
                'Total Usufruído': debitos_totais,
                'Saldo Disponível': saldo_atual
            })
        
        df_resumo = pd.DataFrame(resumo)
        
        busca = st.text_input("Buscar Servidor pelo Nome ou CPF")
        if busca:
            df_resumo = df_resumo[df_resumo['Nome'].str.contains(busca, case=False) | df_resumo['CPF'].str.contains(busca)]
            
        st.dataframe(df_resumo, use_container_width=True)
        
        st.markdown("---")
        st.subheader("🖨️ Emitir Declaração Oficial de Saldo")
        servidores_ativos_lista = df_servidores[df_servidores['Status'] == 'Ativo']['Nome'].tolist()
        
        if servidores_ativos_lista:
            sel_certidao = st.selectbox("Escolha o servidor para gerar a folha em PDF", servidores_ativos_lista)
            cpf_certidao = df_servidores[df_servidores['Nome'] == sel_certidao]['CPF'].values[0]
            saldo_certidao = df_declaracoes[df_declaracoes['CPF'] == cpf_certidao]['Saldo'].sum()
            historico_contrib = df_declaracoes[df_declaracoes['CPF'] == cpf_certidao]
            
            if st.button("Gerar Certidão em PDF"):
                pdf_path = gerar_pdf_certidao(sel_certidao, cpf_certidao, saldo_certidao, historico_contrib)
                with open(pdf_path, "rb") as pdf_file:
                    st.download_button(
                        label="⬇️ Baixar Declaração para Imprimir",
                        data=pdf_file,
                        file_name=f"Certidao_TRE_{cpf_certidao}.pdf",
                        mime="application/pdf"
                    )
        else:
            st.warning("Nenhum funcionário ativo disponível para emitir certidão.")

# 2. GERENCIAR SERVIDORES
elif opcao == "Gerenciar Servidores":
    st.subheader("👥 Rotatividade de Funcionários")
    
    with st.expander("➕ Cadastrar Novo Servidor (Admissão / Transferência)"):
        n_cpf = st.text_input("CPF do Funcionário (Apenas números)").strip()
        n_nome = st.text_input("Nome Completo do Funcionário").strip()
        if st.button("Salvar Registro"):
            if n_cpf and n_nome:
                if n_cpf in df_servidores['CPF'].values:
                    st.error("Este CPF já está cadastrado!")
                else:
                    nova_linha = pd.DataFrame([{'CPF': n_cpf, 'Nome': n_nome, 'Status': 'Ativo'}])
                    df_servidores = pd.concat([df_servidores, nova_linha], ignore_index=True)
                    salvar_dados()
                    st.success(f"{n_nome} integrado com sucesso!")
                    st.rerun()
            else:
                st.error("Por favor, preencha todos os campos obrigatórios.")

    st.write("### Painel de Movimentação de Status")
    for idx, row in df_servidores.iterrows():
        c1, c2, c3 = st.columns()
        c1.write(f"🏷️ **{row['Nome']}** (CPF: {row['CPF']})")
        badge = "🟢 Ativo na Escola" if row['Status'] == 'Ativo' else "💤 Inativo (Dormindo)"
        c2.write(badge)
        
        if row['Status'] == 'Ativo':
            if c3.button("Colocar para Dormir 💤", key=f"dormir_{idx}"):
                df_servidores.at[idx, 'Status'] = 'Inativo'
                salvar_dados()
                st.warning(f"{row['Nome']} foi colocado em modo inativo.")
                st.rerun()
        else:
            if c3.button("Reativar na Escola 🟢", key=f"ativar_{idx}"):
                df_servidores.at[idx, 'Status'] = 'Ativo'
                salvar_dados()
                st.success(f"{row['Nome']} foi reativado com sucesso!")
                st.rerun()

# 3. LANÇAR DECLARAÇÃO (CRÉDITO)
elif opcao == "Lançar Declaração (Crédito)":
    st.subheader("➕ Entrada de Novas Declarações do TRE")
    ativos = df_servidores[df_servidores['Status'] == 'Ativo']
    
    if ativos.empty:
        st.warning("Não há nenhum funcionário ativo cadastrado para receber créditos.")
    else:
        func_escolhido = st.selectbox("Selecione o Servidor", ativos['Nome'].tolist())
        cpf_func = ativos[ativos['Nome'] == func_escolhido]['CPF'].values[0]
        
        data_e = st.date_input("Data real da Eleição que ele trabalhou")
        qtd_direito = st.selectbox("Total de dias concedidos nesta folha", [2, 4])
        
        if st.button("Gravar Crédito"):
            nova_dec = pd.DataFrame([{'CPF': cpf_func, 'Data_Eleicao': str(data_e), 'Direito': int(qtd_direito), 'Saldo': int(qtd_direito)}])
            df_declaracoes = pd.concat([df_declaracoes, nova_dec], ignore_index=True)
            df_declaracoes = df_declaracoes.sort_values(by='Data_Eleicao').reset_index(drop=True)
            salvar_dados()
            st.success(f"Crédito de {qtd_direito} dias computado para {func_escolhido}!")

# 4. REGISTRAR FOLGA (DÉBITO COM DESCONTO PEPS)
elif opcao == "Registrar Folga (Débito)":
    st.subheader("➖ Registro de Usufruto de Folga")
    ativos = df_servidores[df_servidores['Status'] == 'Ativo']
    
    if ativos.empty:
        st.warning("Não há funcionários ativos aptos para usufruir folgas.")
    else:
        func_escolhido = st.selectbox("Selecione o Servidor que está tirando folga hoje", ativos['Nome'].tolist())
        cpf_func = ativos[ativos['Nome'] == func_escolhido]['CPF'].values
        data_f = st.date_input("Data do dia da folga gozada")
        
        if st.button("Confirmar Baixa de 1 Dia"):
            indices_direito = df_declaracoes[(df_declaracoes['CPF'] == cpf_func) & (df_declaracoes['Saldo'] > 0)].index
            
            if len(indices_direito) > 0:
                idx_alvo = indices_direito
                df_declaracoes.at[idx_alvo, 'Saldo'] -= 1
                
                nova_folga = pd.DataFrame([{'CPF': cpf_func, 'Data_Folga': str(data_f)}])
                df_folgas = pd.concat([df_folgas, nova_folga], ignore_index=True)
                
                salvar_dados()
                st.success(f"Sucesso! 1 dia foi debitado automaticamente do direito mais antigo de {func_escolhido}.")
                st.rerun()
            else:
                st.error(f"Erro: O servidor {func_escolhido} não possui nenhum saldo disponível no sistema.")
