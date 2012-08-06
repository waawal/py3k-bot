""" Message-bot running on heroku, tweets all new packages that supports py3k
    (checks for updates on old <3k packages also)
"""


import os
import xmlrpclib
from time import time, sleep
from datetime import datetime

import requests
from twitter import OAuth, Twitter


QUERY_INTERVAL = 2 * 60 # In seconds, intervals between queries to PYPI, 2 min.
PYPI_SERVICE = 'http://pypi.python.org/pypi'
TIMEOUT = 5 # In seconds.

CLASSIFIERS = frozenset(("Programming Language :: Python :: 3",
                         "Programming Language :: Python :: 3.0",
                         "Programming Language :: Python :: 3.1",
                         "Programming Language :: Python :: 3.2",
                         "Programming Language :: Python :: 3.3",
                         "Programming Language :: Python :: 3.4",
                         ))


twitter = Twitter(auth=OAuth(os.environ['OAUTH_TOKEN'],
                             os.environ['OAUTH_SECRET'],
                             os.environ['CONSUMER_KEY'],
                             os.environ['CONSUMER_SECRET'],
                             ))


def get_meta(project, timeout=TIMEOUT):
    """ Gets the projects json-representation from PYPI.
    """
    meta = requests.get('http://pypi.python.org/pypi/{0}/json'.format(project),
                        timeout=timeout)
    return meta.json['info']

def post_to_twitter(projectname, meta, msgtype):
    """ Composes a twitter-post and sends it on its way.
    """
    chrcount = 0
    message = []

    msgtype = '[{0}]'.format(msgtype.upper())
    message.append(msgtype)
    chrcount += len(msgtype)

    message.append(projectname)
    chrcount += len(projectname)

    message.append('pypi:')
    chrcount += len('pypi:')
    message.append('http://pypi.python.org/pypi/{0}/'.format(projectname))
    chrcount += 21 # t.co-urls are at most 21

    # If a home-page is provided, lets use it, otherwise - fall back to crate.
    if meta.get('home_page') and not meta.get('home_page') == "UNKNOWN":
        message.extend(('www:', meta['home_page']))
        chrcount += (len('www:') + 21)
    else:
        message.extend(('crate.io:',
                        'https://crate.io/packages/{0}/'.format(projectname)))
        chrcount += (len('crate.io:') + 21)

    # Important, add #python
    message.append('#python')
    chrcount += 7

    # Building the summary.
    chrcount += (len(message) + 1) # 1 = the space before the summary.
    chrsleft = 140 - chrcount
    
    if meta.get('summary'):
        if len(meta['summary']) > chrsleft:
            message.insert(2, "".join((meta['summary'][:(chrsleft-3)], '...')))
        else:
            message.insert(2, meta['summary'])
    finalmessage = " ".join(message)

    # All done!
    print "Posting to twitter: ", finalmessage, "length: ", len(finalmessage)
    twitter.statuses.update(status=finalmessage)

def check_for_updates():
    """ Checks for new projects and updates.
    """
    client = xmlrpclib.ServerProxy(PYPI_SERVICE)
    updates = client.changelog(int(time() - QUERY_INTERVAL))
    # Returns a list of ['vimeo', '0.1.2', 1344087619,
    #                    'update description, _pypi_hidden, classifiers']
    
    if updates: print updates # Log to heroku.

    for module in updates:
        name, version, timestamp, actions = module
        if 'create' in actions:
            sleep(3) # Sleep 3 secs awaiting json-representation.
            try:
                meta = get_meta(name)
            except TypeError:
                meta = {}
            if CLASSIFIERS.intersection(meta.get('classifiers')):
                supported.add(name)
                post_to_twitter(name, meta, 'new')

    for module in updates: # Must iterate 2 times, updates can come before new.
        name, version, timestamp, actions = module
        if 'new release' in actions or 'classifiers' in actions:
            if name not in supported:
                try:
                    meta = get_meta(name)
                except TypeError:
                    meta = {}
                if CLASSIFIERS.intersection(meta.get('classifiers')):
                    supported.add(name)
                    post_to_twitter(name, meta, 'update')


def get_supported(classifiers):
    """ Builds a set of the PYPI-projects currently listed under the provided
        classifiers.
    """
    client = xmlrpclib.ServerProxy(PYPI_SERVICE)
    multicall = xmlrpclib.MultiCall(client)
    [multicall.browse([classifier]) for classifier in CLASSIFIERS]
    supported = set()
    for results in multicall():
        # Returns a list of ['projectname', 'version']
        supported = supported.union([result[0] for result in results])
    return supported


if __name__ == '__main__':
    supported = get_supported(CLASSIFIERS)
    while True:
        beginprocessing = time()
        check_for_updates()
        endprocessing = time()
        sleep(QUERY_INTERVAL - (endprocessing - beginprocessing)) # Consider processing time.

