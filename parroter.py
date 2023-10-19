#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright (C) 2021 Erin Morelli.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.x

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see [https://www.gnu.org/licenses/].
"""

import os
import re
import sys
import json
import pickle
import argparse
from getpass import getpass
from datetime import datetime, timedelta

import yaml
import requests
from yaspin import yaspin

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException


# Script credits
__title__ = 'EM Slack Party Parroter'
__copyright__ = 'Copyright (c) 2017-2023, Erin Morelli'
__author__ = 'Erin Morelli'
__email__ = 'me@erin.dev'
__license__ = 'GPL-3.0'
__version__ = '2.0'


class EmSlackPartyParroter:
    """Class to interact with the Slack emoji customizer."""

    API_ROOT = 'https://slack.com/api'
    PARROT_ROOT = os.path.join(
        'https://raw.githubusercontent.com',  # GitHub raw file root
        'jmhobbs',                            # Username
        'cultofthepartyparrot.com',           # Repository
        'main'                              # Branch
    )
    BROWSERS = [k.lower() for k, v in webdriver.__dict__.items()
                if getattr(v, '__name__', '') == 'WebDriver']
    DEFAULT_BROWSER = 'chrome'

    def __init__(self):
        """Initialize class and connect to Slack."""
        self._parrot = {
            'yaml': f'{self.PARROT_ROOT}/parrots.yaml',
            'img': f'{self.PARROT_ROOT}/parrots'
        }
        self._guest = {
            'yaml': f'{self.PARROT_ROOT}/guests.yaml',
            'img': f'{self.PARROT_ROOT}/guests'
        }
        self._flags = {
            'yaml': f'{self.PARROT_ROOT}/flags.yaml',
            'img': f'{self.PARROT_ROOT}/flags',
        }

        # Build arg parser
        self._build_parser()

        # Parse args
        self.args = self._parse_args()

        # Specify bs parser
        self._bs_parser = 'html.parser'

        # Build Slack team URLs
        self.team_url = f'https://{self.args.team}.slack.com'
        self.emoji_url = f'{self.team_url}/customize/emoji'

        # Set requests caching data
        self._cache = {
            'pickle_protocol': 2,
            'cookie_expire_default': {
                'hours': 1
            },
            'cookies_file': '.slack_cookies',
            'api_key_file': '.slack_api_key'
        }

        # Setup selenium with chrome
        self.driver = self._get_browser_driver(self.args.browser)

        # Start session with Slack cookies
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 Gecko/20100101 Firefox/60.0'
        })
        self._load_cookie_jar(refresh=self.args.refresh)

        # Get API token for session
        self.api_token = self._load_api_key(refresh=self.args.refresh)

    def _build_parser(self):
        """Build the CLI argument parser."""
        self._parser = argparse.ArgumentParser(
            description=f'{__title__} v{__version__} / '
                        f'by {__author__} <{__email__}>',
            formatter_class=argparse.RawTextHelpFormatter
        )

        # Create credentials argument group
        auth_group = self._parser.add_argument_group('Slack Credentials')

        # Add credential arguments
        auth_group.add_argument(
            '-t', '--team',
            default=os.getenv('SLACK_TEAM'),
            help='Slack team name.\n'
                 'Defaults to the $SLACK_TEAM environment variable.',
            type=str.lower
        )
        auth_group.add_argument(
            '-e', '--email',
            default=os.getenv('SLACK_EMAIL'),
            help='Slack user email address.\n'
                 'Defaults to the $SLACK_EMAIL environment variable.'
        )
        auth_group.add_argument(
            '-p', '--password',
            default=os.getenv('SLACK_PASSWORD'),
            help='Slack user password.\n'
                 'Defaults to the $SLACK_PASSWORD environment variable.'
        )
        auth_group.add_argument(
            '-c', '--channel',
            default=os.getenv('SLACK_CHANNEL'),
            help='Slack channel name to send new parrot messages to.\n'
                 'Defaults to the $SLACK_CHANNEL environment variable.\n'
                 'Can be a public channel, private channel, or username.\n'
                 'e.g. "#public-channel", "private-channel", "@username"'
        )

        # Add optional arguments
        self._parser.add_argument(
            '-g', '--include_guests',
            action='store_true',
            help='Add Party Guests to Slack, in addition to standard parrots.'
        )
        self._parser.add_argument(
            '-f', '--include_flags',
            action='store_true',
            help='Add Flag Parrots to Slack, in addition to standard parrots.'
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
        self._parser.add_argument(
            '-b', '--browser',
            default=self.DEFAULT_BROWSER,
            choices=self.BROWSERS,
            metavar='BROWSER',
            help=f'Browser to use for headless requests. [Default: {self.DEFAULT_BROWSER}]',
        )

    def _parse_args(self, required=False):
        """Load credentials from args or prompt the user for them."""
        args = self._parser.parse_args()

        # Prompt user for missing args
        if not args.team:
            if hasattr(self, 'args') and hasattr(self.args, 'team'):
                args.team = self.args.team
            else:
                args.team = input('Slack Team: ').strip()
        if not args.email and required:
            args.email = input('Slack Email: ').strip()

        # Return args
        return args

    @staticmethod
    def _get_browser_driver(browser):
        """Get browser driver object from selenium."""
        module = getattr(webdriver, browser)

        if module:
            driver_module = getattr(module, 'webdriver')
            args = {}

            if hasattr(module, 'options'):
                options_module = getattr(module, 'options')
                if options_module:
                    options = options_module.Options()
                    options.add_argument('headless')
                    args['options'] = options

            return driver_module.WebDriver(**args)

        sys.exit(f'ERROR: not a valid browser option: {browser}')

    def _store_cookies(self, cookies):
        """Store user cookies to local cache file."""
        pickle.dump(
            (self.args.team, cookies),
            open(self._cache['cookies_file'], 'wb+'),
            protocol=self._cache['pickle_protocol']
        )

    def _load_cookies(self):
        """Load user cookies from local cache file."""
        return pickle.load(open(self._cache['cookies_file'], 'rb'))

    def _fill_cookie_jar(self, cookies):
        """Load cached cookies into instance Requests cookie jar."""
        for cookie in cookies:
            for exclude in ['sameSite', 'expiry', 'httpOnly']:
                if exclude in cookie:
                    del cookie[exclude]
            self.session.cookies.set(**cookie)

    def _cookies_expired(self, cookies):
        """Check if user cookies have expired."""
        now = datetime.now()

        # Get modification time of cookie file
        mod_time = datetime.fromtimestamp(
            os.path.getmtime(self._cache['cookies_file'])
        )

        # Set default refresh time
        refresh = timedelta(**self._cache['cookie_expire_default'])

        # Check cookie file modification time
        return now - mod_time > refresh

    def _load_cookie_jar(self, refresh=False):
        """Retrieve cookies from local cache or new from Downpour."""
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

        # Return the cookie dict
        return cookies

    def _validate_email_code(self):
        """Prompt user for email verification code."""
        email_code = input('Check your email for a 6-digit confirmation code: ').strip()
        digits = list(email_code.replace('-', ''))
        if len(digits) != 6:
            sys.exit('ERROR: Invalid confirmation code')

        inputs = self.driver.find_elements_by_css_selector('input[maxlength="1"]')

        for idx, el in enumerate(inputs):
            el.send_keys(digits[idx])

    def _get_login_page(self):
        """Get the non-OAuth slack team login page."""
        self.driver.get(self.team_url)

        # Check for presence of login form and return if found
        try:
            form = WebDriverWait(self.driver, 10)\
                .until(lambda x: x.find_element_by_id('signup_email'))
        except NoSuchElementException:
            # Attempt to load non-OAuth login page
            non_oauth_url = f'{self.team_url}/?no_sso=1'
            self.driver.get(non_oauth_url)

            # Check for presence of login form and return if found
            try:
                form = WebDriverWait(self.driver, 10) \
                    .until(lambda x: x.find_element_by_id('sigup_email'))
            except NoSuchElementException:
                # Exit and print error message if login form is not found
                sys.exit('ERROR: There was a problem logging in to Slack.')

        return form

    def _get_cookies(self):
        """Login to Slack to retrieve user cookies."""
        self._get_login_page()

        # Get login form elements
        email = self.driver.find_element_by_id('signup_email')
        submit = self.driver.find_element_by_id('submit_btn')

        # Set login info
        email.send_keys(self.args.email)

        # Submit login
        submit.click()

        # Check for emailed code
        try:
            WebDriverWait(self.driver, 10)\
                .until(lambda x: x.find_element_by_css_selector('div[data-qa="confirmation_code_input"]'))
        except NoSuchElementException:
            pass
        else:
            self._validate_email_code()

        # Check that we're successfully logged in
        try:
            script = 'return localStorage.localConfig_v2'
            result = WebDriverWait(self.driver, 10)\
                .until(lambda d: d.execute_script(script))

            # Load slack data
            if not json.loads(result)['teams']:
                raise KeyError

            # Return data
            return self.driver.get_cookies()
        except Exception:
            sys.exit('ERROR: There was a problem logging in to Slack. '
                     'Check your team, email, and password and try again.')

    def _load_api_key(self, refresh=False):
        """Load API key from cache or get new one."""
        if refresh:
            token = self._get_api_token()
            self._store_api_token(token)
            return token

        # Attempt to get token from cache
        try:
            token = self._load_api_token()
        except Exception:
            return self._load_api_key(refresh=True)

        # Make sure token is still valid
        if not self._validate_api_token(token):
            return self._load_api_key(refresh=True)

        # Return valid token
        return token

    def _store_api_token(self, token):
        """Store API token to file."""
        open(self._cache['api_key_file'], 'w+').write(token)

    def _load_api_token(self):
        """Load API token from file."""
        return open(self._cache['api_key_file'], 'r').read().strip()

    def _validate_api_token(self, token):
        """Validate that the token is still valid for this team."""
        team_res = self.session.get(
            f'{self.API_ROOT}/team.info',
            params={'token': token}
        )
        team_res.raise_for_status()
        team_info = team_res.json()
        return team_info['ok'] and team_info['team']['name'] == self.args.team

    def _get_api_token(self):
        """Retrieve the user's session API key."""
        self.driver.get(self.emoji_url)

        # Get API token from page data
        try:
            script = 'return window.boot_data.api_token'
            token = WebDriverWait(self.driver, 10) \
                .until(lambda d: d.execute_script(script))
        except Exception:
            sys.exit('ERROR: There was a problem logging in to Slack. '
                     'Check your team, email, and password and try again.')

        # Otherwise return token
        return token

    def yes_or_no(self, question):
        """Prompts the user for a yes or no answer to a question."""
        reply = str(input(question + ' (y/n): ')).lower().strip()
        if reply[0] == 'y':
            return True
        if reply[0] == 'n':
            return False
        return self.yes_or_no(question)

    def get_current_emoji_list(self):
        """Retrieve list of current Slack team emoji."""
        emoji_res = self.session.get(
            f'{self.API_ROOT}/emoji.list',
            params={'token': self.api_token}
        )
        emoji_res.raise_for_status()

        # Get JSON response
        emoji_list = emoji_res.json()

        # Check for response errors
        if not emoji_list['ok'] or 'emoji' not in emoji_list.keys():
            sys.exit('ERROR: Unable to load Slack emoji')

        # Return list of current emoji
        return emoji_list['emoji'].keys()

    def get_guests_list(self):
        """Retrieve up-to-date guests list from GitHub."""
        guests = requests.get(self._guest['yaml'])
        guests.raise_for_status()
        return yaml.load(guests.text, Loader=yaml.SafeLoader)

    def get_flags_list(self):
        """Retrieve up-to-date flag parrot list from GitHub."""
        flags = requests.get(self._flags['yaml'])
        flags.raise_for_status()
        return yaml.load(flags.text, Loader=yaml.SafeLoader)

    def get_parrot_list(self):
        """Retrieve up-to-date parrot list from GitHub."""
        parrots = requests.get(self._parrot['yaml'])
        parrots.raise_for_status()
        return yaml.load(parrots.text, Loader=yaml.SafeLoader)

    def get_emoji_list(self, current_emoji, emojis, is_guest=False, is_flag=False):
        """Get a formatted list of emoji."""
        emoji_list = []

        # Loop over all parrots
        for emoji in emojis:
            # Set whether this is a party guest or not
            emoji['is_guest'] = is_guest

            # Set whether this is a flag parrot or not
            emoji['is_flag'] = is_flag

            # Check if we can use an HD image
            if 'hd' in emoji.keys():
                emoji['use_hd'] = True
                emoji['slug'] = re.split(r'[/.]', emoji['hd'])[1]

            # Otherwise use the standard GIF image
            elif 'gif' in emoji.keys():
                emoji['use_hd'] = False
                emoji['slug'] = re.split(r'\.', emoji['gif'])[0]

            # If we're only listing, do that
            if self.args.list_available:
                print(
                    f':{emoji["slug"]}:',
                    file=sys.stdout
                )
                continue

            # Add the parrot if it doesn't already exist
            if emoji['slug'] not in current_emoji:
                emoji_list.append(emoji)

        return emoji_list

    def get_parrots_to_add(self, current_emoji, parrots, guests=None, flags=None):
        """Determine which parrots are not already added to the team."""
        parrots_to_add = self.get_emoji_list(current_emoji, parrots, False, False)
        guests_to_add = []
        flags_to_add = []

        if guests is not None:
            guests_to_add = self.get_emoji_list(current_emoji, guests, True, False)

        if flags is not None:
            flags_to_add = self.get_emoji_list(current_emoji, flags, False, True)

        # Return list of parrots and guests to be added
        return parrots_to_add + guests_to_add + flags_to_add

    def post_emoji(self):
        """Make a POST request to add a new Slack team emoji."""
        emoji_add_res = self.session.post(
            f'{self.API_ROOT}/emoji.add',
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
            sys.exit('ERROR: Unable to upload Slack emoji')

    def add_parrot(self, parrot):
        """Upload a new parrot emoji to a Slack team."""
        parrot_file = parrot['hd'] if parrot['use_hd'] else parrot['gif']

        # Get parrot image file path
        if parrot['is_guest']:
            file_root = self._guest['img']
        elif parrot['is_flag']:
            file_root = self._flags['img']
        else:
            file_root = self._parrot['img']

        parrot_url = os.path.join(file_root, parrot_file)

        # Get parrot
        parrot_img = requests.get(parrot_url, stream=True)
        parrot_img.raise_for_status()

        # Navigate to the emoji page
        emoji_page = self.session.get(self.emoji_url)
        emoji_page.raise_for_status()

        # Upload parrot
        emoji_upload_res = self.session.post(
            f'{self.API_ROOT}/emoji.add',
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
        """Add new parrots."""
        added = []

        # Loop over parrots to add
        for parrot in parrots:
            # Add the parrot
            error = self.add_parrot(parrot)

            # Report any errors
            if error is not None:
                print(f'+ Error adding \'{parrot["slug"]}\', {error}',
                      file=sys.stderr)
                continue

            # Report success
            print(f'+ Added :{parrot["slug"]}:')
            added.append(parrot)

        # Return list of added parrots
        return added

    def parrot(self):
        """Get and upload new parrots to Slack team."""
        parrots = self.get_parrot_list()
        guests = []
        flags = []

        # Get guests
        if self.args.include_guests:
            guests = self.get_guests_list()

        # Get Flags
        if self.args.include_flags:
            flags = self.get_flags_list()

        # Get existing emoji list
        current_emoji = self.get_current_emoji_list()

        # If we're listing existing, do that and exit
        if self.args.list_existing:
            print('Existing Parrots:')

            # Only show parrot emojis
            for emoji in current_emoji:
                print(f':{emoji}:')
            sys.exit()

        # Initialize CLI output
        print('Available Parrots:' if self.args.list_available
              else 'Starting Parroting...')

        # Get parrots to add
        to_add = self.get_parrots_to_add(current_emoji, parrots, guests, flags)

        # Exit if we're just listing
        if self.args.list_available:
            sys.exit()

        # Bail if there are no parrots to add
        if not to_add:
            print('No new parrots to add!')
            sys.exit()

        # Report number of new parrots found
        s = '' if len(to_add) == 1 else 's'
        print(f'Found {len(to_add)} new parrot{s} to add!')

        # List the parrots
        for parrot in to_add:
            print(f':{parrot["slug"]}:')

        # Exit if we're just listing
        if self.args.list_new:
            sys.exit()

        # Prompt user to continue
        approved = True if self.args.quiet \
            else self.yes_or_no('Add them to your Slack team?')

        # Check for approval
        if not approved:
            sys.exit()

        # Add parrots
        return self.add_parrots(to_add)

    def report(self, added):
        """Print added parrots and send Slack notification."""
        print(f'Successfully added {len(added)} new parrots!')

        # Check if we need to alert a Slack channel
        if self.args.channel is None:
            return

        # Set up message content
        s = 's' if len(added) > 1 else ''
        message = f'*Added {len(added)} new Party Parrot{s}!*'

        # Add each parrot to message
        for new in added:
            message += '\n+ :{slug}: `:{slug}:`'.format(**new)

        # Send Slack message
        sent = self.session.post(
            f'{self.API_ROOT}/chat.postMessage',
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
            print(f'ERROR: Unable to send Slack message: {sent_json["error"]}',
                  file=sys.stderr)


def main():
    """Primary parroter function."""
    parroter = EmSlackPartyParroter()

    # Start parroting
    added = parroter.parrot()

    # Finish parroting
    if added:
        parroter.report(added)


# Run the parroter via CLI
if __name__ == '__main__':
    main()
