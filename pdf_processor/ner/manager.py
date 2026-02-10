import asyncio
import json
import logging
from pathlib import Path
from typing import Literal

from .base import BaseExtractor, NERResult
from .strategies import SpacyExtractor, LocalLLMExtractor, CloudLLMExtractor

logger = logging.getLogger(__name__)

NERMethod = Literal["spacy", "local", "cloud"]

class NERManager:
    def __init__(self, method: NERMethod = "spacy"):
        self.method = method
        self.extractor = self._get_extractor(method)
        logger.info(f"Initialized NERManager with method: {method}")

    def _get_extractor(self, method: NERMethod) -> BaseExtractor:
        if method == "spacy":
            return SpacyExtractor()
        elif method == "local":
            return LocalLLMExtractor()
        elif method == "cloud":
            return CloudLLMExtractor()
        else:
            logger.warning(f"Unknown method {method}, defaulting to spacy.")
            return SpacyExtractor()

    async def process_and_save(self, text: str, output_dir: Path):
        """
        Run extraction and save result to JSON.
        This is meant to be fire-and-forget or awaited effectively.
        """
        logger.info(f"Starting NER extraction for {output_dir.name} using {self.method}...")
        
        try:
            result: NERResult = await self.extractor.extract(text)
            
            output_path = output_dir / "ner_results.json"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(result.model_dump_json(indent=2))
                
            logger.info(f"NER results saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to process NER for {output_dir.name}: {e}")
