#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright (c) 2017 Erin Morelli.

Title       : EM Slack Party Parroter
Author      : Erin Morelli
Email       : erin@erinmorelli.com
License     : MIT
Version     : 0.1
"""

# Future
from __future__ import print_function

# Built-ins
import os
import re
import sys
from getpass import getpass

# Third-party
import requests
from requests.packages import urllib3
from bs4 import BeautifulSoup

# Import urllib for Python 2 and 3
try:
    from urllib import quote  # Python 2.X
except ImportError:
    from urllib.parse import quote  # Python 3+

# Script credits
__title__ = 'EM Slack Party Parroter'
__copyright__ = 'Copyright (c) 2017, Erin Morelli'
__author__ = 'Erin Morelli'
__email__ = 'erin@erinmorelli.com'
__license__ = 'MIT'
__version__ = '0.1'

# Disable SSL warnings
urllib3.disable_warnings()

# Handle Python 3+ input
try:
    raw_input
except NameError:
    raw_input = input

# Build the Party Parrot GitHub raw file URL
PARROT_ROOT = os.path.join(
    'https://raw.githubusercontent.com',  # GitHub raw file root
    'jmhobbs',                            # Username
    'cultofthepartyparrot.com',           # Repository
    'master',                             # Branch
    '{0}'
)


class EmSlackPartyParroter(object):
    """Class to interact with the Slack emoji customizer."""

    def __init__(self, team, email, password):
        """Initialize class and connect to Slack.

        Args:
            team (str): Slack team name slug
            email (str): Slack team user email address
            password (str): Slack team user password

        """
        self._parrot = {
            'json': PARROT_ROOT.format('parrots.json'),
            'img': PARROT_ROOT.format('parrots')
        }

        # Set auth
        self.auth = {
            'team': team,
            'email': email,
            'password': password
        }

        # Specify bs parser
        self._bs_parser = 'html.parser'

        # Build Slack team URLs
        self.team_url = 'https://{team}.slack.com'.format(team=team)
        self.emoji_url = '{team_url}/customize/emoji'.format(
            team_url=self.team_url
        )

        # Start slack session
        self.session = self.start_session()

    def get_current_emoji_list(self):
        """Retrieve list of current Slack team emoji."""
        emoji_page = self.session.get(self.emoji_url)
        emoji_page.raise_for_status()

        # Set emoji name parsing regex
        emoji_regex = r'data-emoji-name=\"(.*?)\"'

        # Find all emoji names on page
        emoji = re.findall(emoji_regex, emoji_page.text)

        # Return list of emoji
        return emoji

    def get_form_crumb(self, page):
        """Parse form on page to retrieve Slack crumb.

        Args:
            page (requests.Response): Page response object to parse

        Returns:
            str: Slack crumb string

        """
        soup = BeautifulSoup(page.text, self._bs_parser)
        return soup.find('input', attrs={'name': 'crumb'})['value']

    def start_session(self):
        """Login to Slack to start browsing session.

        Returns:
            requests.Session: Logged in Slack session object

        """
        session = requests.Session()

        # Load login page
        login_page = session.get(self.team_url)
        login_page.raise_for_status()

        # Get login crumb
        login_crumb = self.get_form_crumb(login_page)

        # Set params
        data = [
            'signin=1',
            'redir=',
            'crumb={0}'.format(quote(login_crumb.encode('utf-8'), safe='*')),
            'email={0}'.format(quote(self.auth['email'], safe='*')),
            'password={0}'.format(quote(self.auth['password'], safe='*')),
            'remember=on'
        ]

        # Login to Downpour
        login = session.post(
            self.team_url,
            data='&'.join(data),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            allow_redirects=False
        )
        login.raise_for_status()

        # Return logged in session
        return session

    def get_parrot_list(self):
        """Retrieve up-to-date parrot list from GitHub.

        Returns:
            list: Parsed JSON list of current parrots

        """
        parrots = requests.get(self._parrot['json'])
        parrots.raise_for_status()

        # Return parsed JSON
        return parrots.json()

    def add_parrot(self, parrot, use_hd=False):
        """Upload a new parrot emoji to a Slack team.

        Args:
            parrot (dict): Parrot emoji data
            hd (bool, optional): Whether to use an HD image file
                Default: False

        Returns:
            str: Error data, if there was a error, otherwise None

        """
        parrot_file = parrot['hd'] if use_hd else parrot['gif']

        # Get parrot image file path
        parrot_url = os.path.join(self._parrot['img'], parrot_file)

        # Get parrot
        parrot_img = requests.get(parrot_url, stream=True)
        parrot_img.raise_for_status()

        # Navigate to the emoji page
        emoji_page = self.session.get(self.emoji_url)
        emoji_page.raise_for_status()
        emoji_crumb = self.get_form_crumb(emoji_page)

        # Upload parrot
        emoji_upload = self.session.post(
            self.emoji_url,
            data={
                'add': 1,
                'crumb': emoji_crumb,
                'name': parrot['slug'],
                'mode': 'data'
            },
            files={
                'img': parrot_img.raw
            },
            allow_redirects=False
        )
        emoji_upload.raise_for_status()

        # Check for any errors
        if b'alert_error' in emoji_upload.content:
            # Parse page text
            soup = BeautifulSoup(emoji_upload.text, self._bs_parser)

            # Get error information
            error = soup.find('p', attrs={'class': 'alert_error'})

            # Return error text
            return error.text

    def parrot(self):
        """Get and upload new parrots to Slack team.

        Returns:
            list: List of added parrots

        """
        parrots = self.get_parrot_list()

        # Get existing emoji list
        current_emoji = self.get_current_emoji_list()

        # Initialize added parrots tracker
        added = []

        # Loop over all parrots
        for parrot in parrots:
            # Check if we can use an HD image
            if 'hd' in parrot.keys():
                use_hd = True
                parrot['slug'] = re.split(r'\/|\.', parrot['hd'])[1]

            # Otherwise use the standard GIF image
            elif 'gif' in parrot.keys():
                use_hd = False
                parrot['slug'] = re.split(r'\.', parrot['gif'])[0]

            # Add the parrot if it doesn't already exist
            if parrot['slug'] not in current_emoji:
                error = self.add_parrot(parrot, use_hd)

                # Report any errors
                if error is not None:
                    print(
                        '+ Error adding \'{parrot_slug}\', {error}'.format(
                            parrot_slug=parrot['slug'],
                            error=error
                        ),
                        file=sys.stderr
                    )
                    continue

                # Report success
                print(
                    '+ Added :{parrot_slug}:'.format(
                        parrot_slug=parrot['slug']
                    ),
                    file=sys.stdout
                )
                added.append(parrot)

        # Return list of added parrots
        return added

    @staticmethod
    def get_credentials():
        """Prompt user for Slack credentials.

        Returns:
            dict: User credentials
        """
        print('Login to Slack:', file=sys.stdout)

        # User prompts
        team = raw_input('+ Team Name: ').strip().lower()
        email = raw_input('+ Email: ').strip()
        password = getpass('+ Password: ')

        # Return dict of user data
        return {
            'team': team,
            'email': email,
            'password': password
        }


def main():
    """Main parroter function."""
    print('=== EM Slack Party Parroter ===', file=sys.stdout)

    # Get user Slack credentials
    auth = EmSlackPartyParroter.get_credentials()
    print('', file=sys.stdout)

    # Initialize the parroter
    parroter = EmSlackPartyParroter(**auth)

    # Start parroting
    print('Starting Parroting...', file=sys.stdout)
    added = parroter.parrot()

    # Finish parroting
    if not added:
        print('No new parrots to add!', file=sys.stdout)
    else:
        print(
            'Successfully added {count} new parrots!'.format(count=len(added)),
            file=sys.stdout
        )

# Run the parroter via CLI
if __name__ == '__main__':
    main()
