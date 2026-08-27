"""
Tiny line-chart geometry helper.

Keeps coordinate math out of the template: give it a set of series
sharing one y-scale and it returns SVG-ready point strings. If this
dashboard grows real data, swap the caller's source (still just a
list of numbers in, points out) and nothing else changes.
"""

WIDTH = 680
HEIGHT = 200
PAD_LEFT = 8
PAD_RIGHT = 8
PAD_TOP = 10
PAD_BOTTOM = 10


def build_line_chart(categories, series, max_value):
    """
    categories: list of x-axis labels (e.g. months)
    series: list of {"name", "color", "values"} dicts, one value per category
    max_value: y-axis scale ceiling

    Returns a dict with plot geometry and, per series, a `points`
    string for <polyline> and an `area_points` string for the
    filled-area variant (first series only needs area_points).
    """
    plot_width = WIDTH - PAD_LEFT - PAD_RIGHT
    plot_height = HEIGHT - PAD_TOP - PAD_BOTTOM
    baseline_y = PAD_TOP + plot_height

    if not categories:
        return {
            'width': WIDTH,
            'height': HEIGHT,
            'baseline_y': baseline_y,
            'series': [],
            'x_labels': [],
        }

    # A zero ceiling is valid when a new dashboard has no activity yet.
    max_value = max(float(max_value), 1)
    steps = max(len(categories) - 1, 1)
    x_step = plot_width / steps

    def coords(values):
        pts = []
        for i, v in enumerate(values):
            x = PAD_LEFT + i * x_step
            y = PAD_TOP + plot_height - (v / max_value * plot_height)
            pts.append((round(x, 1), round(y, 1)))
        return pts

    rendered_series = []
    for s in series:
        pts = coords(s['values'])
        points_str = ' '.join(f'{x},{y}' for x, y in pts)
        area_str = (
            f'{pts[0][0]},{baseline_y} ' + points_str +
            f' {pts[-1][0]},{baseline_y}'
        )
        rendered_series.append({
            'name': s['name'],
            'color': s['color'],
            'points': points_str,
            'point_data': [
                {
                    'x': x,
                    'y': y,
                    'category': categories[index],
                    'value': s['values'][index],
                }
                for index, (x, y) in enumerate(pts)
            ],
            'area_points': area_str,
            'last_point': pts[-1],
        })

    x_labels = []
    for i, label in enumerate(categories):
        x_labels.append({'label': label, 'x': round(PAD_LEFT + i * x_step, 1)})

    return {
        'width': WIDTH,
        'height': HEIGHT,
        'baseline_y': PAD_TOP + plot_height,
        'series': rendered_series,
        'x_labels': x_labels,
    }
