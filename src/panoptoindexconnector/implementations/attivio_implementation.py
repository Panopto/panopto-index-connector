"""
Methods for the connector application to convert and sync content to the target endpoint

Implement these methods for the connector application
"""

# Standard Library Imports
import json
import logging
import os

# Third party
import requests

# Global constants
DIR = os.path.dirname(os.path.realpath(__file__))
LOG = logging.getLogger(__name__)


#########################################################################
#
# Exported methods to implement
#
#########################################################################


def convert_to_target(panopto_content, config):
    """
    Implement this method to convert to target format
    """

    field_mapping = config.field_mapping

    target_content = {field_mapping['Id']: panopto_content['Id']}

    target_content['fields'] = {
        field: panopto_content['VideoContent'][key]
        for key, field in field_mapping['Metadata'].items()
        if panopto_content['VideoContent'][key]
    }

    target_content['fields'].update({
        field: panopto_content['VideoContent'][key]
        for key, field in field_mapping['Info'].items()
        if panopto_content['VideoContent'][key]
    })

    LOG.debug('Converted document is %s', json.dumps(target_content, indent=2))

    # Principals
    target_content['permissions'] = [
        {
            'principal': {
                'name': principal.get('Username') or principal.get('Groupname'),
                'realm': 'Panopto',
                'type': 'user' if principal.get('Username') else 'group'
            },
            'readable': True
        }
        for principal in panopto_content['VideoContent']['Principals']
    ]

    return target_content


def push_to_target(target_content, config):
    """
    Implement this method to push converted content to the target
    """

    target_address = config.target_address
    target_credentials = config.target_credentials

    auth = requests.auth.HTTPBasicAuth(target_credentials['username'], target_credentials['password'])

    # Connect
    session = _connect_to_attivio(target_address, auth)

    # Do the write
    url = '{attivio}/rest/ingestApi/feedDocuments/{session}'.format(attivio=target_address, session=session)
    data = json.dumps(target_content)
    headers = {'Content-Type': 'application/json'}

    response = requests.post(url=url, auth=auth, data=data, headers=headers)

    if not response.ok:
        LOG.error('Failed response: %s, %s', response, response.text)
    response.raise_for_status()

    # Commit
    _commit_session_to_attivio(target_address, auth, session)

    # Close
    _disconnect_session_in_attivio(target_address, auth, session)


def delete_from_target(video_id, config):
    """
    Implement this method to push converted content to the target
    """

    target_address = config.target_address
    target_credentials = config.target_credentials

    auth = requests.auth.HTTPBasicAuth(target_credentials['username'], target_credentials['password'])

    # Connect
    session = _connect_to_attivio(target_address, auth)

    # Do the deletion
    url = '{attivio}/rest/ingestApi/delete/{session}'.format(attivio=target_address, session=session)
    data = json.dumps([video_id])
    headers = {'Content-Type': 'application/json'}

    response = requests.post(url=url, auth=auth, data=data, headers=headers)

    if not response.ok:
        LOG.error('Failed response: %s, %s', response, response.text)
    response.raise_for_status()

    # Commit
    _commit_session_to_attivio(target_address, auth, session)

    # Close
    _disconnect_session_in_attivio(target_address, auth, session)


#########################################################################
#
# Local helpers
#
#########################################################################


def _connect_to_attivio(target_address, auth):
    """
    Connecto to attivio and return session id
    """
    url = '{attivio}/rest/ingestApi/connect'.format(attivio=target_address)
    response = requests.get(url=url, auth=auth)
    response.raise_for_status()
    return response.json()


def _commit_session_to_attivio(target_address, auth, session):
    """
    Commit the changes in a session to attivio
    """
    url = '{attivio}/rest/ingestApi/commit/{session}'.format(attivio=target_address, session=session)
    response = requests.get(url=url, auth=auth)
    response.raise_for_status()


def _disconnect_session_in_attivio(target_address, auth, session):
    """
    Disconnect a session in attivio
    """
    url = '{attivio}/rest/ingestApi/disconnect/{session}'.format(attivio=target_address, session=session)
    response = requests.get(url=url, auth=auth)
    response.raise_for_status()
