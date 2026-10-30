"""
Official ContextBench Evaluation Adapter for RepoNeedle.

Translates ContextBench benchmark instances into RepoNeedle retrieval queries,
runs frozen evaluation configurations (ARM-101-BASE, BASE-BM25), and formats
predictions conforming to official ContextBench trajectory format.

Strictly enforces zero information leakage using LeakageGuard.
Preserves evaluation denominator on checkout or indexing failures.
"""

import sys
import os
import time
import json
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from reponeedle.models import FileDoc, Query, BudgetConfig, AblationConfig
from reponeedle.engine import RepoNeedleEngine
from reponeedle.core.graph import RepoGraph
from reponeedle.core.lexical import BM25Index
from research.contextbench_evaluation.leakage_guard import LeakageGuard, DataLeakageSecurityException


# Memory profiling via native Windows API
class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


try:
    ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
except Exception:
    pass

def get_process_rss_mb() -> float:
    try:
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return float(counters.WorkingSetSize) / (1024.0 * 1024.0)
    except Exception:
        pass
    return 0.0


class FrozenConfigurationRegistry:
    """
    Enforces immutable configuration settings for external benchmarking.
    """
    @staticmethod
    def get_arm_101() -> Dict[str, Any]:
        """
        Stage 3.12-3.14 Champion: Soft Lexical Damping (tau=0.25) + Level 1 Verified Edges (unattenuated).
        """
        return {
            "system_id": "ARM-101-BASE",
            "soft_damping_tau": 0.25,
            "hub_attenuation_policy": "unattenuated",
            "edge_filter": "level_1_verified",
            "enable_lexical": True,
            "enable_semantic": True,
            "enable_graph": True,
            "doc_filter_penalty": 0.50,
            "budget_tokens": 8000,
            "allow_skeletons": True,
        }

    @staticmethod
    def get_base_bm25() -> Dict[str, Any]:
        """
        Baseline: Decoupled Okapi BM25.
        """
        return {
            "system_id": "BASE-BM25",
            "soft_damping_tau": 0.0,
            "hub_attenuation_policy": "none",
            "edge_filter": "none",
            "enable_lexical": True,
            "enable_semantic": False,
            "enable_graph": False,
            "doc_filter_penalty": 1.0,
            "budget_tokens": 8000,
            "allow_skeletons": True,
        }


class ContextBenchAdapter:
    """
    Runs external ContextBench evaluation without information leakage.
    """
    def __init__(self, config_name: str = "ARM-101-BASE", repo_cache_dir: Optional[Path] = None):
        self.config_name = config_name
        if config_name.upper() in ("ARM-101", "ARM-101-BASE", "CHAMPION"):
            self.config = FrozenConfigurationRegistry.get_arm_101()
        elif config_name.upper() in ("BM25", "BASE-BM25"):
            self.config = FrozenConfigurationRegistry.get_base_bm25()
        else:
            raise ValueError(f"Unknown frozen configuration: {config_name}")

        self.repo_cache_dir = repo_cache_dir or (ROOT_DIR / "external" / "contextbench_repos")

    def run_task(self, raw_instance: Dict[str, Any], file_docs: Optional[List[FileDoc]] = None) -> Dict[str, Any]:
        """
        Processes a single ContextBench task.
        Strictly sanitizes raw_instance to eliminate any potential target leakage.
        """
        # 1. Strict leakage prevention
        sanitized_input = LeakageGuard.inspect_and_sanitize(raw_instance)
        LeakageGuard.assert_no_leakage_in_engine_call(sanitized_input)

        instance_id = sanitized_input.get("instance_id", "unknown")
        repo = sanitized_input.get("repo", "unknown")
        base_commit = sanitized_input.get("base_commit", "unknown")
        query_text = sanitized_input.get("problem_statement", "")

        t0 = time.perf_counter()
        initial_rss = get_process_rss_mb()

        # Handle missing query or missing repository documents
        if not query_text:
            return {
                "instance_id": instance_id,
                "repo": repo,
                "base_commit": base_commit,
                "system_id": self.config["system_id"],
                "status": "ERROR_EMPTY_QUERY",
                "ranked_files": [],
                "packed_context": [],
                "retrieval_time_ms": 0.0,
                "memory_rss_mb": initial_rss,
                "token_count": 0,
                "error": "Query problem_statement is empty",
            }

        if file_docs is None or len(file_docs) == 0:
            return {
                "instance_id": instance_id,
                "repo": repo,
                "base_commit": base_commit,
                "system_id": self.config["system_id"],
                "status": "ERROR_CHECKOUT_FAILED",
                "ranked_files": [],
                "packed_context": [],
                "retrieval_time_ms": 0.0,
                "memory_rss_mb": initial_rss,
                "token_count": 0,
                "error": f"Repository checkout unavailable for {repo} at {base_commit}",
            }

        # 2. Build index and execute retrieval
        try:
            if self.config["system_id"] == "BASE-BM25":
                bm25 = BM25Index()
                bm25.fit(file_docs)
                scores = bm25.score(query_text)
                ranked_indices = np.argsort(-scores)
                ranked_paths = [file_docs[idx].path for idx in ranked_indices]
            else:
                # ARM-101-BASE: Decoupled Okapi BM25 with soft lexical damping and Level 1 verified call edges
                engine = RepoNeedleEngine.from_documents(file_docs, ablation_config=AblationConfig.candidate_c())
                query_obj = Query(text=query_text)
                res = engine.retrieve(query_obj, budget_config=BudgetConfig(target_tokens=self.config["budget_tokens"], allow_skeletons=self.config["allow_skeletons"]))
                ranked_paths = [f.path for f in res.files]

            exec_time_ms = (time.perf_counter() - t0) * 1000.0
            peak_rss = get_process_rss_mb()

            return {
                "instance_id": instance_id,
                "repo": repo,
                "base_commit": base_commit,
                "system_id": self.config["system_id"],
                "status": "SUCCESS",
                "ranked_files": ranked_paths,
                "packed_context": ranked_paths[:10],
                "retrieval_time_ms": round(exec_time_ms, 2),
                "memory_rss_mb": round(peak_rss, 1),
                "token_count": 0,
                "error": None,
            }

        except Exception as e:
            exec_time_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "instance_id": instance_id,
                "repo": repo,
                "base_commit": base_commit,
                "system_id": self.config["system_id"],
                "status": "ERROR_EXECUTION_FAILURE",
                "ranked_files": [],
                "packed_context": [],
                "retrieval_time_ms": round(exec_time_ms, 2),
                "memory_rss_mb": round(get_process_rss_mb(), 1),
                "token_count": 0,
                "error": str(e),
            }
