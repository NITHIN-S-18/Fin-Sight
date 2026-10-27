class FinSightError(Exception):
    """Base exception for FinSight application errors."""


class DatasetError(FinSightError):
    """Base exception for dataset layer failures."""


class DatasetLoadError(DatasetError):
    """Raised when one or more dataset files cannot be loaded."""


class DatasetValidationError(DatasetError):
    """Raised when a dataset file fails structural or content validation."""


class DatasetNotFoundError(DatasetError):
    """Raised when a dataset record cannot be found."""


class UserNotFoundError(DatasetNotFoundError):
    """Raised when a user record cannot be found."""


class TransactionNotFoundError(DatasetNotFoundError):
    """Raised when a transaction record cannot be found."""


class SubscriptionNotFoundError(DatasetNotFoundError):
    """Raised when no subscription transactions are available for a user."""


class SubscriptionProcessingError(FinSightError):
    """Raised when subscription intelligence cannot be generated."""


class EmiNotFoundError(DatasetNotFoundError):
    """Raised when no EMI transactions are available for a user."""


class EmiProcessingError(FinSightError):
    """Raised when EMI intelligence cannot be generated."""


class BnplNotFoundError(DatasetNotFoundError):
    """Raised when no BNPL transactions are available for a user."""


class BnplProcessingError(FinSightError):
    """Raised when BNPL intelligence cannot be generated."""


class ExposureNotFoundError(DatasetNotFoundError):
    """Raised when financial exposure data cannot be found for a user."""


class ExposureDataUnavailableError(DatasetNotFoundError):
    """Raised when a user has no financial data to build an exposure report."""


class ExposureProcessingError(FinSightError):
    """Raised when financial exposure intelligence cannot be generated."""


class DashboardProcessingError(FinSightError):
    """Raised when dashboard intelligence cannot be generated."""

