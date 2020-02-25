"""
Methods for the connector application to convert and sync content to the target endpoint

Implement these methods for the connector application
"""

# Standard Library Imports
import json
import logging
import os

# Third party
# import requests

# Global constants
DIR = os.path.dirname(os.path.realpath(__file__))
LOG = logging.getLogger(__name__)


#########################################################################
#
# Exported methods to implement
#
#########################################################################

# since this is debug, we'll disable using all the args
# pylint: disable=unused-argument

def convert_to_target(panopto_content, field_mapping):
    """
    Implement this method to convert to target format
    """

    LOG.info('Received the following panopto content: %s', json.dumps(panopto_content, indent=2))

    target_content = {'id': panopto_content['Id']}

    target_content['fields'] = {
        field: panopto_content['VideoContent'][key]
        for key, field in field_mapping['Metadata'].items()
    }

    target_content['fields'].update({
        field: panopto_content['VideoContent'][key]
        for key, field in field_mapping['Info'].items()
    })

    # Principals
    target_content['permissions'] = [
        {
            'principal': {
                'name': principal.get('Username', principal.get('Groupname')),
                'type': 'user' if principal.get('Username') else 'group'
            },
            'readable': True
        }
        for principal in panopto_content['VideoContent']['Principals']
    ]

    return target_content


def push_to_target(target_content, target_address, target_credentials, config):
    """
    Implement this method to push converted content to the target
    """

    LOG.info('Would push the following to target: %s', json.dumps(target_content, indent=2))


def delete_from_target(video_id, target_address, target_credentials):
    """
    Implement this method to push converted content to the target
    """

    LOG.info('Would delete the following target: %s', video_id)
