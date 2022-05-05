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

class UserGroupMapping(Enum):
    """
    SAML Azure AD user group mapping attribute used for Panopto user group
    """

    GROUP_ID = "id"
    SAM_ACCOUNT_NAME = "onPremisesSamAccountName"

