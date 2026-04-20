
import httpx

from .config import CONFIG


class OllamaClient:
    """Client for interacting with a local Ollama server."""

    def __init__(self):
        self.config = CONFIG.get("local_models", {})
        self.endpoint = self.config.get("endpoint", "http://localhost:11434")
        self.model = self.config.get("model", "llama3.1")

    def query(self, prompt: str) -> str:
        """Send a query to the local Ollama model."""
        if not self.config.get("enabled", False):
            return "Local model support is not enabled in the configuration."

        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.endpoint}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "Error: No response from model.")
        except httpx.RequestError as e:
            return f"Error connecting to Ollama: {e}"
        except Exception as e:
            return f"An unexpected error occurred: {e}"
