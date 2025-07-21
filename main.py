import tkinter as tk
from flight_gui import FlightUpdaterApp
import config


if __name__ == '__main__':
    root = tk.Tk()
    app = FlightUpdaterApp(root)
    root.mainloop()
