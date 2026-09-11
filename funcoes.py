import os
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib import colors
from reportlab.pdfgen import canvas

DB_SERVIDORES = "servidores.csv"
DB_DECLARACOES = "declaracoes.csv"
DB_FOLGAS = "folgas.csv"
ARQUIVO_LOGO = "logo_escola.png"

# --- CLASSE AUXILIAR PARA NUMERAÇÃO DE PÁGINAS DINÂMICA (Página X de Y) ---
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.dimgrey)
        
        # Desenha uma linha discreta acima do rodapé em todas as páginas
        self.setLineWidth(0.5)
        self.setStrokeColor(colors.lightgrey)
        self.line(36, 45, letter[0] - 36, 45)
        
        # Texto do rodapé institucional e numeração dinâmica automatizada
        texto_rodape = f"Controle de Folgas TRE - E.E. Clovis de Lucca | Emitido em {datetime.now().strftime('%d/%m/%Y')}"
        texto_pagina = f"Página {self._pageNumber} de {page_count}"
        
        self.drawString(36, 32, texto_rodape)
        self.drawRightString(letter[0] - 36, 32, texto_pagina)
        self.restoreState()


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

def gerar_pdf_certidao(nome, cpf, saldo, historico_creditos, nome_assinante, cargo_assinante):
    filename = "certidao_folgas.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    
    style_t = ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=13, leading=16, alignment=TA_CENTER)
    style_e = ParagraphStyle('E', fontName='Helvetica', fontSize=8, leading=14, alignment=TA_CENTER)
    style_c = ParagraphStyle('C', fontName='Helvetica', fontSize=11, leading=17, alignment=TA_JUSTIFY)
    style_d = ParagraphStyle('D', fontName='Helvetica', fontSize=11, leading=16, alignment=TA_RIGHT)
    style_a = ParagraphStyle('A', fontName='Helvetica', fontSize=11, leading=16, alignment=TA_CENTER)
    
    story = []
    
    if os.path.exists(ARQUIVO_LOGO):
        img = Image(ARQUIVO_LOGO, width=120, height=60)
        img.hAlign = 'CENTER'
        story.append(img)
        story.append(Spacer(1, 12))
        
    story.extend([
        Paragraph("<b>Secretaria de Estado da Educação</b>", style_t),
        Paragraph("<b>Unidade Regional de Ensino de São Bernardo do Campo</b>", style_t),
        Paragraph("<b>E.E. Clovis de Lucca</b>", style_t),
        Paragraph("<b>Rua dos Vianas, 1915 - Baeta Neves - S.B. Campo - SP</b>", style_e),
        Paragraph("<b>E-mail: <font color='navy'><u>e009124a@educacao.sp.gov.br</u></font> - Fone: 11 - 4332-6372</b>", style_e),
        Spacer(1, 25),
        Paragraph("<u><b>CERTIDÃO DE LIQUIDAÇÃO DE FOLGAS - TRE</b></u>", style_t),
        Spacer(1, 30)
    ])
    
    dt_atual = datetime.now().strftime("%d/%m/%Y")
    texto = f"Certifico, para os devidos fins de direito e regularização de prontuário, que o(a) servidor(a) <b>{nome.upper()}</b>, inscrito(a) no CPF sob o nº <b>{cpf}</b>, em exercício nesta unidade escolar, possui nesta data o saldo acumulado de <b>{saldo} dia(s) de folga</b> pendente(s) de usufruto, decorrente(s) de convocações pela Justiça Eleitoral (TRE), conforme previsto na legislação vigente."
    story.append(Paragraph(texto, style_c))
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("O saldo acima descrito é composto pelas seguintes movimentações e direitos ainda disponíveis:", style_c))
    story.append(Spacer(1, 10))
    
    if len(historico_creditos) == 0 or saldo == 0:
        story.append(Paragraph("- Não há créditos ou saldos pendentes registrados.", style_c))
    else:
        for _, row in historico_creditos.iterrows():
            if row['Saldo'] > 0:
                story.append(Paragraph(f"• Eleição em {row['Data_Eleicao']}: Direito a {row['Direito']} dias | <b>Saldo Restante: {row['Saldo']} dia(s)</b>", style_c))
                
    story.append(Spacer(1, 40))
    texto_local = f"São Bernardo do Campo, {dt_atual}."
    story.append(Paragraph(texto_local, style_d))
    story.append(Spacer(1, 50))
    
    story.append(Paragraph("____________________________________________", style_a))
    story.append(Paragraph(f"<b>{nome_assinante.upper()}</b>", style_a))
    story.append(Paragraph(f"{cargo_assinante}", style_a))
    doc.build(story)
    return filename

def gerar_pdf_lista_geral(df_resumo):
    filename = "relatorio_saldos_geral.pdf"
    # Margens levemente reduzidas para aproveitar o espaço útil da folha
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=45, bottomMargin=60)
    styles = getSampleStyleSheet()
    
    style_t = ParagraphStyle('T', fontName='Helvetica-Bold', fontSize=13, leading=16, alignment=TA_CENTER)
    style_e = ParagraphStyle('E', fontName='Helvetica', fontSize=8, leading=14, alignment=TA_CENTER)
    style_th = ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=TA_CENTER)
    style_td = ParagraphStyle('TD', fontName='Helvetica', fontSize=9, leading=12)
    style_td_c = ParagraphStyle('TDC', fontName='Helvetica', fontSize=9, leading=12, alignment=TA_CENTER)
    
    story = []
    
    if os.path.exists(ARQUIVO_LOGO):
        img = Image(ARQUIVO_LOGO, width=100, height=50)
        img.hAlign = 'CENTER'
        story.append(img)
        story.append(Spacer(1, 10))
        
    story.extend([
        Paragraph("<b>Secretaria de Estado da Educação</b>", style_t),
        Paragraph("<b>Unidade Regional de Ensino de São Bernardo do Campo</b>", style_t),
        Paragraph("<b>E.E. Clovis de Lucca</b>", style_t),
        Paragraph("<b>Rua dos Vianas, 1915 - Baeta Neves - S.B. Campo - SP</b>", style_e),
        Paragraph("<b>E-mail: <font color='navy'><u>e009124a@educacao.sp.gov.br</u></font> - Fone: 11 - 4332-6372</b>", style_e),
        Spacer(1, 15),
        Paragraph("<b>RELAÇÃO GERAL DE SALDOS DE FOLGAS - TRE</b>", style_t),
        Spacer(1, 15)
    ])
    
    data = [[Paragraph("<b>CPF</b>", style_th), Paragraph("<b>Nome do Servidor</b>", style_th), Paragraph("<b>Status</b>", style_th), Paragraph("<b>Total Conq.</b>", style_th), Paragraph("<b>Total Usuf.</b>", style_th), Paragraph("<b>Saldo Disponível</b>", style_th)]]
    for _, row in df_resumo.iterrows():
        data.append([Paragraph(str(row['CPF']), style_td_c), Paragraph(str(row['Nome']), style_td), Paragraph(str(row['Status']), style_td_c), Paragraph(str(row['Total Conquistado']), style_td_c), Paragraph(str(row['Total Usufruído']), style_td_c), Paragraph(f"<b>{row['Saldo Disponível']}</b>", style_td_c)])
    
    tabela = Table(data, colWidths=[90, 220, 50, 60, 60, 60])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(tabela)
    
    # ATIVAÇÃO DO NUMBEREDCANVAS: Constrói o PDF aplicando a paginação automatizada
    doc.build(story, canvasmaker=NumberedCanvas)
    return filename
