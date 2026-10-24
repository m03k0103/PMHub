#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMHub LLM Assist Package (admin/llm/)
=====================================
Provides deterministic digest generation, budgeted & cached LLM client,
and halluncination-free ID-referenced discovery judgment (Drop 81 / Track [LLM-Assist]).
"""

from .digest import build_discovery_digest
from .client import LLMClient, DEFAULT_LLM_BUDGET
from .discovery_judge import judge_discovery_digest

__all__ = [
    "build_discovery_digest",
    "LLMClient",
    "DEFAULT_LLM_BUDGET",
    "judge_discovery_digest",
]
