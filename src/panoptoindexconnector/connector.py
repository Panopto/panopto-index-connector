#!/usr/bin/env python
"""
A prototype of the example connector app we will publish.
"""


# Standard Library Imports
import argparse
from datetime import datetime, timedelta
import glob
import json
import logging
import os
import sys
import time

# Third party
import readline
import requests

# Local
from panoptoindexconnector.connector_config import ConnectorConfig, InvalidConfiguration
from panoptoindexconnector.helpers import format_request_secure
from panoptoindexconnector.target_handler import TargetHandler


# 2 minute grace period on oauth expiration
EXPIRATION_GRACE_PERIOD = timedelta(minutes=2)
LOG = logging.getLogger(__name__)
MIN_DATETIME = datetime(2008, 1, 1)


###################################################################################################
#
# Methods
#
###################################################################################################


def get_ids_to_update(oauth_token, panopto_site_address, from_date, next_token):
    """
    Get the ids to update from Panopto
    """

    url = '{site}/Panopto/api/v1/searchIndexSync/updates?'.format(site=panopto_site_address)
    params = {
        'fromDate': from_date,
        'nextToken': next_token,
    }
    headers = {'Authorization': 'Bearer ' + oauth_token}

    response = requests.get(url=url, params=params, headers=headers)

    LOG.debug('Request was %s', format_request_secure(response.request))
    response.raise_for_status()

    LOG.debug('Received updates response %s', json.dumps(response.json(), indent=2))
    LOG.info('Received %i updates to process', len(response.json().get('Updates')))

    return response.json()


def get_last_update_time(profile_name):
    """
    Read last update time
    """

    file_name = get_profile_state_filepath(profile_name)

    # Assume a default from before the site existed
    last_update_time = MIN_DATETIME

    # If the tracking file can be found and contains content, use that as the last update time
    if os.path.exists(file_name):
        with open(file_name, 'r') as file_handle:
            lines = file_handle.readlines()
            if lines:
                last_update_time_str = lines[-1].strip()
                last_update_time = datetime.fromisoformat(last_update_time_str)
    else:
        LOG.debug('File %s not found', file_name)
    LOG.debug('Last update time is %s', last_update_time)

    return last_update_time


def get_profile_state_filepath(profile_name):
    """
    Gets the state file locatoin for the profile
    """

    home = os.path.expanduser('~')
    return os.path.join(home, '.panopto-connector.' + profile_name)


def get_oauth_token(panopto_site_address, panopto_oauth_credentials):
    """
    Get an oauth token from Panopto
    """
    url = '{site}/Panopto/oauth2/connect/token'.format(site=panopto_site_address)

    data = {
        'client_id': panopto_oauth_credentials['client_id'],
        'client_secret': panopto_oauth_credentials['client_secret'],
        'grant_type': panopto_oauth_credentials['grant_type'],
        'scope': 'api',
    }
    # grant_type password uses username and password, others don't
    if panopto_oauth_credentials.get('username'):
        data['username'] = panopto_oauth_credentials['username']
    if panopto_oauth_credentials.get('password'):
        data['password'] = panopto_oauth_credentials['password']

    # sending get request and saving the response as response object
    response = requests.post(url=url, data=data)
    LOG.debug(response.content)
    response.raise_for_status()

    return response.json()


def get_video_content(oauth_token, panopto_site_address, video_id):
    """
    Get the video content to update
    """

    url = '{site}/Panopto/api/v1/searchIndexSync/content?'.format(site=panopto_site_address)
    params = {'id': video_id}
    headers = {'Authorization': 'Bearer ' + oauth_token}

    response = requests.get(url=url, params=params, headers=headers)
    LOG.debug('Request was %s', format_request_secure(response.request))

    response.raise_for_status()

    LOG.debug('Received content response %s', json.dumps(response.json(), indent=2))

    return response.json()


def parse_api_update_time(update_time_str):
    """
    Parses the update time from the Panopto Search Integration API
    """
    # Strip off the Z if it exists
    update_time_str = update_time_str.rstrip('Z')
    # Strip off the floats as datetime package only accepts exactly 6 digits of float,
    # and we don't need that level of precision
    split = update_time_str.split('.')
    assert len(split) in (1, 2), 'Unexpected time format: %s' % update_time_str
    update_time_str = split[0]
    second_decimal_str = split[1] if len(split) == 2 else '0'
    # Parse the last time the document was updated by panopto API format
    update_time = datetime.strptime(update_time_str, '%Y-%m-%dT%H:%M:%S')
    # Python datetime strptime only supports microsecond format; so we process the seconds string separately
    # and ensure there is at least a microsecond increment to avoid resyncing the same video
    second_decimal = timedelta(seconds=float('0.' + second_decimal_str)) + timedelta(microseconds=1)
    update_time += second_decimal

    return update_time


def renew_oauth_token_if_needed(panopto_site_address, panopto_oauth_credentials, oauth_token, expiration_date):
    """
    Returns the current oauth token if it is present and valid, else gets a new one if it is missing
    or soon to expire
    :returns: oauth_token, expiration_date
    """
    if not oauth_token or not expiration_date or expiration_date <= datetime.utcnow():
        now = datetime.utcnow()
        oauth_token_response = get_oauth_token(panopto_site_address, panopto_oauth_credentials)
        oauth_token = oauth_token_response['access_token']
        expiration_date = now + timedelta(seconds=oauth_token_response['expires_in']) - EXPIRATION_GRACE_PERIOD
    return oauth_token, expiration_date


def save_last_update_time(last_update_time, profile_name):
    """
    Save the last update time to the state tracking file
    """

    file_name = get_profile_state_filepath(profile_name)
    LOG.debug('Saving to location %s', file_name)
    LOG.debug('Last update time is %s', last_update_time)

    with open(file_name, 'a') as file_handle:
        file_handle.write(last_update_time.isoformat() + '\n')


def should_push(video_content_response, config):
    """
    Returns true/false for whether we should push this video.

    Will return "true" if either the permission allowlist is not set, or
    if the video content contains the allowlisted permission
    """
    # if there's no allowlist, proceed
    if not config.principal_allowlist:
        return True
    # else we have a allowlist; let's match against it
    principals = video_content_response['VideoContent']['Principals']
    # we'll just walk the permission allowlist and check match against each principal
    for allowed_principal in config.principal_allowlist:
        # Format it as <User|Group>:<IdProvider>:<Name>
        LOG.debug('Considering allowed principal %s', allowed_principal)
        try:
            principal_type, id_provider, name = allowed_principal.split(':')
            assert principal_type in ('User', 'Group')
        except Exception:  # pylint: disable=broad-except
            LOG.error('Invalid principal in principal allowlist. Expected format '
                      '<User|Group>:<IdProvider>:<Name>, received %s', allowed_principal)
            sys.exit(2)
        name_key = principal_type + 'name'  # Username or Groupname
        for principal in principals:
            LOG.debug('Considering principal %s', principal)
            principal_name = principal.get(name_key)
            principal_provider = principal.get('IdentityProvider') or 'Panopto'
            if principal_name == name and principal_provider == id_provider:
                return True
    return False


def sync_video_by_id(handler, oauth_token, config, video_id):
    """
    Sync video metadata from Panopto to target by ID
    """

    video_content_response = get_video_content(oauth_token, config.panopto_site_address, video_id)
    if video_content_response['Deleted']:
        handler.delete_from_target(video_content_response['Id'])
    else:
        if should_push(video_content_response, config):
            target_content = handler.convert_to_target(video_content_response)
            handler.push_to_target(target_content, config)
        else:
            LOG.info('Skipping update for video %s as it did not match principal allowlist', video_id)


def trigger_rebuild(profile_name):
    """
    Save MIN_DATETIME as last update to trigger a rebuild
    """
    LOG.info('Triggering rebuild by resetting last update')
    save_last_update_time(MIN_DATETIME, profile_name)


###################################################################################################
#
# System layer
#
###################################################################################################


def run(config, profile_name):
    """
    Run a sync given a config
    """

    assert isinstance(config, ConnectorConfig), 'config must be of type %s' % ConnectorConfig

    # Get time to update from
    last_update_time = get_last_update_time(profile_name)

    while True:
        LOG.info('Beginning search index sync')

        start_time = datetime.utcnow()
        last_update_time, exception = sync(config, last_update_time)

        if exception:

            LOG.exception('Failed to sync the search index: current up to %s | %s', last_update_time, exception)
            remaining_time = config.polling_retry_minimum

        else:
            remaining_time = start_time + config.polling_frequency - datetime.utcnow()

        save_last_update_time(last_update_time, profile_name)

        wait(remaining_time)


def sync(config, last_update_time):
    """
    Query for updates and run a sync up to the current point in time
    """
    LOG.info('Beginning incremental sync from %s to %s beginning at %s.',
             config.panopto_site_address, config.target_address, last_update_time)

    handler = TargetHandler(config)

    start_time = datetime.utcnow()
    oauth_token, expiration = None, None

    next_token = None
    exception = None

    new_last_update_time = last_update_time

    handler.initialize()

    try:
        for _ in range(1000):
            # Renew the oauth token if needed
            oauth_token, expiration = renew_oauth_token_if_needed(
                config.panopto_site_address, config.panopto_oauth_credentials, oauth_token, expiration)
            # Hack: The API is currently returning a second rounded next token which can lead to issues if there has
            # been a bulk update on a site and more than 100 videos have the same update time rounded to the nearest
            # second. So we'll workaround this here for now by always omitting the next token and favoring instead
            # always using new_last_update_time; fix next token as None.
            get_ids_response = get_ids_to_update(oauth_token, config.panopto_site_address, last_update_time, next_token)
            for update in get_ids_response['Updates']:
                # Renew the oauth token if needed
                oauth_token, expiration = renew_oauth_token_if_needed(
                    config.panopto_site_address, config.panopto_oauth_credentials, oauth_token, expiration)

                video_id = update['VideoId']

                update_time = parse_api_update_time(update['UpdateTime'])
                LOG.info('Syncing video last updated %s', update_time)

                sync_video_by_id(handler, oauth_token, config, video_id)
                new_last_update_time = update_time
                # Sleep to avoid getting throttled by the API
                time.sleep(config.sleep_seconds)
            next_token = get_ids_response['NextToken']
            if next_token:
                LOG.info('Pagination continued at token: %s', next_token)
            else:
                LOG.info('Sync complete')
                break
        else:
            LOG.warning('Did not complete a sync in 1000 passes')
    except requests.exceptions.HTTPError as ex:
        LOG.exception('Received error response %s | %s', ex.response.status_code, ex.response.text)
        exception = ex
    except Exception as ex:  # pylint: disable=broad-except
        LOG.exception('Received general exception')
        exception = ex
    finally:
        handler.teardown()

    # When there is no exception, we can take max of the new_last_update_time and the
    # start time of the loop as the new base point
    if exception is None:
        new_last_update_time = max(new_last_update_time, start_time)

    return new_last_update_time, exception


def wait(remaining_time):
    """
    Wait the remaining time
    """

    wait_seconds = remaining_time.total_seconds()
    if wait_seconds <= 0:
        LOG.warning('Received a negative wait time. Continuing now')
    else:
        LOG.info('Waiting %s until next sync', remaining_time)
        time.sleep(wait_seconds)


###################################################################################################
#
# Script handling
#
###################################################################################################


def main():
    """
    CLI entry point
    """

    args = parse_args()
    set_logger(args.logging_level)

    if args.configuration_file:
        config = ConnectorConfig(args.configuration_file)
    else:
        # If config file wasn't passed in on CLI query for it
        config = prompt_user_configuration_file()

    # Trim extension and folder to generate a unique profile name
    profile_name = os.path.split(os.path.splitext(config.config_file_path)[0])[1]
    LOG.info('Starting connector profile %s with configuration \n%s', profile_name, config)

    rebuild = args.rebuild
    # A little bit hacky; if we don't have a CLI arg, assume we are in interactive mode
    # and we should prompt the user whether to trigger a rebuild
    if not args.rebuild and not args.configuration_file:

        # In interactive state, if rebuild was not passed on CLI, check with user
        # as we can't tell if they are running on CLI or double click packaged program
        profile_name = os.path.split(os.path.splitext(config.config_file_path)[0])[1]
        rebuild = prompt_user_rebuild(profile_name)

    if rebuild:
        trigger_rebuild(profile_name)

    run(config, profile_name)


def parse_args():
    """
    Parse commandline arguments.
    """

    # Description
    parser = argparse.ArgumentParser(description='Connect a Panopto search index with an external index.')

    # Logging levels, local and third party
    parser.add_argument('--logging-level', choices=['warn', 'info', 'debug'], default='info')

    parser.add_argument('-c', '--configuration-file', required=False, help='Path to a config file')
    parser.add_argument('--rebuild', action='store_true', help='Trigger a rebuild by clearing the state file')

    return parser.parse_args()


def prompt_user_configuration_file():
    """
    Get the profile to use from the user
    """

    config = None
    while not config:
        location = prompt_user_with_autocomplete('What is the path to your configuration file?\n > ')

        try:
            config = ConnectorConfig(location)
        except FileNotFoundError:
            LOG.info('The configuration file at "%s" was not found', location)
        except InvalidConfiguration as ice:
            LOG.info('The YAML was invalid in the configuration file: %s', ice)

    return config


def prompt_user_rebuild(profile_name):
    """
    Prompt the user t/f whether they would like to rebuild
    """
    print('Would you like to rebuild profile %s? Rebuilding takes extra time to current and may incur extra '
          'costs or resources on your target.' % profile_name)
    query = ' (y for yes, any other key for no) > '
    result = input(query)
    return result.lower() == 'y' or result.lower() == 'yes'


def prompt_user_with_autocomplete(prompt):
    """
    Prompt with file path autocomplete
    """
    def complete(text, state):
        return (glob.glob(text+'*')+[None])[state]

    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(complete)

    return input(prompt)


def set_logger(logging_level):
    """
    Set the logging level and format
    """

    # Add logging setup here
    log_format = '%(asctime)s %(levelname)-8s%(module)16s - %(message)s'
    log_date_format = '%Y-%m-%d %H:%M:%S'

    # Set logging level
    logging_level = logging.getLevelName(logging_level.upper())
    logging.basicConfig(format=log_format, level=logging_level, datefmt=log_date_format)


if __name__ == '__main__':
    main()
