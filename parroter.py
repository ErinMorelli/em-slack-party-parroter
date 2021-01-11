#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright (c) 2017-2021, Erin Morelli.

Title       : EM Slack Party Parroter
Author      : Erin Morelli
Email       : erin@erinmorelli.com
License     : MIT
Version     : 0.6
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
__copyright__ = 'Copyright (c) 2017-2021, Erin Morelli'
__author__ = 'Erin Morelli'
__email__ = 'erin@erinmorelli.com'
__license__ = 'MIT'
__version__ = '0.6'

# Disable SSL warnings
urllib3.disable_warnings()

# Handle Python 3+ input
try:
    raw_input
except NameError:
    raw_input = input


class EmSlackPartyParroter(object):
    """Class to interact with the Slack emoji customizer."""

    API_ROOT = 'https://slack.com/api/{0}'
    PARROT_ROOT = os.path.join(
        'https://raw.githubusercontent.com',  # GitHub raw file root
        'jmhobbs',                            # Username
        'cultofthepartyparrot.com',           # Repository
        'master',                             # Branch
        '{0}'
    )

    def __init__(self):
        """Initialize class and connect to Slack."""
        self._parrot = {
            'json': self.PARROT_ROOT.format('parrots.json'),
            'img': self.PARROT_ROOT.format('parrots')
        }
        self._guest = {
            'json': self.PARROT_ROOT.format('guests.json'),
            'img': self.PARROT_ROOT.format('guests')
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
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 Gecko/20100101 Firefox/60.0'
        })
        self._load_cookie_jar(refresh=self.args.refresh)

        # Get API token for session
        self.api_token = self._get_api_token()

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
            '-t', '--team',
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
            '-e', '--email',
            default=os.getenv('SLACK_EMAIL'),
            help='\n'.join(
                [
                    'Slack user email address.',
                    'Defaults to the $SLACK_EMAIL environment variable.'
                ]
            )
        )
        auth_group.add_argument(
            '-p', '--password',
            default=os.getenv('SLACK_PASSWORD'),
            help='\n'.join(
                [
                    'Slack user password.',
                    'Defaults to the $SLACK_PASSWORD environment variable.'
                ]
            )
        )
        auth_group.add_argument(
            '-c', '--channel',
            default=os.getenv('SLACK_CHANNEL'),
            help='\n'.join(
                [
                    'Slack channel name to send new parrot messages to.',
                    'Defaults to the $SLACK_CHANNEL environment variable.',
                    'Can be a public channel, private channel, or username.',
                    'e.g. "#public-channel", "private-channel", "@username"'
                ]
            )
        )

        # Add optional arguments
        self._parser.add_argument(
            '-g', '--include_guests',
            action='store_true',
            help='Add Party Guests to your team in addition to standard parrots.'
        )
        self._parser.add_argument(
            '-l', '--list_existing',
            action='store_true',
            help='Displays a list of your Slack team\'s existing parrots.'
        )
        self._parser.add_argument(
            '-a', '--list_available',
            action='store_true',
            help='Displays a list of all available parrots.'
        )
        self._parser.add_argument(
            '-n', '--list_new',
            action='store_true',
            help='Displays a list of new parrots for your Slack team.'
        )
        self._parser.add_argument(
            '-r', '--refresh',
            default=False,
            help='Force a refresh of cached login data',
            action='store_true'
        )
        self._parser.add_argument(
            '-q', '--quiet',
            default=False,
            help='Don\'t prompt for approval to add parrots.',
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
            if hasattr(self, 'args') and hasattr(self.args, 'team'):
                args.team = self.args.team
            else:
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
            (self.args.team, cookies),
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
            # Skip cookies that don't expire
            if not cookie.expires:
                continue

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
                (team, cookies) = self._load_cookies()
            except IOError:
                refresh = True
            else:
                # Check for expired cookies
                expired = self._cookies_expired(cookies)

                # Check for missing or expired cookies or different team name
                if not cookies or expired or team != self.args.team:
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
        if not re.search(tf_regex, page.content.decode('utf-8')):
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
        if re.search(post_regex, landing.content.decode('utf-8')):
            return (landing, self.team_url)

        # Set up non-OAuth page url
        non_oauth_url = '{team_url}/?no_sso=1'.format(team_url=self.team_url)

        # Attempt to load non-OAuth login page
        login = self.session.get(non_oauth_url)
        login.raise_for_status()

        # Check for presence of login form and return if found
        if re.search(post_regex, login.content.decode('utf-8')):
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

        return None

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

    def _get_api_token(self):
        """Retrieve the user's session API key."""
        emoji_page = self.session.get(self.emoji_url)
        emoji_page.raise_for_status()

        # Set regex to find token
        token_regex = r'\"api_token\":\s?\"(xoxs-[a-zA-Z0-9\-]+)\"'

        # Find the session token on page
        token = re.findall(token_regex, emoji_page.text)

        # Check for result
        if not token:
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

        # Otherwise return token
        return token[0]

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
        emoji_res = self.session.get(
            self.API_ROOT.format('emoji.list'),
            params={
                'token': self.api_token
            }
        )
        emoji_res.raise_for_status()

        # Get JSON response
        emoji_list = emoji_res.json()

        # Check for response errors
        if not emoji_list['ok'] or 'emoji' not in emoji_list.keys():
            print(
                'ERROR: Unable to load Slack emoji',
                file=sys.stderr
            )
            sys.exit(1)

        # Return list of current emoji
        return emoji_list['emoji'].keys()

    def get_guests_list(self):
        """Retrieve up-to-date guests list from GitHub.

        Returns:
            list: Parsed JSON list of current guests

        """
        guests = requests.get(self._guest['json'])
        guests.raise_for_status()

        # Return parsed JSON
        return guests.json()

    def get_parrot_list(self):
        """Retrieve up-to-date parrot list from GitHub.

        Returns:
            list: Parsed JSON list of current parrots

        """
        parrots = requests.get(self._parrot['json'])
        parrots.raise_for_status()

        # Return parsed JSON
        return parrots.json()

    def get_emoji_list(self, current_emoji, emojis, is_guest=False):
        """Get a formatted list of emoji.

        Args:
            current_emoji (list): All current Slack emojis for the team
            emojis (list): Available emoji from CultOfThePartyParrot
            is_guest (bool): Whether or not these are Party Guest emojis

        Returns:
            list: Formatted list of dicts of emoji data

        """
        emoji_list = []

        # Loop over all parrots
        for emoji in emojis:
            # Set whether this is a part guest or not
            emoji['is_guest'] = is_guest

            # Check if we can use an HD image
            if 'hd' in emoji.keys():
                emoji['use_hd'] = True
                emoji['slug'] = re.split(r'\/|\.', emoji['hd'])[1]

            # Otherwise use the standard GIF image
            elif 'gif' in emoji.keys():
                emoji['use_hd'] = False
                emoji['slug'] = re.split(r'\.', emoji['gif'])[0]

            # If we're only listing, do that
            if self.args.list_available:
                print(
                    ':{emoji}:'.format(emoji=emoji['slug']),
                    file=sys.stdout
                )
                continue

            # Add the parrot if it doesn't already exist
            if emoji['slug'] not in current_emoji:
                emoji_list.append(emoji)

        return emoji_list

    def get_parrots_to_add(self, current_emoji, parrots, guests=None):
        """Determine which parrots are not already added to the team.

        Args:
            current_emoji (list): List of current team emojis
            parrots (list): List of available parrot emojis
            guests (list): List of available guest emojis

        Returns:
            list: Parrot emojis to be added to the team

        """
        parrots_to_add = self.get_emoji_list(current_emoji, parrots)
        guests_to_add = []

        if guests is not None:
            guests_to_add = self.get_emoji_list(current_emoji, guests, True)

        # Return list of parrots and guests to be added
        return parrots_to_add + guests_to_add

    def post_emoji(self):
        """Make a POST request to add a new Slack team emoji."""
        emoji_add_res = self.session.post(
            self.API_ROOT.format('emoji.add'),
            params={
                'token': self.api_token,
                'mode': 'data',
                'name': ''
            }
        )
        emoji_add_res.raise_for_status()

        # Get JSON response
        emoji_add = emoji_add_res.json()

        # Check for response errors
        if not emoji_add['ok']:
            print(
                'ERROR: Unable to upload Slack emoji',
                file=sys.stderr
            )
            sys.exit(1)

    def add_parrot(self, parrot):
        """Upload a new parrot emoji to a Slack team.

        Args:
            parrot (dict): Parrot emoji data

        Returns:
            str: Error data, if there was a error, otherwise None

        """
        parrot_file = parrot['hd'] if parrot['use_hd'] else parrot['gif']

        # Get parrot image file path
        if parrot['is_guest']:
            parrot_url = os.path.join(self._guest['img'], parrot_file)
        else:
            parrot_url = os.path.join(self._parrot['img'], parrot_file)

        # Get parrot
        parrot_img = requests.get(parrot_url, stream=True)
        parrot_img.raise_for_status()

        # Navigate to the emoji page
        emoji_page = self.session.get(self.emoji_url)
        emoji_page.raise_for_status()

        # Upload parrot
        emoji_upload_res = self.session.post(
            self.API_ROOT.format('emoji.add'),
            data={
                'token': self.api_token,
                'name': parrot['slug'],
                'mode': 'data'
            },
            files={
                'image': parrot_img.raw
            },
            allow_redirects=False
        )
        emoji_upload_res.raise_for_status()

        # Get JSON response
        emoji_upload = emoji_upload_res.json()

        # Check for response errors
        if not emoji_upload['ok'] and 'error' in emoji_upload.keys():
            return emoji_upload['error']

        return None

    def add_parrots(self, parrots):
        """Add new parrots.

        Args:
            parrots (list): List of dicts of parrot emoji data

        """
        added = []

        # Loop over parrots to add
        for parrot in parrots:
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

    def parrot(self):
        """Get and upload new parrots to Slack team.

        Returns:
            list: List of added parrots

        """
        parrots = self.get_parrot_list()
        guests = []

        # Get guests
        if self.args.include_guests:
            guests = self.get_guests_list()

        # Get existing emoji list
        current_emoji = self.get_current_emoji_list()

        # If we're listing existing, do that and exit
        if self.args.list_existing:
            print('Existing Parrots:', file=sys.stdout)

            # Only show parrot emojis
            for emoji in current_emoji:
                print(
                    ':{parrot}:'.format(parrot=emoji),
                    file=sys.stdout
                )
            sys.exit()

        # Initialize CLI output
        if self.args.list_available:
            print('Available Parrots:', file=sys.stdout)
        else:
            print('Starting Parroting...', file=sys.stdout)

        # Get parrots to add
        to_add = self.get_parrots_to_add(current_emoji, parrots, guests)

        # Exit if we're just listing
        if self.args.list_available:
            sys.exit()

        # Bail if there are no parrots to add
        if not to_add:
            print('No new parrots to add!', file=sys.stdout)
            sys.exit()

        # Report number of new parrots found
        print(
            'Found {count} new parrot{s} to add!'.format(
                count=len(to_add),
                s='' if len(to_add) == 1 else 's'
            ),
            file=sys.stdout
        )

        # List the parrots
        for parrot in to_add:
            print(
                ':{parrot}:'.format(parrot=parrot['slug']),
                file=sys.stdout
            )

        # Exit if we're just listing
        if self.args.list_new:
            sys.exit()

        # Prompt user to continue
        if self.args.quiet:
            approved = True
        else:
            approved = self.yes_or_no('Add them to your Slack team?')

        # Check for approval
        if not approved:
            sys.exit()

        # Add parrots
        return self.add_parrots(to_add)

    def report(self, added):
        """Print added parrots and send Slack notification.

        Args:
            added (list): List of added Parrot emoji data

        """
        print(
            'Successfully added {count} new parrots!'.format(count=len(added)),
            file=sys.stdout
        )

        # Check if we need to alert a Slack channel
        if self.args.channel is None:
            return

        # Set up message content
        message = '*Added {count} new Party Parrot{s}!*'.format(
            count=len(added),
            s='s' if len(added) > 1 else ''
        )

        # Add each parrot to message
        for new in added:
            message += '\n+ :{slug}: `:{slug}:`'.format(**new)

        # Send Slack message
        sent = self.session.post(
            self.API_ROOT.format('chat.postMessage'),
            data={
                'token': self.api_token,
                'channel': self.args.channel,
                'text': message
            }
        )
        sent.raise_for_status()

        # Get JSON response
        sent_json = sent.json()

        # Check for bad response from Slack
        if not sent_json['ok']:
            print(
                'ERROR: Unable to send Slack message: {error}'.format(
                    error=sent_json['error']
                ),
                file=sys.stderr
            )


def main():
    """Primary parroter function."""
    parroter = EmSlackPartyParroter()
    print('', file=sys.stdout)

    # Start parroting
    added = parroter.parrot()

    # Finish parroting
    if added:
        parroter.report(added)


# Run the parroter via CLI
if __name__ == '__main__':
    main()
