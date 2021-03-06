import os

from datetime import date
from django.test import TestCase, TransactionTestCase

import tasks
import requester
import ldates
import chart

from models import Artist, Update, User, WeekData


def makeUser(name, registered=date(2004, 2, 2), last_updated=date.today(), image="http://www.example.com"):
    return User.objects.create(username=name, registered=registered, last_updated=last_updated, image=image)


class UserTests(TransactionTestCase):
    """Check unusual usernames are considered valid"""
    def testValid(self):
        names = ["Mrs DNA", "392414", "_abc_"]
        for name in names:
            self.assertTrue(User.valid_username(name), "Failed on: '"+name+"'")

    def testInvalid(self):
        names = [" "]
        for name in names:
            self.assertFalse(User.valid_username(name), "Expected invalid name on: '"+name+"'")


class XMLHandling(TestCase):
    """Tests for valid and troublesome Last.fm XML files"""
    def setUp(self):
        path = os.path.dirname(__file__)
        path = os.path.join(path, "test-data")
        self.requester = requester.TestRequester(path)

    def tearDown(self):
        Artist.objects.all().delete()
        WeekData.objects.all().delete()

    def testWeeklyChartParsing(self):
        chartList = list(tasks.fetch_chart_list('aradnuk', self.requester))
        expected  = [(1108296002, 1108900802), (1108900801, 1109505601),
                        (1109505601, 1110110401), (1110110401, 1110715201)]
        self.assertSequenceEqual(chartList, expected)

    def testWeekDataParsing(self):
        data = tasks._parse_week_artist_data(tasks.week_data('aradnuk', self.requester, 1109505601, 1110110401))
        self.assertEqual(len(data.keys()), 74)
        playcount, artistId = data[data.keys()[0]]
        artist = Artist.objects.get(id=artistId)
        self.assertEqual(playcount, 79)
        self.assertEqual(artist.name, "BT")

    def testAwkwardXmlRecovery(self):
        data = tasks._parse_week_artist_data(tasks.week_data('Eddard_Stark', self.requester, 1175385600, 1175990400))
        self.assertEqual(len(data.keys()), 1)
        playcount, artistId = data[data.keys()[0]]
        self.assertEqual(playcount, 32)

    def testMoreAwkwardXmlRecovery(self):
        data = tasks._parse_week_artist_data(tasks.week_data('Dieg0', self.requester, 1284854400, 1285459200))
        self.assertEqual(len(data.keys()), 1)
        playcount, artistId = data[data.keys()[0]]
        self.assertEqual(playcount, 1)


class WeeklyTrackDataHandling(TestCase):
    pass


class Updates(TransactionTestCase):
    def setUp(self):
        # Create a test user
        self.testUserA = makeUser("aradnuk")
        self.testUserB = makeUser("kibbls")
        self.testUserC = makeUser("mayric")

        # User A has two updates in progress, B has one complete and C has one in progress
        Update.objects.create(user=self.testUserA, week_idx=1, type=Update.ARTIST)
        Update.objects.create(user=self.testUserA, week_idx=2, type=Update.ARTIST)
        Update.objects.create(user=self.testUserB, week_idx=1, status=Update.COMPLETE, type=Update.TRACK)
        Update.objects.create(user=self.testUserC, week_idx=1, type=Update.ARTIST)

    def testIsUpdating(self):
        self.assertTrue(Update.objects.is_updating(self.testUserA))
        self.assertFalse(Update.objects.is_updating(self.testUserB))
 
    def testWeeksFetched(self):
        bFetched = Update.objects.weeks_fetched(self.testUserB)
        self.assertEqual(len(bFetched), 1)
        self.assertEqual(list(bFetched)[0][0], 1)
        self.assertEqual(list(bFetched)[0][1], Update.TRACK)

    def testStalled(self):
        self.assertEqual(len(Update.objects.stalled()), 0)


class Dates(TestCase):
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

    def testAllSundaysFallingIn(self):
        years = ldates.years_to_today()
        indices = []
        for year in years:
            indices.extend(ldates.all_sundays_falling_in(year))

        expected = range(0, ldates.first_sunday_on_or_after(date(years[-1]+1, 1, 1)))
        self.assertEqual(indices, expected)


class ChartTests(TransactionTestCase):
    def setUp(self):
        self.user = makeUser("test-charts")
        self.user2 = makeUser("test-charts-2")

        # Test artists
        self.a = Artist.objects.create(name='a')
        self.b = Artist.objects.create(name='b')
        self.c = Artist.objects.create(name='c')
        self.d = Artist.objects.create(name='d')

        # Artist and weekly plays for user 1
        artists_and_plays = (
            (self.a, (1, 1, 1, 1, 1)),
            (self.b, (None, None, None, 1, 1)),
            (self.c, (1, 2, 3, 4, 5)))
        for artist, weekplays in artists_and_plays:
            week = 0
            for plays in weekplays:
                if plays is not None:
                    WeekData.objects.create(user=self.user, week_idx=week, artist=artist, plays=plays, rank=1)
                week += 1

        # User 2 only plays artist d
        WeekData.objects.create(user=self.user2, week_idx=4, artist=self.d, plays=10, rank=1)
        WeekData.objects.create(user=self.user2, week_idx=5, artist=self.d, plays=10, rank=1)

    def testFullChart(self):
        c = chart.Chart(self.user, 0, 10)
        expected = [(self.c, 15), (self.a, 5), (self.b, 2)]
        self.assertSequenceEqual(expected, c)
        self.assertEqual(15, c.max)

    def testCount(self):
        self.assertSequenceEqual([], chart.Chart(self.user, 0, 10, count=0))
        self.assertSequenceEqual([(self.c, 15)], chart.Chart(self.user, 0, 10, count=1))
        self.assertSequenceEqual([(self.c, 15), (self.a, 5)], chart.Chart(self.user, 0, 10, count=2))

    def testExcludeBeforeStart(self):
        c = chart.Chart(self.user, 3, 10)
        c.set_exclude_before_start()
        self.assertSequenceEqual([(self.b, 2)], c)

    def testExcludeMonths(self):
        # TODO: Alter test to set dates to last sunday--
        pass

    def testExcludeBeforeStartAndExcludeMonths(self):
        # TODO: Alter test to set dates to last sunday--
        pass


class WeekDataTests(TransactionTestCase):
    def setUp(self):
        self.user = makeUser("test-charts")
        self.a = Artist.objects.create(name='a')
        self.b = Artist.objects.create(name='b')

        # Artist and weekly plays for user 1
        artists_and_plays = (
            (self.a, (1, 2, 3, 4, 5)),
            (self.b, (None, 2, None, 1, 1)))
        for artist, weekplays in artists_and_plays:
            week = 0
            for plays in weekplays:
                if plays is not None:
                    WeekData.objects.create(user=self.user, week_idx=week, artist=artist, plays=plays, rank=1)
                week += 1

    def testUserWeeklyPlaysOfArtist(self):
        playsOfA = WeekData.objects.user_weekly_plays_of_artists(self.user.id, self.a.id, 0, 10)
        playsOfB = WeekData.objects.user_weekly_plays_of_artists(self.user.id, self.b.id, 0, 2)
        self.assertEquals([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)], playsOfA)
        self.assertEquals([(1, 2)], playsOfB)
