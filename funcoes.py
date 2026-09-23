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
    """Carrega as tabelas do Supabase, garante nomes de colunas e limpa dados nulos"""
    try:
        supabase = inicializar_conexao()
        
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

# --- ADAPTADOR INTELIGENTE CORRIGIDO (SALVAMENTO COMPATÍVEL) ---
def salvar_dados(df_servidores, df_declaracoes, df_folgas):
    """
    Intercipta as ações do app.py, valida datas futuras, processa a gravação
    no Supabase e faz o abatimento automático dos saldos de folga.
    """
    try:
        supabase = inicializar_conexao()
        hoje = date.today()
        
        # 1. PROCESSAMENTO DE FOLGAS GOZADAS (DÉBITOS) COM VALIDAÇÕES CRÍTICAS
        if isinstance(df_folgas, pd.DataFrame) and not df_folgas.empty:
            res_banco_f = supabase.table("folgas_gozadas").select("cpf").execute()
            total_banco_f = len(res_banco_f.data)
            
            if len(df_folgas) > total_banco_f:
                linha_nova_f = df_folgas.iloc[-1]
                data_gozo_str = str(linha_nova_f['Data_Gozo']).strip()
                
                # Converte e valida estritamente se a data do gozo está no futuro
                try:
                    data_gozo_obj = datetime.strptime(data_gozo_str, "%Y-%m-%d").date()
                except ValueError:
                    data_gozo_obj = hoje
                    
                if data_gozo_obj > hoje:
                    st.error(f"⚠️ Erro de Lançamento: Não é permitido registrar folgas em datas futuras ({data_gozo_str}).")
                    return False
                
                cpf_alvo = str(linha_nova_f['CPF']).strip()
                qtd_descontar = int(linha_nova_f['Quantidade'])
                
                # Grava o débito da folga na nuvem
                dados_debito = {"cpf": cpf_alvo, "data_gozo": data_gozo_str, "quantidade": qtd_descontar}
                supabase.table("folgas_gozadas").insert(dados_debito).execute()
                
                # Executa o abatimento automático do saldo nas declarações ativas do funcionário
                res_creditos = supabase.table("declaracoes").select("id, saldo").eq("cpf", cpf_alvo).gt("saldo", 0).order("id").execute()
                if res_creditos.data:
                    for credito in res_creditos.data:
                        if qtd_descontar <= 0:
                            break
                        id_credito = credito['id']
                        saldo_atual = int(credito['saldo'])
                        
                        if saldo_atual >= qtd_descontar:
                            novo_saldo = saldo_atual - qtd_descontar
                            qtd_descontar = 0
                        else:
                            qtd_descontar -= saldo_atual
                            novo_saldo = 0
                            
                        supabase.table("declaracoes").update({"saldo": novo_saldo}).eq("id", id_credito).execute()
                return True

        # 2. PROCESSAMENTO DE DECLARAÇÕES (CRÉDITOS)
        if isinstance(df_declaracoes, pd.DataFrame) and not df_declaracoes.empty:
            res_banco = supabase.table("declaracoes").select("cpf").execute()
            total_banco = len(res_banco.data)
            
            if len(df_declaracoes) > total_banco:
                linha_nova = df_declaracoes.iloc[-1]
                
                # Tenta capturar o nome exato digitado no formulário mapeando variáveis comuns do app.py
                txt_eleicao = str(linha_nova['Eleicao']).strip()
                if not txt_eleicao or txt_eleicao.lower() == 'nan':
                    if 'eleicao_nome' in st.session_state:
                        txt_eleicao = str(st.session_state.eleicao_nome).strip()
                    elif 'nome_eleicao' in st.session_state:
                        txt_eleicao = str(st.session_state.nome_eleicao).strip()
                    else:
                        txt_eleicao = f"Convocação - {hoje.strftime('%d/%m/%Y')}"
                
                dados_credito = {
                    "cpf": str(linha_nova['CPF']).strip(),
                    "eleicao": txt_eleicao,
                    "direito": int(linha_nova['Direito']),
                    "saldo": int(linha_nova['Saldo'])
                }
                supabase.table("declaracoes").insert(dados_credito).execute()
                return True

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
        st.error(f"Erro operacional no banco de dados: {e}")
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
    
    story.append(Paragraph("<b>Histórico de Convocações / Eleições Cadastradas:</b>", text_style))
    story.append(Spacer(1, 5))
    
    dados_tabela = [[Paragraph("<b>Convocação / Eleição</b>", table_text), Paragraph("<b>Dias Conquistados</b>", table_text), Paragraph("<b>Saldo Atual</b>", table_text)]]
    
    if isinstance(historico, pd.DataFrame) and not historico.empty:
        for _, r in historico.iterrows():
            eleicao_val = r.get('Eleicao', r.get('eleicao', 'Convocação Registrada'))
            direito_val = r.get('Direito', r.get('direito', 0))
            saldo_val = r.get('Saldo', r.get('saldo', 0))
            
            if str(eleicao_val).strip().lower() == 'nan' or not str(eleicao_val).strip():
                eleicao_val = "Convocação Registrada"
                
            dados_tabela.append([
                Paragraph(str(eleicao_val), table_text),
                Paragraph(f"{int(direito_val)} dia(s)", table_text),
                Paragraph(f"{int(saldo_val)} dia(s)", table_text)
            ])
    else:
        dados_tabela.append([Paragraph("Nenhum registro discriminado encontrado.", table_text), Paragraph("-", table_text), Paragraph("-", table_text)])
        
    t_hist = Table(dados_tabela, colWidths=)
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
