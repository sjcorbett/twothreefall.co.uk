# Django settings for twothreefall project.

import socket
import sys

DEV = socket.gethostname() == "fook"
del socket

import os

from secrets import *

DEBUG = DEV
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('Sam', 'sam@twothreefall.co.uk'),
)

MANAGERS = ADMINS

# Initially set in secrets.
if 'test' in sys.argv:
    DATABASES['default'] = {
        'ENGINE' : 'django.db.backends.sqlite3',
        'NAME' : 'ttf.sqlite'
    }

TIME_ZONE = 'Europe/London'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = False

# Absolute path to the directory that holds media.
MEDIA_ROOT = '/home/sam/code/ttf/twothreefall/media/' if DEV else \
    '/var/www/twothreefall.co.uk/twothreefall/media/'

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
MEDIA_URL = 'http://127.0.0.1:8000/media/' if DEV else \
    "http://twothreefall.co.uk/media/"

# STATIC_ROOT set in secrets
STATIC_URL = '/static/'
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
#    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Including broke admin css?
ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.gzip.GZipMiddleware',
)

ROOT_URLCONF = 'twothreefall.urls'

INTERNAL_IPS = ('127.0.0.1',)

APPEND_SLASH = True

########## Apps ###############################################################

INSTALLED_APPS = (
    # required for admin
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.sitemaps',
    'django.contrib.staticfiles',

    'twothreefall',
    'twothreefall.lastfmexplorer',
    # 'twothreefall.scrabble',
    # 'twothreefall.blog',
    # 'reversetag',
    'djcelery',
    # 'typogrify',
    'django_extensions',
    # 'tagging',
    # 'disqus',

    # django-sentry
    # 'indexer',
    # 'paging',
    # 'sentry',
    # 'sentry.client',

)

########## Dev options ########################################################

if DEV:
    MIDDLEWARE_CLASSES += ('debug_toolbar.middleware.DebugToolbarMiddleware',)
    INSTALLED_APPS += ('debug_toolbar',)
    DEBUG_TOOLBAR_CONFIG = {
        'INTERCEPT_REDIRECTS' : False
    }

########## Memcached ##########################################################

CACHE_BACKEND = 'memcached://127.0.0.1:11211/'
CACHE_USER_TIMEOUT = 1 if DEV else 60 * 5 # five minutes
CACHE_DATA_TIMEOUT = 1 if DEV else 60 * 60 * 24 * 7 # one week

########## Template contexts ##################################################

def basic_context(request):
    return { 'MEDIA_URL' : MEDIA_URL, 'DEV' : DEV } 

TEMPLATE_DIRS = (
    os.path.join(os.path.dirname(__file__), 'templates/html'),
    os.path.join(os.path.dirname(__file__), 'lastfmexplorer/templates/html'),
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'twothreefall.settings.basic_context',
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.static',
)



