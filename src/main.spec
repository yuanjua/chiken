# -*- mode: python ; coding: utf-8 -*-
# Universal build specification for PyInstaller with ChromaDB support
# Usage: EXECUTABLE_NAME=<target-name> pyinstaller main.spec

import os
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import copy_metadata

# Get the name from environment variable, default to 'main' if not provided
exe_name = os.environ.get('EXECUTABLE_NAME', 'main')

# Collect ChromaDB data files
chromadb_datas = collect_data_files('chromadb')

# Collect LiteLLM data files (tokenizers and other data)
litellm_datas = collect_data_files('litellm')

# Collect tiktoken data files (encoding vocabularies)
tiktoken_datas = collect_data_files('tiktoken')
tiktoken_ext_datas = collect_data_files('tiktoken_ext')

# FastMCP metadata
fastmcp_datas = copy_metadata('fastmcp')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        *chromadb_datas,
        *litellm_datas,
        *tiktoken_datas,
        *tiktoken_ext_datas,
        *fastmcp_datas,
    ],
    hiddenimports=[
        # ChromaDB hidden imports to fix PyInstaller issues
        "chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2",
        "onnxruntime",
        "tokenizers",
        "tqdm",
        "chromadb.telemetry.product.posthog",
        "chromadb.api.segment",
        "chromadb.api.rust",
        "chromadb.db.impl",
        "chromadb.db.impl.sqlite",
        "chromadb.migrations",
        "chromadb.migrations.embeddings_queue",
        "chromadb.segment.impl.manager",
        "chromadb.segment.impl.manager.local",
        "chromadb.execution.executor.local",
        "chromadb.quota.simple_quota_enforcer",
        "chromadb.rate_limit.simple_rate_limit",
        "chromadb.segment.impl.metadata",
        "chromadb.segment.impl.metadata.sqlite",
        # Additional imports that might be needed
        "chromadb.db.mixins",
        "chromadb.db.mixins.sysdb",
        "chromadb.ingest",
        "chromadb.segment",
        "chromadb.segment.impl",
        "chromadb.segment.impl.vector",
        "chromadb.segment.impl.vector.local_hnsw",
        "chromadb.segment.impl.vector.local_persistent_hnsw",
        # tiktoken imports
        "tiktoken",
        "tiktoken.core",
        "tiktoken.load",
        "tiktoken.model",
        "tiktoken.registry",
        "tiktoken._educational",
        "tiktoken_ext",
        "tiktoken_ext.openai_public",
        # LiteLLM imports
        "litellm",
        "litellm.utils",
        "litellm.cost_calculator",
        "litellm.litellm_core_utils",
        "litellm.litellm_core_utils.default_encoding",
        "litellm.litellm_core_utils.llm_cost_calc.utils",
        "litellm.litellm_core_utils.tokenizers",
        "tokenizers",
        "regex._regex",
        "fastmcp",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=os.environ.get("APPLE_SIGNING_IDENTITY"),
    entitlements_file="entitlements.plist" if os.environ.get("APPLE_SIGNING_IDENTITY") else None,
)
