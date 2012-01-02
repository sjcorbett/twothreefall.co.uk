import os
from datetime import date

from django.utils import unittest
from lastfmexplorer import ldates

from lastfmexplorer.models import Artist, Update, User
import tasks, requester

class XMLHandling(unittest.TestCase):
    """Tests for valid Last.fm XML files"""
    def setUp(self):
        path = os.path.dirname(__file__)
        path = os.path.join(path, "test-data")
        self.requester = requester.TestRequester(path)

    def testWeeklyChartParsing(self):
        chartList = list(tasks.fetch_chart_list('aradnuk', self.requester))
        expected  = [(1108296002, 1108900802), (1108900801, 1109505601),
                        (1109505601, 1110110401), (1110110401, 1110715201)]
        self.assertListEqual(chartList, expected)

    def testWeekDataParsing(self):
        data = tasks.week_data('aradnuk', self.requester, 1109505601, 1110110401)
        self.assertEqual(len(data.keys()), 74)

        playcount, artistId = data[1]
        artist = Artist.objects.get(id=1)
        self.assertEqual(playcount, 79)
        self.assertEqual(artist.name, "BT")



class RequestErrorHandling(unittest.TestCase):
    """.. and ones for invalid Last.fm XML files"""
    pass

class WeeklyTrackDataHandling(unittest.TestCase):
    pass

class Updates(unittest.TestCase):

    @classmethod
    def setUpClass(instance):
        # Create a test user
        instance.testUserA = User.objects.create(username="aradnuk", registered=date(2004, 2, 2),
            last_updated=date.today(), image="http://www.example.com")
        instance.testUserB = User.objects.create(username="kibbls", registered=date(2006, 2, 2),
            last_updated=date.today(), image="http://www.example.com")
        instance.testUserC = User.objects.create(username="mayric", registered=date(2008, 2, 2),
            last_updated=date.today(), image="http://www.example.com")

        # User A has two updates in progress, B has one complete and C has one in progress
        Update.objects.create(user=instance.testUserA, week_idx=1)
        Update.objects.create(user=instance.testUserA, week_idx=2)
        Update.objects.create(user=instance.testUserB, week_idx=1, status=Update.COMPLETE)
        Update.objects.create(user=instance.testUserC, week_idx=1)

    def testIsUpdating(self):
        self.assertTrue(Update.objects.is_updating(self.testUserA))
        self.assertFalse(Update.objects.is_updating(self.testUserB))
 
    def testWeeksFetched(self):
        bFetched = Update.objects.weeks_fetched(self.testUserB)
        self.assertEqual(len(bFetched), 1)
        self.assertEqual(bFetched[0].week_idx, 1)


class Dates(unittest.TestCase):
    def testSundaysBetween(self):
        # First charts release week ending 20/02/2005
        d = date
        self.assertEqual(ldates.sundays_between(d(2005, 1, 1), d(2005, 2, 28)), [0, 1])
        self.assertEqual(ldates.sundays_between(d(2005, 2, 20), d(2005, 2, 28)), [0, 1])
        self.assertEqual(ldates.sundays_between(d(2005, 2, 20), d(2005, 2, 20)), [0])

        # no Sundays between Tuesday and Friday in one week.
        self.assertEqual(ldates.sundays_between(d(2012, 3, 13), d(2012, 3, 16)), [])

        # From the beginning of time..
        self.assertEquals(ldates.sundays_between(d(2005, 2, 20), d.today()), range(0, ldates.idx_last_sunday+1))
