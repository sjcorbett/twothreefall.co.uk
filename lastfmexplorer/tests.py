from django.utils import unittest

import tasks, requester

class XMLHandling(unittest.TestCase):
    """Tests for valid Last.fm XML files"""
    def __init__(self, methodName):
        import os
        unittest.TestCase.__init__(self, methodName)
        path = os.path.dirname(__file__)
        path = os.path.join(path, "test-data")
        self.requester = requester.TestRequester(path)

    def testWeeklyChartParsing(self):
        chartList = list(tasks.chart_list('aradnuk', self.requester))
        expected  = [(1108296002, 1108900802), (1108900801, 1109505601),
                        (1109505601, 1110110401), (1110110401, 1110715201)]
        self.assertListEqual(chartList, expected)

    def testWeekDataParsing(self):
        data = tasks.week_data('aradnuk', self.requester, 1109505601, 1110110401)
        self.assertEqual(len(data.keys()), 74)
        # .. assertions against contents of db


class RequestErrorHandling(unittest.TestCase):
    """.. and ones for invalid Last.fm XML files"""
    pass