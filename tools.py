import os
import posixpath
import requests


DIR = os.path.abspath(os.path.dirname(__file__))
RES_DIR = os.path.join(DIR, 'res')


class Pushd(object):
    """
    Context to push a directory
    """
    # pylint: disable=too-few-public-methods

    def __init__(self, *args):
        self.original_path = os.getcwd()
        self._newdir = os.path.join(*args)

    def __enter__(self):
        os.chdir(self._newdir)

    def __exit__(self, typ, value, throwback):
        os.chdir(self.original_path)


def data_files():
    """
    Translates the manifest into the datafiles
    """
    with open(os.path.join(DIR, 'MANIFEST')) as manifest:
        return [line.strip() for line in manifest if line.strip() and '#' not in line]


def restore_icon(res_dir=RES_DIR):
    """
    Currently no good download option -- copy off of seasyn
    """

    _ensure_dir(res_dir)

    print('Restoring panopto icon...')

    url = 'https://www.panopto.com/wp-content/themes/panopto/library/images/favicons/favicon.ico'
    logo = os.path.join(res_dir, 'panopto.ico')

    # Get favicon icon and store to res\panopto.ico
    r = requests.get(url)

    if r.status_code == 200:
        with open(logo, 'wb') as f:
            f.write(r.content)

        return to_posix(logo)

    return ""


#
# Internal
#


def _ensure_dir(dirpath):
    """
    Ensure that a directory exists
    """
    if not os.path.exists(dirpath):
        os.mkdir(dirpath)


def to_posix(path):
    """
    Convert a path to posix representation
    """
    return os.path.splitdrive(path)[1].replace(os.path.sep, posixpath.sep) or posixpath.curdir
