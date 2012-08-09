""" Message-bot running on heroku, tweets all new packages that supports py3k
    (checks for updates of old <3k packages also)
"""


import os
import xmlrpclib
from time import time, sleep
from datetime import datetime

from twitter import OAuth, Twitter


QUERY_INTERVAL = 2 * 60 # In seconds, intervals between queries to PYPI, 2 min.
PYPI_SERVICE = 'http://pypi.python.org/pypi'
CLASSIFIERS = frozenset(("Programming Language :: Python :: 3",
                         "Programming Language :: Python :: 3.0",
                         "Programming Language :: Python :: 3.1",
                         "Programming Language :: Python :: 3.2",
                         "Programming Language :: Python :: 3.3",
                         ))


def count_chars_of_tweet(tweet):
    """ Counts the characters within a tweet.
    """
    chars = len(tweet) # we initially append the future spaces between words
    for part in tweet:
        if part.startswith("http://", "https://"):
            chars += 21 # t.co-urls are at most 21
        else:
            chars += len(part)
    return chars

def post_to_twitter(projectname, meta, msgtype):
    """ Composes a twitter-post and sends it on its way.
    """
    DIVIDER = "-"
    message = []

    msgtype = '[{0}]'.format(msgtype.upper())
    message.append(msgtype)

    message.append(projectname)
    message.append(DIVIDER)

    message.append('pypi:')
    message.append('http://pypi.python.org/pypi/{0}/'.format(projectname))

    # If a home-page is provided, lets use it, otherwise - fall back to crate.
    homepage = meta.get('home_page', 'UNKNOWN')
    if not homepage == "UNKNOWN":
        message.append('www:')
        message.append(homepage)
    else:
        message.append('crate.io:')
        message.append('https://crate.io/packages/{0}/'.format(projectname))

    # Important, add #python
    message.append('#python')

    # Building the summary.
    currentchars = count_chars_of_tweet(message)
    chrsleft = 140 - (currentchars + 1) # +1 = the space before summary.
    
    summary = meta.get('summary', 'UNKNOWN')
    if not summary == "UNKNOWN":
        if len(summary) > chrsleft:
            message.insert(2, "".join((summary[:(chrsleft-3)], '...'))) # Trunc.
        else:
            message.insert(2, summary)
    
    finalmessage = " ".join(message)

    # All done!
    AUTH = OAuth(os.environ['OAUTH_TOKEN'],
                 os.environ['OAUTH_SECRET'],
                 os.environ['CONSUMER_KEY'],
                 os.environ['CONSUMER_SECRET'],
                 )
    twitter = Twitter(auth=AUTH)
    twitter.statuses.update(status=finalmessage)

def check_for_updates(supported, classifiers, interval, service):
    """ Checks for new projects and updates.
    """
    startprocessing = time() # Let's do this!
    client = xmlrpclib.ServerProxy(service)
    updates = client.changelog(startprocessing - interval)
    # Returns a list of:
    #['vimeo', '0.1.2', 1344087619,'update description, classifiers']
    
    if updates:
        print updates # Log to heroku.

        for module in updates:
            name, version, timestamp, actions = module
            if 'create' in actions:
                meta = client.release_data(name, version)
                if classifiers.intersection(meta.get('classifiers')):
                    supported.add(name)
                    post_to_twitter(name, meta, 'new')

        for module in updates: # Updates can come before new.
            name, version, timestamp, actions = module
            if 'new release' in actions or 'classifiers' in actions:
                if name not in supported:
                    meta = client.release_data(name, version)
                    if classifiers.intersection(meta.get('classifiers')):
                        supported.add(name)
                        post_to_twitter(name, meta, 'update')

    endprocessing = time()
    processingtime = endprocessing - startprocessing
    return processingtime

def get_supported(classifiers, service):
    """ Builds a set of the PYPI-projects currently listed under the provided
        classifiers.
    """
    client = xmlrpclib.ServerProxy(service)
    multicall = xmlrpclib.MultiCall(client)
    [multicall.browse([classifier]) for classifier in classifiers]
    supported = set()
    for results in multicall(): # Returns a list of ['projectname', 'version']
        supported = supported.union([result[0] for result in results])
    return supported


if __name__ == '__main__':
    supported = get_supported(classifiers=CLASSIFIERS, service=PYPI_SERVICE)
    sleep(QUERY_INTERVAL)
    while True:
        processingtime = check_for_updates(supported=supported,
                                           classifiers=CLASSIFIERS,
                                           interval=QUERY_INTERVAL,
                                           service=PYPI_SERVICE,
                                           )
        sleep(QUERY_INTERVAL - processingtime) # Consider processing time.

