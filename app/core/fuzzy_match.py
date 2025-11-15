from rapidfuzz import fuzz

def fuzzy_name_match(name1: str, name2: str) -> int:
    """
    Returns a similarity score between 0 and 100.
    """
    if not name1 or not name2:
        return 0

    return fuzz.token_sort_ratio(name1.lower(), name2.lower())
