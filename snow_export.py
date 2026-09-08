"""
File writers for `snow.py export`: XLSX, PDF and CSV.

Deliberately standard library only. snow.py has no third-party dependencies and
runs under whichever interpreter is on PATH, so pulling in openpyxl/reportlab
would make `export` fail on machines where the rest of the CLI works. Both
formats here are simple enough to emit directly: an .xlsx file is a zip of XML
parts, and a .pdf is a handful of numbered objects plus a cross-reference table.

Rows arrive as a list of dicts of already-flattened strings.
"""

import datetime
import os
import zipfile

# ----- shared ------------------------------------------------------------


def cell_text(value):
    """One record value as a single-line string."""
    if value is None:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def table_of(rows, columns=None):
    """(columns, list-of-list-of-str) for a list of record dicts."""
    if not rows:
        return (columns or []), []
    cols = list(columns) if columns else list(rows[0].keys())
    body = [[cell_text(r.get(c, "")) for c in cols] for r in rows]
    return cols, body


# ----- CSV ---------------------------------------------------------------


def write_csv(path, columns, body):
    import csv

    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        writer.writerows(body)
    return path


# ----- XLSX --------------------------------------------------------------
#
# The minimum set of parts Excel will open: content types, package and workbook
# relationships, the workbook, a two-font stylesheet (normal + bold header) and
# one worksheet. Cell values are written as inline strings, which avoids a
# shared-string table and keeps everything in one pass.

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

# Two cell formats: 0 = plain, 1 = bold on a light grey fill (the header row).
STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2">
<font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
</fonts>
<fills count="3">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF1F3B57"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def xml_escape(text):
    out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Control characters are illegal in XML 1.0 and make Excel reject the file.
    return "".join(c for c in out if c >= " " or c == "\t")


def column_ref(index):
    """0 -> A, 25 -> Z, 26 -> AA."""
    ref = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        ref = chr(65 + rem) + ref
    return ref


def is_number(text):
    """True for values Excel should hold as numbers rather than text."""
    if not text or text.strip() != text:
        return False
    try:
        float(text)
    except ValueError:
        return False
    # Leading zeros are identifiers (incident numbers, sys_ids), not quantities.
    return not (len(text) > 1 and text[0] == "0" and text[1] != ".")


def sheet_xml(columns, body):
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
    ]

    widths = []
    for i, col in enumerate(columns):
        longest = max([len(col)] + [len(r[i]) for r in body]) if body else len(col)
        widths.append('<col min="%d" max="%d" width="%.1f" customWidth="1"/>'
                      % (i + 1, i + 1, min(max(longest + 2, 8), 60)))
    if widths:
        parts.append("<cols>" + "".join(widths) + "</cols>")

    parts.append("<sheetData>")

    def row_xml(number, values, style):
        cells = []
        for i, value in enumerate(values):
            ref = "%s%d" % (column_ref(i), number)
            if style == 0 and is_number(value):
                cells.append('<c r="%s"><v>%s</v></c>' % (ref, value))
            elif value:
                cells.append('<c r="%s" s="%d" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
                             % (ref, style, xml_escape(value)))
            elif style:
                cells.append('<c r="%s" s="%d"/>' % (ref, style))
        return '<row r="%d">%s</row>' % (number, "".join(cells))

    parts.append(row_xml(1, columns, 1))
    for n, values in enumerate(body, start=2):
        parts.append(row_xml(n, values, 0))
    parts.append("</sheetData>")

    if columns:
        span = "A1:%s%d" % (column_ref(len(columns) - 1), len(body) + 1)
        parts.append('<autoFilter ref="%s"/>' % span)
    parts.append("</worksheet>")
    return "".join(parts)


def workbook_xml(sheet_name):
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="%s" sheetId="1" r:id="rId1"/></sheets></workbook>'
        % xml_escape(sheet_name)
    )


def clean_sheet_name(title):
    """Excel forbids []:*?/\\ in sheet names and caps them at 31 characters."""
    name = "".join(" " if c in "[]:*?/\\" else c for c in (title or "Data")).strip()
    return (name or "Data")[:31]


def write_xlsx(path, columns, body, title="Data"):
    # A frozen header is set on the sheet itself; done here to keep sheet_xml short.
    sheet = sheet_xml(columns, body).replace(
        "<sheetData>",
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        "</sheetView></sheetViews><sheetData>",
        1,
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("xl/workbook.xml", workbook_xml(clean_sheet_name(title)))
        z.writestr("xl/_rels/workbook.xml.rels", WORKBOOK_RELS)
        z.writestr("xl/styles.xml", STYLES)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return path


# ----- PDF ---------------------------------------------------------------
#
# Landscape Letter, Helvetica, one grid table with the header repeated on every
# page. Only the 14 standard PDF fonts are used, so no font has to be embedded.

PAGE_W, PAGE_H = 792.0, 612.0          # landscape Letter, in points
MARGIN = 36.0
FONT_SIZE = 8.0
HEAD_SIZE = 8.5
LINE_H = 13.0

# Helvetica advance widths, in 1/1000 em, for the printable ASCII range. Used to
# fit text to a column; anything outside the range is charged the width of "n".
HELV = (
    "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 "
    "556 556 556 556 556 556 556 556 556 556 278 278 584 584 584 556 "
    "1015 667 667 722 722 667 611 778 722 278 500 667 556 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 278 278 278 469 556 "
    "333 556 556 500 556 556 278 556 556 222 222 500 222 833 556 556 "
    "556 556 333 500 278 556 500 722 500 500 500 334 260 334 584"
).split()


def text_width(text, size, bold=False):
    """Width of `text` in points. Bold is ~5% wider than regular Helvetica."""
    total = 0
    for ch in text:
        code = ord(ch)
        total += int(HELV[code - 32]) if 32 <= code <= 126 else 556
    width = total * size / 1000.0
    return width * 1.05 if bold else width


def fit(text, width, size, bold=False):
    """`text` clipped with an ellipsis so it fits inside `width` points."""
    if text_width(text, size, bold) <= width:
        return text
    ellipsis = text_width("...", size, bold)
    out = ""
    used = 0.0
    for ch in text:
        code = ord(ch)
        advance = (int(HELV[code - 32]) if 32 <= code <= 126 else 556) * size / 1000.0
        if bold:
            advance *= 1.05
        if used + advance + ellipsis > width:
            break
        out += ch
        used += advance
    return (out.rstrip() + "...") if out else ""


def pdf_escape(text):
    out = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    # PDF string literals are bytes; drop anything outside Latin-1.
    return "".join(c if 32 <= ord(c) <= 126 else ("?" if ord(c) > 126 else " ") for c in out)


def column_widths(columns, body, available):
    """
    Share the page width between columns, proportional to their widest cell.

    Every column gets a floor so a narrow one stays readable, and the result is
    scaled to exactly fill the available width.
    """
    if not columns:
        return []
    natural = []
    for i, col in enumerate(columns):
        widest = text_width(col, HEAD_SIZE, bold=True)
        for row in body[:400]:            # a sample is enough to size the column
            widest = max(widest, text_width(row[i][:80], FONT_SIZE))
        natural.append(min(widest + 10, available * 0.45))

    floor = min(46.0, available / len(columns))
    natural = [max(w, floor) for w in natural]
    scale = available / sum(natural)
    return [w * scale for w in natural]


def page_content(columns, widths, rows, title, subtitle, page_no, pages):
    """The content stream for one page: title, header band, rows, footer."""
    out = []
    y = PAGE_H - MARGIN

    if page_no == 1 and title:
        out.append("BT /F2 14 Tf 0.12 0.23 0.34 rg 1 0 0 1 %.1f %.1f Tm (%s) Tj ET"
                   % (MARGIN, y - 11, pdf_escape(title)))
        y -= 26
        if subtitle:
            out.append("BT /F1 8.5 Tf 0.42 0.45 0.5 rg 1 0 0 1 %.1f %.1f Tm (%s) Tj ET"
                       % (MARGIN, y - 8, pdf_escape(subtitle)))
            y -= 20

    # Header band.
    band = y - LINE_H
    out.append("0.12 0.23 0.34 rg %.1f %.1f %.1f %.1f re f"
               % (MARGIN, band, PAGE_W - 2 * MARGIN, LINE_H))
    x = MARGIN
    for i, col in enumerate(columns):
        out.append("BT /F2 %.1f Tf 1 1 1 rg 1 0 0 1 %.1f %.1f Tm (%s) Tj ET"
                   % (HEAD_SIZE, x + 4, band + 4, pdf_escape(fit(col, widths[i] - 8, HEAD_SIZE, True))))
        x += widths[i]
    y = band

    # Body, with a hairline under every row and a tint on alternate ones.
    for n, row in enumerate(rows):
        y -= LINE_H
        if n % 2:
            out.append("0.96 0.97 0.98 rg %.1f %.1f %.1f %.1f re f"
                       % (MARGIN, y, PAGE_W - 2 * MARGIN, LINE_H))
        x = MARGIN
        for i, value in enumerate(row):
            out.append("BT /F1 %.1f Tf 0.1 0.1 0.12 rg 1 0 0 1 %.1f %.1f Tm (%s) Tj ET"
                       % (FONT_SIZE, x + 4, y + 4, pdf_escape(fit(value, widths[i] - 8, FONT_SIZE))))
            x += widths[i]
        out.append("0.87 0.89 0.91 RG 0.4 w %.1f %.1f m %.1f %.1f l S"
                   % (MARGIN, y, PAGE_W - MARGIN, y))

    out.append("BT /F1 7.5 Tf 0.45 0.48 0.52 rg 1 0 0 1 %.1f %.1f Tm (Page %d of %d) Tj ET"
               % (MARGIN, MARGIN - 12, page_no, pages))
    return "\n".join(out)


def write_pdf(path, columns, body, title="", subtitle=""):
    widths = column_widths(columns, body, PAGE_W - 2 * MARGIN)

    # How many rows fit: the first page also carries the title block.
    usable = PAGE_H - 2 * MARGIN - LINE_H
    first = max(1, int((usable - (46 if title else 0)) / LINE_H))
    rest = max(1, int(usable / LINE_H))

    chunks = []
    if body:
        chunks.append(body[:first])
        remaining = body[first:]
        while remaining:
            chunks.append(remaining[:rest])
            remaining = remaining[rest:]
    else:
        chunks.append([])

    streams = [
        page_content(columns, widths, chunk, title, subtitle, i + 1, len(chunks))
        for i, chunk in enumerate(chunks)
    ]

    # Objects: 1 catalog, 2 pages, 3 + 4 fonts, then a page and a stream each.
    objects = []
    page_ids = [5 + 2 * i for i in range(len(chunks))]
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append("<< /Type /Pages /Count %d /Kids [%s] >>"
                   % (len(page_ids), " ".join("%d 0 R" % i for i in page_ids)))
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    for i, stream in enumerate(streams):
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.0f %.0f] "
            "/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents %d 0 R >>"
            % (PAGE_W, PAGE_H, page_ids[i] + 1)
        )
        objects.append(stream)          # marked as a stream by position, below

    stream_indexes = {page_ids[i] + 1 for i in range(len(chunks))}

    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, payload in enumerate(objects, start=1):
        offsets.append(len(buf))
        buf += b"%d 0 obj\n" % number
        if number in stream_indexes:
            data = payload.encode("latin-1", "replace")
            buf += b"<< /Length %d >>\nstream\n" % len(data)
            buf += data
            buf += b"\nendstream\n"
        else:
            buf += payload.encode("latin-1", "replace") + b"\n"
        buf += b"endobj\n"

    start_xref = len(buf)
    buf += b"xref\n0 %d\n" % (len(objects) + 1)
    buf += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        buf += b"%010d 00000 n \n" % offset
    buf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, start_xref)

    with open(path, "wb") as fh:
        fh.write(bytes(buf))
    return path


# ----- entry point -------------------------------------------------------

WRITERS = {"xlsx": write_xlsx, "pdf": write_pdf, "csv": write_csv}


def write(path, fmt, rows, columns=None, title="", subtitle=""):
    """Write `rows` to `path` in `fmt`. Returns (path, columns, row count)."""
    cols, body = table_of(rows, columns)
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)

    if fmt == "xlsx":
        write_xlsx(path, cols, body, title or "Data")
    elif fmt == "pdf":
        write_pdf(path, cols, body, title, subtitle)
    elif fmt == "csv":
        write_csv(path, cols, body)
    else:
        raise ValueError("unknown format %r" % fmt)
    return path, cols, len(body)


def stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
