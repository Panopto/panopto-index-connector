"""
General helpers
"""

# Standard Library Imports
import logging
import os

# Global constants
DIR = os.path.dirname(os.path.realpath(__file__))
LOG = logging.getLogger(__name__)


def format_request_secure(request):
    """
    Format a request, but obscure any sensitive headers
    """

    request_str = "url = %s | headers = %s | body = %s" % (
        request.url, format_headers_secure(request.headers), request.body)

    return request_str


def format_headers_secure(headers):
    """
    Blacklist anything sensitive
    """
    secure_headers = dict(headers)  # shallow fine here since these are 1-layer of strings

    for key, value in headers.items():
        if key.lower().startswith('auth'):
            secure_headers[key] = value[0:2] + '****' + value[-2:]

    return secure_headers
