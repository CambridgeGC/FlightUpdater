import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from shutil import move
from typing import Any

from model.flight_display_row import FlightDisplayRow
from view.flight_table_formatter import FlightTableFormatter

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class GAPdfPrinter:
    def __init__(
        self,
        save_to_file: bool = False,
        grl_only: bool = True,
        group_by_launch_type: bool = True,
        include_non_grl_non_club: bool = False,
    ):
        self.save_to_file = save_to_file
        self.grl_only = grl_only
        self.group_by_launch_type = group_by_launch_type
        self.include_non_grl_non_club = include_non_grl_non_club

        self.formatter = FlightTableFormatter(
            grl_only=grl_only,
            group_by_launch_type=group_by_launch_type,
        )

    def print_ga(
        self,
        flights_unsorted: list[FlightDisplayRow],
        flight_date: Any,
    ) -> Path | None:
        if not REPORTLAB_AVAILABLE:
            raise RuntimeError(
                "ReportLab is not installed. Install reportlab to enable printing."
            )

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.close()

        doc = SimpleDocTemplate(
            tmp.name,
            pagesize=landscape(A4),
            leftMargin=20,
            rightMargin=20,
            topMargin=20,
            bottomMargin=20,
        )

        styles = getSampleStyleSheet()
        styles["Heading2"].fontSize = 12
        styles["Heading3"].fontSize = 10

        story = [
            Paragraph(f"Gliding.App Flights - {flight_date}", styles["Heading2"]),
            Spacer(1, 6),
        ]

        sections = self.formatter.build_sections(
            flights_unsorted,
            "All Flights",
            group_by_launch_type=self.group_by_launch_type,
            include_non_grl_non_club=self.include_non_grl_non_club,
        )

        for section_title, section_flights in sections:
            self._add_pdf_table(
                story,
                styles,
                section_title,
                section_flights,
            )

        doc.build(story)

        if self.save_to_file:
            target = self._downloads_target()
            move(tmp.name, target)
            return target

        if sys.platform.startswith("win"):
            os.startfile(tmp.name, "print")
        else:
            os.system(f'lpr "{tmp.name}"')

        return None

    def _add_pdf_table(
        self,
        story: list,
        styles,
        title: str,
        subset: list[FlightDisplayRow],
    ) -> None:
        if not subset:
            return

        story.append(Paragraph(title, styles["Heading3"]))
        story.append(Spacer(1, 6))

        data = [[
            "No", "Seq", "Launch", "Aircraft", "Takeoff", "Landing",
            "P1", "P2", "Payer", "Tow", "Tug pilot", "Height",
            "Category", "From", "To",
        ]]

        for idx, flight in enumerate(subset, start=1):
            launch = (flight.launch_method or "").lower()
            height_str = str(flight.height_ft or "") if launch == "aerotow" else ""

            tow_pilot = self._truncate(
                (
                    f"{flight.tow_pilot_account or ''} "
                    f"{flight.tow_pilot_name or ''}"
                ).strip(),
                18,
            )

            data.append([
                idx,
                flight.sequence_number or "",
                flight.launch_method or "",
                self.formatter.aircraft_str(flight),
                flight.takeoff_str(),
                flight.landing_str(),
                self.formatter.crew_str(
                    flight.pic_account,
                    flight.pic_name,
                    30,
                    pad_char="\u00A0",
                ),
                self.formatter.crew_str(
                    flight.p2_account,
                    flight.p2_name,
                    30,
                    pad_char="\u00A0",
                ),
                flight.payer_account or "",
                flight.tow_callsign or "",
                tow_pilot,
                height_str,
                flight.category or "",
                self.formatter.fixed_width(flight.airfield_takeoff, 10).strip(),
                self.formatter.fixed_width(flight.airfield_landing, 10).strip(),
            ])

        col_widths = [
            7 * mm,    # No
            9 * mm,    # Seq
            17 * mm,   # Launch
            25 * mm,   # Aircraft
            12 * mm,   # Takeoff
            12 * mm,   # Landing
            42 * mm,   # P1
            42 * mm,   # P2
            10 * mm,   # Payer
            14 * mm,   # Tow
            25 * mm,   # Tug pilot
            11 * mm,   # Height
            18 * mm,   # Category
            10 * mm,   # From
            10 * mm,   # To
        ]

        table = Table(data, colWidths=col_widths, repeatRows=1)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),

            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (0, 1), (1, -1), "RIGHT"),
            ("ALIGN", (4, 1), (5, -1), "CENTER"),

            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (6, 1), (7, -1), "Courier"),

            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))

        story.append(table)
        story.append(Spacer(1, 12))

    def _downloads_target(self) -> Path:
        downloads = Path.home() / "Downloads"
        downloads.mkdir(exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return downloads / f"GlidingApp_{stamp}.pdf"

    @staticmethod
    def _truncate(value: object, max_len: int) -> str:
        text = str(value or "").strip()

        if len(text) <= max_len:
            return text

        if max_len <= 1:
            return text[:max_len]

        return text[: max_len - 1] + "…"