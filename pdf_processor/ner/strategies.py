import os
import json
import logging
import spacy
from typing import List, Optional
import httpx
from openai import AsyncOpenAI

from .base import BaseExtractor, NERResult

logger = logging.getLogger(__name__)

class SpacyExtractor(BaseExtractor):
    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize SpaCy extractor.
        Ensure 'python -m spacy download en_core_web_sm' (or trf) is run.
        """
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            logger.warning(f"Model '{model_name}' not found. Downloading...")
            from spacy.cli import download
            download(model_name)
            self.nlp = spacy.load(model_name)

    async def extract(self, text: str) -> NERResult:
        # Standard SpaCy processing (CPU intensive, so in real app might want to run in executor if very large)
        # For snippets, it's fast enough.
        doc = self.nlp(text)
        
        persons = sorted(list(set([ent.text for ent in doc.ents if ent.label_ == "PERSON"])))
        
        # Simple rule-based salutation
        salutation = "To Whom It May Concern,"
        if persons:
            salutation = f"Dear {persons[0]},"
            
        return NERResult(
            names=persons,
            salutation=salutation,
            generated_summary="Summary generation not supported in pure SpaCy mode.",
            metadata={"method": "spacy", "model": self.nlp.meta["name"]}
        )

class LocalLLMExtractor(BaseExtractor):
    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "llama3.2"):
        """
        Connects to a local OAI-compatible endpoint (like Ollama).
        """
        self.client = AsyncOpenAI(base_url=base_url, api_key="ollama")
        self.model = model

    async def extract(self, text: str) -> NERResult:
        prompt = f"""
        Analyze the following text from an IPO document.
        1. Extract all names of relevant individuals (signatories, directors).
        2. Generate a formal salutation for the primary contact.
        3. Write a 1-sentence summary of the text.

        Return ONLY a JSON object with keys: "names" (list of strings), "salutation" (string), "generated_summary" (string).
        
        Text:
        {text[:2000]}
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            
            return NERResult(
                names=data.get("names", []),
                salutation=data.get("salutation", "To Whom It May Concern,"),
                generated_summary=data.get("generated_summary", ""),
                metadata={"method": "local_llm", "model": self.model}
            )
        except Exception as e:
            logger.error(f"Local LLM extraction failed: {e}")
            return NERResult(
                names=[], 
                salutation="To Whom It May Concern,", 
                metadata={"method": "local_llm", "error": str(e)}
            )

class CloudLLMExtractor(BaseExtractor):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo-preview"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set. Cloud extraction will fail.")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = model

    async def extract(self, text: str) -> NERResult:
        if not self.api_key:
             return NERResult(
                names=[], 
                salutation="Error: No API Key", 
                metadata={"method": "cloud_llm", "error": "Missing API Key"}
            )

        prompt = f"""
        Extract entities from this IPO text. Return JSON: {{ "names": [], "salutation": "", "generated_summary": "" }}
        
        Text:
        {text[:2000]}
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            
            return NERResult(
                names=data.get("names", []),
                salutation=data.get("salutation", ""),
                generated_summary=data.get("generated_summary", ""),
                metadata={"method": "cloud_llm", "model": self.model}
            )
        except Exception as e:
            logger.error(f"Cloud extraction failed: {e}")
            return NERResult(
                names=[], 
                salutation="Error", 
                metadata={"method": "cloud_llm", "error": str(e)}
            )
