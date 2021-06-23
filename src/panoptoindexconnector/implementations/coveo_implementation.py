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


def convert_to_target(panopto_content, config):
    """
    Implement this method to convert to target format
    """

    field_mapping = config.field_mapping

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
    if not config.skip_permissions:
        target_content['permissions'] = [
            {
                'allowedPermissions': [
                    {
                        'identityType': 'Group' if principal.get('Groupname') else 'User',
                        'identity': principal.get('Email') or principal.get('Groupname') or 'admin@acco.unt'
                    }
                    for principal in panopto_content['VideoContent']['Principals']
                    if principal.get('Groupname') != 'Public'
                    and (principal.get('Email') or principal.get('Groupname') or principal.get('Username') == 'admin')
                ]
            }
        ]
        target_content['permissions'][0]['allowAnonymous'] = any(
            principal.get('Groupname') == 'Public'
            for principal in panopto_content['VideoContent']['Principals']
        )
    else:
        # https://docs.coveo.com/en/107/index-content/simple-permission-model-definition-examples
        target_content['permissions'] = [{"allowAnonymous": True}]

    LOG.debug('Converted document is %s', json.dumps(target_content, indent=2))

    return target_content


def push_to_target(target_content, config):
    """
    Implement this method to push converted content to the target
    """

    push_needed_security_mappings(target_content, config)
    push_content_data(target_content, config)


def push_content_data(target_content, config):
    """
    Push the actual content
    """
    field_mapping = config.field_mapping

    url = '{coveourl}/push/v1/organizations/{org}/sources/{source}/documents?documentId=%s' % (
        _get_document_id(config.panopto_site_address, target_content[field_mapping['Id']]))
    _ = _send_coveo_request(config, url, 'put', json=target_content)


def push_needed_security_mappings(target_content, config):
    """
    Push em
    """

    # We use a single rule with potentially multiple values, so we always grab the first
    principal = target_content['permissions'][0]
    # If this video has allow anonymous on it, there is nothing to do
    if principal.get('allowAnonymous', False):
        return
    allow_permissions = principal['allowedPermissions']
    needed_permissions = [p for p in allow_permissions if should_map_security(p['identity'])]
    if needed_permissions:
        ensure_each_security_mapping(target_content, config, needed_permissions)
    LOG.info('Pushed %i new security identities', len(needed_permissions))


def ensure_each_security_mapping(target_content, config, needed_permissions):
    """
    1 x 1
    """
    provider_id = config.target_credentials.get('security_provider')
    for permission in needed_permissions:
        # get the permission
        # body = permissions_to_batch_body([needed_permission])
        body = {
            "identity": {
                "name": permission["identity"],
                "type": permission["identityType"].upper()
            }
        }
        uri = '{coveourl}/push/v1/organizations/{org}/providers/%s/permissions' % provider_id
        _send_coveo_request(config, uri, 'put', json=body)


def delete_from_target(video_id, config):
    """
    Implement this method to push converted content to the target
    """

    url = '{coveourl}/push/v1/organizations/{org}/sources/{source}/documents?documentId=' + \
        _get_document_id(config.panopto_site_address, video_id)
    _ = _send_coveo_request(config, url, 'delete')


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


def _send_coveo_request(config, url_format, requesttype, additional_headers=None, skip_default_headers=False, **kwargs):
    """
    Internal helper to send a request for coveo
    """

    requesttype = requesttype.lower()

    if requesttype not in ('get', 'put', 'delete', 'post'):
        raise ValueError('Unexpected rest request type: %s' % requesttype)

    target_address = config.target_address
    target_credentials = config.target_credentials

    headers = dict() if skip_default_headers else _get_default_headers(target_credentials['api_key'])

    if additional_headers:
        headers.update(additional_headers)

    # Supply default config based defaults if not given
    url = url_format.format(
        coveourl=target_address,
        org=target_credentials['organization'],
        source=target_credentials['source'])

    handler = requests.__dict__[requesttype]

    response = handler(url=url, headers=headers, **kwargs)
    if not response.ok:
        LOG.error('Failed response\n%s', format_request_secure(response.request))
    response.raise_for_status()
    return response


SECURITY_IDS_MAPPED_TO_PROVIDER = set()
"""
Keeps a record of users pushed to the provider;
just a per process lifespan to get unblocked.
"""


def record_security_mapping(key):
    """
    Just cheap way to ensure we've defined the mappings
    """
    SECURITY_IDS_MAPPED_TO_PROVIDER.add(key)


def should_map_security(key):
    """
    T/f whether the user needs to be mapped
    """
    return key not in SECURITY_IDS_MAPPED_TO_PROVIDER


def _get_document_id(panopto_site_address, vid):
    """
    Coveo document id must be formatted as a uri
    """
    return '{site}/Panopto/Pages/Viewer.aspx?id={id}'.format(
        site=panopto_site_address, id=vid)


def _get_default_headers(api_key):
    """
    Gets the common headers
    """
    return {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + api_key,
        'Accept': 'application/json'}


def permissions_to_batch_body(permissions):
    """
    Maps a coveo allow permission to a coveo security identity
    """
    members, mappings = [], []
    for permission in permissions:
        if permission['identityType'].lower() == 'group':
            members.append({
                'name': permission['identity'],
                'type': 'GROUP',  # UPPER strict here
                'members': [],
                'wellKnowns': [],
            })
        if permission['identityType'].lower() == 'user':
            mappings.append({
                'identity': {
                    'name': permission['identity'],
                    'type': 'USER',  # UPPER strict here
                },
                'mappings': [{
                    'name': permission['identity'],
                    'type': 'USER',
                    'provider': 'Email Security Provider'
                }],
                'wellKnowns': []
            })
            members.append({
                'name': permission['identity'],
                'type': 'USER',  # UPPER strict here
            })
        else:
            LOG.warning('Permission %s could not be mapped to an identity', permission)
    return {'members': members, 'mappings': mappings, 'delete': []}


def _set_status(status, config):
    """
    Set the status of your push source
    """
    #  https://api.cloud.coveo.com/push/v1/organizations/<orgid>/sources/<srcid>/status?statusType=<status>
    url = '{coveourl}/push/v1/organizations/{org}/sources/{source}/status?statusType=' + status
    _ = _send_coveo_request(config, url, 'post')

    LOG.info('Successfully set coveo push source status to %s', status)
