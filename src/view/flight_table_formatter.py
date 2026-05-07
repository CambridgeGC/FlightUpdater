from datetime import datetime

from model.flight_display_row import FlightDisplayRow


LogLine = tuple[str, str | None]


class FlightTableFormatter:
    GROUPS = ["aerotow", "winch", "self-launch", "tmg", "other"]

    def __init__(
        self,
        grl_only: bool = True,
        group_by_launch_type: bool = False,
    ):
        self.grl_only = grl_only
        self.group_by_launch_type = group_by_launch_type

    def filter_grl_flights(
        self,
        flights: list[FlightDisplayRow],
    ) -> list[FlightDisplayRow]:
        if not self.grl_only:
            return flights

        return [
            f for f in flights
            if f.source != "GA"
            or (f.airfield_takeoff or "").upper() == "GRL"
            or (f.airfield_landing or "").upper() == "GRL"
        ]

    def sort_flights_for_display(
        self,
        flights: list[FlightDisplayRow],
        group_by_launch_type: bool | None = None,
    ) -> list[FlightDisplayRow]:
        if group_by_launch_type is None:
            group_by_launch_type = self.group_by_launch_type

        def time_key(f: FlightDisplayRow):
            return (f.takeoff_time is None, f.takeoff_time or datetime.min.time())

        if not group_by_launch_type:
            return sorted(flights, key=time_key)

        tug_count = len({
            f.tow_callsign
            for f in flights
            if (f.launch_method or "").lower() == "aerotow" and f.tow_callsign
        })

        if tug_count > 1:
            return sorted(
                flights,
                key=lambda f: (
                    f.tow_callsign
                    if (f.launch_method or "").lower() == "aerotow"
                    else "",
                    *time_key(f),
                ),
            )

        return sorted(flights, key=time_key)

    def format_flights(
        self,
        flights_unsorted: list[FlightDisplayRow],
        title: str,
        notes_only: bool = False,
        group_by_launch_type: bool | None = None,
    ) -> list[LogLine]:
        if group_by_launch_type is None:
            group_by_launch_type = self.group_by_launch_type

        flights = self.filter_grl_flights(flights_unsorted)
        flights = self.sort_flights_for_display(
            flights,
            group_by_launch_type=group_by_launch_type,
        )

        lines: list[LogLine] = []
        header = self.header()

        if group_by_launch_type:
            for group in self.GROUPS:
                if group == "other":
                    subset = [
                        f for f in flights
                        if (f.launch_method or "").lower() not in self.GROUPS[:-1]
                    ]
                else:
                    subset = [
                        f for f in flights
                        if (f.launch_method or "").lower() == group
                    ]

                if not subset:
                    continue

                lines.append(("", None))
                lines.append((f"--- {group.upper()} Flights ---", None))
                lines.append((header, None))
                lines.extend(self._format_rows(subset, notes_only=notes_only))

            return lines

        lines.append(("", None))
        lines.append((title, None))
        lines.append((header, None))
        lines.extend(self._format_rows(flights, notes_only=notes_only))
        return lines

    def format_ga_notes(
        self,
        flights_unsorted: list[FlightDisplayRow],
    ) -> list[LogLine]:
        flights = [f for f in flights_unsorted if f.notes]

        if not flights:
            return []

        flights = sorted(
            flights,
            key=lambda f: (
                f.takeoff_time is None,
                f.takeoff_time or datetime.min.time(),
            ),
        )

        lines: list[LogLine] = [
            ("", None),
            ("GA flights with notes", None),
            (
                f"{'No':>3} "
                f"{'Seq':>6} "
                f"{'Aircraft':16}"
                f"{'Takeoff':8}"
                f"{'Notes':80}",
                None,
            ),
        ]

        for idx, flight in enumerate(flights, start=1):
            tag = "even" if idx % 2 == 0 else "odd"
            seq = flight.sequence_number or ""
            aircraft = self.aircraft_str(flight)

            line = (
                f"{idx:3} "
                f"{seq:6} "
                f"{aircraft:16}"
                f"{flight.takeoff_str():8}"
                f"{flight.notes or '':80}"
            )

            lines.append((line, tag))

        return lines

    def header(self) -> str:
        return (
            f"{'No':>3} "
            f"{'Seq':>6} "
            f"{'Launch':12}"
            f"{'Aircraft':16}"
            f"{'Takeoff':8}{'Landing':8}"
            f"{'P1':35}{'P2':35}{'Payer':8}"
            f"{'Tow':10}{'Tug pilot':36}{'Height':8}"
            f"{'Category':15}"
            f"{'From':10}{'To':10}"
            f"{'Source':6}"
        )

    def _format_rows(
        self,
        flights: list[FlightDisplayRow],
        notes_only: bool = False,
    ) -> list[LogLine]:
        lines: list[LogLine] = []
        idx = 0

        for flight in flights:
            note_str = flight.notes if flight.notes else ""

            if notes_only and not note_str:
                continue

            idx += 1
            tag = "even" if idx % 2 == 0 else "odd"

            launch = (flight.launch_method or "").lower()
            height_str = str(flight.height_ft or "") if launch == "aerotow" else ""

            tow_pilot = (
                f"{flight.tow_pilot_account or '':6}"
                f"{flight.tow_pilot_name or '':30}"
            )

            seq = flight.sequence_number or ""
            aircraft = self.aircraft_str(flight)

            line = (
                f"{idx:3} "
                f"{seq:6} "
                f"{flight.launch_method or '':12}"
                f"{aircraft:16}"
                f"{flight.takeoff_str():8}"
                f"{flight.landing_str():8}"
                f"{self.crew_str(flight.pic_account, flight.pic_name, 30):35}"
                f"{self.crew_str(flight.p2_account, flight.p2_name, 30):35}"
                f"{flight.payer_account or '':8}"
                f"{flight.tow_callsign or '':10}"
                f"{tow_pilot:36}"
                f"{height_str:8}"
                f"{flight.category or '':15}"
                f"{flight.airfield_takeoff or '':10}"
                f"{flight.airfield_landing or '':10}"
                f"{flight.source or '':6}"
            )

            lines.append((line, tag))

        return lines

    @staticmethod
    def aircraft_str(flight: FlightDisplayRow) -> str:
        reg = (flight.registration or "").strip()
        cs = (flight.callsign or "").strip()

        cs4 = f"{cs[:4]:<4}"

        if reg and cs and reg != cs:
            return f"{cs4}: {reg}"

        return reg or cs4

    @staticmethod
    def crew_str(
        account: str,
        name: str,
        name_width: int = 18,
        pad_char: str = " ",
    ) -> str:
        acct = (account or "").strip()[:4]

        if acct:
            acct_str = f"{acct:>4}"
        else:
            acct_str = " " * 4

        if pad_char != " ":
            acct_str = acct_str.replace(" ", pad_char)

        nm = (name or "")[:name_width]
        return f"{acct_str} {nm:<{name_width}}"