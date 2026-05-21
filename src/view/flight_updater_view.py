import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import traceback
from pathlib import Path
from tkcalendar import DateEntry

from model.flight_display_row import FlightDisplayRow
from services.flight_comparison_service import find_unmatched

from view.flight_table_formatter import FlightTableFormatter
from view.ga_pdf_printer import GAPdfPrinter


try:
    from config import VERSION
except ImportError:
    VERSION = "unknown"

class FlightUpdaterApp:
    def __init__(self, root: tk.Tk, updater_service):
        self.root = root
        self.service = updater_service

        self.ga: list[FlightDisplayRow] = []
        self.kt: list[FlightDisplayRow] = []
        self.al: list[FlightDisplayRow] = []

        self.launch_sort = tk.BooleanVar(value=True)
        self.include_non_grl_club_departures = tk.BooleanVar(value=True)
        self.list_non_club_non_grl_departures = tk.BooleanVar(value=False)
        self.dry_run_only = tk.BooleanVar(value=True)
        self.show_json = tk.BooleanVar(value=False)
        self.print_to_file = tk.BooleanVar(value=False)
        self.modify_payer = tk.BooleanVar(value=True)

        version = self._get_version()
        aerolog_mode = self._get_aerolog_mode()

        root.title(f"Flight Updater - {version} - Aerolog: {aerolog_mode}")
        root.geometry("1900x1000")

        header_frame = ttk.Frame(root)
        header_frame.pack(fill="x", padx=10, pady=5, anchor="w")

        # ============================================================
        # Block 1: Fetch / options
        # ============================================================
        fetch_frame = ttk.LabelFrame(header_frame, text="Fetch and options")
        fetch_frame.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="nw")

        ttk.Label(fetch_frame, text="Date:").grid(
            row=0,
            column=0,
            sticky="w",
            padx=5,
            pady=5,
        )

        self.date_entry = DateEntry(fetch_frame, date_pattern="yyyy-MM-dd")
        self.date_entry.grid(
            row=0,
            column=1,
            sticky="w",
            padx=5,
            pady=5,
        )

        self.compare_btn = ttk.Button(
            fetch_frame,
            text="Fetch and Compare",
            command=self.start,
        )
        self.compare_btn.grid(
            row=0,
            column=2,
            sticky="w",
            padx=5,
            pady=5,
        )

        ttk.Checkbutton(
            fetch_frame,
            text="Sort by Launch Type",
            variable=self.launch_sort,
        ).grid(
            row=1,
            column=0,
            columnspan=3,
            sticky="w",
            padx=5,
            pady=2,
        )

        ttk.Checkbutton(
            fetch_frame,
            text="List non-club non-GRL departures",
            variable=self.list_non_club_non_grl_departures,
        ).grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="w",
            padx=5,
            pady=2,
        )


        ttk.Checkbutton(
            fetch_frame,
            text="Modify Payer",
            variable=self.modify_payer,
        ).grid(
            row=4,
            column=0,
            columnspan=3,
            sticky="w",
            padx=5,
            pady=2,
        )


        # ============================================================
        # Block 2: Lists / print
        # ============================================================
        list_frame = ttk.LabelFrame(header_frame, text="Lists and print")
        list_frame.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="nw")

        self.list_ga_btn = ttk.Button(
            list_frame,
            text="List GA",
            command=self.list_ga,
        )
        self.list_ga_btn.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.list_ktrax_btn = ttk.Button(
            list_frame,
            text="List Ktrax",
            command=self.list_ktrax,
        )
        self.list_ktrax_btn.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        self.list_aerolog_btn = ttk.Button(
            list_frame,
            text="List Aerolog",
            command=self.list_aerolog,
        )
        self.list_aerolog_btn.grid(row=0, column=2, sticky="w", padx=5, pady=5)

        self.test_errors_btn = ttk.Button(
            list_frame,
            text="Test for errors",
            command=self.test_for_errors,
        )
        self.test_errors_btn.grid(row=1, column=0, sticky="w", padx=5, pady=5)

        self.clear_btn = ttk.Button(
            list_frame,
            text="Clear",
            command=self.clear,
        )
        self.clear_btn.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        self.print_btn = ttk.Button(
            list_frame,
            text="Print GA",
            command=self.print_ga,
        )
        self.print_btn.grid(row=1, column=2, sticky="w", padx=5, pady=5)

        ttk.Checkbutton(
            list_frame,
            text="Print GA to file",
            variable=self.print_to_file,
        ).grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="w",
            padx=5,
            pady=2,
        )


        # ============================================================
        # Block 3: Aerolog upload
        # ============================================================
        upload_frame = ttk.LabelFrame(header_frame, text="Aerolog upload")
        upload_frame.grid(row=0, column=2, padx=(0, 10), pady=5, sticky="nw")

        self.send_aerolog_btn = ttk.Button(
            upload_frame,
            text="Send GA to Aerolog",
            command=self.send_ga_to_aerolog,
        )
        self.send_aerolog_btn.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=5,
        )

        ttk.Checkbutton(
            upload_frame,
            text="Also upload non-GRL club departures",
            variable=self.include_non_grl_club_departures,
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            padx=5,
            pady=2,
        )

        ttk.Checkbutton(
            upload_frame,
            text="Dryrun only",
            variable=self.dry_run_only,
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=5,
            pady=2,
        )

        ttk.Checkbutton(
            upload_frame,
            text="Show JSON",
            variable=self.show_json,
        ).grid(
            row=3,
            column=0,
            sticky="w",
            padx=5,
            pady=2,
        )


        # ============================================================
        # Block 4: Aircraft
        # ============================================================
        aircraft_frame = ttk.LabelFrame(header_frame, text="Aircraft")
        aircraft_frame.grid(row=0, column=3, padx=(0, 10), pady=5, sticky="nw")

        self.load_aircraft_btn = ttk.Button(
            aircraft_frame,
            text="Load Aerolog Aircraft",
            command=self.load_aerolog_aircraft_file,
        )
        self.load_aircraft_btn.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.compare_aircraft_btn = ttk.Button(
            aircraft_frame,
            text="Compare Aircraft",
            command=self.compare_aircraft,
        )
        self.compare_aircraft_btn.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        self.list_ga_aircraft_btn = ttk.Button(
            aircraft_frame,
            text="List GA Aircraft",
            command=self.list_ga_aircraft,
        )
        self.list_ga_aircraft_btn.grid(row=1, column=0, sticky="w", padx=5, pady=5)

        self.list_al_aircraft_btn = ttk.Button(
            aircraft_frame,
            text="List AL Aircraft",
            command=self.list_al_aircraft,
        )
        self.list_al_aircraft_btn.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        # ============================================================
        # Block 5: Instructions
        # ============================================================
        instructions_frame = ttk.LabelFrame(header_frame, text="Instructions")
        instructions_frame.grid(row=0, column=4, padx=(0, 10), pady=5, sticky="nw")

        self.instructions_btn = ttk.Button(
            instructions_frame,
            text="Instructions",
            command=self.show_instructions,
        )
        self.instructions_btn.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.log_widget = scrolledtext.ScrolledText(root, state="disabled")
        self.log_widget.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_widget.tag_configure("even", background="white")
        self.log_widget.tag_configure("odd", background="#f0f0f0")
        self.log_widget.tag_configure("error", foreground="red")
        self.log_widget.tag_configure("error_even", foreground="red", background="white")
        self.log_widget.tag_configure("error_odd", foreground="red", background="#f0f0f0")

        threading.Thread(
            target=self._initialise_ogn_ddb_worker,
            daemon=True,
        ).start()

    def _initialise_ogn_ddb_worker(self) -> None:
        try:
            result = self.service.initialise_ogn_ddb()

            self.log_message(
                f"Loaded OGN DDB: "
                f"{result.get('record_count', 0)} records"
            )
            self.log_message(
                f"OGN cache: {result.get('cache_path', '')}"
            )

        except Exception:
            self.log_message("WARNING: Could not load OGN DDB:")
            self.log_message(traceback.format_exc())

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
        self.instructions_btn.config(state=state)

        self.load_aircraft_btn.config(state=state)
        self.compare_aircraft_btn.config(state=state)
        self.list_ga_aircraft_btn.config(state=state)
        self.list_al_aircraft_btn.config(state=state)
        
    def list_ga(self) -> None:
        self.clear()
        self.print_flights(
            self.ga,
            "All Gliding.App flights",
            group_by_launch_type=self.launch_sort.get(),
        )

    def list_ktrax(self) -> None:
        self.clear()
        self.print_flights(
            self.kt,
            "All Ktrax flights",
            group_by_launch_type=self.launch_sort.get(),
        )

    def list_aerolog(self) -> None:
        self.clear()
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

    def load_aerolog_aircraft_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Aerolog aircraft Excel file",
            filetypes=[
                ("Excel files", "*.xlsx *.xlsm *.xltx *.xltm"),
                ("All files", "*.*"),
            ],
        )

        if not file_path:
            return

        try:
            self.log_message("")
            self.log_message(f"Loading Aerolog aircraft file: {file_path}")

            result = self.service.load_aerolog_aircraft_file(file_path)

            self.log_message(
                f"Loaded {result['record_count']} Aerolog aircraft records."
            )
            self.log_message(f"JSON cache: {result['cache_path']}")
            self.log_message(f"Excel cache: {result['excel_cache_path']}")

        except Exception:
            self.log_message("ERROR loading Aerolog aircraft file:")
            self.log_message(traceback.format_exc())
            messagebox.showerror(
                "Load Aerolog Aircraft",
                "Failed to load Aerolog aircraft file. See log for details.",
            )

    def list_ga_aircraft(self) -> None:
        try:
            self.clear()
            lines = self.service.list_glidingapp_aircraft_report()

            for line in lines:
                self.log_message(line)

        except Exception:
            self.log_message("ERROR listing Gliding.App aircraft:")
            self.log_message(traceback.format_exc())
            messagebox.showerror(
                "List GA Aircraft",
                "Failed to list Gliding.App aircraft. See log for details.",
            )


    def list_al_aircraft(self) -> None:
        try:
            self.clear()
            lines = self.service.list_aerolog_aircraft_report()

            for line in lines:
                self.log_message(line)

        except FileNotFoundError as exc:
            self.log_message("ERROR listing Aerolog aircraft:")
            self.log_message(str(exc))
            messagebox.showerror(
                "List AL Aircraft",
                "No Aerolog aircraft cache found. Load an Aerolog aircraft file first.",
            )

        except Exception:
            self.log_message("ERROR listing Aerolog aircraft:")
            self.log_message(traceback.format_exc())
            messagebox.showerror(
                "List AL Aircraft",
                "Failed to list Aerolog aircraft. See log for details.",
            )
    def compare_aircraft(self) -> None:
        try:
            self.clear()
            self.log_message("Loading Gliding.App aircraft and comparing with Aerolog cache...")
            self.log_message("")

            lines = self.service.compare_aircraft()

            for line in lines:
                self.log_message(line)

        except FileNotFoundError as exc:
            self.log_message("ERROR comparing aircraft:")
            self.log_message(str(exc))
            messagebox.showerror(
                "Compare Aircraft",
                "No Aerolog aircraft cache found. Load an Aerolog aircraft file first.",
            )

        except Exception:
            self.log_message("ERROR comparing aircraft:")
            self.log_message(traceback.format_exc())
            messagebox.showerror(
                "Compare Aircraft",
                "Failed to compare aircraft. See log for details.",
            )

    def _send_ga_to_aerolog_worker(self) -> None:
        try:
            self.log_message("")
            self.log_message("Sending Gliding.App flights to Aerolog...")

            formatter = FlightTableFormatter(
                grl_only=False,
                group_by_launch_type=False,
            )

            ga_flights_to_send = self._get_ga_flights_planned_for_aerolog_upload()


            # Always show the simple list, for both dry run and live send.
            self._print_aerolog_upload_summary(ga_flights_to_send)

            result = self.service.send_glidingapp_flights_to_aerolog(
                ga_flights_to_send,
                modify_payer=self.modify_payer.get(),
                dry_run=self.dry_run_only.get(),
            )

            self.log_message(
                f"Aerolog send result: "
                f"status={result.get('status')}, "
                f"sent={result.get('sent')}, "
                f"records={result.get('record_count')}"
            )

            # Only print JSON when it is a dry run and Show JSON is ticked.
            if result.get("status") == "dry_run" and self.show_json.get():
                payload = result.get("payload")
                if payload is not None:
                    self.log_message("")
                    self.log_message("Aerolog payload JSON:")

                    payload_json = json.dumps(
                        payload,
                        indent=2,
                        ensure_ascii=False,
                        default=str,
                    )

                    for line in payload_json.splitlines():
                        self.log_message(line)

        except Exception:
            self.log_message("ERROR sending to Aerolog:")
            self.log_message(traceback.format_exc())

        finally:
            self.log_widget.after(0, lambda: self._set_buttons_enabled(True))

    def _instructions_file_path(self) -> Path:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / "INSTRUCTIONS.md"

        return Path(__file__).resolve().parents[2] / "INSTRUCTIONS.md"

    def show_instructions(self) -> None:
        instructions_path = self._instructions_file_path()

        try:
            lines = instructions_path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            messagebox.showerror(
                "Instructions",
                f"Could not open instructions file:\n"
                f"{instructions_path}\n\n{exc}",
            )
            return

        win = tk.Toplevel(self.root)
        win.title("FlightUpdater Instructions")
        win.geometry("950x750")

        text = scrolledtext.ScrolledText(
            win,
            wrap="word",
            state="normal",
        )
        text.pack(fill="both", expand=True, padx=10, pady=10)

        text.tag_configure(
            "h1",
            font=("TkDefaultFont", 18, "bold"),
            spacing1=10,
            spacing3=8,
        )
        text.tag_configure(
            "h2",
            font=("TkDefaultFont", 14, "bold"),
            spacing1=8,
            spacing3=6,
        )
        text.tag_configure(
            "h3",
            font=("TkDefaultFont", 12, "bold"),
            spacing1=6,
            spacing3=4,
        )
        text.tag_configure(
            "bullet",
            lmargin1=25,
            lmargin2=45,
            spacing1=2,
            spacing3=2,
        )
        text.tag_configure(
            "numbered",
            lmargin1=25,
            lmargin2=45,
            spacing1=2,
            spacing3=2,
        )
        text.tag_configure(
            "code",
            font=("Courier New", 10),
            background="#f0f0f0",
            lmargin1=20,
            lmargin2=20,
            spacing1=2,
            spacing3=2,
        )
        text.tag_configure(
            "normal",
            font=("TkDefaultFont", 10),
            spacing1=2,
            spacing3=2,
        )
        text.tag_configure(
            "bold",
            font=("TkDefaultFont", 10, "bold"),
        )
        text.tag_configure(
            "inline_code",
            font=("Courier New", 10),
            background="#f0f0f0",
        )

        in_code_block = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue

            if in_code_block:
                text.insert(tk.END, line + "\n", "code")

            elif stripped.startswith("### "):
                text.insert(tk.END, stripped[4:] + "\n", "h3")

            elif stripped.startswith("## "):
                text.insert(tk.END, stripped[3:] + "\n", "h2")

            elif stripped.startswith("# "):
                text.insert(tk.END, stripped[2:] + "\n", "h1")

            elif stripped.startswith("- "):
                text.insert(tk.END, "• ", "bullet")
                self._insert_markdown_inline(
                    text,
                    stripped[2:],
                    base_tag="bullet",
                )
                text.insert(tk.END, "\n", "bullet")

            elif self._is_numbered_markdown_line(stripped):
                self._insert_markdown_inline(
                    text,
                    stripped,
                    base_tag="numbered",
                )
                text.insert(tk.END, "\n", "numbered")

            else:
                self._insert_markdown_inline(
                    text,
                    line,
                    base_tag="normal",
                )
                text.insert(tk.END, "\n", "normal")

        text.configure(state="disabled")

    def _insert_markdown_inline(
        self,
        text_widget: scrolledtext.ScrolledText,
        line: str,
        base_tag: str = "normal",
    ) -> None:
        """
        Insert a single Markdown line with simple inline formatting.

        Supports:
        - **bold**
        - `inline code`
        """
        i = 0

        while i < len(line):
            if line.startswith("**", i):
                end = line.find("**", i + 2)

                if end != -1:
                    bold_text = line[i + 2:end]
                    text_widget.insert(tk.END, bold_text, (base_tag, "bold"))
                    i = end + 2
                    continue

            if line.startswith("`", i):
                end = line.find("`", i + 1)

                if end != -1:
                    code_text = line[i + 1:end]
                    text_widget.insert(tk.END, code_text, (base_tag, "inline_code"))
                    i = end + 1
                    continue

            next_bold = line.find("**", i)
            next_code = line.find("`", i)

            candidates = [
                pos for pos in (next_bold, next_code)
                if pos != -1
            ]

            next_special = min(candidates) if candidates else len(line)

            text_widget.insert(
                tk.END,
                line[i:next_special],
                base_tag,
            )

            i = next_special

    @staticmethod
    def _is_numbered_markdown_line(line: str) -> bool:
        if "." not in line:
            return False

        number, _rest = line.split(".", 1)

        return number.isdigit()

    def _print_aerolog_upload_summary(
        self,
        flights: list[FlightDisplayRow],
    ) -> None:
        self.log_message("")
        self.log_message("Flights that would be sent to Aerolog:")

        header = (
            f"{'Sync Key':>8} "
            f"{'CS':8}"
            f"{'Registration':14}"
            f"{'PIC':36}"
            f"{'Takeoff':8}"
            f"{'From':10}"
            f"{'To':10}"
        )
        self.log_message(header)

        for idx, flight in enumerate(flights, start=1):
            tag = "even" if idx % 2 == 0 else "odd"

            pic = (
                f"{flight.pic_account or ''} "
                f"{flight.pic_name or ''}"
            ).strip()

            line = (
                f"{str(flight.sync_key or ''):>8} "
                f"{flight.callsign or '':8}"
                f"{flight.registration or '':14}"
                f"{pic[:36]:36}"
                f"{flight.takeoff_str():8}"
                f"{flight.airfield_takeoff or '':10}"
                f"{flight.airfield_landing or '':10}"
            )

            self.log_message(line, tag)

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


    def _get_version(self) -> str:
        return VERSION


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
        include_non_grl_sections: bool = True,
        error_style: bool = False,
    ) -> None:
        formatter = FlightTableFormatter(
            grl_only=False,
            group_by_launch_type=group_by_launch_type,
        )

        for line, tag in formatter.format_flights(
            flights_unsorted,
            title,
            notes_only=notes_only,
            group_by_launch_type=group_by_launch_type,
            include_non_grl_sections=include_non_grl_sections,
            include_non_grl_non_club=(
                self.list_non_club_non_grl_departures.get()
            ),
        ):
            if error_style:
                if tag == "even":
                    tag = "error_even"
                elif tag == "odd":
                    tag = "error_odd"
                else:
                    tag = "error"

            self.log_message(line, tag)

    def print_ga_notes(self, flights_unsorted: list[FlightDisplayRow]) -> None:
        formatter = FlightTableFormatter(
            grl_only=False,
            group_by_launch_type=False,
        )

        for line, tag in formatter.format_ga_notes(flights_unsorted):
            self.log_message(line, tag)

    def print_ga(self) -> None:
        if not self.ga:
            messagebox.showinfo("Print GA", "No Gliding.App flights to print.")
            return

        try:
            printer = GAPdfPrinter(
                save_to_file=self.print_to_file.get(),
                grl_only=False,
                group_by_launch_type=self.launch_sort.get(),
                include_non_grl_non_club=(
                    self.list_non_club_non_grl_departures.get()
                ),
            )

            output_path = printer.print_ga(
                self.ga,
                self.date_entry.get_date(),
            )

            if output_path is not None:
                self.log_message(f"Saved PDF to {output_path}")
            else:
                self.log_message("Sent Gliding.App PDF to printer")

        except Exception as exc:
            self.log_message("ERROR printing Gliding.App flights:")
            self.log_message(traceback.format_exc())
            messagebox.showerror("Print GA", f"Failed to output PDF:\n{exc}")

    def test_for_errors(self) -> None:
        if not self.ga:
            messagebox.showinfo(
                "Test for errors",
                "No Gliding.App flights loaded. Fetch flights first.",
            )
            return
        self.clear()
        self.print_test_for_errors()


    def print_test_for_errors(self) -> None:
        error_groups = self.service.test_for_errors(self.ga)

        ga_flights_planned_for_upload = (
            self._get_ga_flights_planned_for_aerolog_upload()
        )

        aircraft_error_lines = (
            self.service.aerolog_upload_aircraft_error_report(
                ga_flights_planned_for_upload
            )
        )

        self.log_message("")
        self.log_message("Possible Gliding.App errors", "error")

        if not error_groups and not aircraft_error_lines:
            self.log_message("No errors found.")
            return

        for heading, flights in error_groups.items():
            self.print_flights(
                flights,
                heading,
                group_by_launch_type=False,
                include_non_grl_sections=False,
                error_style=True,
            )

        if aircraft_error_lines:
            self.log_message("")

            for line in aircraft_error_lines:
                self.log_message(line, "error")

    def _get_ga_flights_planned_for_aerolog_upload(
        self,
    ) -> list[FlightDisplayRow]:
        formatter = FlightTableFormatter(
            grl_only=False,
            group_by_launch_type=False,
        )

        return formatter.filter_aerolog_upload_flights(
            self.ga,
            include_non_grl_club_departures=(
                self.include_non_grl_club_departures.get()
            ),
        )