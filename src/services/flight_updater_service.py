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

from pathlib import Path

from glidinglib.clients.aerolog_aircraft_client import AerologAircraftClient
from glidinglib.models.aerolog_aircraft_model import AerologAircraft
from glidinglib.models.glidingapp_aircraft_model import GlidingAppAircraft
from typing import Any
from glidinglib.clients.ogn_ddb_client import OgnDdbClient

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

        self.aerolog_aircraft_client = AerologAircraftClient(app_name="FlightUpdater")
        self.ga_aircraft: list[GlidingAppAircraft] = []
        self.al_aircraft: list[AerologAircraft] = []
        self.ogn_ddb_client = OgnDdbClient(app_name="FlightUpdater")
        self.ogn_records: list[dict[str, Any]] = []

        ktrax_config = config.get("ktrax", {})
        self.ktrax_service = KtraxFlightService(
            KtraxFlightClient(
                ktrax_id=ktrax_config.get("id", "GRANSDEN LODGE"),
                tz=ktrax_config.get("tz"),
            )
        )
        self.ga_base_combination_flights: list[CombinationFlight] = []
        self.ga_combination_flights: list[CombinationFlight] = []

    def initialise_ogn_ddb(
        self,
        force_refresh: bool = False,
    ) -> dict:
        records = self.ogn_ddb_client.load(force_refresh=force_refresh)
        self.ogn_records = records

        return {
            "record_count": len(records),
            "cache_path": str(self.ogn_ddb_client.cache_path),
        }


    def _find_ogn_record_for_ga(
        self,
        ga: GlidingAppAircraft,
    ) -> dict[str, Any] | None:
        flarm_id = self._normalise_flarm_id(ga.flarm_id)

        if not flarm_id:
            return None

        if not self.ogn_records:
            self.initialise_ogn_ddb()

        record = self.ogn_ddb_client.find_by_device_id(flarm_id)

        if record is not None:
            return record

        # Fallback in case OGN or GA has prefixes / punctuation differences.
        for candidate in self.ogn_records:
            candidate_id = self._normalise_flarm_id(candidate.get("device_id"))

            if candidate_id == flarm_id:
                return candidate

        return None


    @staticmethod
    def _normalise_flarm_id(value: object) -> str:
        return (
            str(value or "")
            .strip()
            .upper()
            .replace("ICAO:", "")
            .replace("FLARM:", "")
            .replace("OGN:", "")
            .replace(":", "")
            .replace("-", "")
            .replace(" ", "")
        )


    @staticmethod
    def _ogn_field(
        record: dict[str, Any] | None,
        field_name: str,
    ) -> str:
        if not record:
            return ""

        return str(record.get(field_name, "") or "").strip()

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
    
    def load_aerolog_aircraft_file(
        self,
        excel_path: str | Path,
    ) -> dict:
        records = self.aerolog_aircraft_client.update_cache_from_excel(excel_path)
        self.al_aircraft = records

        return {
            "record_count": len(records),
            "cache_path": str(self.aerolog_aircraft_client.cache_path),
            "excel_cache_path": str(self.aerolog_aircraft_client.excel_cache_path),
        }


    def load_aerolog_aircraft_cache(self) -> list[AerologAircraft]:
        self.al_aircraft = self.aerolog_aircraft_client.load()
        return self.al_aircraft


    def load_glidingapp_aircraft(self) -> list[GlidingAppAircraft]:
        aircraft_by_registration = self.aircraft_service.get_aircraft_by_registration()

        # Deduplicate defensively.
        by_key: dict[str, GlidingAppAircraft] = {}

        for aircraft in aircraft_by_registration.values():
            key = (
                str(aircraft.id)
                if aircraft.id is not None
                else self._normalise_aircraft_id(
                    aircraft.registration or aircraft.callsign
                )
            )
            by_key[key] = aircraft

        self.ga_aircraft = sorted(
            by_key.values(),
            key=lambda a: (
                self._normalise_aircraft_id(a.registration),
                self._normalise_aircraft_id(a.callsign),
            ),
        )

        return self.ga_aircraft


    def compare_aircraft(self) -> list[str]:
        ga_aircraft = self.load_glidingapp_aircraft()

        if not self.al_aircraft:
            aerolog_aircraft = self.load_aerolog_aircraft_cache()
        else:
            aerolog_aircraft = self.al_aircraft

        ga_index = self._index_glidingapp_aircraft(ga_aircraft)
        al_index = self._index_aerolog_aircraft(aerolog_aircraft)

        missing_in_aerolog: list[GlidingAppAircraft] = []
        missing_in_glidingapp: list[AerologAircraft] = []
        differences: list[tuple[GlidingAppAircraft, AerologAircraft, list[str]]] = []

        for ga in ga_aircraft:
            al = self._find_matching_aerolog_aircraft(ga, al_index)

            if al is None:
                missing_in_aerolog.append(ga)
                continue

            diffs = self._aircraft_differences(ga, al)
            if diffs:
                ogn = self._find_ogn_record_for_ga(ga)
                differences.append((ga, al, ogn, diffs))

        for al in aerolog_aircraft:
            if self._find_matching_glidingapp_aircraft(al, ga_index) is None:
                missing_in_glidingapp.append(al)

        return self._format_aircraft_comparison(
            ga_aircraft=ga_aircraft,
            aerolog_aircraft=aerolog_aircraft,
            missing_in_aerolog=missing_in_aerolog,
            missing_in_glidingapp=missing_in_glidingapp,
            differences=differences,
        )


    def _index_glidingapp_aircraft(
        self,
        aircraft: list[GlidingAppAircraft],
    ) -> dict[str, GlidingAppAircraft]:
        index: dict[str, GlidingAppAircraft] = {}

        for item in aircraft:
            for key in self._glidingapp_aircraft_keys(item):
                index.setdefault(key, item)

        return index


    def _index_aerolog_aircraft(
        self,
        aircraft: list[AerologAircraft],
    ) -> dict[str, AerologAircraft]:
        index: dict[str, AerologAircraft] = {}

        for item in aircraft:
            for key in self._aerolog_aircraft_keys(item):
                index.setdefault(key, item)

        return index


    def _find_matching_aerolog_aircraft(
        self,
        ga: GlidingAppAircraft,
        al_index: dict[str, AerologAircraft],
    ) -> AerologAircraft | None:
        for key in self._glidingapp_aircraft_keys(ga):
            match = al_index.get(key)
            if match is not None:
                return match

        return None


    def _find_matching_glidingapp_aircraft(
        self,
        al: AerologAircraft,
        ga_index: dict[str, GlidingAppAircraft],
    ) -> GlidingAppAircraft | None:
        for key in self._aerolog_aircraft_keys(al):
            match = ga_index.get(key)
            if match is not None:
                return match

        return None


    def _glidingapp_aircraft_keys(
        self,
        aircraft: GlidingAppAircraft,
    ) -> set[str]:
        keys = {
            self._normalise_aircraft_id(aircraft.registration),
            self._normalise_aircraft_id(aircraft.callsign),
        }

        return {key for key in keys if key}


    def _aerolog_aircraft_keys(
        self,
        aircraft: AerologAircraft,
    ) -> set[str]:
        keys = {
            self._normalise_aircraft_id(aircraft.registration),
            self._normalise_aircraft_id(aircraft.short_registration),
            self._normalise_aircraft_id(aircraft.competition_registration),
        }

        return {key for key in keys if key}
    
    @staticmethod
    def _values_differ(left: object, right: object) -> bool:
        left_text = FlightUpdaterService._normalise_aircraft_id(str(left or ""))
        right_text = FlightUpdaterService._normalise_aircraft_id(str(right or ""))

        if not left_text and not right_text:
            return False

        return left_text != right_text


    def _aircraft_differences(
        self,
        ga: GlidingAppAircraft,
        al: AerologAircraft,
    ) -> list[str]:
        reg_diff = self._values_differ(
            ga.registration,
            al.registration,
        )

        cn_diff = self._values_differ(
            ga.callsign,
            al.competition_registration,
        )

        if reg_diff and cn_diff:
            return ["Both"]

        if reg_diff:
            return ["Reg"]

        if cn_diff:
            return ["CN"]

        return []


    @staticmethod
    def _values_differ(left: object, right: object) -> bool:
        left_text = FlightUpdaterService._normalise_aircraft_id(left)
        right_text = FlightUpdaterService._normalise_aircraft_id(right)

        if not left_text and not right_text:
            return False

        return left_text != right_text


    def _format_aircraft_comparison(
        self,
        ga_aircraft: list[GlidingAppAircraft],
        aerolog_aircraft: list[AerologAircraft],
        missing_in_aerolog: list[GlidingAppAircraft],
        missing_in_glidingapp: list[AerologAircraft],
        differences: list[
            tuple[GlidingAppAircraft, AerologAircraft, dict[str, Any] | None, list[str]]
        ],
    ) -> list[str]:
        lines: list[str] = []

        lines.append("Aircraft comparison")
        lines.append("")
        lines.append(f"Gliding.App aircraft: {len(ga_aircraft)}")
        lines.append(f"Aerolog aircraft:    {len(aerolog_aircraft)}")
        lines.append(f"Missing in Aerolog:  {len(missing_in_aerolog)}")
        lines.append(f"Missing in GA:       {len(missing_in_glidingapp)}")
        lines.append(f"Differences:         {len(differences)}")
        lines.append("")

        if missing_in_aerolog:
            lines.append("In Gliding.App but not in Aerolog")
            lines.append(
                f"{'Callsign':10}"
                f"{'Registration':15}"
                f"{'Type':20}"
                f"{'Category':12}"
            )

            for a in missing_in_aerolog:
                lines.append(
                    f"{self._fixed_width(a.callsign, 10)}"
                    f"{self._fixed_width(a.registration, 15)}"
                    f"{self._fixed_width(a.aircraft_type, 20)}"
                    f"{self._fixed_width(a.category, 12)}"
                )

            lines.append("")

        if missing_in_glidingapp:
            lines.append("In Aerolog but not in Gliding.App")
            lines.append(
                f"{'Registration':15}"
                f"{'Short':10}"
                f"{'Competition':15}"
                f"{'Model':20}"
                f"{'Type':8}"
            )

            for a in missing_in_glidingapp:
                lines.append(
                    f"{self._fixed_width(a.registration, 15)}"
                    f"{self._fixed_width(a.short_registration, 10)}"
                    f"{self._fixed_width(a.competition_registration, 15)}"
                    f"{self._fixed_width(a.model, 20)}"
                    f"{self._fixed_width(a.aircraft_type, 8)}"
                )

            lines.append("")

        if differences:
            lines.append("Aircraft with differences")
            lines.append(
                f"{'AL Reg':15}"
                f"{'AL CS':10}"
                f"{'AL model':12}"
                f"{'GA Reg':15}"
                f"{'GA CS':12}"
                f"{'GA type':15}"
                f"{'GA Flarm ID':12}"
                f"{'OGN CN':10}"
                f"{'OGN type':18}"
                f"{'OGN Reg':15}"
                f"{'Differences':12}"
            )

            for ga, al, ogn, diffs in differences:
                difference_text = diffs[0] if diffs else ""

                lines.append(
                    f"{self._fixed_width(al.registration, 15)}"
                    f"{self._fixed_width(al.competition_registration, 10)}"
                    f"{self._fixed_width(al.model, 12)}"
                    f"{self._fixed_width(ga.registration, 15)}"
                    f"{self._fixed_width(ga.callsign, 12)}"
                    f"{self._fixed_width(ga.aircraft_type, 15)}"
                    f"{self._fixed_width(ga.flarm_id, 12)}"
                    f"{self._fixed_width(self._ogn_field(ogn, 'cn'), 10)}"
                    f"{self._fixed_width(self._ogn_field(ogn, 'aircraft_model'), 18)}"
                    f"{self._fixed_width(self._ogn_field(ogn, 'registration'), 15)}"
                    f"{self._fixed_width(difference_text, 12)}"
                )

            lines.append("")

        return lines
    
    @staticmethod
    def _fixed_width(value: object, width: int) -> str:
        text = str(value or "").strip()

        if len(text) > width:
            text = text[:width]

        return f"{text:<{width}}"
    
    @staticmethod
    def _normalise_aircraft_id(value: str | None) -> str:
        return (
            str(value or "")
            .strip()
            .upper()
            .replace("-", "")
            .replace(" ", "")
        )
    
    def list_glidingapp_aircraft_report(self) -> list[str]:
        aircraft = sorted(
            self.load_glidingapp_aircraft(),
            key=lambda a: (
                self._normalise_aircraft_id(a.registration),
                self._normalise_aircraft_id(a.callsign),
            ),
        )

        lines: list[str] = []
        lines.append("Gliding.App aircraft")
        lines.append("")
        lines.append(f"Count: {len(aircraft)}")
        lines.append("")
        lines.append(
            f"{'Registration':15}"
            f"{'Callsign':10}"
            f"{'Type':20}"
            f"{'Category':12}"
            f"{'Pilots':8}"
            f"{'Launch':12}"
            f"{'FLARM ID':12}"
        )

        for a in aircraft:
            lines.append(
                f"{self._fixed_width(a.registration, 15)}"
                f"{self._fixed_width(a.callsign, 10)}"
                f"{self._fixed_width(a.aircraft_type, 20)}"
                f"{self._fixed_width(a.category, 12)}"
                f"{self._fixed_width(a.pilots, 8)}"
                f"{self._fixed_width(a.launch_method, 12)}"
                f"{self._fixed_width(a.flarm_id, 12)}"
            )

        return lines


    def list_aerolog_aircraft_report(self) -> list[str]:
        if not self.al_aircraft:
            aircraft = self.load_aerolog_aircraft_cache()
        else:
            aircraft = self.al_aircraft

        aircraft = sorted(
            aircraft,
            key=lambda a: (
                self._normalise_aircraft_id(a.registration),
                self._normalise_aircraft_id(a.competition_registration),
            ),
        )

        lines: list[str] = []
        lines.append("Aerolog aircraft")
        lines.append("")
        lines.append(f"Count: {len(aircraft)}")
        lines.append("")
        lines.append(
            f"{'Registration':15}"
            f"{'Short':10}"
            f"{'Comp No':10}"
            f"{'Model':25}"
            f"{'Type':8}"
            f"{'Owner':20}"
            f"{'Ledger':12}"
            f"{'Tug':5}"
        )

        for a in aircraft:
            lines.append(
                f"{self._fixed_width(a.registration, 15)}"
                f"{self._fixed_width(a.short_registration, 10)}"
                f"{self._fixed_width(a.competition_registration, 10)}"
                f"{self._fixed_width(a.model, 25)}"
                f"{self._fixed_width(a.aircraft_type, 8)}"
                f"{self._fixed_width(a.owner, 20)}"
                f"{self._fixed_width(a.ledger_account, 12)}"
                f"{self._fixed_width('Y' if a.is_tug else '', 5)}"
            )

        return lines

    def aerolog_upload_aircraft_error_report(
        self,
        flights_to_upload: list[FlightDisplayRow],
    ) -> list[str]:
        """
        Check aircraft used by GA flights planned for Aerolog upload.

        Reports aircraft where the GA registration and/or callsign do not agree
        with the Aerolog aircraft cache.
        """
        if not flights_to_upload:
            return []

        try:
            aerolog_aircraft = (
                self.al_aircraft
                if self.al_aircraft
                else self.load_aerolog_aircraft_cache()
            )
        except FileNotFoundError:
            return [
                "Aircraft planned for Aerolog upload with Aerolog aircraft differences",
                "",
                "Aerolog aircraft cache not found. Load an Aerolog aircraft file first.",
            ]

        al_index = self._index_aerolog_aircraft(aerolog_aircraft)

        aircraft_by_registration = self.aircraft_service.get_aircraft_by_registration()
        aircraft_by_callsign = self.aircraft_service.get_aircraft_by_callsign()

        rows: list[tuple[GlidingAppAircraft, AerologAircraft | None, str]] = []
        seen: set[str] = set()

        for flight in flights_to_upload:
            ga_aircraft = self._find_glidingapp_aircraft_for_flight(
                flight,
                aircraft_by_registration,
                aircraft_by_callsign,
            )

            aircraft_key = (
                self._normalise_aircraft_id(ga_aircraft.registration)
                or self._normalise_aircraft_id(ga_aircraft.callsign)
            )

            if not aircraft_key or aircraft_key in seen:
                continue

            seen.add(aircraft_key)

            al_aircraft = self._find_matching_aerolog_aircraft(
                ga_aircraft,
                al_index,
            )

            if al_aircraft is None:
                rows.append((ga_aircraft, None, "Missing"))
                continue

            difference = self._aircraft_difference_code(
                ga_aircraft,
                al_aircraft,
            )

            if difference:
                rows.append((ga_aircraft, al_aircraft, difference))

        return self._format_aerolog_upload_aircraft_errors(rows)


    def _find_glidingapp_aircraft_for_flight(
        self,
        flight: FlightDisplayRow,
        aircraft_by_registration: dict,
        aircraft_by_callsign: dict,
    ) -> GlidingAppAircraft:
        reg_key = (flight.registration or "").strip().upper()
        cs_key = (flight.callsign or "").strip().upper()

        aircraft = (
            aircraft_by_registration.get(reg_key)
            or aircraft_by_callsign.get(cs_key)
        )

        if aircraft is not None:
            return aircraft

        # Fallback if the service dictionaries use a different normalisation.
        flight_reg = self._normalise_aircraft_id(flight.registration)
        flight_cs = self._normalise_aircraft_id(flight.callsign)

        for candidate in aircraft_by_registration.values():
            candidate_reg = self._normalise_aircraft_id(candidate.registration)
            candidate_cs = self._normalise_aircraft_id(candidate.callsign)

            if candidate_reg in {flight_reg, flight_cs}:
                return candidate

            if candidate_cs in {flight_reg, flight_cs}:
                return candidate

        # Last-resort stub, so the report can still show something useful.
        return GlidingAppAircraft(
            callsign=flight.callsign or "",
            registration=flight.registration or "",
            aircraft_type="",
            flarm_id="",
        )


    def _aircraft_difference_code(
        self,
        ga: GlidingAppAircraft,
        al: AerologAircraft,
    ) -> str:
        reg_diff = self._values_differ(
            ga.registration,
            al.registration,
        )

        cn_diff = self._values_differ(
            ga.callsign,
            al.competition_registration,
        )

        if reg_diff and cn_diff:
            return "Both"

        if reg_diff:
            return "Reg"

        if cn_diff:
            return "CN"

        return ""


    @staticmethod
    def _values_differ(left: object, right: object) -> bool:
        left_text = FlightUpdaterService._normalise_aircraft_id(left)
        right_text = FlightUpdaterService._normalise_aircraft_id(right)

        if not left_text and not right_text:
            return False

        return left_text != right_text


    def _format_aerolog_upload_aircraft_errors(
        self,
        rows: list[tuple[GlidingAppAircraft, AerologAircraft | None, str]],
    ) -> list[str]:
        if not rows:
            return []

        rows = sorted(
            rows,
            key=lambda row: (
                self._normalise_aircraft_id(row[0].registration),
                self._normalise_aircraft_id(row[0].callsign),
            ),
        )

        lines: list[str] = []

        lines.append("Aircraft planned for Aerolog upload with Aerolog aircraft differences")
        lines.append(
            f"{'AL Reg':15}"
            f"{'AL Cs':10}"
            f"{'AL model':20}"
            f"{'GA Reg':15}"
            f"{'GA Callsign':12}"
            f"{'GA type':15}"
            f"{'GA Flarm ID':12}"
            f"{'Differences':12}"
        )

        for ga, al, difference in rows:
            lines.append(
                f"{self._fixed_width(al.registration if al else '', 15)}"
                f"{self._fixed_width(al.competition_registration if al else '', 10)}"
                f"{self._fixed_width(al.model if al else '', 20)}"
                f"{self._fixed_width(ga.registration, 15)}"
                f"{self._fixed_width(ga.callsign, 12)}"
                f"{self._fixed_width(ga.aircraft_type, 15)}"
                f"{self._fixed_width(ga.flarm_id, 12)}"
                f"{self._fixed_width(difference, 12)}"
            )

        return lines