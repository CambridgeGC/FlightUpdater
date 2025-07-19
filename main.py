import tkinter as tk
from flight_gui import FlightUpdaterApp
import config


if __name__ == '__main__':
    # Verify configuration
    if config.API_TOKEN.startswith('<'):
        print('Please set your API token in environment variable FLIGHT_API_TOKEN or edit main.py')
        exit(1)

    root = tk.Tk()
    app = FlightUpdaterApp(root, api_token=config.API_TOKEN, aerolog_path=config.AEROLOG_PATH)
    root.mainloop()
