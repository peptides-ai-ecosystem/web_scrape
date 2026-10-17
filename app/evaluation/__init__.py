"""
CSV Sync Evaluation Module
==========================
Automated verification that data was correctly inserted into
the database after a sync, by comparing CSV expectations
against the live DB state.

Usage:
    from app.evaluation.runner import run_evaluation
"""

from app.evaluation.runner import run_evaluation

__all__ = ["run_evaluation"]
