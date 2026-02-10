from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class NERResult(BaseModel):
    names: List[str] = Field(default_factory=list, description="List of extracted names found in the text")
    salutation: str = Field(..., description="Generated salutation, e.g., 'Dear Mr. Smith,'")
    generated_summary: Optional[str] = Field(None, description="Optional summary or intro text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata about the extraction method and confidence")

class BaseExtractor(ABC):
    """
    Abstract base class for NER and Text Generation strategies.
    All strategies (SpaCy, Local LLM, Cloud LLM) must inherit from this.
    """

    @abstractmethod
    async def extract(self, text: str) -> NERResult:
        """
        Extract entities and generate salutation from the given text.
        
        Args:
            text (str): The input text context (e.g., first few pages of a PDF).
            
        Returns:
            NERResult: Structured output complying with the defined schema.
        """
        pass
