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
import pickle
import argparse
from getpass import getpass
from datetime import datetime, timedelta

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

        # Set requests caching data
        self._cache = {
            'pickle_protocol': 2,
            'cookie_expire_default': {
                'hours': 1
            },
            'cookies_file': '.slack_cookies'
        }

        # Start slack session
        self.session = requests.Session()
        self._load_cookie_jar(refresh=self.args.refresh)

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
        self._parser.add_argument(
            '-r', '--refresh',
            default=False,
            help='Force a refresh of cached login data',
            action='store_true'
        )
        self._parser.add_argument(
            '-n', '--no_prompt',
            default=False,
            help='Don\'t prompt for approval to add parrots',
            action='store_true'
        )

    def _parse_args(self, required=False):
        """Load credentials from args or prompt the user for them.

        Returns:
            object: User credentials and other CLI arguments

        """
        args = self._parser.parse_args()

        # Prompt user for missing args
        if not args.team:
            args.team = raw_input('Slack Team: ').strip()
        if not args.email and required:
            args.email = raw_input('Slack Email: ').strip()
        if not args.password and required:
            args.password = getpass('Slack Password: ')

        # Return args
        return args

    def _store_cookies(self, cookies):
        """Store user cookies to local cache file.

        Args:
            RequestsCookieJar: Requests session cookie jar object from Downpour

        """
        pickle.dump(
            cookies,
            open(self._cache['cookies_file'], 'wb+'),
            protocol=self._cache['pickle_protocol']
        )

    def _load_cookies(self):
        """Load user cookies from local cache file."""
        return pickle.load(open(self._cache['cookies_file'], 'rb'))

    def _fill_cookie_jar(self, cookies):
        """Load cached cookies into instance Requests cookie jar.

        Args:
            RequestsCookieJar: Requests session cookie jar object from Downpour

        """
        self.session.cookies.update(cookies)

    def _cookies_expired(self, cookies):
        """Check if user cookies have expired.

        Args:
            RequestsCookieJar: Requests session cookie jar object from Downpour

        Retuns:
            bool: True if any required cookies have expired, else False

        """
        now = datetime.now()

        # Get modification time of cookie file
        mod_time = datetime.fromtimestamp(
            os.path.getmtime(self._cache['cookies_file'])
        )

        # Set default refresh time
        refresh = timedelta(**self._cache['cookie_expire_default'])

        # Check cookie file modification time
        if now - mod_time > refresh:
            return True

        # Check on Downpour cookie expiration times
        for cookie in cookies:
            # Get cookie expiration
            expires = datetime.fromtimestamp(cookie.expires)

            # Exit if cookie has expired
            if now > expires:
                return True

        # Return not expired
        return False

    def _load_cookie_jar(self, refresh=False):
        """Retrieve cookies from local cache or new from Downpour.

        Args:
            refresh (bool, optional): Force a refresh of cached cookie data

        """
        if not refresh:
            try:
                cookies = self._load_cookies()
            except IOError:
                refresh = True
            else:
                # Check for missing or expired cookies
                if not cookies or self._cookies_expired(cookies):
                    refresh = True

        # Get new cookies
        if refresh:
            # Parse args
            self.args = self._parse_args(True)

            # Retrieve cookies from Downpour
            cookies = self._get_cookies()

            # Store new cookies
            self._store_cookies(cookies)

        # Fill the cookie jar
        self._fill_cookie_jar(cookies)

    def _get_form_crumb(self, page, crumb='crumb'):
        """Parse form on page to retrieve Slack crumb.

        Args:
            page (requests.Response): Page response object to parse

        Returns:
            str: Slack crumb string

        """
        soup = BeautifulSoup(page.text, self._bs_parser)
        return soup.find('input', attrs={'name': crumb})['value']

    def _validate_tfa(self, page, team_url):
        """Check for and validate TFA codes for login.

        Args:
            page (requests.Response): Page response object to parse
            team_url: Slack team URL to use for login post call

        Returns:
           requests.Response: Login page response object

        """
        tf_regex = r'<input id="auth_code"'

        # Return if no TFA
        if not re.search(tf_regex, page.content):
            return page

        # Prompt user for TFA code
        tfa_code = raw_input('Two-Factor Authentication Code: ').strip()

        # Get login crumb
        login_crumb = self._get_form_crumb(page)
        login_sig = self._get_form_crumb(page, 'sig')

        # Set params
        data = [
            'signin_2fa=1',
            'doing_2fa=1',
            'redir=',
            'using_backup=',
            'remember=1',
            'sig={0}'.format(quote(login_sig.encode('utf-8'), safe='*')),
            'crumb={0}'.format(quote(login_crumb.encode('utf-8'), safe='*')),
            '2fa_code={0}'.format(tfa_code)
        ]

        # Login to Downpour
        login = self.session.post(
            team_url,
            data='&'.join(data),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            allow_redirects=False
        )
        login.raise_for_status()

        # Return logged in session and page object
        return login

    def _get_login_page(self):
        """Get the non-OAuth slack team login page.

        Returns:
           requests.Response: Login page response object
           string: URL to use for login post call

        """
        post_regex = r'<form id="signin_form" action="/" method="post"'

        # Load initial team landing page
        landing = self.session.get(self.team_url)
        landing.raise_for_status()

        # Check for presence of login form and return if found
        if re.search(post_regex, landing.content):
            return (landing, self.team_url)

        # Set up non-OAuth page url
        non_oauth_url = '{team_url}/?no_sso=1'.format(team_url=self.team_url)

        # Attempt to load non-OAuth login page
        login = self.session.get(non_oauth_url)
        login.raise_for_status()

        # Check for presence of login form and return if found
        if re.search(post_regex, login.content):
            return (login, non_oauth_url)

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

    def _get_cookies(self):
        """Login to Slack to retrieve user cookies.

        Returns:
            RequestsCookieJar: Logged in Slack response object cookie jar

        """
        (login_page, team_url) = self._get_login_page()

        # Get login crumb
        login_crumb = self._get_form_crumb(login_page)

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
        login = self.session.post(
            team_url,
            data='&'.join(data),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            allow_redirects=False
        )
        login.raise_for_status()

        # Check for two-factor auth
        validated = self._validate_tfa(login, team_url)

        # Check that we're successfully logged in
        # Slack will return a 302 for successful POST requests here
        if validated.status_code != 302:
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
        return validated.cookies

    def yes_or_no(self, question):
        """Prompts the user for a yes or no answer to a question.

        Args:
            question (str): Question to prompt the user with

        Returns:
            bool: True or False response to the question

        """
        reply = str(raw_input(question + ' (y/n): ')).lower().strip()
        if reply[0] == 'y':
            return True
        if reply[0] == 'n':
            return False
        return self.yes_or_no(question)

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

    def get_parrot_list(self):
        """Retrieve up-to-date parrot list from GitHub.

        Returns:
            list: Parsed JSON list of current parrots

        """
        parrots = requests.get(self._parrot['json'])
        parrots.raise_for_status()

        # Return parsed JSON
        return parrots.json()

    def get_parrots_to_add(self, parrots, current_emoji):
        """Determine which parrots are not already added to the team.

        Args:
            parrots (list): List of available parrot emojis
            current_emoji (list): List of current team emojis

        Returns:
            list: Parrot emojis to be added to the team

        """
        parrots_to_add = []

        # Loop over all parrots
        for parrot in parrots:
            # Check if we can use an HD image
            if 'hd' in parrot.keys():
                parrot['use_hd'] = True
                parrot['slug'] = re.split(r'\/|\.', parrot['hd'])[1]

            # Otherwise use the standard GIF image
            elif 'gif' in parrot.keys():
                parrot['use_hd'] = False
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
                parrots_to_add.append(parrot)

        # Return list of parrots to be added
        return parrots_to_add

    def add_parrot(self, parrot):
        """Upload a new parrot emoji to a Slack team.

        Args:
            parrot (dict): Parrot emoji data

        Returns:
            str: Error data, if there was a error, otherwise None

        """
        parrot_file = parrot['hd'] if parrot['use_hd'] else parrot['gif']

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

        # Get parrots to add
        parrots_to_add = self.get_parrots_to_add(parrots, current_emoji)

        # Exit if we're just listing
        if self.args.list_available:
            sys.exit()

        # Bail if there are no parrots to add
        if not parrots_to_add:
            print('No new parrots to add!', file=sys.stdout)
            sys.exit()

        # Report number of new parrots found
        print(
            'Found {count} new parrot{s} to add!'.format(
                count=len(parrots_to_add),
                s='' if len(parrots_to_add) == 1 else 's'
            ),
            file=sys.stdout
        )

        # Prompt user to continue
        if self.args.no_prompt:
            approved = True
        else:
            approved = self.yes_or_no('Add them to your Slack team?')

        # Check for approval
        if not approved:
            sys.exit()

        # Loop over parrots to add
        for parrot in parrots_to_add:
            # Add the parrot
            error = self.add_parrot(parrot)

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


def main():
    """Primary parroter function."""
    parroter = EmSlackPartyParroter()
    print('', file=sys.stdout)

    # Start parroting
    added = parroter.parrot()

    # Finish parroting
    if added:
        print(
            'Successfully added {count} new parrots!'.format(count=len(added)),
            file=sys.stdout
        )

# Run the parroter via CLI
if __name__ == '__main__':
    main()
