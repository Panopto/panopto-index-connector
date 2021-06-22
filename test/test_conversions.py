"""
Tests for document conversion; largely an example for how one can set up tests for their own document conversions.
"""

# Standard Library Imports
import logging
import os


# Global constants
DIR = os.path.dirname(os.path.realpath(__file__))
LOG = logging.getLogger(__name__)


# pylint: disable=invalid-name
# pylint: disable=missing-docstring


def test_attivio_conversion():

    # Configuration
    from panoptoindexconnector.implementations import attivio_implementation as implementation
    from panoptoindexconnector.connector_config import ConnectorConfig
    attivio_path = os.path.join(DIR, '..', 'src', 'panoptoindexconnector', 'implementations', 'attivio.yaml')
    field_mapping = ConnectorConfig(attivio_path).field_mapping

    # Dummy content and useful example
    panopto_content = {
        'Id': 'de799c45-ccde-4187-80b8-ca383c540db5',
        'VideoContent' : {
            'Title': 'My title',
            'Language': 'English',
            'Url': 'https://url.moo',
            'ThumbnailUrl': 'http://url.moo',
            'Summary': 'Just a dummy',
            'MachineTranscription': 'We are robots',
            'HumanTranscription': 'We are humans',
            'ScreenCapture': 'This is text',
            'Presentation': 'I was extracted from a powerpoint',
            'Principals': [
            ]
        }
    }

    # Test conversion and assert attivio formatting
    attivio_content = implementation.convert_to_target(panopto_content, field_mapping)

    assert attivio_content[field_mapping['Id']] == panopto_content['Id']
