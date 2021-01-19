"""
Methods for the connector application to convert and sync content to the target endpoint

Start with this template to implement these methods for the connector application
"""

# Standard Library Imports
import json
import logging
import os

# Third party
import requests

# Home rolled
from panoptoindexconnector.helpers import format_request_secure

# Global constants
DIR = os.path.dirname(os.path.realpath(__file__))
LOG = logging.getLogger(__name__)


#########################################################################
#
# Exported methods to implement
#
#########################################################################

#
# Example Coveo Doc
#
"""
{
    'author': 'Alice Smith',
    'date': '2017-11-08T12:18:41.666Z',
    'documenttype': 'Text',
    'filename': 'mytext.txt',
    'language': [
        'English'
    ],
    'permanentid': 'sample95829alice84720permanent93829id',
    'sourcetype': 'Push',
    'title': 'My Text',
    'fileExtension': '.txt',
    'data': 'This is a sample text written by Alice Smith.',
    'permissions': [
        {
            'allowAnonymous': false,
            'allowedPermissions': [
                {
                    'identity': 'AlphaTeam',
                    'identityType': 'Group'
                }
            ],
            'deniedPermissions': [
                {
                    'identity': 'bob@example.com',
                    'identityType': 'User'
                }
            ]
        }
    ]
}
"""


def convert_to_target(panopto_content, field_mapping):
    """
    Implement this method to convert from panopto content format to target format
    """

    target_content = {
        field_mapping['Id']: panopto_content['Id'],
        'documenttype': 'Panopto',
        field_mapping['Info']['Language']: panopto_content['VideoContent']['Language'],
        field_mapping['Info']['Title']: panopto_content['VideoContent']['Title'],
    }

    for key, target_field in field_mapping['Metadata'].items():
        if panopto_content['VideoContent'][key]:
            target_content[target_field] = panopto_content['VideoContent'][key]

    # Principals
    target_content['permissions'] = [
        {
            'allowedPermissions': [
                {
                    'identityType': 'Group' if principal.get('Groupname') else 'User',
                    'identity': principal.get('Email') or principal.get('Groupname')
                }
                for principal in panopto_content['VideoContent']['Principals']
                if principal.get('Groupname') != 'Public'
                and (principal.get('Email') or principal.get('Groupname'))
            ]
        }
    ]
    target_content['permissions'][0]['allowAnonymous'] = any(
        principal.get('Groupname') == 'Public'
        for principal in panopto_content['VideoContent']['Principals']
    )

    LOG.debug('Converted document is %s', json.dumps(target_content, indent=2))

    return target_content


def push_to_target(target_content, config):
    """
    Implement this method to push converted content to the target
    """

    target_address = config.target_address
    target_credentials = config.target_credentials
    field_mapping = config.field_mapping

    url = '{coveo}/push/v1/organizations/{org}/sources/{source}/documents?documentId={id}'.format(
        coveo=target_address,
        org=target_credentials['organization'],
        source=target_credentials['source'],
        id=_get_document_id(config.panopto_site_address, target_content[field_mapping['Id']]))
    headers = _get_headers(target_credentials['api_key'])

    response = requests.put(url=url, json=target_content, headers=headers)
    LOG.debug('Request was %s', format_request_secure(response.request))

    if not response.ok:
        LOG.error('Failed response: %s, %s', response, response.text)
    response.raise_for_status()


def delete_from_target(video_id, config):
    """
    Implement this method to push converted content to the target
    """

    target_address = config.target_address
    target_credentials = config.target_credentials

    url = '{coveo}/push/v1/organizations/{org}/sources/{source}/documents?documentId={id}'.format(
        coveo=target_address, org=target_credentials['organization'],
        source=target_credentials['source'],
        id=_get_document_id(config.panopto_site_address, video_id))
    headers = _get_headers(target_credentials['api_key'])

    response = requests.delete(url=url, headers=headers)
    LOG.debug('Request was %s', format_request_secure(response.request))

    if not response.ok:
        LOG.error('Failed response: %s, %s', response, response.text)
    response.raise_for_status()


#
# Initialize and teardown steps here allow updating the coveo state correctly
#

def initialize(config):
    """
    Set the coveo push source status
    """
    _set_status('INCREMENTAL', config)


def teardown(config):
    """
    Set the coveo push source status
    """
    _set_status('IDLE', config)


##############################################
#
# Helpers
#
##############################################


def _get_document_id(panopto_site_address, vid):
    """
    Coveo document id must be formatted as a uri
    """
    return '{site}/Panopto/Pages/Viewer.aspx?id={id}'.format(
        site=panopto_site_address, id=vid)


def _get_headers(api_key):
    """
    Gets the common headers
    """
    return {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key}


def _set_status(status, config):
    """
    Set the status of your push source
    """
    #  https://api.cloud.coveo.com/push/v1/organizations/<MyOrganizationId>/sources/<MySourceId>/status?statusType=<MyStatusType>
    url = '{coveo}/push/v1/organizations/{org}/sources/{source}/status?statusType={status}'.format(
        coveo=config.target_address,
        org=config.target_credentials['organization'],
        source=config.target_credentials['source'],
        status=status)
    headers = _get_headers(config.target_credentials['api_key'])

    response = requests.post(url=url, headers=headers)
    LOG.debug('Request was %s', format_request_secure(response.request))

    response.raise_for_status()

    LOG.info('Successfully set coveo push source status to %s', status)

