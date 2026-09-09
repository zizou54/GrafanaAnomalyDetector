"""Render the versioned Markdown guide with readable tables and full-page figures.

Requires reportlab and a local Calibri font (Windows documentation workstation).
Review rendered pages with pdftoppm before publishing. No runtime config is read.
"""
import html
from pathlib import Path
import re
import textwrap
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
    Spacer, Table, TableStyle, PageBreak, Image, NextPageTemplate, Preformatted)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'release/GRAFANA_ANOMALY_DETECTOR_E2E_KURULUM_UPGRADE_KILAVUZU_v1.5.1_TR.md'
OUTPUT = ROOT / 'docs/e2e-guide-v1.5.1-tr.pdf'


def main():
    for name, file in [('Guide', 'calibri.ttf'), ('GuideBold', 'calibrib.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(Path('C:/Windows/Fonts') / file)))
    pdfmetrics.registerFontFamily('Guide', normal='Guide', bold='GuideBold', italic='Guide', boldItalic='GuideBold')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='GuideBody', fontName='Guide', fontSize=11,
        leading=15, spaceAfter=7, textColor=colors.HexColor('#203047')))
    styles.add(ParagraphStyle(name='GuideCell', parent=styles['GuideBody'], fontSize=9.5, leading=13, spaceAfter=0))
    styles.add(ParagraphStyle(name='GuideCode', fontName='Courier', fontSize=8.5, leading=11,
        backColor=colors.HexColor('#f3f6fa'), borderPadding=8, spaceAfter=12))
    for level, size in [(1, 25), (2, 18), (3, 13)]:
        styles.add(ParagraphStyle(name=f'G{level}', fontName='GuideBold', fontSize=size,
            leading=size+5, textColor=colors.HexColor('#17415f'), spaceBefore=12,
            spaceAfter=10, keepWithNext=True))

    def inline(text):
        text = html.escape(text)
        text = re.sub(r'\[([^]]+)\]\(([^)]+)\)', r'\1', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        return re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', text)

    width, height = A4
    margin = 43
    fig_width, fig_height = landscape(A3)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#63748b'))
        canvas.setFont('Guide', 9)
        canvas.drawString(margin, 22, 'Anomaly Detector 1.5.1 | Kurulum ve operasyon')
        canvas.drawRightString(canvas._pagesize[0]-margin, 22, str(doc.page))
        canvas.restoreState()

    doc = BaseDocTemplate(str(OUTPUT), pagesize=A4, title='Anomaly Detector 1.5.1 - E2E Guide',
                          author='Grafana Anomaly Detector', leftMargin=margin, rightMargin=margin)
    doc.addPageTemplates([
        PageTemplate(id='text', frames=[Frame(margin, 40, width-2*margin, height-85,
                                              leftPadding=0, rightPadding=0)], onPage=footer, pagesize=A4),
        PageTemplate(id='figure', frames=[Frame(margin, 40, fig_width-2*margin, fig_height-85,
                                                leftPadding=0, rightPadding=0)], onPage=footer, pagesize=landscape(A3))])
    flow, figures = [], []
    lines = SOURCE.read_text(encoding='utf-8-sig').splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith('```'):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                block.extend(textwrap.wrap(lines[i], 86, replace_whitespace=False,
                    drop_whitespace=False) or [''])
                i += 1
            flow.append(Preformatted('\n'.join(block), styles['GuideCode']))
            i += 1
            continue
        if line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                if not re.fullmatch(r'[| :\-]+', lines[i]):
                    rows.append([Paragraph(inline(cell.strip()), styles['GuideCell'])
                                 for cell in lines[i].strip('|').split('|')])
                i += 1
            columns = len(rows[0])
            weights = [0.38, 0.62] if columns == 2 else [1/columns]*columns
            table = Table(rows, colWidths=[(width-2*margin)*x for x in weights], repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e7eff5')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f7f9fc')]),
                ('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('LINEBELOW', (0,0), (-1,0), .5, colors.HexColor('#a7bbcb'))]))
            flow.extend([table, Spacer(1, 12)])
            continue
        picture = re.match(r'!\[([^]]*)\]\(([^)]+)\)', line)
        if picture:
            figures.append((picture[1], SOURCE.parent / picture[2]))
            flow.append(Paragraph(f'Gorsel {len(figures)}: {inline(picture[1])}. Tam boyutlu goruntu ekler bolumundedir.', styles['GuideBody']))
            i += 1
            continue
        heading = re.match(r'^(#{1,3}) (.+)', line)
        if heading:
            if len(heading[1]) == 2:
                flow.append(PageBreak())
            flow.append(Paragraph(inline(heading[2]), styles[f'G{len(heading[1])}']))
            i += 1
            continue
        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r'^(#|\||```|!\[|- |\d+\. )', lines[i]):
            paragraph.append(lines[i])
            i += 1
        flow.append(Paragraph(inline(' '.join(paragraph)), styles['GuideBody']))
    for number, (caption, file) in enumerate(figures, 1):
        flow.extend([NextPageTemplate('figure'), PageBreak(),
                     Paragraph(f'Gorsel {number} - {inline(caption)}', styles['G3'])])
        image = Image(str(file))
        ratio = min((fig_width-2*margin)/image.imageWidth, (fig_height-140)/image.imageHeight)
        image.drawWidth, image.drawHeight = image.imageWidth*ratio, image.imageHeight*ratio
        flow.append(image)
    doc.build(flow)
    print(OUTPUT.name)


if __name__ == '__main__':
    main()
