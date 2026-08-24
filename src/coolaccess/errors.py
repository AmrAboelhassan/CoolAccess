"""Typed failures for deterministic CoolAccess domain operations."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable machine-readable error codes."""

    INVALID_SELECTION = "invalid_selection"
    STRUCTURAL_MISMATCH = "structural_mismatch"
    FULL_STATE_MISMATCH = "full_state_mismatch"
    INVALID_STATIC_SELECTION = "invalid_static_selection"
    INVALID_REPLACEMENT = "invalid_replacement"
    INVALID_MARGINAL_ADDITION = "invalid_marginal_addition"
    INTERNAL_CONSISTENCY = "internal_consistency"


class CoolAccessDomainError(ValueError):
    """Base error carrying deterministic details without HTTP concerns."""

    code: ErrorCode

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(sorted((details or {}).items()))


class InvalidSelectionError(CoolAccessDomainError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.INVALID_SELECTION, details=details)


class StructuralMismatchError(CoolAccessDomainError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.STRUCTURAL_MISMATCH, details=details)


class FullStateMismatchError(CoolAccessDomainError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.FULL_STATE_MISMATCH, details=details)


class InvalidStaticSelectionError(CoolAccessDomainError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.INVALID_STATIC_SELECTION, details=details)


class InvalidReplacementError(CoolAccessDomainError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.INVALID_REPLACEMENT, details=details)


class InvalidMarginalAdditionError(CoolAccessDomainError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.INVALID_MARGINAL_ADDITION, details=details)


class InternalConsistencyError(CoolAccessDomainError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=ErrorCode.INTERNAL_CONSISTENCY, details=details)
