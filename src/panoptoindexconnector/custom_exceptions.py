class CustomExceptions:
    """
    User-defined exceptions
    """

    class Error(Exception):
        """Base class for other exceptions"""
        pass

    class QuotaLimitExceededError(Error):
        """Raised when the Tenant quota has exceeded"""
        pass

    class UsernameMappingError(Error):
        """Raised when configuration username mapping value is not valid"""
        pass