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

    class ConfigurationError(Error):
        """Raised when configuration is not properly set"""
        pass