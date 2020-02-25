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
# {
  # 'author': 'Alice Smith',
  # 'date': '2017-11-08T12:18:41.666Z',
  # 'documenttype': 'Text',
  # 'filename': 'mytext.txt',
  # 'language': [
    # 'English'
  # ],
  # 'permanentid': 'sample95829alice84720permanent93829id',
  # 'sourcetype': 'Push',
  # 'title': 'My Text',
  # 'fileExtension': '.txt',
  # 'data': 'This is a sample text written by Alice Smith.',
  # 'permissions': [
    # {
      # 'allowAnonymous': false,
      # 'allowedPermissions': [
        # {
          # 'identity': 'AlphaTeam',
          # 'identityType': 'Group'
        # }
      # ],
      # 'deniedPermissions': [
        # {
          # 'identity': 'bob@example.com',
          # 'identityType': 'User'
        # }
      # ]
    # }
  # ]
# }
#

def convert_to_target(panopto_content, field_mapping):
    """
    Implement this method to convert from panopto content format to target format
    """

    target_content = {
        field_mapping['Id']: panopto_content['Id'],
        'documenttype': 'Panopto',
        field_mapping['Info']['Language']: panopto_content['VideoContent']['Language'],
        field_mapping['Info']['Title']: panopto_content['VideoContent']['TItle'],
    }

    target_content['data'] = ' '.join([
        panopto_content['VideoContent'][key]
        for key, field in field_mapping['Metadata'].items()
        if panopto_content['VideoContent'][key]
    ])

    # Principals
    target_content['permissions'] = [
        {
            'allowedPermissions': [
                {
                    'identityType': 'Group' if 'Groupname' in principal else 'User',
                    'identity': principal.get('Email', principal.get('Groupname'))
                }
                for principal in panopto_content['VideoContent']['Principals']
                if principal.get('Groupname') != 'Public'
            ]
        }
    ]
    target_content['permissions'][0]['allowAnonymous'] = any(
        principal.get('Groupname') == 'Public'
        for principal in panopto_content['VideoContent']['Principals']
    )

    LOG.debug('Converted document is %s', json.dumps(target_content, indent=2))

    return target_content


def push_to_target(target_content, target_address, target_credentials, config):
    """
    Implement this method to push converted content to the target
    """

    field_mapping = config.field_mapping

    url = '{coveo}/push/v1/organizations/{org}/sources/{source}/documents?documentId={id}'.format(
        coveo=target_address,
        org=target_credentials['organization'],
        source=target_credentials['source'],
        id=target_content[field_mapping['id']])
    data = json.dumps(target_content)
    headers = {'Content-Type': 'application/json', 'Authorization': target_credentials['oauthtoken']}

    response = requests.put(url=url, data=data, headers=headers)

    if not response.ok:
        LOG.error('Failed response: %s, %s', response, response.text)
    response.raise_for_status()


def delete_from_target(video_id, target_address, target_credentials):
    """
    Implement this method to push converted content to the target
    """

    url = '{coveo}/push/v1/organizations/{org}/sources/{source}/documents?documentId={id}'.format(
        coveo=target_address, org=target_credentials['organization'], source=target_credentials['source'], id=video_id)
    headers = {'Content-Type': 'application/json', 'Authorization': target_credentials['oauthtoken']}

    response = requests.delete(url=url, headers=headers)

    if not response.ok:
        LOG.error('Failed response: %s, %s', response, response.text)
    response.raise_for_status()
