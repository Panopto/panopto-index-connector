"""
Methods for the connector application to convert and sync content to the target endpoint

Start with this template to implement these methods for the connector application
"""

# Standard Library Imports
# import json
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


def convert_to_target(panopto_content, field_mapping):
    """
    Implement this method to convert from panopto content format to target format
    """

    raise NotImplementedError("This is only a template")


def push_to_target(target_content, config):
    """
    Implement this method to push converted content to the target
    """

    # Values on the config file are the same as in the yaml configuration file
    #
    # config.field_mapping
    # config.panopto_oauth_credentials
    # config.panopto_site_address
    # config.target_address
    # config.target_credentials

    # So your implementation might look like
    # url = config.target_address + '/some/uri/path'
    # auth = {'Authorization': 'Bearer ' + config.target_credentials['apikey']
    # requests.put(url=url, auth=auth, json=target_content)

    raise NotImplementedError("This is only a template")


def delete_from_target(video_id, config):
    """
    Implement this method to push converted content to the target
    """

    # Same config as above.
    # So your implementation might look like
    # url = config.target_address + '/some/uri/path'
    # auth = {'Authorization': 'Bearer ' + config.target_credentials['apikey']
    # requests.put(url=url, auth=auth, json=target_content)

    raise NotImplementedError("This is only a template")
