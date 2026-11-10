"""Small, dependency-free XLSX exporter. Text is always stored as text, never a formula."""
from decimal import Decimal
from io import BytesIO
import re
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile

from django.utils import timezone

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def xml(element):
    return tostring(element, encoding='utf-8', xml_declaration=True)


def column_name(number):
    result = ''
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def workbook_bytes(sheets):
    output = BytesIO()
    workbook = Element('workbook', xmlns=NS, attrib={'xmlns:r': REL})
    sheet_list = SubElement(workbook, 'sheets')
    relations = Element('Relationships', xmlns='http://schemas.openxmlformats.org/package/2006/relationships')
    types = Element('Types', xmlns='http://schemas.openxmlformats.org/package/2006/content-types')
    SubElement(types, 'Default', Extension='rels', ContentType='application/vnd.openxmlformats-package.relationships+xml')
    SubElement(types, 'Default', Extension='xml', ContentType='application/xml')
    SubElement(types, 'Override', PartName='/xl/workbook.xml', ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml')
    SubElement(types, 'Override', PartName='/xl/styles.xml', ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml')
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for index, (name, headers, rows) in enumerate(sheets, 1):
            SubElement(sheet_list, 'sheet', name=name, sheetId=str(index), attrib={'r:id': f'rId{index}'})
            SubElement(relations, 'Relationship', Id=f'rId{index}', Type=f'{REL}/worksheet', Target=f'worksheets/sheet{index}.xml')
            SubElement(types, 'Override', PartName=f'/xl/worksheets/sheet{index}.xml', ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
            sheet = Element('worksheet', xmlns=NS)
            views = SubElement(sheet, 'sheetViews')
            view = SubElement(views, 'sheetView', workbookViewId='0')
            SubElement(view, 'pane', ySplit='1', topLeftCell='A2', activePane='bottomLeft', state='frozen')
            cols = SubElement(sheet, 'cols')
            for col in range(1, len(headers) + 1):
                SubElement(cols, 'col', min=str(col), max=str(col), width='24', customWidth='1')
            data = SubElement(sheet, 'sheetData')
            count = 0
            for count, values in enumerate(_with_header(headers, rows), 1):
                row = SubElement(data, 'row', r=str(count))
                for col, value in enumerate(values, 1):
                    cell = SubElement(row, 'c', r=f'{column_name(col)}{count}', s='1' if count == 1 else '0')
                    if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
                        cell.set('s', '2')
                        SubElement(cell, 'v').text = str(value)
                    else:
                        cell.set('t', 'inlineStr')
                        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', '' if value is None else str(value))[:32767]
                        SubElement(SubElement(cell, 'is'), 't', attrib={'xml:space': 'preserve'}).text = text
            SubElement(sheet, 'autoFilter', ref=f'A1:{column_name(len(headers))}{count}')
            archive.writestr(f'xl/worksheets/sheet{index}.xml', xml(sheet))
        SubElement(relations, 'Relationship', Id='styles', Type=f'{REL}/styles', Target='styles.xml')
        archive.writestr('xl/workbook.xml', xml(workbook))
        archive.writestr('xl/_rels/workbook.xml.rels', xml(relations))
        archive.writestr('[Content_Types].xml', xml(types))
        root_rel = Element('Relationships', xmlns='http://schemas.openxmlformats.org/package/2006/relationships')
        SubElement(root_rel, 'Relationship', Id='rId1', Type=f'{REL}/officeDocument', Target='xl/workbook.xml')
        archive.writestr('_rels/.rels', xml(root_rel))
        archive.writestr('xl/styles.xml', f'''<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="{NS}"><numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00###"/></numFmts>
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF157665"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>''')
    return output.getvalue()


def _with_header(headers, rows):
    yield headers
    yield from rows


def report_workbook(context, documents, payments, expenses):
    summary = [
        ['Davr', context['period_label']], ['Boshlanish', str(context['start'] or 'Barcha davr')],
        ['Tugash', str(context['today'])], ['Valyuta', 'UZS'],
        ['Sof savdo tushumi', context['revenue']], ['Yalpi foyda', context['profit']],
        ['Xarajatlar', context['expenses']], ['Hisobiy sof foyda', context['net']],
        ['Sotuvlar soni', context['sale_count']], ['Qaytarishlar soni', context['return_count']],
        ['To‘lov kirimi', context['incoming']], ['To‘lov chiqimi', context['outgoing']],
        ['Balanslar', 'Joriy, barcha davr bo‘yicha. Tanlangan davr bilan cheklanmaydi.'],
    ]
    def sales_rows():
        for doc in documents:
            sign = -1 if doc.kind == 'return' else 1
            for line in doc.lines.all():
                yield [doc.pk, timezone.localtime(doc.created_at).strftime('%Y-%m-%d %H:%M'), doc.get_kind_display(), doc.buyer_name or str(doc.partner or ''), doc.buyer_phone or (doc.partner.phone if doc.partner else ''), str(doc.warehouse), line.product.name, line.product.sku, line.quantity, line.product.unit, line.price, sign * line.quantity * line.price, line.cost, sign * (line.price - line.cost) * line.quantity]
    return workbook_bytes([
        ('Umumiy', ['Ko‘rsatkich', 'Qiymat'], summary),
        ('Savdo va qaytarish', ['Hujjat', 'Sana', 'Turi', 'Xaridor', 'Telefon', 'Ombor', 'Tovar', 'Artikul', 'Miqdor', 'Birlik', 'Birlik narxi', 'Sof summa', 'Birlik tannarxi', 'Yalpi foyda'], sales_rows()),
        ('To‘lovlar', ['Sana', 'Hamkor', 'Yo‘nalish', 'Summa', 'Usul', 'Izoh'], ([timezone.localtime(p.created_at).strftime('%Y-%m-%d %H:%M'), str(p.partner), p.get_direction_display(), p.amount, p.get_method_display(), p.notes] for p in payments)),
        ('Xarajatlar', ['Sana', 'Nomi', 'Summa', 'Izoh'], ([str(e.date), e.title, e.amount, e.notes] for e in expenses)),
        ('Joriy balanslar', ['Hamkor', 'Turi', 'Telefon', 'Balans (UZS)'], ([r['partner'].name, r['partner'].get_kind_display(), r['partner'].phone, r['balance']] for r in context['balances'])),
    ])
