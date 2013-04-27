import StringIO
import gzip
import urllib2
import logging
import traceback

from httplib import BadStatusLine
from urllib import urlencode

from twothreefall.settings import LASTFM_API_KEY

class Requester:

    def __init__(self, saveResponses=False):
        # TODO: Last.fm seems to have disabled gzip encoding?!
        self.shouldGzip = False
        self.saveResponses = saveResponses

    def url_for_request(self, method, extras):
        """To be overriden by subclasses"""
        raise NotImplementedError("Should be overriden by subclass")

    # TODO: Handle HTTP 503s.
    def make(self, method, extras=None):
        """
        Requests data from Last.fm.
          method: string name of an API method
          extras: any arguments, whether required or optional.
        """
        query = self.url_for_request(method, extras)
        logging.info(query)

        req = urllib2.Request(query)
        if self.shouldGzip:
            req.add_header('Accept-encoding', 'gzip')
        req.add_header('User-agent', 'Last.fm Explorer')

        result = { 'success' : False }

        max_retries = 2 
        attempt     = 0

        while not result['success'] and attempt < max_retries:
            attempt += 1
            try:
                r = urllib2.urlopen(req, timeout=60).read()
                result['data'] = self.__unzip(r) if self.shouldGzip else r
                result['success'] = True
                if self.saveResponses:
                    self.__save_response(method, extras, result['data'])

            except urllib2.HTTPError, e:
                logging.error("Requestor errored accessing " + query + " - " + str(e.code))
                result['error'] = { 'code' : e.code, 'message' : e.msg }

            except urllib2.URLError, e:
                logging.error("Requestor failed to fetch " + query + ' - URLError.')
                result['error'] = { 'message' : e.reason }

            except BadStatusLine:
                logging.error("Requestor caught BadStatusLine, attempt %d" % (attempt,))
                result['error'] = { 'message' : "Request gave BadStatusLine" }

            except IOError, e:
                logging.error("Requestor caught IOError, attempt %d" % (attempt,))
                result['error'] = { 'message' : "Request gave IOError: " + str(e) }

            except Exception as instance:
                logging.error("Requestor caught unknown exception for request " + query + " - " + str(type(instance)))
                logging.error(traceback.format_exc())
                result['error'] = { 'messasge' : "Unknown problem" }

        return result

    def __save_response(self, method, extras, data):
        """Writes given data to disk"""

        import os, re
        to = "/tmp/lex/"
        if not os.path.exists(to):
            os.mkdir(to)

        removeables = re.compile('[/&?:]')
        filename = method + '-' + '_'.join("%s=%s" % kv for kv in extras.iteritems())
        filename = os.path.join(to, removeables.sub('_', filename))
        with open(filename, 'w') as f:
            f.write(data)

    def __unzip(self, data):
        """Unzips a gzipped stream.  Since gzip reads a file the data is represented as a file in memory. """
        compressed = StringIO.StringIO(data)
        gzipper    = gzip.GzipFile(fileobj=compressed)
        return gzipper.read()


class LastFMRequester(Requester):
    """Proper requests to Last.fm"""

    def __init__(self):
        Requester.__init__(self, saveResponses=False)

    def url_for_request(self, method, extras):
        args = urlencode(extras) if extras else ""
        return "http://ws.audioscrobbler.com/2.0/?method=%s&api_key=%s&%s" % (method, LASTFM_API_KEY, args)


class TestRequester(Requester):
    """Requests to the local file system to use when testing"""

    def __init__(self, rootDataDir):
        Requester.__init__(self, saveResponses=False)
        self.rootDataDir = rootDataDir

    def url_for_request(self, method, extras):
        if method == 'user.getweeklychartlist':
            testFile = "%s/weeklychartlist.xml" % (extras['user'],)
        elif method == 'user.getweeklyartistchart':
            testFile = "%(user)s/%(from)s-%(to)s.xml" % extras
        else:
            raise ValueError("Unknown method %s given to TestRequester" % (method,))
        
        return "file://%s/%s/%s" % (self.rootDataDir, method, testFile)
