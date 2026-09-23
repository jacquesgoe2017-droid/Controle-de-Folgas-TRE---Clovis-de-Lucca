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
            df_servidores = pd.DataFrame(columns=["CPF", "Nome", "Status"])
        else:
            df_servidores = df_servidores.rename(columns={
                'cpf': 'CPF', 'nome': 'Nome', 'status': 'Status'
            })
            
        # 2. Carrega Declarações (Créditos)
        res_declaracoes = supabase.table("declaracoes").select("*").execute()
        df_declaracoes = pd.DataFrame(res_declaracoes.data)
        if df_declaracoes.empty:
            df_declaracoes = pd.DataFrame(columns=["CPF", "Eleicao", "Direito", "Saldo"])
        else:
            df_declaracoes = df_declaracoes.rename(columns={
                'cpf': 'CPF', 'eleicao': 'Eleicao', 'direito': 'Direito', 'saldo': 'Saldo'
            })
            
        # 3. Carrega Folgas Gozadas (Débitos)
        res_folgas = supabase.table("folgas_gozadas").select("*").execute()
        df_folgas = pd.DataFrame(res_folgas.data)
        if df_folgas.empty:
            df_folgas = pd.DataFrame(columns=["CPF", "Data_Gozo", "Quantidade"])
        else:
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

# --- ADAPTADOR INTELIGENTE COMPATÍVEL ---
def salvar_dados(df_servidores, df_declaracoes, df_folgas):
    """
    Salva diretamente os novos registros e atualizações comparando o estado do app
    com o que já está permanentemente inserido no Supabase.
    """
    try:
        supabase = inicializar_conexao()
        
        # 1. SALVAMENTO DE SERVIDORES
        if isinstance(df_servidores, pd.DataFrame) and not df_servidores.empty:
            for idx, row in df_servidores.iterrows():
                dados_servidor = {
                    "cpf": str(row['CPF']).strip(),
                    "nome": str(row['Nome']).strip().upper(),
                    "status": str(row['Status']).strip()
                }
                supabase.table("servidores").upsert(dados_servidor, on_conflict="cpf").execute()
        
        # 2. SALVAMENTO DE DECLARAÇÕES (CRÉDITOS)
        if isinstance(df_declaracoes, pd.DataFrame) and not df_declaracoes.empty:
            res_banco = supabase.table("declaracoes").select("cpf, eleicao, direito, saldo").execute()
            df_banco = pd.DataFrame(res_banco.data)
            
            for idx, row in df_declaracoes.iterrows():
                cpf_str = str(row['CPF']).strip()
                eleicao_str = str(row['Eleicao']).strip()
                direito_int = int(row['Direito'])
                saldo_int = int(row['Saldo'])
                
                ja_salvo = False
                if not df_banco.empty:
                    ja_salvo = not df_banco[
                        (df_banco['cpf'] == cpf_str) & 
                        (df_banco['eleicao'] == eleicao_str) & 
                        (df_banco['direito'] == direito_int)
                    ].empty
                
                if not ja_salvo:
                    dados_credito = {
                        "cpf": cpf_str,
                        "eleicao": eleicao_str,
                        "direito": direito_int,
                        "saldo": saldo_int
                    }
                    supabase.table("declaracoes").insert(dados_credito).execute()

        # 3. SALVAMENTO DE FOLGAS GOZADAS (DÉBITOS)
        if isinstance(df_folgas, pd.DataFrame) and not df_folgas.empty:
            res_banco_folgas = supabase.table("folgas_gozadas").select("cpf, data_gozo, quantidade").execute()
            df_banco_folgas = pd.DataFrame(res_banco_folgas.data)
            
            for idx, row in df_folgas.iterrows():
                cpf_str = str(row['CPF']).strip()
                data_str = str(row['Data_Gozo']).strip()
                qtd_int = int(row['Quantidade'])
                
                ja_salvo = False
                if not df_banco_folgas.empty:
                    ja_salvo = not df_banco_folgas[
                        (df_banco_folgas['cpf'] == cpf_str) & 
                        (df_banco_folgas['data_gozo'] == data_str) &
                        (df_banco_folgas['quantidade'] == qtd_int)
                    ].empty
                
                if not ja_salvo:
                    dados_debito = {
                        "cpf": cpf_str,
                        "data_gozo": data_str,
                        "quantidade": qtd_int
                    }
                    supabase.table("folgas_gozadas").insert(dados_debito).execute()
                    
        return True
    except Exception as e:
        st.error(f"Erro ao salvar dados no Supabase: {e}")
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
    
    # --- TABELA DE HISTÓRICO DISCRIMINADO ---
    story.append(Paragraph("<b>Histórico de Convocações / Eleições Cadastradas:</b>", text_style))
    story.append(Spacer(1, 5))
    
    historico_limpo = historico.rename(columns={'eleicao': 'Eleicao', 'direito': 'Direito', 'saldo': 'Saldo', 'Eleicao': 'Eleicao', 'Direito': 'Direito', 'Saldo': 'Saldo'})
    
    dados_tabela = [[Paragraph("<b>Convocação / Eleição</b>", table_text), Paragraph("<b>Dias Conquistados</b>", table_text), Paragraph("<b>Saldo Atual</b>", table_text)]]
    
    if not historico_limpo.empty:
        for _, r in historico_limpo.iterrows():
            dados_tabela.append([
                Paragraph(str(r['Eleicao']), table_text),
                Paragraph(f"{int(r['Direito'])} dia(s)", table_text),
                Paragraph(f"{int(r['Saldo'])} dia(s)", table_text)
            ])
    else:
        dados_tabela.append([Paragraph("Nenhum registro discriminado encontrado.", table_text), Paragraph("-", table_text), Paragraph("-", table_text)])
        
    t_hist = Table(dados_tabela, colWidths=[250, 110, 110])
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
