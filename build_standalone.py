#!/usr/bin/env python
"""
Build the standalone installer
"""

# Standard Library Imports
import argparse
from itertools import chain
import logging
import os
import platform
import posixpath
from subprocess import check_call, CalledProcessError

# In House
from tools import Pushd, data_files, restore_icon


DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)))
LOG = logging.getLogger(__name__)


def _build_standalone_installer(name, entrypoint, icon, one_file=True):
    """
    Build a standalone installer using pyinstaller
    """

    with Pushd(DIR):

        add_data = list(chain(*[
            ('--add-data',
             data_file + ';' + posixpath.normpath(posixpath.dirname(data_file)))
            for data_file in data_files()
        ]))

        # Either file or directory outputs from pyinstaller
        output_type = '-F' if one_file else '-D'

        paths = r"--paths=src\panoptoindexconnector;src\panoptoindexconnector\implementations"

        cmd = [
            'pyinstaller',
            entrypoint,
            '--name', name,
            '--icon', icon,
            paths,
            output_type,
            '--version-file', 'version_info',
            '--clean', '-y',
        ] + add_data

        return_code = 0
        print('Using pyinstaller found at')
        check_call(['where', 'pyinstaller'])
        print('Running:', ' '.join(cmd))

        try:
            check_call(cmd)
        except CalledProcessError as cpe:
            LOG.exception(cpe)
            return_code = cpe.returncode

    return return_code


#################################
#
# Script handling
#
#################################


def build_verb(args):
    # pylint: disable=unused-argument
    """
    Verb to build the standalone installer.

    Assumes pre-requisites have been installed outside of this.
    """

    # Fetch panopto icon
    icon = restore_icon()

    # Run PyInstaller
    return _build_standalone_installer(
        name='panopto-connector',
        entrypoint='src/panoptoindexconnector/connector.py',
        icon=icon,
        one_file=args.one_file
    )


def main():
    """
    Entrypoint
    """

    major, minor = map(int, platform.python_version_tuple()[:2])
    assert major >= 3 and minor >= 4, "Only supports python >= 3.4"

    args = parse_args()
    set_logger(args)
    return_code = build_verb(args)

    if return_code:
        raise SystemExit(return_code)


def parse_args():
    """Parse commandline arguments."""

    # Description
    parser = argparse.ArgumentParser(description='Build the standalone Windows Search DB Installer.')

    # Logging level
    parser.add_argument('-d', '--debug', help='Set debug level logging.', action='store_true')

    # Add new arguments here: https://docs.python.org/2/howto/argparse.html
    parser.add_argument('--one-file', choices=['on', 'off'], default='on',
                        help='Enable or disable one-file distribution build.')

    args = parser.parse_args()
    args.one_file = args.one_file == 'on'

    return args


def set_logger(args):
    """Set the logging level and format"""

    # Add logging setup here
    log_format = '%(asctime)s %(levelname)-8s%(module)25s - %(message)s'
    log_date_format = '%H:%M:%S'  # briefs
    logging_level = logging.DEBUG if args.debug else logging.INFO

    # Set main level
    logging.basicConfig(format=log_format, level=logging_level, datefmt=log_date_format)


if __name__ == '__main__':
    main()
