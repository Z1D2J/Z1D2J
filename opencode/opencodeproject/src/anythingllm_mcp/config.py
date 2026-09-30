"""Configuration management for AnythingLLM MCP Server."""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass
class AnythingLLMConfig:
    """Configuration for AnythingLLM API connection."""
    
    base_url: str = "http://localhost:3001"
    api_key: str = ""
    timeout: int = 30
    debug: bool = False
    
    @classmethod
    def from_env(cls) -> "AnythingLLMConfig":
        """Load configuration from environment variables."""
        load_dotenv()
        
        return cls(
            base_url=os.getenv("ANYTHINGLLM_BASE_URL", "http://localhost:3001"),
            api_key=os.getenv("ANYTHINGLLM_API_KEY", ""),
            timeout=int(os.getenv("ANYTHINGLLM_TIMEOUT", "30")),
            debug=os.getenv("ANYTHINGLLM_DEBUG", "false").lower() == "true",
        )
    
    def validate(self) -> bool:
        """Validate configuration."""
        if not self.api_key:
            raise ValueError("ANYTHINGLLM_API_KEY is required")
        if not self.base_url:
            raise ValueError("ANYTHINGLLM_BASE_URL is required")
        return True


# Global configuration instance
_config: Optional[AnythingLLMConfig] = None


def get_config() -> AnythingLLMConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = AnythingLLMConfig.from_env()
    return _config


def set_config(config: AnythingLLMConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config