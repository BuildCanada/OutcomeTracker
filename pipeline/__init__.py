"""
Promise Tracker Data Pipeline

A modular, resilient pipeline for ingesting, processing, and linking government data
to track promise fulfillment.

Stages:
1. Ingestion: Collect raw data from government sources
2. Processing: Transform raw data into structured evidence items
3. Linking: Link evidence to promises and score progress
"""

__version__ = "2.0.0"
__author__ = "Promise Tracker Team"

from .core.job_runner import JobRunner
from .orchestrator import PipelineOrchestrator

__all__ = ["JobRunner", "PipelineOrchestrator"]

# This file makes the pipeline directory a Python package 