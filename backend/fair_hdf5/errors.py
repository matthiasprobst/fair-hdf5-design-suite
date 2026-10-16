"""Errors that callers can safely present as invalid user input."""


class DesignError(ValueError):
    """Invalid blueprint or unreadable uploaded HDF5 content."""


class UploadTooLarge(DesignError):
    """An uploaded file exceeds the configured limit."""
