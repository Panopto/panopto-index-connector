"""
Methods for the connector application to convert and sync content to the target endpoint

Implement these methods for the connector application
"""

# Standard Library Imports
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

def convert_to_target(panopto_content, config):
    """
    Implement this method to convert to target format
    """

    target_content = {'id': panopto_content['Id']}

    return target_content


def push_to_target(target_content, config):
    """
    Implement this method to push converted content to the target
    """

    LOG.info('Would push the following to target: %s', target_content['id'])


def delete_from_target(video_id, config):
    """
    Implement this method to push converted content to the target
    """

    LOG.info('Would delete the following target: %s', video_id)
