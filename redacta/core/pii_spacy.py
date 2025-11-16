import re
from typing import Optional

import spacy
from spacy.language import Language

from ..types import EntitySpan


class SpaCyPIIDetector:
    """PII detector using spaCy NER and regex patterns.
    
    Detects common PII entities like PERSON names, EMAIL addresses,
    and PHONE numbers.
    """
    
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )
    
    PHONE_PATTERN = re.compile(
        r'\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    )
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        """Initialize the PII detector.
        
        Args:
            model_name: Name of the spaCy model to use
        """
        self.model_name = model_name
        self._nlp: Optional[Language] = None
    
    @property
    def nlp(self) -> Language:
        """Lazy-load the spaCy model.
        
        Returns:
            Loaded spaCy Language model
        """
        if self._nlp is None:
            try:
                self._nlp = spacy.load(self.model_name)
            except OSError:
                raise RuntimeError(
                    f"spaCy model '{self.model_name}' not found. "
                    f"Install it with: python -m spacy download {self.model_name}"
                )
        return self._nlp
    
    def detect(self, text: str) -> list[EntitySpan]:
        """Detect PII entities in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of detected EntitySpan objects, sorted by start position
        """
        entities: list[EntitySpan] = []
        
        doc = self.nlp(text)
        
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                entities.append(EntitySpan(
                    label="PERSON",
                    start=ent.start_char,
                    end=ent.end_char,
                    text=ent.text
                ))
        
        for match in self.EMAIL_PATTERN.finditer(text):
            entities.append(EntitySpan(
                label="EMAIL",
                start=match.start(),
                end=match.end(),
                text=match.group()
            ))
        
        for match in self.PHONE_PATTERN.finditer(text):
            entities.append(EntitySpan(
                label="PHONE",
                start=match.start(),
                end=match.end(),
                text=match.group()
            ))
        
        entities = self._remove_overlapping(entities)
        entities.sort(key=lambda e: e.start)
        
        return entities
    
    def _remove_overlapping(self, entities: list[EntitySpan]) -> list[EntitySpan]:
        """Remove overlapping entities, keeping the longest one.
        
        Args:
            entities: List of entities that may overlap
            
        Returns:
            List of non-overlapping entities
        """
        if not entities:
            return []
        
        entities = sorted(entities, key=lambda e: (e.start, -(e.end - e.start)))
        
        result = []
        last_end = -1
        
        for entity in entities:
            if entity.start >= last_end:
                result.append(entity)
                last_end = entity.end
        
        return result
