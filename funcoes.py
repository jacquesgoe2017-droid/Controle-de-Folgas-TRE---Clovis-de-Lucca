import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from datetime import datetime
import os

# --- CONEXÃO COM O SUPABASE ---
def inicializar_conexao():
    """Inicializa a conexão automática com o Supabase utilizando os Secrets oficiais"""
    return st.connection("supabase", type=SupabaseConnection)

# --- INICIALIZAR BANCOS (CARREGAR DO SUPABASE) ---
def inicializar_bancos():
    """Carrega as tabelas do Supabase e converte para DataFrames do Pandas"""
    try:
        supabase = inicializar_conexao()
        
        # 1. Carrega Servidores
        res_servidores = supabase.table("servidores").select("*").execute()
        df_servidores = pd.DataFrame(res_servidores.data)
        if df_servidores.empty:
            df_servidores = pd.DataFrame(columns=["cpf", "nome", "status"])
        else:
            # Padroniza os nomes das colunas em maiúsculo para compatibilidade com o seu app.py
            df_servidores.columns = ['CPF', 'Nome', 'Status']
            
        # 2. Carrega Declarações (Créditos)
        res_declaracoes = supabase.table("declaracoes").select("*").execute()
        df_declaracoes = pd.DataFrame(res_declaracoes.data)
        if df_declaracoes.empty:
            df_declaracoes = pd.DataFrame(columns=["id", "cpf", "eleicao", "direito", "saldo"])
        
        # Ajusta maiúsculas/minúsculas para bater com o app.py antigo
        df_declaracoes = df_declaracoes.rename(columns={
            'cpf': 'CPF', 'eleicao': 'Eleicao', 'direito': 'Direito', 'saldo': 'Saldo'
        })
            
        # 3. Carrega Folgas Gozadas (Débitos)
        res_folgas = supabase.table("folgas_gozadas").select("*").execute()
        df_folgas = pd.DataFrame(res_folgas.data)
        if df_folgas.empty:
            df_folgas = pd.DataFrame(columns=["id", "cpf", "data_gozo", "quantidade"])
            
        df_folgas = df_folgas.rename(columns={
            'cpf': 'CPF', 'data_gozo': 'Data_Gozo', 'quantidade': 'Quantidade'
        })
            
        return df_servidores, df_declaracoes, df_folgas
        
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados: {e}")
        return (
            pd.DataFrame(columns=["CPF", "Nome", "Status"]),
            pd.DataFrame(columns=["CPF", "Eleicao", "Direito", "Saldo"]),
            pd.DataFrame(columns=["CPF", "Data_Gozo", "Quantidade"])
        )

# --- ADAPTADOR INTELIGENTE PARA SALVAR DADOS ---
def salvar_dados(*args, **kwargs):
    """
    Identifica automaticamente os dados gerados pelo formulário do app.py
    e os direciona para a tabela correta no Supabase.
    """
    try:
        supabase = inicializar_conexao()
        
        # Verifica se o app.py enviou dados pelos formulários através do st.session_state ou variáveis de contexto
        # Buscando dados do cadastro de Servidor
        if 'novo_cpf' in st.session_state and st.session_state.novo_cpf:
            dados = {
                "cpf": str(st.session_state.novo_cpf).strip(),
                "nome": str(st.session_state.novo_nome).strip().upper(),
                "status": "Ativo"
            }
            supabase.table("servidores").insert(dados).execute()
            st.success("Servidor cadastrado permanentemente no Supabase!")
            return True
            
        # Buscando dados do lançamento de Declaração (Crédito)
        elif 'decl_cpf' in st.session_state and st.session_state.decl_cpf:
            dados = {
                "cpf": str(st.session_state.decl_cpf).strip(),
                "eleicao": str(st.session_state.decl_eleicao).strip(),
                "direito": int(st.session_state.decl_direito),
                "saldo": int(st.session_state.decl_direito) # Inicialmente o saldo é igual ao direito conquistado
            }
            supabase.table("declaracoes").insert(dados).execute()
            st.success("Declaração de crédito salva permanentemente no Supabase!")
            return True
            
        # Buscando dados do registro de Folga (Débito)
        elif 'folga_cpf' in st.session_state and st.session_state.folga_cpf:
            dados = {
                "cpf": str(st.session_state.folga_cpf).strip(),
                "data_gozo": str(st.session_state.folga_data),
                "quantidade": int(st.session_state.folga_qtd)
            }
            supabase.table("folgas_gozadas").insert(dados).execute()
            st.success("Uso de folga registrado permanentemente no Supabase!")
            return True
            
        else:
            # Caso o app use nomes diferentes de variáveis nas outras abas
            st.warning("Formulário enviado, mas as variáveis de salvamento precisam ser mapeadas.")
            return False
            
    except Exception as e:
        st.error(f"Erro ao gravar dados no banco de dados: {e}")
        return False

# --- GERADORES DE PDF (REPORTLAB) ---
def gerar_pdf_lista_geral(df_resumo):
    pdf_filename = "Relatorio_Saldos_Geral.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], alignment=1, spaceAfter=20, fontSize=16)
    normal_center = ParagraphStyle('NormalCenter', parent=styles['Normal'], alignment=1, fontSize=10)
    
    story.append(Paragraph("<b>E.E. CLOVIS DE LUCCA</b>", title_style))
    story.append(Paragraph("<b>Controle de Folgas TRE - Relatório Geral de Saldos</b>", title_style))
    story.append(Spacer(1, 15))
    
    table_data = [[Paragraph(f"<b>{col}</b>", normal_center) for col in df_resumo.columns]]
    for idx, row in df_resumo.iterrows():
        table_data.append([Paragraph(str(item), normal_center) for item in row])
        
    t = Table(table_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    doc.build(story)
    return pdf_filename

def gerar_pdf_certidao(nome, cpf, saldo, historico, emissor, cargo):
    pdf_filename = f"Certidao_TRE_{cpf.replace('.','').replace('-','')}.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=1, fontSize=14, spaceAfter=30)
    text_style = ParagraphStyle('Text', parent=styles['Normal'], alignment=4, fontSize=12, leading=18, spaceAfter=15)
    sign_style = ParagraphStyle('Sign', parent=styles['Normal'], alignment=1, fontSize=11, leading=16)
    
    story.append(Paragraph("<b>ESTADO DE SÃO PAULO</b><br/>SECRETARIA DE ESTADO DA EDUCAÇÃO<br/><b>E.E. CLOVIS DE LUCCA</b>", sign_style))
    story.append(Spacer(1, 30))
    story.append(Paragraph("<b>DECLARAÇÃO DE SALDO - FOLGAS TRE</b>", title_style))
    
    data_hoje = datetime.now().strftime("%d de %B de %Y")
    meses = {'January': 'janeiro', 'February': 'fevereiro', 'March': 'março', 'April': 'abril', 'May': 'maio', 'June': 'junho', 'July': 'julho', 'August': 'agosto', 'September': 'setembro', 'October': 'outubro', 'November': 'novembro', 'December': 'dezembro'}
    for eng, pt in meses.items():
        data_hoje = data_hoje.replace(eng, pt)
        
    texto = f"Declaramos para os devidos fins de direito e controle interno, que o(a) servidor(a) <b>{nome}</b>, inscrito(a) no CPF sob o nº <b>{cpf}</b>, conta atualmente com um saldo remanescente de <b>{saldo} dia(s)</b> de folga gerada(s) por services prestados à Justiça Eleitoral (TRE), estando apto(a) a usufruí-lo(s) mediante prévia anuência da direção escolar."
    story.append(Paragraph(texto, text_style))
    story.append(Spacer(1, 40))
    
    story.append(Paragraph(f"São Bernardo do Campo, {data_hoje}.", text_style))
    story.append(Spacer(1, 60))
    story.append(Paragraph(f"_______________________________________<br/><b>{emissor}</b><br/>{cargo}", sign_style))
    
    doc.build(story)
    return pdf_filename
