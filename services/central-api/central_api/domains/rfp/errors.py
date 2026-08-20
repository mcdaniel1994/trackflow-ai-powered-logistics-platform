"""Typed failures crossing the RFP stage-to-worker boundary."""


class RfpProcessingError(RuntimeError):
    """Base class whose message is safe to keep out of logs and API responses."""


class RetryableRfpProcessingError(RfpProcessingError):
    """A database, provider, or network stage failed and may succeed on retry."""


class DeterministicRfpProcessingError(RfpProcessingError):
    """The requested work cannot become valid through a retry."""
