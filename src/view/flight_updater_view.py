import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import traceback
from pathlib import Path
from tkcalendar import DateEntry

from model.flight_display_row import FlightDisplayRow
from services.flight_comparison_service import find_unmatched

from view.flight_table_formatter import FlightTableFormatter
from view.ga_pdf_printer import GAPdfPrinter

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
        formatter = FlightTableFormatter(
            grl_only=self.grl_only.get(),
            group_by_launch_type=group_by_launch_type,
        )

        for line, tag in formatter.format_flights(
            flights_unsorted,
            title,
            notes_only=notes_only,
            group_by_launch_type=group_by_launch_type,
        ):
            self.log_message(line, tag)


    def print_ga_notes(self, flights_unsorted: list[FlightDisplayRow]) -> None:
        formatter = FlightTableFormatter(
            grl_only=self.grl_only.get(),
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
                grl_only=self.grl_only.get(),
                group_by_launch_type=self.launch_sort.get(),
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