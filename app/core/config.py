"""Core configuration for the Scientific Knowledge Graph platform."""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field


BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
GRAPH_PATH = DATA_DIR / "knowledge_graph.json"
INDEX_PATH = DATA_DIR / "search_index.npz"
DOCS_DB_PATH = DATA_DIR / "documents_fast.json"

SOURCES_DIR = Path(os.getenv(
    "SOURCES_DIR",
    "/mnt/nvme2n1/dockertestfolder/info/Источники информации",
))


@dataclass
class LLMConfig:
    """Configuration for the two available llama.cpp LLM endpoints."""
    primary_base_url: str = "http://arrayredes.ddns.net:54322/v1"
    primary_model: str = "inferencerlabs/DeepSeek-V4-Flash-MLX-2.8bit-INF"
    secondary_base_url: str = "http://arrayredes.ddns.net:44445/v1"
    secondary_model: str = "Qwen3.5-27B-Uncensored-HauhauCS-Aggressive-Q5_K_M.gguf"
    timeout: int = 120
    max_tokens: int = 2048
    temperature: float = 0.1


@dataclass
class EmbeddingConfig:
    model_name: str = "cointegrated/rubert-tiny2"
    dim: int = 312
    batch_size: int = 32
    max_seq_length: int = 512


@dataclass
class Settings:
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunk_size: int = 1200
    chunk_overlap: int = 200
    max_docs_per_run: int = int(os.getenv("MAX_DOCS", "0")) or 0  # 0 = all
    top_k_retrieval: int = 15
    top_k_rerank: int = 8
    bm25_weight: float = 0.4
    vector_weight: float = 0.6


settings = Settings()
