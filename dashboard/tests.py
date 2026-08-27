from django.test import SimpleTestCase

from .charting import build_line_chart


class LineChartTests(SimpleTestCase):
    def test_chart_contains_tooltip_data_for_each_series_point(self):
        chart = build_line_chart(
            ['Jan', 'Feb'],
            [{'name': 'Submitted', 'color': 'maroon', 'values': [0, 4]}],
            max_value=4,
        )

        series = chart['series'][0]
        self.assertEqual(series['point_data'][0]['category'], 'Jan')
        self.assertEqual(series['point_data'][1]['value'], 4)
        self.assertEqual(len(series['point_data']), 2)

    def test_empty_chart_data_is_safe(self):
        chart = build_line_chart([], [], max_value=0)

        self.assertEqual(chart['series'], [])
        self.assertEqual(chart['x_labels'], [])
