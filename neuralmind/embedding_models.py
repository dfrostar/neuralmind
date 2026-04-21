"""
embedding_models.py — Pluggable Embedding Models
================================================

Allows enterprises to swap embedding models:
- Default: sentence-transformers/all-MiniLM-L6-v2 (fast, lightweight)
- Domain-specific: Custom fine-tuned models
- Provider models: OpenAI, Anthropic (with caching to stay local-first)
- Specialized: Code embeddings (e.g., CodeBERT), legal, medical, etc.

Benefits:
- Better semantic understanding for specific domains
- Fine-tuning on proprietary code patterns
- Cost optimization (smaller models for less critical projects)
- Regulatory compliance (use models trained on approved data)

Configuration:
  [embeddings.model]
  type = "sentence-transformers"  # or "huggingface", "ollama", "custom"
  name = "sentence-transformers/all-MiniLM-L6-v2"
  dimensions = 384

  [embeddings.model.options]
  device = "cuda"  # or "cpu", "mps"
  batch_size = 32
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ============================================================================
# Embedding Model Interface
# ============================================================================


class EmbeddingModel(ABC):
    """Abstract base class for embedding models."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Model name/identifier."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding vector dimensions."""

    @property
    @abstractmethod
    def model_type(self) -> str:
        """Type: 'sentence-transformers', 'huggingface', 'ollama', 'custom'."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """
        Embed a single text string.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (list of floats)
        """

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """

    @abstractmethod
    def get_config(self) -> dict[str, Any]:
        """
        Get model configuration for serialization.

        Returns:
            Config dict to save in index metadata
        """


# ============================================================================
# Concrete Implementations
# ============================================================================


class SentenceTransformersModel(EmbeddingModel):
    """Sentence Transformers (default, fast, lightweight)."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
        batch_size: int = 32,
    ):
        """
        Initialize Sentence Transformers model.

        Args:
            model_name: HuggingFace model identifier
            device: "cpu", "cuda", "mps"
            batch_size: Batch size for inference
        """
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model = None
        self._dimensions = None

    @property
    def name(self) -> str:
        return self.model_name

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            try:
                from sentence_transformers import SentenceTransformer

                model = SentenceTransformer(self.model_name, device=self.device)
                self._dimensions = model.get_sentence_embedding_dimension()
                model = None  # Clear for lazy loading
            except Exception:
                self._dimensions = 384  # Default fallback
        return self._dimensions

    @property
    def model_type(self) -> str:
        return "sentence-transformers"

    def _get_model(self):
        """Lazy load model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """Embed single text."""
        model = self._get_model()
        embeddings = model.encode(text, convert_to_tensor=False)
        return embeddings.tolist() if hasattr(embeddings, "tolist") else list(embeddings)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed batch of texts."""
        model = self._get_model()
        embeddings = model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_tensor=False,
            show_progress_bar=False,
        )
        return [e.tolist() if hasattr(e, "tolist") else list(e) for e in embeddings]

    def get_config(self) -> dict[str, Any]:
        return {
            "type": "sentence-transformers",
            "name": self.model_name,
            "dimensions": self.dimensions,
            "device": self.device,
            "batch_size": self.batch_size,
        }


class OllamaModel(EmbeddingModel):
    """Ollama local LLM embeddings (for local-only deployments)."""

    def __init__(
        self,
        model_name: str = "nomic-embed-text",
        endpoint: str = "http://localhost:11434",
    ):
        """
        Initialize Ollama model.

        Args:
            model_name: Ollama model name
            endpoint: Ollama server endpoint
        """
        self.model_name = model_name
        self.endpoint = endpoint
        self._dimensions = None

    @property
    def name(self) -> str:
        return f"ollama/{self.model_name}"

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            try:
                import requests

                response = requests.post(
                    f"{self.endpoint}/api/embed",
                    json={"model": self.model_name, "input": "test"},
                    timeout=5,
                )
                if response.status_code == 200:
                    embeddings = response.json().get("embeddings", [[]])
                    self._dimensions = len(embeddings[0]) if embeddings else 768
                else:
                    self._dimensions = 768
            except Exception:
                self._dimensions = 768
        return self._dimensions

    @property
    def model_type(self) -> str:
        return "ollama"

    def embed_text(self, text: str) -> list[float]:
        """Embed single text via Ollama."""
        import requests

        response = requests.post(
            f"{self.endpoint}/api/embed",
            json={"model": self.model_name, "input": text},
            timeout=30,
        )
        if response.status_code == 200:
            embeddings = response.json().get("embeddings", [])
            return embeddings[0] if embeddings else [0.0] * self.dimensions
        raise RuntimeError(f"Ollama embedding failed: {response.text}")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed batch via Ollama."""
        import requests

        response = requests.post(
            f"{self.endpoint}/api/embed",
            json={"model": self.model_name, "input": texts},
            timeout=30,
        )
        if response.status_code == 200:
            return response.json().get("embeddings", [])
        raise RuntimeError(f"Ollama embedding failed: {response.text}")

    def get_config(self) -> dict[str, Any]:
        return {
            "type": "ollama",
            "name": self.model_name,
            "endpoint": self.endpoint,
            "dimensions": self.dimensions,
        }


# ============================================================================
# Model Registry & Factory
# ============================================================================


class EmbeddingModelRegistry:
    """Registry of available embedding models."""

    _models: dict[str, type[EmbeddingModel]] = {
        "sentence-transformers": SentenceTransformersModel,
        "ollama": OllamaModel,
    }

    @classmethod
    def register(cls, name: str, model_class: type[EmbeddingModel]) -> None:
        """Register a model."""
        cls._models[name.lower()] = model_class

    @classmethod
    def get(cls, name: str) -> type[EmbeddingModel] | None:
        """Get a model class by name."""
        return cls._models.get(name.lower())

    @classmethod
    def list_available(cls) -> list[str]:
        """List all registered models."""
        return sorted(cls._models.keys())


class EmbeddingModelFactory:
    """Create embedding model instances."""

    @staticmethod
    def create(model_type: str, model_name: str, **options: Any) -> EmbeddingModel:
        """
        Create an embedding model.

        Args:
            model_type: "sentence-transformers", "ollama", etc.
            model_name: Specific model identifier
            **options: Model-specific options

        Returns:
            EmbeddingModel instance

        Raises:
            ValueError: If model type not registered
        """
        model_class = EmbeddingModelRegistry.get(model_type)
        if model_class is None:
            available = ", ".join(EmbeddingModelRegistry.list_available())
            raise ValueError(
                f"Unknown embedding model type: {model_type}. "
                f"Available: {available}"
            )

        if model_type == "sentence-transformers":
            return SentenceTransformersModel(model_name=model_name, **options)
        elif model_type == "ollama":
            return OllamaModel(model_name=model_name, **options)
        else:
            # Fallback: try to instantiate class directly
            return model_class(model_name=model_name, **options)

    @staticmethod
    def from_config(config: dict[str, Any]) -> EmbeddingModel:
        """
        Create model from configuration dict.

        Config format:
            {
                "type": "sentence-transformers",
                "name": "sentence-transformers/all-MiniLM-L6-v2",
                "options": {"device": "cuda"}
            }
        """
        model_type = config.get("type", "sentence-transformers")
        model_name = config.get("name", "sentence-transformers/all-MiniLM-L6-v2")
        options = config.get("options", {})

        return EmbeddingModelFactory.create(model_type, model_name, **options)


# ============================================================================
# Default Model
# ============================================================================


def get_default_embedding_model() -> EmbeddingModel:
    """Get the default embedding model (fast and lightweight)."""
    return SentenceTransformersModel(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        device="cpu",
        batch_size=32,
    )
