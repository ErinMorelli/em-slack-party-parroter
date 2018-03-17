#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
reload(sys)
sys.setdefaultencoding('utf8')

import re
import requests
import mechanize
from getpass import getpass
from pprint import pprint

team = raw_input('Slack Team: ').strip()
email = raw_input('Google Email: ').strip()
password = getpass('Google Password: ')

team_url = 'https://{team}.slack.com'.format(team=team)

session = requests.Session()

landing = session.get(team_url)
landing.raise_for_status()

oauth_url_regex = r'<a href="(https://accounts\.google\.com/o/oauth2/.*)" '
oauth_url_match = re.search(oauth_url_regex, landing.content)
oauth_url = oauth_url_match.group(1)
oauth_url = re.sub(r'&amp;', '&', oauth_url)
print oauth_url

br = mechanize.Browser()
br.open(oauth_url)
br.select_form(id='gaia_loginform')
br['Email'] = email
br.submit()
br.response()
br.select_form(id='gaia_loginform')
br['Passwd'] = password
br.submit()
br.response()
br.select_form()
print br.read()
# print br.__dict__
