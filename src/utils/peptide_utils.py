import re
from typing import Set, List, Optional, Dict

def normalize_to_slug(name: str) -> str:
    """Standard slugification: lowercase and replace non-alphanumeric with dashes."""
    if not name:
        return ""
    # Lowercase
    slug = name.lower()
    # Replace non-alphanumeric with dashes
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    # Strip leading/trailing dashes
    return slug.strip('-')

def get_peptide_candidates(raw_name: str) -> Set[str]:
    """
    Generates a set of possible slugs for a given peptide name.
    Handles parenthetical aliases and strips common filler words.
    """
    if not raw_name:
        return set()

    candidates = set()
    
    # 1. Original slug
    candidates.add(normalize_to_slug(raw_name))
    
    # 2. Extract parenthetical aliases
    # e.g. "Omberacetam (Noopept)" -> candidates "omberacetam", "noopept"
    parens_matches = re.findall(r'\((.*?)\)', raw_name)
    for match in parens_matches:
        if match.strip():
            candidates.add(normalize_to_slug(match))
            
    # 3. Name without parentheses
    no_parens = re.sub(r'\(.*?\)', '', raw_name).strip()
    if no_parens:
        candidates.add(normalize_to_slug(no_parens))
        
    # 4. Strip common filler/modifiers that don't change the peptide identity
    # "with DAC", "without DAC", "Acetate", "HCL"
    # We EXCLUDE "Fragment", "Beta-4", etc. here because they signify different peptides
    fillers = [
        r'\s+with\s+dac', 
        r'\s+without\s+dac', 
        r'-?dac', 
        r'\s+acetate', 
        r'\s+hcl',
        r'\s+salts?',
        r'\s+solution',
        r'\s+spray'
    ]
    
    base_name = raw_name.lower()
    for filler in fillers:
        base_name = re.sub(filler, '', base_name).strip()
    
    if base_name:
        candidates.add(normalize_to_slug(base_name))
        
    return candidates

def find_best_match(raw_name: str, db_identifiers: Set[str], db_essences: Dict[str, str]) -> Optional[str]:
    """
    Finds the best matching identifier in the DB for a given raw name.
    1. Try candidates against exact DB identifiers.
    2. Try candidates against DB essences.
    """
    candidates = get_peptide_candidates(raw_name)
    for cand in candidates:
        if cand in db_identifiers:
            return cand
        if cand in db_essences:
            return db_essences[cand]
    return None

def extract_essence(slug_or_name: str) -> str:
    """
    Extracts the 'essence' of a peptide slug by removing generic versioning 
    but keeping identifying markers.
    """
    if not slug_or_name:
        return ""
        
    slug = normalize_to_slug(slug_or_name)
    
    # Remove generic dosage-like suffixes (e.g., -5mg, -10)
    # but be careful not to remove important numbers in names like CJC-1295
    # We only remove numeric suffixes if they are separated by a dash and common
    slug = re.sub(r'-(10|5|2|50|100)$', '', slug)
    
    # Remove common fillers (same as above but for slugs)
    fillers = [r'-with-dac', r'-without-dac', r'-dac', r'-acetate', r'-hcl', r'-salts?']
    for f in fillers:
        slug = re.sub(f, '', slug)
        
    return slug
