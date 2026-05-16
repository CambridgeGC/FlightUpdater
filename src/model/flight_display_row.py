from dataclasses import dataclass
from datetime import date, time
from typing import Optional


@dataclass
class FlightDisplayRow:
    source: str
    uuid: str = ""
    sync_key: int | None = None
    sequence_number: int | None = None
    flight_date: Optional[date] = None
    launch_method: str = ""
    registration: str = ""
    callsign: str = ""
    takeoff_time: Optional[time] = None
    landing_time: Optional[time] = None
    pic_account: str = ""
    pic_name: str = ""
    p2_account: str = ""
    p2_name: str = ""
    payer_account: str = ""
    other_name: str = ""
    tow_callsign: str = ""
    tow_pilot_account: str = ""
    tow_pilot_name: str = ""
    height_ft: Optional[int] = None
    category: str = ""
    notes: str = ""
    airfield_takeoff: str = ""
    airfield_landing: str = ""
    aircraft_category: str = ""
    is_club_aircraft: bool = False

    def takeoff_str(self) -> str:
        return self.takeoff_time.strftime("%H:%M") if self.takeoff_time else ""

    def landing_str(self) -> str:
        return self.landing_time.strftime("%H:%M") if self.landing_time else ""

    def date_str(self) -> str:
        return self.flight_date.isoformat() if self.flight_date else ""