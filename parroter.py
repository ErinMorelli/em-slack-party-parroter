#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright (c) 2017 Erin Morelli.

Title       : EM Slack Party Parroter
Author      : Erin Morelli
Email       : erin@erinmorelli.com
License     : MIT
Version     : 0.1a
"""

# Future
from __future__ import print_function

# Built-ins
import re
import sys
import json
from urllib import quote

# Third-party
import yaml
import requests
from bs4 import BeautifulSoup
from requests.packages import urllib3

# TODO: Remove when done
from pprint import pprint

# Script credits
__title__ = 'EM Slack Party Parroter'
__copyright__ = 'Copyright (c) 2017, Erin Morelli'
__author__ = 'Erin Morelli'
__email__ = 'erin@erinmorelli.com'
__license__ = 'MIT'
__version__ = '0.1a'

# Disable SSL warnings
urllib3.disable_warnings()

# Party Parrot GitHub contants
PARROT_ROOT = 'https://raw.githubusercontent.com/jmhobbs/cultofthepartyparrot.com/master/{0}'
PARROT_JSON = PARROT_ROOT.format('parrots.json')
PARROT_IMG = PARROT_ROOT.format('parrots')


def get_current_emoji_list(session):
    emoji_page = session.get(emoji_url)
    emoji_page.raise_for_status()
    emoji_regex = r'data-emoji-name=\"(.*?)\"'
    emoji = re.findall(emoji_regex, emoji_page.text)
    return emoji


def get_form_crumb(page):
    soup = BeautifulSoup(page.text, "html.parser")
    return soup.find("input", attrs={"name": "crumb"})["value"]


def start_slack_session():
    # Start requests session
    session = requests.Session()

    # Load login page
    login_page = session.get(team_url)
    login_page.raise_for_status()

    # Get login crumb
    login_crumb = get_form_crumb(login_page)

    # Set params
    data = [
        'signin=1',
        'redir=',
        'crumb={0}'.format(quote(login_crumb.encode('utf-8'), safe='*')),
        'email={0}'.format(quote(auth['email'], safe='*')),
        'password={0}'.format(quote(auth['password'], safe='*')),
        'remember=on'
    ]

    # Login to Downpour
    login = session.post(
        team_url,
        data='&'.join(data),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        allow_redirects=False
    )
    login.raise_for_status()

    return session

def get_parrot_list():
    parrots = requests.get(PARROT_JSON)
    return parrots.json()



# TODO: Remove when done
# Load Slack credentials for testing
auth = yaml.load(open('credentials.yml').read())

# Build team URL
team_url = 'https://{team}.slack.com'.format(team=auth['team'])
emoji_url = '{team_url}/customize/emoji'.format(team_url=team_url)

# Get all parrots
parrots = get_parrot_list()

# Login to slack
session = start_slack_session()

# Get existing emoji
current_emoji = get_current_emoji_list(session)

added = []
skipped = []

for parrot in parrots:
    if 'hd' in parrot.keys():
        parrot_name = re.split(r'\/|\.', parrot['hd'])[1]
    elif 'gif' in parrot.keys():
        parrot_name = re.split(r'\.', parrot['gif'])[0]

    if parrot_name in current_emoji:
        skipped.append(parrot['name'])

