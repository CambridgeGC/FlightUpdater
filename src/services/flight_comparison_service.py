from datetime import date, datetime

from model.flight_display_row import FlightDisplayRow


MAX_TOLERANCE_SECONDS = 180


MAX_TOLERANCE_SECONDS = 120


def _times_match(
    t1,
    t2,
    tolerance_seconds: int = MAX_TOLERANCE_SECONDS,
) -> bool:
    if not t1 or not t2:
        return False

    today = date.today()
    delta = abs(
        (
            datetime.combine(today, t1)
            - datetime.combine(today, t2)
        ).total_seconds()
    )

    return delta <= tolerance_seconds


def _normalise(value: str | None) -> str:
    return (value or "").strip().upper()


def flights_match(
    f1: FlightDisplayRow,
    f2: FlightDisplayRow,
    tolerance_seconds: int = MAX_TOLERANCE_SECONDS,
) -> bool:
    if not _aircraft_matches(f1, f2):
        return False

    if not _tow_aircraft_matches(f1, f2):
        return False

    if not _times_match(f1.takeoff_time, f2.takeoff_time, tolerance_seconds):
        return False

    if not _times_match(f1.landing_time, f2.landing_time, tolerance_seconds):
        return False

    return True

def _aircraft_matches(
    f1: FlightDisplayRow,
    f2: FlightDisplayRow,
) -> bool:
    f1_keys = _aircraft_keys(f1)
    f2_keys = _aircraft_keys(f2)

    return bool(f1_keys & f2_keys)


def _aircraft_keys(flight: FlightDisplayRow) -> set[str]:
    keys = {
        _normalise_aircraft_id(flight.callsign),
        _normalise_aircraft_id(flight.registration),
    }

    return {key for key in keys if key}


def _tow_aircraft_matches(
    f1: FlightDisplayRow,
    f2: FlightDisplayRow,
) -> bool:
    f1_keys = _tow_aircraft_keys(f1)
    f2_keys = _tow_aircraft_keys(f2)

    # If neither flight has a tow aircraft recorded, that is a match.
    if not f1_keys and not f2_keys:
        return True

    # If only one side has a tow aircraft recorded, that is not a match.
    if not f1_keys or not f2_keys:
        return False

    return bool(f1_keys & f2_keys)


def _tow_aircraft_keys(flight: FlightDisplayRow) -> set[str]:
    keys = {
        _normalise_aircraft_id(getattr(flight, "tow_callsign", "")),
        _normalise_aircraft_id(getattr(flight, "tow_registration", "")),
    }

    return {key for key in keys if key}


def _normalise_aircraft_id(value: str | None) -> str:
    return (
        (value or "")
        .strip()
        .upper()
        .replace("-", "")
        .replace(" ", "")
    )

def find_unmatched(
    source: list[FlightDisplayRow],
    target: list[FlightDisplayRow],
) -> list[FlightDisplayRow]:
    unmatched: list[FlightDisplayRow] = []
    used: set[int] = set()

    for flight in source:
        found = False

        for index, candidate in enumerate(target):
            if index in used:
                continue

            if flights_match(flight, candidate):
                used.add(index)
                found = True
                break

        if not found:
            unmatched.append(flight)

    return unmatched