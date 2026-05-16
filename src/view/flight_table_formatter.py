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
        # grl_only is now only used by the Aerolog upload path.
        # Listing and PDF printing deliberately show all GA flights.
        self.grl_only = grl_only
        self.group_by_launch_type = group_by_launch_type

    def filter_aerolog_upload_flights(
        self,
        flights: list[FlightDisplayRow],
        include_non_grl_club_departures: bool = False,
    ) -> list[FlightDisplayRow]:
        """
        Used only for Aerolog upload.

        Always include GA flights that departed from GRL.

        If include_non_grl_club_departures is True, also include GA flights
        that departed from somewhere other than GRL, but only where the aircraft
        is a club aircraft.
        """
        upload_flights: list[FlightDisplayRow] = []

        for flight in flights:
            if flight.source != "GA":
                continue

            departed_from_grl = (flight.airfield_takeoff or "").upper() == "GRL"
            is_club_aircraft = getattr(flight, "is_club_aircraft", False)

            if departed_from_grl:
                upload_flights.append(flight)
                continue

            if include_non_grl_club_departures and is_club_aircraft:
                upload_flights.append(flight)

        return upload_flights

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

        return sorted(flights, key=time_key)

    def build_sections(
        self,
        flights_unsorted: list[FlightDisplayRow],
        title: str,
        group_by_launch_type: bool | None = None,
    ) -> list[tuple[str, list[FlightDisplayRow]]]:
        """
        Build display/PDF sections.

        Display and print always include all flights supplied.

        For GA flights:
        - flights departing away from GRL go into their own section
        - if launch grouping is enabled, aerotows are split by tug when
          there is more than one tow aircraft
        """
        if group_by_launch_type is None:
            group_by_launch_type = self.group_by_launch_type

        flights = self.sort_flights_for_display(
            flights_unsorted,
            group_by_launch_type=group_by_launch_type,
        )

        away_from_grl_club = [
            f for f in flights
            if f.source == "GA"
            and (f.airfield_takeoff or "").upper() != "GRL"
            and getattr(f, "is_club_aircraft", False)
        ]

        away_from_grl_non_club = [
            f for f in flights
            if f.source == "GA"
            and (f.airfield_takeoff or "").upper() != "GRL"
            and not getattr(f, "is_club_aircraft", False)
        ]

        normal_flights = [
            f for f in flights
            if not (
                f.source == "GA"
                and (f.airfield_takeoff or "").upper() != "GRL"
            )
        ]

        sections: list[tuple[str, list[FlightDisplayRow]]] = []

        if group_by_launch_type:
            sections.extend(
                self._build_launch_sections(normal_flights)
            )
        else:
            if normal_flights:
                sections.append((title, normal_flights))

        if away_from_grl_club:
            sections.append((
                "Flights departing away from GRL - club aircraft",
                self.sort_flights_for_display(
                    away_from_grl_club,
                    group_by_launch_type=False,
                ),
            ))

        if away_from_grl_non_club:
            sections.append((
                "Flights departing away from GRL - non-club aircraft",
                self.sort_flights_for_display(
                    away_from_grl_non_club,
                    group_by_launch_type=False,
                ),
            ))

        return sections

    def _build_launch_sections(
        self,
        flights: list[FlightDisplayRow],
    ) -> list[tuple[str, list[FlightDisplayRow]]]:
        sections: list[tuple[str, list[FlightDisplayRow]]] = []

        aerotow_flights = [
            f for f in flights
            if (f.launch_method or "").lower() == "aerotow"
        ]

        tow_callsigns = sorted({
            f.tow_callsign
            for f in aerotow_flights
            if f.tow_callsign
        })

        if len(tow_callsigns) > 1:
            for tow_callsign in tow_callsigns:
                subset = [
                    f for f in aerotow_flights
                    if f.tow_callsign == tow_callsign
                ]

                if subset:
                    sections.append((
                        f"AEROTOW Flights - {tow_callsign}",
                        self.sort_flights_for_display(
                            subset,
                            group_by_launch_type=False,
                        ),
                    ))

            no_tow = [
                f for f in aerotow_flights
                if not f.tow_callsign
            ]

            if no_tow:
                sections.append((
                    "AEROTOW Flights - no tug recorded",
                    self.sort_flights_for_display(
                        no_tow,
                        group_by_launch_type=False,
                    ),
                ))
        elif aerotow_flights:
            sections.append((
                "AEROTOW Flights",
                self.sort_flights_for_display(
                    aerotow_flights,
                    group_by_launch_type=False,
                ),
            ))

        for group in ["winch", "self-launch", "tmg", "other"]:
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

            if subset:
                sections.append((
                    f"{group.upper()} Flights",
                    self.sort_flights_for_display(
                        subset,
                        group_by_launch_type=False,
                    ),
                ))

        return sections

    def format_flights(
        self,
        flights_unsorted: list[FlightDisplayRow],
        title: str,
        notes_only: bool = False,
        group_by_launch_type: bool | None = None,
    ) -> list[LogLine]:
        sections = self.build_sections(
            flights_unsorted,
            title,
            group_by_launch_type=group_by_launch_type,
        )

        lines: list[LogLine] = []
        header = self.header()

        for section_title, section_flights in sections:
            if not section_flights:
                continue

            lines.append(("", None))
            lines.append((section_title, None))
            lines.append((header, None))
            lines.extend(
                self._format_rows(
                    section_flights,
                    notes_only=notes_only,
                )
            )

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