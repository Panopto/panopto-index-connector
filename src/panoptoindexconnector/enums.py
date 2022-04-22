"""
Enums for connector implementations
"""
from enum import Enum

class UsernameMapping(Enum):
    """
    SAML Azure AD username mapping attribute used for Panopto username
    """

    USER_PRINCIPAL_NAME = "userPrincipalName"
    EMAIL = "mail"

