from datetime import datetime, timedelta

# Tug identifiers
TUGS = {'TUG SB', 'TUG GC'}
MAX_TOLERANCE = 180  # seconds

def is_tug(cn: str) -> bool:
    """Return True if the callsign belongs to a tug."""
    return cn in TUGS

def is_glider(cn: str) -> bool:
    """Return True if the callsign belongs to a glider."""
    return not is_tug(cn)

def parse_time(ts: str) -> datetime.time:
    """Parse a HH:MM string into a time object."""
    return datetime.strptime(ts, '%H:%M').time()

def flights_match(f1: dict, f2: dict, tow: bool = False, tolerance: int = MAX_TOLERANCE) -> bool:
    """
    Determine if two flight records match based on callsign/tow and takeoff times.

    :param f1: First flight dict with keys 'cn', 'tow_cn', 'takeoff'.
    :param f2: Second flight dict.
    :param tow: If True, compare f1.cn to f2.tow_cn; otherwise f1.cn to f2.cn.
    :param tolerance: Maximum allowed differ ence in seconds for takeoff times.
    :returns: True if callsign matches and takeoff difference <= tolerance.
    """
    # Compare callsign or tug identifier
    if tow:
        if f1['cn'] != f2.get('tow_cn'):
            return False
    else:
        if f1['cn'] != f2.get('cn'):
            return False

    # Compare takeoff times
    try:
        t1 = parse_time(f1['takeoff'])
        t2 = parse_time(f2['takeoff'])
        now = datetime.today()
        delta = abs((datetime.combine(now, t1) - datetime.combine(now, t2)).total_seconds())
        return delta <= tolerance
    except Exception:
        return False

def find_unmatched(list1: list, list2: list, tow: bool = False) -> list:
    """
    Return items in list1 that have no matching flight in list2.
    Ensures one-to-one matching using a set of used indices.
    """
    unmatched, used = [], set()
    for a in list1:
        found = False
        for i, b in enumerate(list2):
            if i in used:
                continue
            if flights_match(a, b, tow=tow) or flights_match(a, b, tow=not tow):
                used.add(i)
                found = True
                break
        if not found:
            unmatched.append(a)
    return unmatched

def compare_sources(aerolog: list, other: list) -> list:
    # """Flights in aerolog not found in other source."""
    return find_unmatched(aerolog, other)

def compare_reverse(primary: list, aerolog: list) -> list:
    # """Flights in primary not found in aerolog."""
    return find_unmatched(primary, aerolog)
