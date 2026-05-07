import os
import sys
import tempfile
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, scrolledtext, messagebox
import traceback
from pathlib import Path
from tkcalendar import DateEntry

from model.flight_display_row import FlightDisplayRow
from services.flight_comparison_service import find_unmatched

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
except ImportError:
    colors = None
    landscape = None
    A4 = None
    getSampleStyleSheet = None
    SimpleDocTemplate = None
    Table = None
    TableStyle = None
    Paragraph = None
    Spacer = None


class FlightUpdaterApp:
    def __init__(self, root: tk.Tk, updater_service):
        self.root = root
        self.service = updater_service

        self.ga: list[FlightDisplayRow] = []
        self.kt: list[FlightDisplayRow] = []
        self.al: list[FlightDisplayRow] = []

        self.launch_sort = tk.BooleanVar(value=True)
        self.grl_only = tk.BooleanVar(value=True)
        self.print_to_file = tk.BooleanVar(value=False)        
        self.modify_payer = tk.BooleanVar(value=True)

        version = self._get_version()
        aerolog_mode = self._get_aerolog_mode()

        root.title(f"Flight Updater - {version} - Aerolog: {aerolog_mode}")
        root.geometry("1900x1000")

        top_frame = ttk.Frame(root)
        top_frame.pack(padx=10, pady=5, anchor="w")

        ttk.Label(top_frame, text="Date:").grid(row=0, column=0, sticky="w")

        self.date_entry = DateEntry(top_frame, date_pattern="yyyy-MM-dd")
        self.date_entry.grid(row=0, column=1, padx=(5, 15))

        self.compare_btn = ttk.Button(
            top_frame,
            text="Fetch and Compare",
            command=self.start,
        )
        self.compare_btn.grid(row=0, column=2, sticky="w", padx=(5, 15))

        self.test_errors_btn = ttk.Button(
            top_frame,
            text="Test for errors",
            command=self.test_for_errors,
        )
        self.test_errors_btn.grid(row=0, column=3, sticky="w", padx=(5, 15))

        self.send_aerolog_btn = ttk.Button(
            top_frame,
            text="Send GA to Aerolog",
            command=self.send_ga_to_aerolog,
        )
        self.send_aerolog_btn.grid(row=0, column=4, sticky="w", padx=(5, 15))

        ctrl_frame = ttk.Frame(root)
        ctrl_frame.pack(padx=10, pady=(10, 0), anchor="w")

        self.list_ktrax_btn = ttk.Button(
            ctrl_frame,
            text="List Ktrax",
            command=self.list_ktrax,
        )
        self.list_ktrax_btn.pack(side="left", padx=(0, 10))

        self.list_ga_btn = ttk.Button(
            ctrl_frame,
            text="List GA",
            command=self.list_ga,
        )
        self.list_ga_btn.pack(side="left", padx=(0, 10))

        self.list_aerolog_btn = ttk.Button(
            ctrl_frame,
            text="List Aerolog",
            command=self.list_aerolog,
        )
        self.list_aerolog_btn.pack(side="left", padx=(0, 10))

        self.clear_btn = ttk.Button(
            ctrl_frame,
            text="Clear",
            command=self.clear,
        )
        self.clear_btn.pack(side="left", padx=(0, 10))

        self.print_btn = ttk.Button(
            ctrl_frame,
            text="Print GA",
            command=self.print_ga,
        )
        self.print_btn.pack(side="left", padx=(5, 15))

        ttk.Checkbutton(
            ctrl_frame,
            text="Print GA to file",
            variable=self.print_to_file,
        ).pack(side="left", padx=(10, 0))        


        ttk.Checkbutton(
            ctrl_frame,
            text="Sort by Launch Type",
            variable=self.launch_sort,
        ).pack(side="left", padx=(10, 0))

        ttk.Checkbutton(
            ctrl_frame,
            text="GRL flights only",
            variable=self.grl_only,
        ).pack(side="left", padx=(10, 0))

        ttk.Checkbutton(
            ctrl_frame,
            text="Modify Payer",
            variable=self.modify_payer,
        ).pack(side="left", padx=(10, 0))

        self.log_widget = scrolledtext.ScrolledText(root, state="disabled")
        self.log_widget.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_widget.tag_configure("even", background="white")
        self.log_widget.tag_configure("odd", background="#f0f0f0")

    def log_message(self, msg: str, tag: str | None = None) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.insert(tk.END, msg + "\n", tag if tag else None)
        self.log_widget.see(tk.END)
        self.log_widget.configure(state="disabled")

    def clear(self) -> None:
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", tk.END)
        self.log_widget.configure(state="disabled")

    def start(self) -> None:
        self._set_buttons_enabled(False)
        self.clear()
        threading.Thread(target=self.run, daemon=True).start()

    def _set_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"

        self.compare_btn.config(state=state)
        self.list_ga_btn.config(state=state)
        self.list_ktrax_btn.config(state=state)
        self.list_aerolog_btn.config(state=state)
        self.clear_btn.config(state=state)
        self.send_aerolog_btn.config(state=state)
        self.print_btn.config(state=state)
        self.test_errors_btn.config(state=state)

    def _filter_grl_flights(
        self,
        flights: list[FlightDisplayRow],
    ) -> list[FlightDisplayRow]:
        if not self.grl_only.get():
            return flights

        return [
            f for f in flights
            if f.source != "GA"
            or (f.airfield_takeoff or "").upper() == "GRL"
            or (f.airfield_landing or "").upper() == "GRL"
        ]

    def list_ga(self) -> None:
        self.print_flights(
            self.ga,
            "All Gliding.App flights",
            group_by_launch_type=self.launch_sort.get(),
        )

    def list_ktrax(self) -> None:
        self.print_flights(
            self.kt,
            "All Ktrax flights",
            group_by_launch_type=self.launch_sort.get(),
        )

    def list_aerolog(self) -> None:
        self.print_flights(
            self.al,
            "All Aerolog flights",
            group_by_launch_type=self.launch_sort.get(),
        )

    def send_ga_to_aerolog(self) -> None:
        if not self.ga:
            messagebox.showinfo(
                "Send GA to Aerolog",
                "No Gliding.App flights loaded. Fetch flights first.",
            )
            return

        self._set_buttons_enabled(False)
        threading.Thread(target=self._send_ga_to_aerolog_worker, daemon=True).start()

    def _send_ga_to_aerolog_worker(self) -> None:
        try:
            self.log_message("")
            self.log_message("Sending Gliding.App flights to Aerolog...")

            result = self.service.send_glidingapp_flights_to_aerolog(self.ga)

            self.log_message(
                f"Aerolog send result: "
                f"status={result.get('status')}, "
                f"sent={result.get('sent')}, "
                f"records={result.get('record_count')}"
            )

        except Exception:
            self.log_message("ERROR sending to Aerolog:")
            self.log_message(traceback.format_exc())

        finally:
            self.log_widget.after(0, lambda: self._set_buttons_enabled(True))

    def count_types_of_flight(
        self,
        flights: list[FlightDisplayRow],
    ) -> tuple[int, int, int, int, int, int]:
        aerotow = winch = self_launch = tmg = other = 0

        for flight in flights:
            launch = (flight.launch_method or "").lower()

            if launch == "aerotow":
                aerotow += 1
            elif launch == "winch":
                winch += 1
            elif launch == "self-launch":
                self_launch += 1
            elif launch == "tmg":
                tmg += 1
            else:
                other += 1

        total = aerotow + winch + self_launch + tmg + other
        return aerotow, winch, self_launch, tmg, other, total

    def _sort_flights_for_display(
        self,
        flights: list[FlightDisplayRow],
        group_by_launch_type: bool = False,
    ) -> list[FlightDisplayRow]:
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
                    f.tow_callsign if (f.launch_method or "").lower() == "aerotow" else "",
                    *time_key(f),
                ),
            )

        return sorted(flights, key=time_key)

    def _get_version(self) -> str:
        try:
            # PyInstaller: version.txt is next to the exe
            if getattr(sys, "frozen", False):
                version_path = Path(sys.executable).parent / "version.txt"
            else:
                # Dev: project root
                version_path = Path(__file__).resolve().parents[2] / "version.txt"

            return version_path.read_text(encoding="ascii").strip()
        except Exception:
            return "unknown"


    def _get_aerolog_mode(self) -> str:
        # Assumes your config structure matches what your services use
        al_config = self.service.config.get("aerolog", {})
        mode = al_config.get("data_source", "live")

        return mode.upper()


    def run(self) -> None:
        try:
            flight_date = self.date_entry.get_date()

            self.log_message(f"Fetching flights for {flight_date}...")

            self.ga = self.service.get_glidingapp_flights(
                flight_date,
                modify_payer=self.modify_payer.get(),
                )
            self.kt = self.service.get_ktrax_flights(flight_date)
            self.al = self.service.get_aerolog_flights(flight_date)

            kt_not_ga = find_unmatched(self.kt, self.ga)
            ga_not_kt = find_unmatched(self.ga, self.kt)

            al_not_ga = []
            ga_not_al = []

            if self.al:
                al_not_ga = find_unmatched(self.al, self.ga)
                ga_not_al = find_unmatched(self.ga, self.al)

            # self.log_message(
            #     f"Flights in Ktrax but not in Gliding.App: {len(kt_not_ga)}"
            # )
            # self.log_message(
            #     f"Flights in Gliding.App but not in Ktrax: {len(ga_not_kt)}"
            # )
            # self.log_message(
            #     f"Flights in Aerolog but not in Gliding.App: {len(al_not_ga)}"
            # )
            # self.log_message(
            #     f"Flights in Gliding.App but not in Aerolog: {len(ga_not_al)}"
            # )
            self.log_message("")

            self._print_counts()

            if kt_not_ga:
                self.print_flights(
                    kt_not_ga,
                    "Flights in Ktrax but not in Gliding.App",
                    group_by_launch_type=False,
                )

            if ga_not_kt:
                self.print_flights(
                    ga_not_kt,
                    "Flights in Gliding.App but not in Ktrax",
                    group_by_launch_type=False,
                )

            if self.al:
                if al_not_ga:
                    self.print_flights(
                        al_not_ga,
                        "Flights in Aerolog but not in Gliding.App",
                        group_by_launch_type=False,
                    )

                if ga_not_al:
                    self.print_flights(
                        ga_not_al,
                        "Flights in Gliding.App but not in Aerolog",
                        group_by_launch_type=False,
                    )

            self.print_ga_notes(self.ga)
            self.print_test_for_errors()
            


        except Exception:
            self.log_message("ERROR:")
            self.log_message(traceback.format_exc())

        finally:
            self.log_widget.after(0, lambda: self._set_buttons_enabled(True))

    def _print_counts(self) -> None:
        ga_aerotow, ga_winch, ga_self, ga_tmg, ga_other, ga_total = (
            self.count_types_of_flight(self.ga)
        )
        kt_aerotow, kt_winch, kt_self, kt_tmg, kt_other, kt_total = (
            self.count_types_of_flight(self.kt)
        )
        al_aerotow, al_winch, al_self, al_tmg, al_other, al_total = (
            self.count_types_of_flight(self.al)
        )

        header = (
            f"{'Source':15}"
            f"{'Aerotow':>10}"
            f"{'Winch':>10}"
            f"{'Self':>10}"
            f"{'TMG':>10}"
            f"{'Other':>10}"
            f"{'Total':>10}"
        )
        self.log_message(header)

        self.log_message(
            f"{'Gliding.App':15}"
            f"{ga_aerotow:>10}"
            f"{ga_winch:>10}"
            f"{ga_self:>10}"
            f"{ga_tmg:>10}"
            f"{ga_other:>10}"
            f"{ga_total:>10}"
        )

        self.log_message(
            f"{'Ktrax':15}"
            f"{kt_aerotow:>10}"
            f"{kt_winch:>10}"
            f"{kt_self:>10}"
            f"{kt_tmg:>10}"
            f"{kt_other:>10}"
            f"{kt_total:>10}"
        )

        self.log_message(
            f"{'Aerolog':15}"
            f"{al_aerotow:>10}"
            f"{al_winch:>10}"
            f"{al_self:>10}"
            f"{al_tmg:>10}"
            f"{al_other:>10}"
            f"{al_total:>10}"
        )

        self.log_message("")

    def print_flights(
        self,
        flights_unsorted: list[FlightDisplayRow],
        title: str,
        notes_only: bool = False,
        group_by_launch_type: bool = False,
    ) -> None:
        flights_unsorted = self._filter_grl_flights(flights_unsorted)

        flights = self._sort_flights_for_display(
            flights_unsorted,
            group_by_launch_type=group_by_launch_type,
        )

        header = (
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

        if group_by_launch_type:
            groups = ["aerotow", "winch", "self-launch", "tmg", "other"]

            for group in groups:
                if group == "other":
                    subset = [
                        f
                        for f in flights
                        if (f.launch_method or "").lower() not in groups[:-1]
                    ]
                else:
                    subset = [
                        f
                        for f in flights
                        if (f.launch_method or "").lower() == group
                    ]

                if not subset:
                    continue

                self.log_message("")
                self.log_message(f"--- {group.upper()} Flights ---")
                self.log_message(header)

                self._print_flight_rows(subset, notes_only)
            return

        self.log_message("")
        self.log_message(title)
        self.log_message(header)
        self._print_flight_rows(flights, notes_only)

    def _aircraft_str(self, flight: FlightDisplayRow) -> str:
        reg = (flight.registration or "").strip()
        cs = (flight.callsign or "").strip()

        cs4 = f"{cs[:4]:<4}"

        if reg and cs and reg != cs:
            return f"{cs4}: {reg}"

        return reg or cs4

    def _print_flight_rows(
        self,
        flights: list[FlightDisplayRow],
        notes_only: bool,
    ) -> None:
        idx = 0

        for flight in flights:
            launch = (flight.launch_method or "").lower()

            note_str = flight.notes if flight.notes else ""

            if notes_only and not note_str:
                continue

            idx += 1
            tag = "even" if idx % 2 == 0 else "odd"

            height_str = ""
            if launch == "aerotow":
                height_str = str(flight.height_ft or "")

            tow_pilot = (
                f"{flight.tow_pilot_account or '':6}"
                f"{flight.tow_pilot_name or '':30}"
            )

            aircraft_str = self._aircraft_str(flight)
            line = (
                f"{idx:3} "
                f"{(flight.sequence_number or ''):6} "
                f"{flight.launch_method or '':12}"
                f"{aircraft_str:16}"
                f"{flight.takeoff_str():8}"
                f"{flight.landing_str():8}"
                f"{self._crew_str(flight.pic_account, flight.pic_name, 30):35}"
                f"{self._crew_str(flight.p2_account, flight.p2_name, 30):35}"
                f"{flight.payer_account or '':8}"
                f"{flight.tow_callsign or '':10}"
                f"{tow_pilot:36}"
                f"{height_str:8}"
                f"{flight.category or '':15}"
                f"{flight.airfield_takeoff or '':10}"
                f"{flight.airfield_landing or '':10}"
                f"{flight.source or '':6}"
            )

            self.log_message(line, tag)

    def _crew_str(self, account: str, name: str, name_width: int = 18) -> str:
        acct = (account or "")[:4]
        nm = (name or "")[:name_width]
        return f"{acct:<4} {nm:<{name_width}}"

    def print_ga_notes(self, flights_unsorted: list[FlightDisplayRow]) -> None:
        flights = [
            f for f in flights_unsorted
            if f.notes
        ]

        if not flights:
            return

        flights = sorted(
            flights,
            key=lambda f: (
                f.takeoff_time is None,
                f.takeoff_time or datetime.min.time(),
            ),
        )

        self.log_message("")
        self.log_message("GA flights with notes")

        header = (
            f"{'No':4}{'Seq':4}{'Aircraft':10}"
            f"{'Takeoff':8}"
            f"{'Notes':80}"
        )
        self.log_message(header)

        for idx, flight in enumerate(flights, start=1):
            tag = "even" if idx % 2 == 0 else "odd"

            line = (
                f"{idx:3} "
                f"{(flight.sequence_number or ''):3} "
                f"{flight.callsign or '':10}"
                f"{flight.takeoff_str():8}"
                f"{flight.notes or '':80}"
            )

            self.log_message(line, tag)

    def print_ga(self) -> None:
        if not self.ga:
            messagebox.showinfo("Print GA", "No Gliding.App flights to print.")
            return

        if SimpleDocTemplate is None:
            messagebox.showerror(
                "Print GA",
                "ReportLab is not installed. Install reportlab to enable printing.",
            )
            return

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
        story = [
            Paragraph(
                f"Gliding.App Flights - {self.date_entry.get_date()}",
                styles["Heading2"],
            ),
            Spacer(1, 6),
        ]

        flights = self._filter_grl_flights(self.ga)
        flights = self._sort_flights_for_display(
            flights,
            group_by_launch_type=self.launch_sort.get(),
        )

        def add_pdf_table(title: str, subset: list[FlightDisplayRow]) -> None:
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

                tow_pilot = (
                    f"{flight.tow_pilot_account or ''} "
                    f"{flight.tow_pilot_name or ''}"
                ).strip()

                data.append([
                    idx,
                    flight.sequence_number or "",
                    flight.launch_method or "",
                    self._aircraft_str(flight),
                    flight.takeoff_str(),
                    flight.landing_str(),
                    self._crew_str(flight.pic_account, flight.pic_name, 30),
                    self._crew_str(flight.p2_account, flight.p2_name, 30),
                    flight.payer_account or "",
                    flight.tow_callsign or "",
                    tow_pilot,
                    height_str,
                    flight.category or "",
                    flight.airfield_takeoff or "",
                    flight.airfield_landing or "",
                ])

            from reportlab.lib.units import mm

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

                ("FONTNAME", (6, 1), (7, -1), "Courier"),  # P1 + P2 data

                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]))

            styles["Heading2"].fontSize = 12
            styles["Heading3"].fontSize = 10

            story.append(table)
            story.append(Spacer(1, 12))

        if self.launch_sort.get():
            groups = ["aerotow", "winch", "self-launch", "tmg", "other"]

            for group in groups:
                if group == "other":
                    subset = [
                        f for f in flights
                        if (f.launch_method or "").lower() not in groups[:-1]
                    ]
                else:
                    subset = [
                        f for f in flights
                        if (f.launch_method or "").lower() == group
                    ]

                add_pdf_table(f"{group.upper()} Flights", subset)
        else:
            add_pdf_table("All Flights", flights)

        doc.build(story)

        try:
            if self.print_to_file.get():
                from pathlib import Path
                from shutil import move

                downloads = Path.home() / "Downloads"
                downloads.mkdir(exist_ok=True)

                from datetime import datetime

                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                filename = f"GlidingApp_{stamp}.pdf"
                target = downloads / filename

                move(tmp.name, target)

                self.log_message(f"Saved PDF to {target}")

            else:
                if sys.platform.startswith("win"):
                    os.startfile(tmp.name, "print")
                else:
                    os.system(f"lpr {tmp.name}")

        except Exception as exc:
            messagebox.showerror("Print GA", f"Failed to output PDF:\n{exc}")

    def test_for_errors(self) -> None:
        if not self.ga:
            messagebox.showinfo(
                "Test for errors",
                "No Gliding.App flights loaded. Fetch flights first.",
            )
            return

        self.print_test_for_errors()


    def print_test_for_errors(self) -> None:
        error_groups = self.service.test_for_errors(self.ga)

        self.log_message("")
        self.log_message("Possible Gliding.App errors")

        if not error_groups:
            self.log_message("No errors found.")
            return

        for heading, flights in error_groups.items():
            self.print_flights(
                flights,
                heading,
                group_by_launch_type=False,
            )