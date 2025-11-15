from rapidfuzz import fuzz

def fuzzy_name_match(name1: str, name2: str) -> int:
    """
    Returns a similarity score between 0 and 100.
    Uses token_sort_ratio which is good for name matching as it handles
    word order differences (e.g., "Ahmed Ali" vs "Ali Ahmed").
    
    Args:
        name1: First name to compare
        name2: Second name to compare
        
    Returns:
        Similarity score from 0-100
    """
    if not name1 or not name2:
        return 0

    # Normalize names: lowercase and strip whitespace
    name1_normalized = name1.lower().strip()
    name2_normalized = name2.lower().strip()
    
    # Use token_sort_ratio which handles word order differences
    # This is better for names like "Ahmed Ali" vs "Ali Ahmed"
    score = fuzz.token_sort_ratio(name1_normalized, name2_normalized)
    
    return score
