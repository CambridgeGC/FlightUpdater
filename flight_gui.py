import os
import sys
import tkinter as tk
import tempfile
import threading
from datetime import datetime

from tkinter import ttk, scrolledtext, filedialog
from tkcalendar import DateEntry

from flight_fetcher import FlightFetcher
from flight_matcher import compare_sources, compare_reverse

from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus   import Paragraph, Spacer

import config

class FlightUpdaterApp:
    def __init__(self, root, api_token, aerolog_path):
        # Initialize data storage
        self.ga = []
        self.kt = []
        self.az = []

        # Track whether to include tows
        self.include_tows = tk.BooleanVar(value=False)

        # Track whether to sort by 
        self.launch_sort = tk.BooleanVar(value=True)        

        # FlightFetcher instance
        self.fetcher = FlightFetcher(api_token, aerolog_path)

        # Window setup
        root.title('Flight Updater '+ config.VERSION)
        root.geometry('1900x1000')

        # Date selector + Fetch button frame
        top_frame = ttk.Frame(root)
        top_frame.pack(padx=10, pady=5, anchor='w')

        ttk.Label(top_frame, text='Date:').grid(row=0, column=0, sticky='w')
        self.date_entry = DateEntry(top_frame, date_pattern='yyyy-MM-dd')
        self.date_entry.grid(row=0, column=1, padx=(5, 15))

        # Fetch button on same row
        self.compare_btn = ttk.Button(top_frame, text='Fetch and Compare', command=self.start)
        self.compare_btn.grid(row=0, column=2, sticky='w', padx=(5, 15))


        # Load Aerolog button on same row
        self.loadaerolog_btn = ttk.Button(top_frame, text='Load Aerolog with Gliding.App flights', command=self.loadaerolog)
        self.loadaerolog_btn.grid(row=0, column=3, sticky='w', padx=(5, 15))

        # Controls frame for Browse and List GA
        ctrl_frame = ttk.Frame(root)
        ctrl_frame.pack(padx=10, pady=(10,0), anchor='w')

        self.listktrax_btn = ttk.Button(ctrl_frame, text='List Ktrax', command=self.listktrax)
        self.listktrax_btn.pack(side='left', padx=(0, 10))

        self.listga_btn = ttk.Button(ctrl_frame, text='List GA', command=self.listga)
        self.listga_btn.pack(side='left', padx=(0, 10))

        self.clear_btn = ttk.Button(ctrl_frame, text='Clear', command=self.clear)
        self.clear_btn.pack(side='left', padx=(0, 10))

        # ← NEW: Print GA button
        self.print_btn = ttk.Button(ctrl_frame, text='Print GA', command=self.print_ga)
        self.print_btn.pack(side='left', padx=(5, 15))

        # Include Tows checkbox 
        ttk.Checkbutton(ctrl_frame, text='Include tows', variable=self.include_tows) \
            .pack(side='left', padx=(10,0))

        # Include Tows checkbox 
        ttk.Checkbutton(ctrl_frame, text='Sort by Launch Type', variable=self.launch_sort) \
            .pack(side='left', padx=(10,0))
        
        # Log area
        self.log_widget = scrolledtext.ScrolledText(root, state='disabled')
        self.log_widget.pack(fill='both', expand=True, padx=10, pady=10)

        # Configure alternating row colors
        self.log_widget.tag_configure('even', background='white')
        self.log_widget.tag_configure('odd', background='#f0f0f0')

    def log_message(self, msg, tag=None):
        """
        Append a message to the log area, optionally with a tag for styling.
        """
        self.log_widget.configure(state='normal')
        if tag:
            self.log_widget.insert(tk.END, msg + '\n', tag)
        else:
            self.log_widget.insert(tk.END, msg + '\n')
        self.log_widget.see(tk.END)
        self.log_widget.configure(state='disabled')

    def print_ga(self):
        """Generate a landscape PDF of GA flights grouped by launch type and sorted by takeoff time, then send to printer."""
        if not self.ga:
            messagebox.showinfo("Print GA", "No GlidingApp flights to print.")
            return

        # Prepare ReportLab document
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        tmp.close()
        doc = SimpleDocTemplate(
            tmp.name,
            pagesize=landscape(A4),
            leftMargin=20, rightMargin=20,
            topMargin=20, bottomMargin=20
        )

        styles = getSampleStyleSheet()
        story = []
        # group heading
        story.append(Paragraph("Gliding.App Flights", styles['Heading2']))
        story.append(Spacer(1, 6))

        groups = ['tow', 'winch', 'tug', 'tmg', 'other']
        for grp in groups:
            # filter subset
            if grp == 'other':
                subset = [
                    f for f in self.ga
                    if (f.get('launch_type') or '').lower() not in groups[:-1]
                ]
            else:
                subset = [
                    f for f in self.ga
                    if (f.get('launch_type') or '').lower() == grp
                ]

            if not subset:
                continue

            # sort by takeoff time
            def _parse_takeoff(rec):
                t = rec.get('takeoff') or ''
                try:
                    return datetime.strptime(t, '%H:%M').time()
                except:
                    return datetime.min.time()
            subset.sort(key=_parse_takeoff)

            # group heading
            story.append(Paragraph(f"{grp.upper()} Flights", styles['Heading3']))
            story.append(Spacer(1, 6))

            # build table data
            data = [[
                'Date','Aircraft','Takeoff','Landing',
                'P1 no', 'P1 name', 'P2 no', 'P2 name','Payer', 'Pax', 'Tow','Height'
            ]]
            for f in subset:
                launch = (f.get('launch_type') or '').lower()
                if launch in ('tug', 'tow'):
                    try:
                        height_str = str(f.get('height') or '')
                    except (TypeError, ValueError):
                        height_str = ''
                else:
                    height_str = ''

                row = [
                    f.get('flight_date',''),
                    f.get('cn',''),
                    f.get('takeoff',''),
                    f.get('landing',''),
                    f.get('pic_account',''),
                    f.get('pic_name',''),
                    f.get('p2_account',''),
                    f.get('p2_name',''),
                    f.get('payer_account',''),
                    f.get('other_name', ''),
                    f.get('tow_cn',''),
                    height_str
                ]
                data.append(row)

            tbl = Table(data, repeatRows=1)
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
                ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ]))

            story.append(tbl)
            story.append(Spacer(1, 12))

        # build and print
        doc.build(story)
        try:
            if sys.platform.startswith('win'):
                os.startfile(tmp.name, "print")
            else:
                # Linux/macOS: requires lpr/CUPS configured
                os.system(f"lpr {tmp.name}")
        except Exception as e:
            messagebox.showerror("Print GA", f"Failed to send to printer:\n{e}")


    def print_flights(self, flights_unsorted, title, inc_tows=True, notes_only=False, group_by_launch_type = False):
        """
        Display flights list with alternating background colors, optionally grouping by launch type.
        """
        # Sort flights by 'takeoff' field (empty or None values become '')
        flights = sorted(
            flights_unsorted,
            key=lambda f: f.get('takeoff') or ''
        )
           
        # Prepare header line
        header = (
            f"{'Seq':4}{'Date':12}{'Launch':8}{'Aircraft':10}{'Takeoff':8}{'Landing':8}"
            f"{'P1':36}{'P2':36}{'Payer':6}{'Other name':15}{'Tow':8}{'Height':8}{'Notes':50}{'Source':6}"
        )

        # If grouping by launch type
        if group_by_launch_type:
            groups = ['tow', 'winch', 'tug', 'tmg', 'other']
            for group in groups:
                if group == 'other':
                    subset = [f for f in flights if (f.get('launch_type') or '').lower() not in groups]
                else:
                    subset = [f for f in flights if (f.get('launch_type') or '').lower() == group]
                if group == 'tug' and not inc_tows:
                    continue
                if not subset:
                    continue

                # Group header
                self.log_message('')
                self.log_message(f"--- {group.upper()} Flights ---")
                self.log_message(header)

                idx = 0
                for f in subset:
                    idx += 1
                    tag = 'even' if idx % 2 == 0 else 'odd'

                    pic_ac = f.get('pic_account') or ''
                    pic_nm = f.get('pic_name') or ''
                    p2_ac = f.get('p2_account') or ''
                    p2_nm = f.get('p2_name') or ''
                    pay_ac = f.get('payer_account') or ''
                    tow_cn = f.get('tow_cn') or ''
                    launch = (f.get('launch_type') or '').lower()
                    note_str = f"{f.get('note',''):50}" if f.get('note') else ''

                    # Height logic
                    if launch in ('tug', 'tow'):
                        try:
                            height_str = str(f.get('height') or '')
                        except (TypeError, ValueError):
                            height_str = ''
                    else:
                        height_str = ''

                    line = (
                        f"{(f.get('seq_no') or ''):3} "
                        f"{(f.get('flight_date') or ''):12}"
                        f"{(f.get('launch_type') or ''):8}"
                        f"{(f.get('cn') or ''):10}"
                        f"{(f.get('takeoff') or ''):8}"
                        f"{(f.get('landing') or ''):8}"
                        f"{pic_ac:6}"
                        f"{pic_nm:30}"
                        f"{p2_ac:6}"
                        f"{p2_nm:30}"
                        f"{pay_ac:6}"
                        f"{(f.get('other_name') or ''):15}"
                        f"{tow_cn:8}"
                        f"{height_str:8}"
                        f"{note_str:50}"
                        f"{(f.get('source') or ''):6}"
                    )
                    if not notes_only or note_str:
                        self.log_message(line, tag)
            return

        # Default: no grouping
        self.log_message('')
        self.log_message(title)
        self.log_message(header)

        idx = 0
        for f in flights:
            if inc_tows or (f.get('launch_type') or '').lower() != 'tug':
                idx += 1
                tag = 'even' if idx % 2 == 0 else 'odd'

                pic_ac = f.get('pic_account') or ''
                pic_nm = f.get('pic_name') or ''
                p2_ac = f.get('p2_account') or ''
                p2_nm = f.get('p2_name') or ''
                pay_ac = f.get('payer_account') or ''
                tow_cn = f.get('tow_cn') or ''
                launch = (f.get('launch_type') or '').lower()
                note_str = f"{f.get('note',''):50}" if f.get('note') else ''

                if launch in ('tug', 'tow'):
                    try:
                        height_str = str(f.get('height') or '')
                    except (TypeError, ValueError):
                        height_str = ''
                else:
                    height_str = ''

                line = (
                    f"{(f.get('seq_no') or ''):3} "
                    f"{(f.get('flight_date') or ''):12}"
                    f"{(f.get('launch_type') or ''):8}"
                    f"{(f.get('cn') or ''):10}"
                    f"{(f.get('takeoff') or ''):8}"
                    f"{(f.get('landing') or ''):8}"
                    f"{pic_ac:6}"
                    f"{pic_nm:30}"
                    f"{p2_ac:6}"
                    f"{p2_nm:30}"
                    f"{pay_ac:6}"
                    f"{(f.get('other_name') or ''):15}"
                    f"{tow_cn:8}"
                    f"{height_str:8}"
                    f"{note_str:50}"
                    f"{(f.get('source') or ''):6}"
                )
                if not notes_only or note_str:
                    self.log_message(line, tag)

    def open_file(self):
        """
        Ask user to select an Aerolog Excel file.
        """
        path = filedialog.askopenfilename(filetypes=[('Excel', '*.xlsx;*.xls')])
        if path:
            self.fetcher.aerolog_path = path

    def start(self):
        """
        Trigger fetch and comparison in background.
        """
        self.compare_btn.config(state='disabled')
        self.listga_btn.config(state='disabled')
        self.loadaerolog_btn.config(state='disabled')
        self.clear_btn.config(state='disabled')
        self.listktrax_btn.config(state='disabled')                
        self.log_widget.configure(state='normal')
        self.log_widget.delete('1.0', tk.END)
        self.log_widget.configure(state='disabled')
        threading.Thread(target=self.run, daemon=True).start()

    def listga(self):
        """
        Show fetched GlidingApp flights.
        """
        self.print_flights(self.ga, "All GlidingApp flights", self.include_tows.get(), group_by_launch_type = self.launch_sort.get())

    def listktrax(self):
        """
        Show fetched GlidingApp flights.
        """
        self.print_flights(self.kt, "All Ktrax flights", self.include_tows.get(), group_by_launch_type = self.launch_sort.get())


    def clear(self):
        # Allow changes to the text
        self.log_widget.configure(state='normal')
        # Delete everything
        self.log_widget.delete('1.0', tk.END)
        # Prevent the user from typing into it
        self.log_widget.configure(state='disabled')
    

    def loadaerolog(self): # holder for aerolog when I have the API
        pass 

    def count_types_of_flight(self, flights):
        tow = winch = tug = tmg = other = 0
        for flight in flights:
            lt = flight.get('launch_type')
            if lt == 'tow':
                tow += 1
            elif lt == 'winch':
                winch += 1
            elif lt == 'tug':
                tug += 1
            elif lt == 'tmg':
                tmg += 1
            else:
                other += 1
        total = tow + winch + tug + tmg + other
        return tow, winch, tug, tmg, other, total

    def run(self):
        """
        Fetch flights, compare sources, and log results.
        """
        date_str = self.date_entry.get_date().strftime('%Y-%m-%d')
        self.ga = self.fetcher.fetch_glidingapp(date_str)
        self.kt = self.fetcher.fetch_ktrax(date_str)
        # self.az = self.fetcher.fetch_aerolog(date_str)

        # Compare
        kt_not_ga = compare_reverse(self.kt, self.ga)
        ga_not_kt = compare_reverse(self.ga, self.kt)
        self.log_message(f"Flights which are in Ktrax but not in GlidingApp: {len(kt_not_ga)} flights")
        self.log_message(f"Flights which are in GlidingApp but not in Ktrax: {len(ga_not_kt)} flights")
        self.log_message('')

        ga_tow, ga_winch, ga_tug, ga_tmg, ga_other, ga_total = self.count_types_of_flight(self.ga)
        kt_tow, kt_winch, kt_tug, kt_tmg, kt_other, kt_total = self.count_types_of_flight(self.ga)
        header = (
            f"{'Source':15}"
            f"{'Tows':>10}"
            f"{'Winch':>10}"
            f"{'Tug':>10}"
            f"{'TMG':>10}"
            f"{'Other':>10}"
            f"{'Total':>10}"
        )

        self.log_message(header)

        line = (
            f"{'Gliding.App':15}"
            f"{ga_tow:>10}"
            f"{ga_winch:>10}"
            f"{ga_tug:>10}"
            f"{ga_tmg:>10}"
            f"{ga_other:>10}"
            f"{ga_total:>10}"
        )
        self.log_message(line)
        line = (
            f"{'Ktrax':15}"
            f"{kt_tow:>10}"
            f"{kt_winch:>10}"
            f"{kt_tug:>10}"
            f"{kt_tmg:>10}"
            f"{kt_other:>10}"
            f"{kt_total:>10}"
        )
        self.log_message(line)

        # miss_kt = compare_sources(self.az, self.kt)
        # miss_ga = compare_sources(self.az, self.ga)
        # rev_kt  = compare_reverse(self.kt, self.az)
        # rev_ga  = compare_reverse(self.ga, self.az)

        self.log_message('')
        # self.log_message(f"Aerolog vs Ktrax: {len(miss_kt)} missing")
        # self.log_message(f"Aerolog vs GlidingApp: {len(miss_ga)} missing")
        # self.log_message(f"Ktrax vs Aerolog: {len(rev_kt)} missing")
        # self.log_message(f"GlidingApp vs Aerolog: {len(rev_ga)} missing")

        # Detailed rows
        if kt_not_ga:
            self.print_flights(kt_not_ga, "Flights in Ktrax but not in Gliding.App", group_by_launch_type = False)
        if ga_not_kt:
            self.print_flights(ga_not_kt, "Flights in Gliding.App but not in Ktrax", group_by_launch_type = False)
        self.print_flights(self.ga, "GA flights with notes", notes_only=True)

        # Re-enable controls on main thread
        self.log_widget.after(0, lambda: [
            self.compare_btn.config(state='normal'),
            self.listga_btn.config(state='normal'),
            self.listktrax_btn.config(state='normal'),
            self.clear_btn.config(state='normal'),
            self.loadaerolog_btn.config(state='normal')
        ])

if __name__ == '__main__':
    import os
    root = tk.Tk()
    API_TOKEN   = os.getenv('FLIGHT_API_TOKEN', '<YOUR_TOKEN>')
    AEROLOG_PATH= os.getenv('AEROLOG_PATH', 'Flights.xlsx')
    app = FlightUpdaterApp(root, api_token=API_TOKEN, aerolog_path=AEROLOG_PATH)
    root.mainloop()
