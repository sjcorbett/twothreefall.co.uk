from django.utils import unittest
from lastfmexplorer.models import Update, User

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


class Updates(unittest.TestCase):

    def __init__(self, methodName):
        from datetime import date
        unittest.TestCase.__init__(self, methodName)

        # Create a test user
        self.testUserA = User.objects.create(username="aradnuk", registered=date(2004, 2, 2),
            last_updated=date.today(), image="http://www.example.com")
        self.testUserB = User.objects.create(username="kibbls", registered=date(2006, 2, 2),
            last_updated=date.today(), image="http://www.example.com")

        # And insert a couple of updates
        Update.objects.create(user=self.testUserA, week_idx=1)
        Update.objects.create(user=self.testUserA, week_idx=2)

    def testIsUpdating(self):
        self.assertTrue(Update.objects.is_updating(self.testUserA))
        self.assertFalse(Update.objects.is_updating(self.testUserB))