import os
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

DB_SERVIDORES = "servidores.csv"
DB_DECLARACOES = "declaracoes.csv"
DB_FOLGAS = "folgas.csv"

def inicializar_bancos():
    if not os.path.exists(DB_SERVIDORES):
        pd.DataFrame(columns=['CPF', 'Nome', 'Status']).to_csv(DB_SERVIDORES, index=False)
    if not os.path.exists(DB_DECLARACOES):
        pd.DataFrame(columns=['CPF', 'Data_Eleicao', 'Direito', 'Saldo']).to_csv(DB_DECLARACOES, index=False)
    if not os.path.exists(DB_FOLGAS):
        pd.DataFrame(columns=['CPF', 'Data_Folga']).to_csv(DB_FOLGAS, index=False)
    
    return (pd.read_csv(DB_SERVIDORES, dtype={'CPF': str}),
            pd.read_csv(DB_DECLARACOES, dtype={'CPF': str}),
            pd.read_csv(DB_FOLGAS, dtype={'CPF': str}))

def salvar_dados(df_s, df_d, df_f):
    df_s.to_csv(DB_SERVIDORES, index=False)
    df_d.to_csv(DB_DECLARACOES, index=False)
    df_f.to_csv(DB_FOLGAS, index=False)

def gerar_pdf_certidao(nome, cpf, saldo, historico_creditos):
    filename = "certidao_folgas.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    
    style_t = ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=14, leading=18, alignment=TA_CENTER)
    style_c = ParagraphStyle('C', fontName='Helvetica', fontSize=11, leading=16, alignment=TA_JUSTIFY)
    
    story = [
        Paragraph("<b>SECRETARIA DE ESTADO DA EDUCAÇÃO</b>", style_t),
        Paragraph("<b>DIRETORIA DE ENSINO - GESTÃO DE ORGANIZAÇÃO ESCOLAR</b>", style_t),
        Spacer(1, 30),
        Paragraph("<u><b>CERTIDÃO DE LIQUIDAÇÃO DE FOLGAS - TRE</b></u>", style_t),
        Spacer(1, 30)
    ]
    
    dt = datetime.now().strftime("%d/%m/%Y")
    texto = f"Certifico que o(a) servidor(a) <b>{nome.upper()}</b>, CPF nº <b>{cpf}</b>, possui em <b>{dt}</b> o saldo de <b>{saldo} dia(s) de folga TRE</b> pendente(s)."
    story.append(Paragraph(texto, style_c))
    story.append(Spacer(1, 15))
    
    if len(historico_creditos) == 0 or saldo == 0:
        story.append(Paragraph("- Não há créditos pendentes.", style_c))
    else:
        for _, row in historico_creditos.iterrows():
            if row['Saldo'] > 0:
                story.append(Paragraph(f"• Eleição {row['Data_Eleicao']}: Direito {row['Direito']}d | <b>Saldo: {row['Saldo']}d</b>", style_c))
                
    story.append(Spacer(1, 40))
    story.append(Paragraph("____________________________________________<br/><b>Gerência de Organização Escolar</b>", style_t))
    doc.build(story)
    return filename
