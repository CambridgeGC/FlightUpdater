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
    if _normalise(f1.callsign) != _normalise(f2.callsign):
        return False

    if _normalise(f1.tow_callsign) != _normalise(f2.tow_callsign):
        return False

    if not _times_match(f1.takeoff_time, f2.takeoff_time, tolerance_seconds):
        return False

    if not _times_match(f1.landing_time, f2.landing_time, tolerance_seconds):
        return False

    return True

    return delta <= tolerance_seconds


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