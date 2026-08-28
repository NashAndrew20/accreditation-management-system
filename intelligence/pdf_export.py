"""Small dependency-free PDF renderer for the reports module.

The report page already prepares the values from the database. This module
keeps PDF layout concerns separate from the query/view code and renders those
same values as text, tables, bars, and line charts.
"""

import math
import textwrap


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 42

MAROON_900 = (67 / 255, 13 / 255, 34 / 255)
MAROON_800 = (87 / 255, 17 / 255, 44 / 255)
MAROON_700 = (110 / 255, 23 / 255, 55 / 255)
CREAM = (242 / 255, 238 / 255, 229 / 255)
SURFACE = (1, 1, 1)
TEXT = (36 / 255, 28 / 255, 31 / 255)
MUTED = (111 / 255, 102 / 255, 93 / 255)
BORDER = (232 / 255, 225 / 255, 211 / 255)
GREEN = (29 / 255, 138 / 255, 91 / 255)
GOLD = (183 / 255, 138 / 255, 46 / 255)
ROSE = (193 / 255, 58 / 255, 99 / 255)
SOFT_GREEN = (224 / 255, 244 / 255, 233 / 255)
SOFT_GOLD = (250 / 255, 240 / 255, 216 / 255)
SOFT_ROSE = (252 / 255, 231 / 255, 238 / 255)


def _number(value):
    return f'{value:.3f}'.rstrip('0').rstrip('.')


def _pdf_safe(value):
    """Convert common web punctuation to a PDF-safe Latin-1 string."""
    replacements = {
        '\u00b7': ' - ',
        '\u2014': ' - ',
        '\u2013': '-',
        '\u2018': "'",
        '\u2019': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u2022': '*',
        '\u2026': '...',
    }
    text = '' if value is None else str(value)
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode('latin-1', 'replace').decode('latin-1')


def _escape_text(value):
    return _pdf_safe(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _color(color):
    return ' '.join(_number(component) for component in color)


def _wrapped_lines(value, width, size):
    characters = max(int(width / max(size * 0.5, 1)), 1)
    lines = []
    for paragraph in _pdf_safe(value).splitlines() or ['']:
        lines.extend(textwrap.wrap(
            paragraph,
            width=characters,
            break_long_words=True,
            break_on_hyphens=False,
        ) or [''])
    return lines


class PdfPage:
    def __init__(self, width=PAGE_WIDTH, height=PAGE_HEIGHT):
        self.width = width
        self.height = height
        self.commands = []

    def text(self, x, y, value, size=10, color=TEXT, bold=False):
        if value is None:
            return
        font = 'F2' if bold else 'F1'
        pdf_y = self.height - y - size
        self.commands.append(
            f'BT /{font} {_number(size)} Tf {_color(color)} rg '
            f'1 0 0 1 {_number(x)} {_number(pdf_y)} Tm '
            f'({_escape_text(value)}) Tj ET'
        )

    def text_wrap(self, x, y, value, width, size=10, color=TEXT, bold=False, leading=None):
        leading = leading or size * 1.35
        for line in _wrapped_lines(value, width, size):
            self.text(x, y, line, size=size, color=color, bold=bold)
            y += leading
        return y

    def rect(self, x, y, width, height, fill=None, stroke=None, line_width=1):
        bottom = self.height - y - height
        commands = ['q']
        if fill is not None:
            commands.append(f'{_color(fill)} rg')
        if stroke is not None:
            commands.extend([f'{_color(stroke)} RG', f'{_number(line_width)} w'])
        commands.append(f'{_number(x)} {_number(bottom)} {_number(width)} {_number(height)} re')
        if fill is not None and stroke is not None:
            commands.append('B')
        elif fill is not None:
            commands.append('f')
        else:
            commands.append('S')
        commands.append('Q')
        self.commands.extend(commands)

    def line(self, x1, y1, x2, y2, color=BORDER, line_width=1):
        self.commands.extend([
            'q', f'{_color(color)} RG', f'{_number(line_width)} w',
            f'{_number(x1)} {_number(self.height - y1)} m',
            f'{_number(x2)} {_number(self.height - y2)} l S', 'Q',
        ])

    def polyline(self, points, color=MAROON_700, line_width=2, fill=None, close=False):
        if not points:
            return
        commands = ['q', f'{_color(color)} RG', f'{_number(line_width)} w']
        if fill is not None:
            commands.append(f'{_color(fill)} rg')
        first_x, first_y = points[0]
        commands.append(f'{_number(first_x)} {_number(self.height - first_y)} m')
        for x, y in points[1:]:
            commands.append(f'{_number(x)} {_number(self.height - y)} l')
        if close:
            commands.append('h')
        commands.append('B' if fill is not None else 'S')
        commands.append('Q')
        self.commands.extend(commands)

    def circle(self, x, y, radius, fill=MAROON_700, stroke=None, line_width=1):
        points = []
        for index in range(13):
            angle = math.pi * 2 * index / 12
            points.append((x + math.cos(angle) * radius, y + math.sin(angle) * radius))
        self.polyline(points, color=stroke or fill, line_width=line_width, fill=fill, close=True)


class PdfDocument:
    def __init__(self):
        self.pages = []

    def add_page(self):
        page = PdfPage()
        self.pages.append(page)
        return page

    def render(self):
        objects = [None, '<< /Type /Catalog /Pages 2 0 R >>', None]
        regular_font = len(objects)
        objects.append('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
        bold_font = len(objects)
        objects.append('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>')

        page_ids = []
        for page in self.pages:
            stream = '\n'.join(page.commands).encode('latin-1', 'replace')
            content_id = len(objects)
            objects.append(
                f'<< /Length {len(stream)} >>\nstream\n{stream.decode("latin-1")}\nendstream'
            )
            page_id = len(objects)
            objects.append(
                '<< /Type /Page /Parent 2 0 R '
                f'/MediaBox [0 0 {page.width} {page.height}] '
                f'/Resources << /Font << /F1 {regular_font} 0 R /F2 {bold_font} 0 R >> >> '
                f'/Contents {content_id} 0 R >>'
            )
            page_ids.append(page_id)

        objects[2] = f'<< /Type /Pages /Kids [{" ".join(f"{page_id} 0 R" for page_id in page_ids)}] /Count {len(page_ids)} >>'

        output = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
        offsets = [0] * len(objects)
        for object_id in range(1, len(objects)):
            offsets[object_id] = len(output)
            output.extend(f'{object_id} 0 obj\n'.encode('ascii'))
            output.extend(objects[object_id].encode('latin-1', 'replace'))
            output.extend(b'\nendobj\n')

        xref_offset = len(output)
        output.extend(f'xref\n0 {len(objects)}\n'.encode('ascii'))
        output.extend(b'0000000000 65535 f \n')
        for offset in offsets[1:]:
            output.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
        output.extend(
            f'trailer\n<< /Size {len(objects)} /Root 1 0 R >>\n'
            f'startxref\n{xref_offset}\n%%EOF\n'.encode('ascii')
        )
        return bytes(output)


def _tone_colors(tone):
    return {
        'green': (GREEN, SOFT_GREEN),
        'gold': (GOLD, SOFT_GOLD),
        'rose': (ROSE, SOFT_ROSE),
    }.get(tone, (MAROON_700, CREAM))


def _draw_header(page, title, subtitle, generated_label):
    page.rect(0, 0, PAGE_WIDTH, 96, fill=MAROON_900)
    page.text(MARGIN, 25, 'JMCFI AMS', size=11, color=(1, 1, 1), bold=True)
    page.text(MARGIN, 44, title, size=21, color=(1, 1, 1), bold=True)
    page.text(MARGIN, 72, subtitle, size=9, color=(1, 1, 1))
    page.text(PAGE_WIDTH - MARGIN - 150, 72, generated_label, size=8, color=(1, 1, 1))


def _draw_kpis(page, metrics, y):
    labels = [
        ('readiness', 'Overall Readiness', '%'),
        ('total', 'Total Submissions', ''),
        ('compliance', 'Compliance Rate', '%'),
        ('revisions', 'Needs Revision', ''),
    ]
    gap = 10
    width = (PAGE_WIDTH - (MARGIN * 2) - gap * 3) / 4
    for index, (key, label, suffix) in enumerate(labels):
        x = MARGIN + index * (width + gap)
        value = metrics.get(key, 0)
        value_text = f'{value}{suffix}'
        page.rect(x, y, width, 68, fill=SURFACE, stroke=BORDER)
        page.text(x + 12, y + 13, value_text, size=19, color=MAROON_800, bold=True)
        page.text_wrap(x + 12, y + 39, label, width - 24, size=8.5, color=MUTED)


def _draw_insights(page, insights, y):
    page.text(MARGIN, y, 'Report insights', size=13, color=TEXT, bold=True)
    y += 22
    gap = 10
    width = (PAGE_WIDTH - (MARGIN * 2) - gap * 2) / 3
    for index, insight in enumerate(insights[:3]):
        tone, background = _tone_colors(insight.get('tone'))
        x = MARGIN + index * (width + gap)
        page.rect(x, y, width, 76, fill=background, stroke=tone)
        page.text(x + 12, y + 12, 'INSIGHT', size=7, color=tone, bold=True)
        page.text_wrap(x + 12, y + 28, insight.get('message', ''), width - 24, size=8.5, color=TEXT, leading=11)


def _draw_area_readiness(page, areas, y):
    card_height = 378
    page.rect(MARGIN, y, PAGE_WIDTH - MARGIN * 2, card_height, fill=SURFACE, stroke=BORDER)
    page.text(MARGIN + 16, y + 16, 'Area readiness', size=13, color=TEXT, bold=True)
    page.text(MARGIN + 16, y + 36, 'Actual complied evidence from the current access scope', size=8.5, color=MUTED)

    columns = 2
    column_gap = 24
    column_width = (PAGE_WIDTH - MARGIN * 2 - 32 - column_gap) / columns
    row_height = 52
    start_y = y + 62
    for index, area in enumerate(areas):
        column = index // 6
        row = index % 6
        x = MARGIN + 16 + column * (column_width + column_gap)
        row_y = start_y + row * row_height
        value = max(0, min(float(area.get('value') or 0), 100))
        page.text(x, row_y, f"{area.get('code', '')} - {area.get('name', '')}", size=8.5, color=TEXT, bold=True)
        page.text(x + column_width - 32, row_y, f'{value:g}%', size=8.5, color=MAROON_700, bold=True)
        bar_y = row_y + 18
        page.rect(x, bar_y, column_width, 9, fill=CREAM)
        page.rect(x, bar_y, column_width * value / 100, 9, fill=MAROON_700)


def _draw_department_chart(page, departments, y):
    chart_height = 260
    page.rect(MARGIN, y, PAGE_WIDTH - MARGIN * 2, chart_height, fill=SURFACE, stroke=BORDER)
    page.text(MARGIN + 16, y + 16, 'Compliance by department', size=13, color=TEXT, bold=True)
    page.text(MARGIN + 16, y + 36, 'Submitted evidence compared with complied evidence', size=8.5, color=MUTED)
    rows = departments[:10]
    if not rows:
        page.text(MARGIN + 16, y + 82, 'No department records are visible for this account.', size=9, color=MUTED)
        return
    max_width = 300
    row_height = 20
    start_y = y + 66
    for index, department in enumerate(rows):
        row_y = start_y + index * row_height
        label = _pdf_safe(department.get('name', ''))
        if len(label) > 27:
            label = f'{label[:25]}...'
        page.text(MARGIN + 16, row_y, label, size=8, color=TEXT)
        bar_x = MARGIN + 180
        rate = max(0, min(float(department.get('compliance') or 0), 100))
        tone, _ = _tone_colors(department.get('tone'))
        page.rect(bar_x, row_y + 2, max_width, 9, fill=CREAM)
        page.rect(bar_x, row_y + 2, max_width * rate / 100, 9, fill=tone)
        page.text(bar_x + max_width + 8, row_y, f'{rate:g}%', size=8, color=TEXT, bold=True)


def _draw_department_table(page, departments, y):
    page.text(MARGIN, y, 'Department detail', size=13, color=TEXT, bold=True)
    y += 20
    columns = [
        ('Department', 220),
        ('Submitted', 72),
        ('Complied', 72),
        ('Rate', 58),
        ('Status', 76),
    ]
    x = MARGIN
    header_height = 23
    page.rect(MARGIN, y, PAGE_WIDTH - MARGIN * 2, header_height, fill=MAROON_800)
    for label, width in columns:
        page.text(x + 8, y + 6, label, size=8, color=(1, 1, 1), bold=True)
        x += width
    y += header_height
    for index, department in enumerate(departments):
        row_height = 23
        fill = SURFACE if index % 2 == 0 else CREAM
        page.rect(MARGIN, y, PAGE_WIDTH - MARGIN * 2, row_height, fill=fill, stroke=BORDER, line_width=0.4)
        values = [
            department.get('name', ''),
            department.get('submitted', 0),
            department.get('compiled', 0),
            f"{department.get('compliance', 0)}%",
            department.get('status', ''),
        ]
        x = MARGIN
        for value, (label, width) in zip(values, columns):
            color = TEXT
            if label == 'Status':
                color, _ = _tone_colors(department.get('tone'))
            page.text(x + 8, y + 6, value, size=8, color=color, bold=label in {'Department', 'Status'})
            x += width
        y += row_height
    return y


def _draw_trend_chart(page, approval_data, revision_data, y):
    chart_height = 260
    page.rect(MARGIN, y, PAGE_WIDTH - MARGIN * 2, chart_height, fill=SURFACE, stroke=BORDER)
    page.text(MARGIN + 16, y + 16, 'Weekly submission trend', size=13, color=TEXT, bold=True)
    page.text(MARGIN + 16, y + 36, 'Values are calculated from submission and review timestamps', size=8.5, color=MUTED)

    chart_x = MARGIN + 48
    chart_y = y + 64
    chart_width = PAGE_WIDTH - MARGIN * 2 - 72
    chart_bottom = chart_y + 150
    for tick in range(4):
        tick_y = chart_y + tick * 50
        page.line(chart_x, tick_y, chart_x + chart_width, tick_y, color=BORDER, line_width=0.5)
    page.line(chart_x, chart_y, chart_x, chart_bottom, color=MUTED, line_width=0.7)
    page.line(chart_x, chart_bottom, chart_x + chart_width, chart_bottom, color=MUTED, line_width=0.7)

    all_values = [
        float(point.get('value') or 0)
        for point in list(approval_data) + list(revision_data)
    ]
    max_value = max(all_values or [1]) or 1

    def points(data):
        if not data:
            return []
        denominator = max(len(data) - 1, 1)
        return [
            (
                chart_x + chart_width * index / denominator,
                chart_bottom - (float(point.get('value') or 0) / max_value * 150),
            )
            for index, point in enumerate(data)
        ]

    approval_points = points(approval_data)
    revision_points = points(revision_data)
    if approval_points:
        page.polyline(approval_points, color=MAROON_700, line_width=2)
        for point in approval_points:
            page.circle(point[0], point[1], 2.5, fill=MAROON_700)
    if revision_points:
        page.polyline(revision_points, color=ROSE, line_width=2)
        for point in revision_points:
            page.circle(point[0], point[1], 2.5, fill=ROSE)

    page.line(chart_x + chart_width - 115, y + 42, chart_x + chart_width - 99, y + 42, color=MAROON_700, line_width=2)
    page.text(chart_x + chart_width - 94, y + 37, 'Approvals', size=8, color=MUTED)
    page.line(chart_x + chart_width - 50, y + 42, chart_x + chart_width - 34, y + 42, color=ROSE, line_width=2)
    page.text(chart_x + chart_width - 29, y + 37, 'Revisions', size=8, color=MUTED)

    if approval_data:
        for index, point in enumerate(approval_data):
            page.text(
                chart_x + chart_width * index / max(len(approval_data) - 1, 1) - 12,
                chart_bottom + 8,
                point.get('label', ''),
                size=7,
                color=MUTED,
            )


def _draw_status_summary(page, statuses, y):
    page.text(MARGIN, y, 'Status summary', size=13, color=TEXT, bold=True)
    y += 20
    x = MARGIN
    for status in statuses:
        width = 125
        if x + width > PAGE_WIDTH - MARGIN:
            x = MARGIN
            y += 42
        page.rect(x, y, width - 8, 32, fill=CREAM, stroke=BORDER)
        page.text(x + 8, y + 6, status.get('label', ''), size=7.5, color=MUTED)
        page.text(x + 8, y + 17, status.get('count', 0), size=11, color=MAROON_800, bold=True)
        x += width


def build_report_pdf(report_context, generated_label='Generated from live database records'):
    """Return a PDF containing the values supplied by the reports view."""
    document = PdfDocument()
    cycle = report_context.get('cycle')
    metrics = report_context.get('report_metrics', {})
    cycle_label = f'Academic Year {cycle.academic_year} - {cycle.name}' if cycle else 'No active accreditation cycle configured'

    first_page = document.add_page()
    _draw_header(first_page, 'Reports and Monitoring', cycle_label, generated_label)
    _draw_kpis(first_page, metrics, 116)
    _draw_insights(first_page, report_context.get('insights', []), 208)
    _draw_area_readiness(first_page, report_context.get('radar_areas', []), 322)

    second_page = document.add_page()
    _draw_header(second_page, 'Department Compliance', cycle_label, generated_label)
    departments = report_context.get('departments', [])
    _draw_department_chart(second_page, departments, 116)
    department_table_y = 402
    if departments and department_table_y + 24 + len(departments) * 23 > PAGE_HEIGHT - MARGIN:
        _draw_department_table(second_page, departments[:14], department_table_y)
        remaining = departments[14:]
    else:
        _draw_department_table(second_page, departments, department_table_y)
        remaining = []

    if remaining:
        third_page = document.add_page()
        _draw_header(third_page, 'Department Compliance - Continued', cycle_label, generated_label)
        _draw_department_table(third_page, remaining, 116)

    trend_page = document.add_page()
    _draw_header(trend_page, 'Submission Activity', cycle_label, generated_label)
    _draw_trend_chart(
        trend_page,
        report_context.get('trend_approval_data', []),
        report_context.get('trend_revision_data', []),
        116,
    )
    _draw_status_summary(trend_page, report_context.get('status_summary', []), 406)

    return document.render()
