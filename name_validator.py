"""
Name validation module for child names.
Validates that child names are appropriate, real names, and not profane or nonsense.
"""

import re
import logging
from typing import Tuple, Optional

# Try to import better-profanity
try:
    from better_profanity import profanity
    PROFANITY_AVAILABLE = True
except ImportError:
    PROFANITY_AVAILABLE = False
    logging.warning("[name_validator] better-profanity not installed. Profanity filtering disabled.")


# Common profanity words (fallback if better-profanity doesn't catch them)
PROFANITY_WORDS = {
    "shit", "damn", "hell", "ass", "bitch", "bastard", "crap", "piss", "fuck", "fucking",
    "dick", "cock", "pussy", "whore", "slut", "cunt", "fag", "nigger", "retard", "gay",
    # Variations
    "shitt", "damnn", "fuckk", "asss", "biatch", "bastardd",
}

# Common nonsense words that should be rejected
NONSENSE_WORDS = {
    # Food items
    "pizza", "burger", "hotdog", "taco", "sushi", "pasta", "cookie", "cake", "pie",
    # Animals (sounds/names)
    "moo", "woof", "meow", "quack", "oink", "bark", "roar", "chirp",
    # Objects
    "keyboard", "mouse", "computer", "phone", "table", "chair", "lamp", "book",
    "car", "truck", "bike", "plane", "train", "boat",
    # Random words
    "test", "example", "sample", "demo", "hello", "world", "foo", "bar", "baz",
    # Colors
    "red", "blue", "green", "yellow", "orange", "purple", "pink", "black", "white",
    # Numbers as words
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    # Common words
    "the", "and", "or", "but", "not", "yes", "no", "ok", "okay",
    # Placeholders
    "child", "kid", "baby", "name", "testname", "dummy", "placeholder",
}


# Common real first names (US Census popular names + common international names)
# This is a curated list of legitimate first names
COMMON_NAMES = {
    # Popular boy names
    "james", "robert", "john", "michael", "william", "david", "richard", "joseph",
    "thomas", "charles", "christopher", "daniel", "matthew", "anthony", "mark",
    "donald", "steven", "paul", "andrew", "joshua", "kenneth", "kevin", "brian",
    "george", "timothy", "ronald", "jason", "edward", "jeffrey", "ryan", "jacob",
    "gary", "nicholas", "eric", "jonathan", "stephen", "larry", "justin", "scott",
    "brandon", "benjamin", "samuel", "frank", "gregory", "raymond", "alexander",
    "patrick", "jack", "dennis", "jerry", "tyler", "aaron", "jose", "henry",
    "adam", "douglas", "nathan", "zachary", "kyle", "noah", "ethan", "jeremy",
    "walter", "christian", "dylan", "cameron", "logan", "mason", "lucas", "jackson",
    "aiden", "oliver", "owen", "wyatt", "carter", "luke", "grayson", "levi",
    
    # Popular girl names
    "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara", "susan",
    "jessica", "sarah", "karen", "nancy", "lisa", "betty", "margaret", "sandra",
    "ashley", "kimberly", "emily", "donna", "michelle", "dorothy", "carol",
    "amanda", "melissa", "deborah", "stephanie", "rebecca", "sharon", "laura",
    "cynthia", "kathleen", "amy", "angela", "shirley", "anna", "brenda", "pamela",
    "emma", "nicole", "virginia", "maria", "helen", "samantha", "ruth", "katherine",
    "christine", "olivia", "sophia", "isabella", "ava", "mia", "charlotte", "amelia",
    "harper", "evelyn", "abigail", "emily", "ella", "elizabeth", "camila", "luna",
    "sofi", "avery", "scarlett", "victoria", "madison", "eleanor", "grace", "chloe",
    "penelope", "layla", "riley", "zoey", "nora", "lily", "aubrey", "hannah",
    "lillian", "addison", "ella", "natalie", "leah", "hazel", "violet", "aurora",
    "savannah", "audrey", "brooklyn", "bella", "claire", "skylar", "lucy", "paisley",
    
    # Common international names
    "mohammed", "ali", "ahmed", "hassan", "omar", "yusuf", "ibrahim", "muhammad",
    "fatima", "aisha", "zainab", "mariam", "khadija", "amina", "sara", "noor",
    "wei", "ming", "li", "zhang", "wang", "liu", "chen", "yang", "huang", "zhao",
    "sato", "suzuki", "tanaka", "watanabe", "yamamoto", "nakamura", "kobayashi",
    "yuki", "haruka", "sakura", "akari", "hinata", "rio", "ren", "yuto", "sota",
    "priya", "arjun", "dev", "raj", "kiran", "ananya", "diya", "isha", "neha",
    "carlos", "juan", "jose", "luis", "miguel", "antonio", "francisco", "diego",
    "maria", "carmen", "ana", "laura", "sofia", "isabella", "valentina", "camila",
    "jean", "pierre", "michel", "philippe", "antoine", "thomas", "nicolas", "lucas",
    "marie", "sophie", "julie", "camille", "lea", "chloe", "emilie", "laura",
    "hans", "peter", "thomas", "michael", "andreas", "stefan", "martin", "christian",
    "anna", "maria", "sarah", "julia", "lisa", "katharina", "sandra", "nicole",
}


def validate_child_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a child's name.
    
    Args:
        name: The name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if name is valid, False otherwise
        - error_message: Error message if invalid, None if valid
    """
    if not name:
        return False, "Please enter a child's name"
    
    # Strip whitespace
    name = name.strip()
    
    # Check length (2-20 characters)
    if len(name) < 2:
        return False, "Name must be at least 2 characters long"
    if len(name) > 20:
        return False, "Name must be no more than 20 characters long"
    
    # Check if only letters (allow spaces, hyphens, apostrophes for compound names)
    # But for this use case, we want single first names only, so just letters
    if not re.match(r'^[a-zA-Z]+$', name):
        return False, "Name must contain only letters (no numbers, spaces, or special characters)"
    
    # Convert to lowercase for checks
    name_lower = name.lower()
    
    # IMPORTANT: Check if it's a common real name FIRST
    # If it's in our curated list of legitimate names, trust it and skip other checks
    # This prevents false positives from profanity filters on legitimate cultural names
    if name_lower in COMMON_NAMES:
        return True, None
    
    # Check against nonsense words
    if name_lower in NONSENSE_WORDS:
        return False, "Please enter a real child's name"
    
    # Additional check: reject if it's clearly not a name (e.g., common words)
    # This catches things that might not be in our nonsense list
    common_words = {"hello", "world", "test", "user", "admin", "password", "login", "email", "website", "internet"}
    if name_lower in common_words:
        return False, "Please enter a real child's name"
    
    # Check for profanity - use better-profanity if available, otherwise use fallback list
    # Only check profanity if name is NOT in COMMON_NAMES (already checked above)
    if PROFANITY_AVAILABLE:
        if profanity.contains_profanity(name_lower):
            return False, "Please enter a real child's name"
    else:
        # Fallback: check against explicit profanity list
        if name_lower in PROFANITY_WORDS:
            return False, "Please enter a real child's name"
    
    # Capitalize first letter for display
    name_capitalized = name.capitalize()
    
    # If not in common names, do additional checks:
    # - Must start with capital letter (after our capitalization)
    # - Must not be all caps or all lowercase (we'll capitalize it)
    # - Must look like a name (not a word pattern that's clearly not a name)
    
    # Additional validation: check if it looks like a real name
    # Names typically have certain patterns - this is a heuristic
    # Very short names (2-3 chars) are less likely to be real unless common
    if len(name) <= 3 and name_lower not in COMMON_NAMES:
        # Allow if it's a known short name, otherwise be more strict
        # Common short names: "al", "ed", "jo", "li", "no", "zo", "max", "leo", "sam", "tom"
        short_names = {"al", "ed", "jo", "li", "no", "zo", "max", "leo", "sam", "tom", "ian", "ray", "jay", "kai", "roy"}
        if name_lower not in short_names:
            # For very short names not in our list, be lenient but log
            logging.info(f"[name_validator] Short name '{name}' not in common list, allowing")
    
    # Final check: if it passed all filters, allow it
    # We're being permissive - if it's not profane and not obviously nonsense, allow it
    # The common names list is a positive signal, but not required
    
    return True, None


def sanitize_child_name(name: str) -> str:
    """
    Sanitize a child's name for safe use.
    Capitalizes first letter, removes extra whitespace.
    
    Args:
        name: The name to sanitize
        
    Returns:
        Sanitized name
    """
    if not name:
        return ""
    
    # Strip whitespace
    name = name.strip()
    
    # Capitalize first letter, lowercase the rest
    if name:
        name = name[0].upper() + name[1:].lower() if len(name) > 1 else name.upper()
    
    return name

