#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright (c) 2017 Erin Morelli.

Title       : EM Slack Party Parroter
Author      : Erin Morelli
Email       : erin@erinmorelli.com
License     : MIT
Version     : 0.2
"""

# Future
from __future__ import print_function

# Built-ins
import os
import re
import sys
import argparse
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
__version__ = '0.2'

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

    def __init__(self):
        """Initialize class and connect to Slack."""
        self._parrot = {
            'json': PARROT_ROOT.format('parrots.json'),
            'img': PARROT_ROOT.format('parrots')
        }

        # Build argparser
        self._build_parser()

        # Parse args
        self.args = self._parse_args()

        # Specify bs parser
        self._bs_parser = 'html.parser'

        # Build Slack team URLs
        self.team_url = 'https://{team}.slack.com'.format(team=self.args.team)
        self.emoji_url = '{team_url}/customize/emoji'.format(
            team_url=self.team_url
        )

        # Start slack session
        self.session = self.start_session()

    def _build_parser(self):
        """Build the CLI argument parser."""
        self._parser = argparse.ArgumentParser(
            description='{title} v{version} / by {author} <{email}>'.format(
                title=__title__,
                version=__version__,
                author=__author__,
                email=__email__
            ),
            formatter_class=argparse.RawTextHelpFormatter
        )

        # Create credentials argument group
        auth_group = self._parser.add_argument_group('Slack Credentials')

        # Add credential arguments
        auth_group.add_argument(
            '--team', '-t',
            default=os.getenv('SLACK_TEAM'),
            help='\n'.join(
                [
                    'Slack team name.',
                    'Defaults to the $SLACK_TEAM environment variable.'
                ]
            ),
            type=str.lower
        )
        auth_group.add_argument(
            '--email', '-e',
            default=os.getenv('SLACK_EMAIL'),
            help='\n'.join(
                [
                    'Slack user email address.',
                    'Defaults to the $SLACK_EMAIL environment variable.'
                ]
            )
        )
        auth_group.add_argument(
            '--password', '-p',
            default=os.getenv('SLACK_PASSWORD'),
            help='\n'.join(
                [
                    'Slack user password.',
                    'Defaults to the $SLACK_PASSWORD environment variable.'
                ]
            )
        )

        # Add optional arguments
        self._parser.add_argument(
            '--list_existing', '-l',
            action='store_true',
            help='Displays a list of your Slack team\'s existing parrots'
        )
        self._parser.add_argument(
            '--list_available', '-a',
            action='store_true',
            help='Displays a list of all available parrots'
        )

    def _parse_args(self):
        """Load credentials from args or prompt the user for them.

        Returns:
            object: User credentials and other CLI arguments

        """
        args = self._parser.parse_args()

        # Prompt user for missing args
        if not args.team:
            args.team_name = raw_input('Slack Team: ').strip()
        if not args.email:
            args.email = raw_input('Slack Email: ').strip()
        if not args.password:
            args.password = getpass('Slack Password: ')

        # Return args
        return args

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

    def get_login_page(self, session):
        """Get the non-OAuth slack team login page.

        Args:
            session (requests.Session): Requests session object

        Returns:
           requests.Session: Updated Requests session object
           requests.Response: Login page response object
           string: URL to use for login post call

        """
        post_regex = r'<form id="signin_form" action="/" method="post"'

        # Load initial team landing page
        landing = session.get(self.team_url)
        landing.raise_for_status()

        # Check for presence of login form and return if found
        if re.search(post_regex, landing.content):
            return (session, landing, self.team_url)

        # Set up non-OAuth page url
        non_oauth_url = '{team_url}/?no_sso=1'.format(team_url=self.team_url)

        # Attempt to load non-OAuth login page
        login = session.get(non_oauth_url)
        login.raise_for_status()

        # Check for presence of login form and return if found
        if re.search(post_regex, login.content):
            return (session, login, non_oauth_url)

        # Exit and print error message if login form is not found
        print(
            ' '.join(
                [
                    'ERROR: There was a problem logging in to Slack.',
                    'OAuth login is not supported at this time.'
                ]
            ),
            file=sys.stderr
        )
        sys.exit(1)

    def start_session(self):
        """Login to Slack to start browsing session.

        Returns:
            requests.Session: Logged in Slack session object

        """
        session = requests.Session()

        # Load login page
        (session, login_page, team_url) = self.get_login_page(session)

        # Get login crumb
        login_crumb = self.get_form_crumb(login_page)

        # Set params
        data = [
            'signin=1',
            'redir=',
            'crumb={0}'.format(quote(login_crumb.encode('utf-8'), safe='*')),
            'email={0}'.format(quote(self.args.email, safe='*')),
            'password={0}'.format(quote(self.args.password, safe='*')),
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

        # Check that we're successfully logged in
        # Slack will return a 302 for successful POST requests here
        if login.status_code != 302:
            print(
                ' '.join(
                    [
                        'ERROR: There was a problem logging in to Slack.',
                        'Check your team, email, and password and try again.'
                    ]
                ),
                file=sys.stderr
            )
            sys.exit(1)

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

        # If we're listing existing, do that and exit
        if self.args.list_existing:
            print('Existing Parrots:', file=sys.stdout)

            # Only show parrot emojis
            for emoji in current_emoji:
                if re.search(r'parrot', emoji, re.I):
                    print(
                        ':{parrot}:'.format(parrot=emoji),
                        file=sys.stdout
                    )
            sys.exit()

        # Initialize added parrots tracker
        added = []
        if self.args.list_available:
            print('Available Parrots:', file=sys.stdout)
        else:
            print('Starting Parroting...', file=sys.stdout)

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

            # If we're only listing, do that
            if self.args.list_available:
                print(
                    ':{parrot}:'.format(parrot=parrot['slug']),
                    file=sys.stdout
                )
                continue

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

        # Exit if we're just listing
        if self.args.list_available:
            sys.exit()

        # Return list of added parrots
        return added


def main():
    """Primary parroter function."""
    parroter = EmSlackPartyParroter()
    print('', file=sys.stdout)

    # Start parroting
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
