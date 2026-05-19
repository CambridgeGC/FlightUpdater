from datetime import date
from copy import deepcopy
from glidinglib.clients.ktrax_flight_client import KtraxFlightClient
from glidinglib.services.glidingapp_flight_service import GlidingAppFlightService
from glidinglib.services.ktrax_flight_service import KtraxFlightService
from glidinglib.services.aerolog_flight_service import AerologFlightService
from glidinglib.services.glidingapp_account_service import GlidingAppAccountService
from glidinglib.services.glidingapp_aircraft_service import GlidingAppAircraftService
from glidinglib.mappers.ktrax_combination_flight_mapper import (
    map_ktrax_flights_to_combination_flights,
)
from glidinglib.mappers.aerolog_combination_flight_mapper import (
    map_aerolog_flights_to_combination_flights,
)
from glidinglib.mappers.glidingapp_combination_flight_mapper import (
    map_glidingapp_flights_to_combination_flights,
)
from glidinglib.models.combination_flight_model import CombinationFlight
from model.flight_display_row import FlightDisplayRow

PAYER_BY_CATEGORY = {
    "trial flight": "1002",
    "city uni": "1225",
    "scouts": "1099",
}

class FlightUpdaterService:
    def __init__(self, config: dict):
        self.config = config

        self.ga_service = GlidingAppFlightService(config)
        self.aerolog_service = AerologFlightService(config)
        self.account_service = GlidingAppAccountService(config)
        self.aircraft_service = GlidingAppAircraftService(config)

        ktrax_config = config.get("ktrax", {})
        self.ktrax_service = KtraxFlightService(
            KtraxFlightClient(
                ktrax_id=ktrax_config.get("id", "GRANSDEN LODGE"),
                tz=ktrax_config.get("tz"),
            )
        )
        self.ga_base_combination_flights: list[CombinationFlight] = []
        self.ga_combination_flights: list[CombinationFlight] = []

    def get_glidingapp_flights(
        self,
        flight_date: date,
        modify_payer: bool = True,
    ) -> list[FlightDisplayRow]:
        ga_flights = self.ga_service.get_flights_for_date(flight_date)
        base_combination_flights = map_glidingapp_flights_to_combination_flights(ga_flights)

        self.ga_base_combination_flights = base_combination_flights

        combination_flights = deepcopy(base_combination_flights)
        aircraft_by_registration = self.aircraft_service.get_aircraft_by_registration()
        aircraft_by_callsign = self.aircraft_service.get_aircraft_by_callsign()

        if modify_payer:
            self._modify_payers_by_category(combination_flights)

        self.ga_combination_flights = combination_flights

        return [
            self._combination_to_display_row(
                f,
                aircraft_by_registration=aircraft_by_registration,
                aircraft_by_callsign=aircraft_by_callsign,
            )
            for f in combination_flights
        ]

    def get_ktrax_flights(self, flight_date: date) -> list[FlightDisplayRow]:
        kt_flights = self.ktrax_service.get_flights_for_date(flight_date)
        combination_flights = map_ktrax_flights_to_combination_flights(kt_flights)
        return [self._combination_to_display_row(f) for f in combination_flights]

    def get_aerolog_flights(self, flight_date: date) -> list[FlightDisplayRow]:
        al_flights = self.aerolog_service.get_flights_for_date(flight_date)
        combination_flights = map_aerolog_flights_to_combination_flights(al_flights)
        return [self._combination_to_display_row(f) for f in combination_flights]

    def _combination_to_display_row(
        self,
        flight: CombinationFlight,
        aircraft_by_registration: dict | None = None,
        aircraft_by_callsign: dict | None = None,
    ) -> FlightDisplayRow:
        aircraft = None

        if aircraft_by_registration or aircraft_by_callsign:
            reg_key = (flight.registration or "").strip().upper()
            cs_key = (flight.callsign or "").strip().upper()

            aircraft = (
                (aircraft_by_registration or {}).get(reg_key)
                or (aircraft_by_callsign or {}).get(cs_key)
            )

        aircraft_category = ""
        is_club_aircraft = False

        if aircraft is not None:
            aircraft_category = aircraft.category or ""
            is_club_aircraft = aircraft_category.strip().lower() == "club"

        return FlightDisplayRow(
            source=flight.source,
            sync_key=flight.sync_key,
            uuid=flight.uuid,
            sequence_number=flight.sequence_number,
            flight_date=flight.flight_date,
            launch_method=flight.launch_method,

            callsign=flight.callsign,
            registration=flight.registration,
            takeoff_time=flight.takeoff_time,
            landing_time=flight.landing_time,

            pic_account=flight.pic_membership_number,
            pic_name=flight.pic_name,
            p2_account=flight.p2_membership_number,
            p2_name=flight.p2_name,
            payer_account=flight.paying_pilot_membership_number,

            tow_callsign=flight.tow_callsign or flight.tow_registration,
            tow_pilot_account=flight.tow_pilot_account,
            tow_pilot_name=flight.tow_pilot_name,
            height_ft=(
                int(flight.tow_release_height_ft)
                if flight.tow_release_height_ft is not None
                else None
            ),

            category=flight.category,
            aircraft_category=aircraft_category,
            is_club_aircraft=is_club_aircraft,

            airfield_takeoff=flight.airfield_takeoff,
            airfield_landing=flight.airfield_landing,
            notes=flight.remarks,
        )    
    def test_for_errors(
        self,
        flights: list[FlightDisplayRow],
    ) -> dict[str, list[FlightDisplayRow]]:
        accounts = self.account_service.get_active_accounts()
        aircraft_by_callsign = self.aircraft_service.get_aircraft_by_callsign()
        aircraft_by_registration = self.aircraft_service.get_aircraft_by_registration()

        instructor_accounts = {
            a.membership_number
            for a in accounts
            if any("instructor" in g.lower() for g in a.groups)
        }

        errors: dict[str, list[FlightDisplayRow]] = {
            "Club aircraft flown by an instructor/BI with no P2": [],
            "P2 as non-members with category not set": [],
            "TMG flights with non-member P2 and invalid category": [],
            "Aerotows with no tug pilot listed": [],
        }

        for f in flights:
            aircraft = (
                aircraft_by_registration.get((f.registration or "").upper())
                or aircraft_by_callsign.get((f.callsign or "").upper())
            )

            is_club_two_seater = (
                aircraft is not None
                and aircraft.category.lower() == "club"
                and aircraft.pilots == 2
            )

            pic_is_instructor = f.pic_account in instructor_accounts
            has_no_p2 = not (f.p2_name or "").strip()

            if is_club_two_seater and pic_is_instructor and has_no_p2:
                errors["Club aircraft flown by an instructor/BI with no P2"].append(f)

            p2_not_member = bool((f.p2_name or "").strip()) and not f.p2_account
            category = (f.category or "").strip().lower()
            launch = (f.launch_method or "").strip().lower()

            is_aerotow = launch == "aerotow"
            has_no_tug_pilot = not (f.tow_pilot_account or "").strip() and not (
                f.tow_pilot_name or ""
            ).strip()

            if is_aerotow and has_no_tug_pilot:
                errors["Aerotows with no tug pilot listed"].append(f)

            if p2_not_member:
                if launch == "tmg":
                    if category in {"trial flight", "city uni", "scouts"}:
                        continue
                    if category not in {"club", "training"}:
                        errors["TMG flights with non-member P2 and invalid category"].append(f)
                elif not category and is_club_two_seater:
                    errors["P2 as non-members with category not set"].append(f)

        return {
            heading: rows
            for heading, rows in errors.items()
            if rows
        }

    def _modify_payers_by_category(
        self,
        flights: list[CombinationFlight],
    ) -> None:
        for flight in flights:
            category_key = (flight.category or "").strip().lower()

            payer = PAYER_BY_CATEGORY.get(category_key)
            if payer:
                flight.paying_pilot_membership_number = payer

    def send_glidingapp_flights_to_aerolog(
        self,
        flights: list[FlightDisplayRow],
        modify_payer: bool = True,
        dry_run: bool = False,
    ) -> dict:
        if not self.ga_base_combination_flights:
            return {
                "status": "no_records",
                "sent": False,
                "record_count": 0,
                "payload": [],
            }

        sync_keys_to_send = {
            f.sync_key
            for f in flights
            if f.source == "GA" and f.sync_key is not None
        }

        combination_flights_to_send = [
            deepcopy(f)
            for f in self.ga_base_combination_flights
            if f.sync_key in sync_keys_to_send
        ]

        if not combination_flights_to_send:
            return {
                "status": "no_records",
                "sent": False,
                "record_count": 0,
                "payload": [],
            }

        if modify_payer:
            self._modify_payers_by_category(combination_flights_to_send)

        return self.aerolog_service.send_combination_flight_log_to_aerolog(
            combination_flights_to_send,
            data_source="config",
            dry_run=dry_run,
        )