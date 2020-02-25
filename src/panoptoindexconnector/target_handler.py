"""
Methods for the connector application to convert and sync content to the target endpoint

Implement these methods for the connector application
"""

# Standard Library Imports
from importlib import import_module
import logging
import os

# Local
from panoptoindexconnector.connector_config import ConnectorConfig

# Global constants
DIR = os.path.dirname(os.path.realpath(__file__))
LOG = logging.getLogger(__name__)


class TargetHandler:
    """
    Handle target conversions, reads, and writes
    """

    def __init__(self, config):
        """
        Initialize the TargetHandler based on the ConnectorConfig
        """
        assert isinstance(config, ConnectorConfig), 'config should be a ConnectorConfig object; got %s' % type(config)

        if not config.target_implementation:
            raise ValueError(
                "Config file %s doesn't defin target_implementation value" % ConnectorConfig.config_file_path
            )

        # Save the config
        self._config = config

        # Inject the dependency
        try:
            self._implementation_module = import_module(
                'panoptoindexconnector.implementations.%s' % config.target_implementation
            )
        except ImportError:
            LOG.exception(
                'Failed to import implementation module panoptoindexconnector.%s', config.target_implementation)
            raise
        LOG.debug('Implementation module = %s', self._implementation_module)

    def convert_to_target(self, panopto_video_content):
        """
        Implement this method to convert to target format
        """
        return self._implementation_module.convert_to_target(
            panopto_video_content, self._config.field_mapping)

    def delete_from_target(self, video_id):
        """
        Implement this method to push converted content to the target
        """
        self._implementation_module.delete_from_target(
            video_id, self._config.target_address, self._config.target_credentials)

    def push_to_target(self, target_content, config):
        """
        Implement this method to push converted content to the target
        """
        self._implementation_module.push_to_target(
            target_content, self._config.target_address, self._config.target_credentials, config)
