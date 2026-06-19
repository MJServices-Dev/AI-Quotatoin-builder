"""
Entity Extractor Module
Handles NLP-based entity extraction from documents
"""

import re
from typing import Dict, List, Any, Optional
import spacy
from spacy.matcher import Matcher


class EntityExtractor:
    """Extract structured entities from text using NLP"""
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize entity extractor
        
        Args:
            model_name: spaCy model name
        """
        self.model_name = model_name
        self.nlp = None
        self.matcher = None
        self._initialize_nlp()
    
    def _initialize_nlp(self):
        """Initialize spaCy NLP model"""
        try:
            self.nlp = spacy.load(self.model_name)
            self.matcher = Matcher(self.nlp.vocab)
            self._add_custom_patterns()
        except OSError:
            print(f"Warning: spaCy model '{self.model_name}' not found.")
            print(f"Please run: python -m spacy download {self.model_name}")
            self.nlp = None
    
    def _add_custom_patterns(self):
        """Add custom patterns for domain-specific entities"""
        if not self.matcher:
            return
        
        # Pattern for quantities (e.g., "5 servers", "10 units")
        quantity_pattern = [
            {"LIKE_NUM": True},
            {"POS": "NOUN", "OP": "+"}
        ]
        self.matcher.add("QUANTITY", [quantity_pattern])
        
        # Pattern for requirements (e.g., "must have", "should include")
        requirement_pattern = [
            {"LOWER": {"IN": ["must", "should", "need", "require"]}},
            {"POS": "VERB", "OP": "?"},
            {"OP": "*"}
        ]
        self.matcher.add("REQUIREMENT", [requirement_pattern])
    
    def extract_entities(self, text: str) -> Dict[str, List[Dict]]:
        """
        Extract all entities from text
        
        Args:
            text: Input text
            
        Returns:
            Dictionary of entity types and their values
        """
        if not self.nlp:
            return {
                'error': 'NLP model not initialized',
                'entities': []
            }
        
        doc = self.nlp(text)
        
        entities = {
            'persons': [],
            'organizations': [],
            'dates': [],
            'money': [],
            'quantities': [],
            'locations': [],
            'other': []
        }
        
        # Extract named entities
        for ent in doc.ents:
            entity_info = {
                'text': ent.text,
                'label': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char
            }
            
            if ent.label_ == 'PERSON':
                entities['persons'].append(entity_info)
            elif ent.label_ == 'ORG':
                entities['organizations'].append(entity_info)
            elif ent.label_ == 'DATE':
                entities['dates'].append(entity_info)
            elif ent.label_ == 'MONEY':
                entities['money'].append(entity_info)
            elif ent.label_ in ['QUANTITY', 'CARDINAL']:
                entities['quantities'].append(entity_info)
            elif ent.label_ in ['GPE', 'LOC']:
                entities['locations'].append(entity_info)
            else:
                entities['other'].append(entity_info)
        
        return entities
    
    def extract_client_info(self, text: str) -> Dict[str, Any]:
        """
        Extract client information from text
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with client details
        """
        if not self.nlp:
            return {'error': 'NLP model not initialized'}
        
        doc = self.nlp(text)
        
        client_info = {
            'name': None,
            'organization': None,
            'email': None,
            'phone': None,
            'address': None
        }
        
        # Extract organization (usually first ORG entity)
        for ent in doc.ents:
            if ent.label_ == 'ORG' and not client_info['organization']:
                client_info['organization'] = ent.text
            elif ent.label_ == 'PERSON' and not client_info['name']:
                client_info['name'] = ent.text
            elif ent.label_ in ['GPE', 'LOC'] and not client_info['address']:
                client_info['address'] = ent.text
        
        # Extract email using regex
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            client_info['email'] = emails[0]
        
        # Extract phone using regex
        phone_pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, text)
        if phones:
            client_info['phone'] = phones[0]
        
        return client_info
    
    def extract_requirements(self, text: str) -> List[str]:
        """
        Extract requirement statements from text
        
        Args:
            text: Input text
            
        Returns:
            List of requirement strings
        """
        if not self.nlp:
            return []
        
        requirements = []
        
        # Split into sentences
        doc = self.nlp(text)
        
        # Keywords that indicate requirements
        requirement_keywords = [
            'must', 'should', 'need', 'require', 'necessary',
            'essential', 'mandatory', 'shall', 'will need',
            'looking for', 'want', 'expect'
        ]
        
        for sent in doc.sents:
            sent_text = sent.text.strip()
            sent_lower = sent_text.lower()
            
            # Check if sentence contains requirement keywords
            if any(keyword in sent_lower for keyword in requirement_keywords):
                requirements.append(sent_text)
            
            # Also check for numbered lists
            if re.match(r'^\d+[\.)]\s+', sent_text):
                requirements.append(sent_text)
        
        return requirements
    
    def extract_financial_info(self, text: str) -> Dict[str, Any]:
        """
        Extract financial information (budget, costs, etc.)
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with financial details
        """
        if not self.nlp:
            return {'error': 'NLP model not initialized'}
        
        doc = self.nlp(text)
        
        financial_info = {
            'budget': None,
            'amounts': [],
            'currency': None
        }
        
        # Extract money entities
        for ent in doc.ents:
            if ent.label_ == 'MONEY':
                financial_info['amounts'].append(ent.text)
                
                # Try to determine currency
                if '$' in ent.text:
                    financial_info['currency'] = 'USD'
                elif '€' in ent.text:
                    financial_info['currency'] = 'EUR'
                elif '£' in ent.text:
                    financial_info['currency'] = 'GBP'
                elif '₹' in ent.text:
                    financial_info['currency'] = 'INR'
        
        # Look for budget mentions
        budget_pattern = r'budget[:\s]+([^\n\.]+)'
        budget_matches = re.findall(budget_pattern, text, re.IGNORECASE)
        if budget_matches:
            financial_info['budget'] = budget_matches[0].strip()
        
        return financial_info
    
    def extract_quantities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract quantities and items
        
        Args:
            text: Input text
            
        Returns:
            List of quantity dictionaries
        """
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        quantities = []
        
        # Pattern: number + noun (e.g., "5 servers", "10 licenses")
        quantity_pattern = r'(\d+)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)'
        matches = re.findall(quantity_pattern, text)
        
        for number, item in matches:
            quantities.append({
                'quantity': int(number),
                'item': item.strip(),
                'unit': 'units'
            })
        
        return quantities
    
    def extract_structured_data(self, text: str) -> Dict[str, Any]:
        """
        Extract all structured data from text
        
        Args:
            text: Input text
            
        Returns:
            Comprehensive dictionary of extracted data
        """
        return {
            'client_info': self.extract_client_info(text),
            'requirements': self.extract_requirements(text),
            'financial_info': self.extract_financial_info(text),
            'quantities': self.extract_quantities(text),
            'entities': self.extract_entities(text)
        }
