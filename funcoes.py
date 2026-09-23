import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from datetime import datetime, date
import os

# --- CONEXÃO COM O SUPABASE ---
def inicializar_conexao():
    """Inicializa a conexão automática com o Supabase utilizando os Secrets oficiais"""
    return st.connection("supabase", type=SupabaseConnection)

# --- INICIALIZAR BANCOS (CARREGAR DO SUPABASE) ---
def inicializar_bancos():
    """Carrega as tabelas do Supabase, remove os IDs e converte para DataFrames do Pandas"""
    try:
        supabase = inicializar_conexao()
        st.cache_data.clear() # Força a limpeza de qualquer cache travado no navegador
        
        # 1. Carrega Servidores
        res_servidores = supabase.table("servidores").select("*").execute()
        df_servidores = pd.DataFrame(res_servidores.data)
        if df_servidores.empty:
            df_servidores = pd.DataFrame(columns=["CPF", "Nome", "Status"])
        else:
            df_servidores = df_servidores.rename(columns={'cpf': 'CPF', 'nome': 'Nome', 'status': 'Status'})
            
        # 2. Carrega Declarações (Créditos)
        res_declaracoes = supabase.table("declaracoes").select("*").execute()
        df_declaracoes = pd.DataFrame(res_declaracoes.data)
        if df_declaracoes.empty:
            df_declaracoes = pd.DataFrame(columns=["CPF", "Eleicao", "Direito", "Saldo"])
        else:
            if 'id' in df_declaracoes.columns:
                df_declaracoes = df_declaracoes.drop(columns=['id'])
            df_declaracoes = df_declaracoes.rename(columns={'cpf': 'CPF', 'eleicao': 'Eleicao', 'direito': 'Direito', 'saldo': 'Saldo'})
            df_declaracoes['Eleicao'] = df_declaracoes['Eleicao'].fillna('').astype(str)
            
        # 3. Carrega Folgas Gozadas (Débitos)
        res_folgas = supabase.table("folgas_gozadas").select("*").execute()
        df_folgas = pd.DataFrame(res_folgas.data)
        if df_folgas.empty:
            df_folgas = pd.DataFrame(columns=["CPF", "Data_Gozo", "Quantidade"])
        else:
            if 'id' in df_folgas.columns:
                df_folgas = df_folgas.drop(columns=['id'])
            df_folgas = df_folgas.rename(columns={'cpf': 'CPF', 'data_gozo': 'Data_Gozo', 'quantidade': 'Quantidade'})
            
        return df_servidores, df_declaracoes, df_folgas
        
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados: {e}")
        return (
            pd.DataFrame(columns=["CPF", "Nome", "Status"]),
            pd.DataFrame(columns=["CPF", "Eleicao", "Direito", "Saldo"]),
            pd.DataFrame(columns=["CPF", "Data_Gozo", "Quantidade"])
        )

# --- ADAPTADOR DE GRAVAÇÃO DIRETA SEM SOBREPOSIÇÃO ---
def salvar_dados(df_servidores, df_declaracoes, df_folgas):
    """
    Salva os dados de forma idêntica e direta, pegando exclusivamente os valores 
    contidos dentro das tabelas do app.py, matando o erro do congelamento de datas.
    """
    try:
        supabase = inicializar_conexao()

        # 1. SALVAMENTO DE DECLARAÇÕES (CRÉDITOS)
        if isinstance(df_declaracoes, pd.DataFrame):
            # Limpa o banco para sincronizar com os dados exatos calculados na tela
            supabase.table("declaracoes").delete().neq("cpf", "000").execute()
            
            if not df_declaracoes.empty:
                lista_creditos = []
                for idx, row in df_declaracoes.iterrows():
                    # Captura estritamente o valor que o seu app.py guardou na coluna local
                    e_txt = str(row.get('Data_Eleicao', row.get('Eleicao', ''))).strip()
                    if not e_txt or e_txt.lower() == 'nan':
                        e_txt = date.today().strftime("%d/%m/%Y")
                        
                    lista_creditos.append({
                        "cpf": str(row['CPF']).strip(),
                        "eleicao": e_txt,
                        "direito": int(row['Direito']),
                        "saldo": int(row['Saldo'])
                    })
                if lista_creditos:
                    supabase.table("declaracoes").insert(lista_creditos).execute()

        # 2. SALVAMENTO DE FOLGAS GOZADAS (DÉBITOS)
        if isinstance(df_folgas, pd.DataFrame):
            supabase.table("folgas_gozadas").delete().neq("cpf", "000").execute()
            
            if not df_folgas.empty:
                lista_debitos = []
                for idx, row in df_folgas.iterrows():
                    f_txt = str(row.get('Data_Folga', row.get('Data_Gozo', ''))).strip()
                    if not f_txt or f_txt.lower() == 'nan':
                        f_txt = date.today().strftime("%d/%m/%Y")
                        
                    lista_debitos.append({
                        "cpf": str(row['CPF']).strip(),
                        "data_gozo": f_txt,
                        "quantidade": 1
                    })
                if lista_debitos:
                    supabase.table("folgas_gozadas").insert(lista_debitos).execute()

        # 3. SALVAMENTO E ATUALIZAÇÃO DE SERVIDORES
        if isinstance(df_servidores, pd.DataFrame) and not df_servidores.empty:
            for idx, row in df_servidores.iterrows():
                dados_servidor = {
                    "cpf": str(row['CPF']).strip(),
                    "nome": str(row['Nome']).strip().upper(),
                    "status": str(row['Status']).strip()
                }
                supabase.table("servidores").upsert(dados_servidor, on_conflict="cpf").execute()
                
        return True
    except Exception as e:
        st.error(f"Erro operacional de gravação: {e}")
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
        
    t = Table(table_data, colWidths=[100, 180, 60, 60, 60, 60])
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
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=1, fontSize=14, spaceAfter=25)
    text_style = ParagraphStyle('Text', parent=styles['Normal'], alignment=4, fontSize=11, leading=16, spaceAfter=12)
    sign_style = ParagraphStyle('Sign', parent=styles['Normal'], alignment=1, fontSize=11, leading=16)
    table_text = ParagraphStyle('TableText', parent=styles['Normal'], alignment=1, fontSize=10)
    
    story.append(Paragraph("<b>ESTADO DE SÃO PAULO</b><br/>SECRETARIA DE ESTADO DA EDUCAÇÃO<br/><b>E.E. CLOVIS DE LUCCA</b>", sign_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph("<b>DECLARAÇÃO OFICIAL DE SALDO - FOLGAS TRE</b>", title_style))
    
    data_hoje = datetime.now().strftime("%d de %B de %Y")
    meses = {'January': 'janeiro', 'February': 'fevereiro', 'March': 'março', 'April': 'abril', 'May': 'maio', 'June': 'junho', 'July': 'julho', 'August': 'agosto', 'September': 'setembro', 'October': 'outubro', 'November': 'novembro', 'December': 'dezembro'}
    for eng, pt in meses.items():
        data_hoje = data_hoje.replace(eng, pt)
        
    texto = f"Declaramos para os devidos fins de direito e controle interno, que o(a) servidor(a) <b>{nome}</b>, inscrito(a) no CPF sob o nº <b>{cpf}</b>, conta atualmente com um saldo remanescente acumulado de <b>{saldo} dia(s)</b> de folga gerada(s) por serviços prestados à Justiça Eleitoral (TRE), estando apto(a) a usufruí-lo(s) mediante prévia anuência da direção escolar de acordo com a legislação vigente."
    story.append(Paragraph(texto, text_style))
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("<b>Histórico de Convocações / Eleições Cadastradas:</b>", text_style))
    story.append(Spacer(1, 5))
    
    dados_tabela = [[Paragraph("<b>Data da Eleição / Convocação</b>", table_text), Paragraph("<b>Dias Conquistados</b>", table_text), Paragraph("<b>Saldo Atual</b>", table_text)]]
    
    if isinstance(historico, pd.DataFrame) and not historico.empty:
        for _, r in historico.iterrows():
            eleicao_val = r.get('Eleicao', r.get('Data_Eleicao', 'Convocação Registrada'))
            direito_val = r.get('Direito', 0)
            saldo_val = r.get('Saldo', 0)
            
            if str(eleicao_val).strip().lower() == 'nan' or not str(eleicao_val).strip():
                eleicao_val = "Convocação Registrada"
                
            dados_tabela.append([
                Paragraph(str(eleicao_val), table_text),
                Paragraph(f"{int(direito_val)} dia(s)", table_text),
                Paragraph(f"{int(saldo_val)} dia(s)", table_text)
            ])
    else:
        dados_tabela.append([Paragraph("Nenhum registro discriminado encontrado.", table_text), Paragraph("-", table_text), Paragraph("-", table_text)])
        
    t_hist = Table(dados_tabela, colWidths=[260, 120, 120])
    t_hist.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_hist)
    
    story.append(Spacer(1, 35))
    story.append(Paragraph(f"São Bernardo do Campo, {data_hoje}.", text_style))
    story.append(Spacer(1, 45))
    story.append(Paragraph(f"_______________________________________<br/><b>{emissor}</b><br/>{cargo}", sign_style))
    
    doc.build(story)
    return pdf_filename
