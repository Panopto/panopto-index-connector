"""
The configuration object for the connector
"""

import io
import copy
from datetime import timedelta
import ruamel.yaml


class ConnectorConfig:
    """
    The configuration for this connector application
    """

    def __init__(self, config_file_path):
        """
        Initialize the configuration
        """

        self._config_file_path = config_file_path
        self._yaml_config = self._get_yaml_config(config_file_path)
        self._str = self._get_securely_displayble_config(self._yaml_config)

    def __str__(self):
        """
        Print self, but hide credentials
        """
        return self._str

    @staticmethod
    def _get_yaml_config(config_file_path):
        """
        Load the config
        """

        with ruamel.yaml.YAML() as yaml:
            with open(config_file_path, 'r') as configstream:
                try:
                    yaml_config = yaml.load(configstream)
                except ruamel.yaml.error.MarkedYAMLError as myerr:
                    message = myerr.context + ' ' + myerr.problem
                    mark = myerr.problem_mark
                    location = 'line: %i col: %i' % (mark.line, mark.column)
                    raise InvalidConfiguration(message + ' ' + location) from myerr
                except ruamel.yaml.error.YAMLError as yerr:
                    raise InvalidConfiguration('Unspecified error') from yerr
        return yaml_config

    @staticmethod
    def _get_securely_displayble_config(yaml_config):
        """
        Generate a config file with obfuscated secrets
        """
        # Make a deepcopy to not affect original yaml config
        yaml_config = copy.deepcopy(yaml_config)
        yaml = ruamel.yaml.YAML()

        # Obfuscate passwords for printable string
        for key in yaml_config:
            if 'credentials' not in key:
                continue
            node = yaml_config[key]
            for node_key in node:
                # allowlist -- only username and client id should be shown
                if node_key not in ('username', 'client_id', 'grant_type'):
                    node[node_key] = '********'

        # Save displayable config
        with io.StringIO() as buffer:
            yaml.dump(yaml_config, buffer)
            return buffer.getvalue()

    # pylint: disable=missing-docstring
    @property
    def config_file_path(self):
        return self._config_file_path

    @property
    def field_mapping(self):
        return self._yaml_config['field_mapping']

    @property
    def panopto_oauth_credentials(self):
        return self._yaml_config['panopto_oauth_credentials']

    @property
    def panopto_site_address(self):
        return self._yaml_config['panopto_site_address'].rstrip('/').rstrip('.')

    @property
    def panopto_username_mapping(self):
        return self._yaml_config['panopto_username_mapping']

    @property
    def polling_frequency(self):
        return timedelta(seconds=self._yaml_config.get('polling_seconds', 3600))

    @property
    def polling_retry_minimum(self):
        return timedelta(seconds=self._yaml_config.get('polling_retry_minimum', 300))

    @property
    def principal_allowlist(self):
        return self._yaml_config.get('principal_allowlist', None)

    @property
    def sleep_seconds(self):
        return self._yaml_config.get('sleep_seconds', 1)

    @property
    def skip_permissions(self):
        # ensures that this is parsed correctly where interpreted as bool or string
        # since yaml flexible; maybe too flexible in this case :)
        return str(self._yaml_config.get('skip_permissions')).lower() == 'true'

    @property
    def target_address(self):
        return self._yaml_config['target_address']

    @property
    def target_credentials(self):
        return self._yaml_config['target_credentials']

    @property
    def target_connection(self):
        return self._yaml_config['target_connection']

    @property
    def target_implementation(self):
        return self._yaml_config['target_implementation']


class InvalidConfiguration(Exception):
    """
    The configuration specified for the connector is not valid yaml
    """

    def __init__(self, message):
        super().__init__('Parse failure: ' + message)
