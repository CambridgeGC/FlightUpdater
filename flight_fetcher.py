import requests
from datetime import datetime
import pandas as pd

# Mapping of raw callsigns to canonical identifiers
aircraft_mapping = {
    'GBODU': 'G-BODU',
    'DU': 'G-BODU',
    'SB': 'TUG SB',
    'GC': 'TUG GC',
    'GELSB': 'TUG SB',
    'GOCGC': 'TUG GC'
}

class FlightFetcher:
    def __init__(self, api_token, aerolog_path, base_url, ktrax_id='GRANSDEN LODGE', tz='1'):
        self.aerolog_path = aerolog_path
        self.ktrax_id = ktrax_id
        self.tz = tz
        self.gliding_url = base_url + '/flights.json'
        self.ktrax_url = 'https://ktrax.kisstech.ch/backend/logbook'
        self.headers = {
            'X-API-KEY': api_token,
            'Accept': 'application/json'
        }

    def fetch_glidingapp(self, date_str):
        params = {'date': date_str}
        resp = requests.get(self.gliding_url, headers=self.headers, params=params)
        resp.raise_for_status()
        return self._normalize_glidingapp(resp.json())

    def _normalize_glidingapp(self, raw):
        flights = []
        _launch_map = {
            'sep-a': 'tug',
            'sleep': 'tow',
            'lier': 'winch',
            'sep':   'tug', # should be sep but gliding.app being inconsistent about when it has this and sep-a
            'tmg':   'tmg'
            }
        for f in raw:
            tow_cn = tow_takeoff = tow_height = None
            tow_uuid = f.get('sleep_uuid')
            if tow_uuid:
                tow = next((x for x in raw if x.get('uuid') == tow_uuid), None)
                if tow:
                    tow_cn = aircraft_mapping.get(str(tow.get('callsign','')).upper(), tow.get('callsign',''))
                    tow_height = tow.get('height')
            cn = aircraft_mapping.get(str(f.get('callsign','')).upper(), f.get('callsign',''))
            flights.append({
                'uuid': f.get('uuid'),
                'seq_no': f.get('volg_nummer'),
                'flight_date':  f.get('datum'),
                'launch_type': _launch_map.get(f.get('start_methode'), f.get('start_methode')),
                'cn':           cn,
                'takeoff':      f.get('start_tijd'),
                'landing':      f.get('landings_tijd'),
                'pic_account':  f.get('pic_m_id'),
                'pic_name':     f.get('gezagvoerder_naam'),
                'p2_account':   f.get('second_pilot_m_id'),
                'p2_name':      f.get('tweede_inzittende_naam'),
                'payer_account':    f.get('paying_pilot_m_id'),
                'tow_cn':       tow_cn,
                'tow_takeoff':  tow_takeoff,
                'height':       None if tow_height in (None, '') else int(round((float(tow_height) * 3.28084 - 254) / 100) * 100),
                'note':         f.get('bijzonderheden'),
                'other_name': '' if f.get('category') == 'other' else f.get('category'),
                'source':       'GA'
            })
        return flights

    def fetch_ktrax(self, date_str):
        params = {
            'query_type': 'ap',
            'id':         self.ktrax_id,
            'tz':         self.tz,
            'dbeg':       date_str,
            'dend':       date_str
        }
        _launch_map = {
            'S': 'tug',
            'T': 'tow',
            'W': 'winch',
        }

        resp = requests.get(self.ktrax_url, params=params)
        resp.raise_for_status()
        data    = resp.json()
        sorties = data.get('sorties', data)
        flights = []

        seq_no = 0
        for f in sorties:
            # default to no tow
            tow_cn  = None
            tow_alt = None
            seq_no = seq_no+1
            tow_seq = f.get('tow_seq')
            if tow_seq is not None:
                # match on 'seq' (not 'uuid')
                tow = next((x for x in sorties if x.get('seq') == tow_seq), None)
                if tow:
                    # map the tow aircraft callsign
                    callsign = str(tow.get('callsign','')).upper()
                    tow_cn   = aircraft_mapping.get(callsign, callsign)
                    # raw altitude (meters)
                    tow_alt  = tow.get('dalt')

            # now map the glider aircraft callsign
            callsign = str(f.get('cn','')).upper()
            cn       = aircraft_mapping.get(callsign, f.get('cn'))

            # compute height in feet (rounded to 100), or None
            if tow_alt not in (None, '', 0):
                try:
                    feet     = float(tow_alt) * 3.28084
                    adj      = feet # these already appear to be AGL
                    height   = int(round(adj / 100) * 100)
                except (TypeError, ValueError):
                    height = None
            else:
                height = None

            flights.append({
                'uuid':        f.get('seq'),
                'seq_no':      seq_no,
                'flight_date': f.get('date'),
                'launch_type': _launch_map.get(f.get('launch'), f.get('launch')),
                'cn':          cn,
                'takeoff':     f.get('tkof',{}).get('time'),
                'landing':     f.get('ldg',{}).get('time'),
                'tow_cn':      tow_cn,
                'height':      height,
                'source':      'KT'
            })

        return flights


    def fetch_aerolog(self, date_str):
        xl = pd.ExcelFile(self.aerolog_path)
        df = xl.parse('Flight log enquiry', skiprows=4)
        df['FLIGHT DATE'] = pd.to_datetime(df['FLIGHT DATE']).dt.date
        target = datetime.strptime(date_str, '%Y-%m-%d').date()
        df = df[df['FLIGHT DATE'] == target]
        flights = []
        for _, r in df.iterrows():
            cn = aircraft_mapping.get(str(r['AIRCRAFT']).upper(), r['AIRCRAFT'])
            tow = aircraft_mapping.get(str(r['TUG']).upper(), r['TUG'])
            flights.append({
                'uuid': r['SEQ'],
                'cn': cn,
                'takeoff': r['TIME UP'].strftime('%H:%M'),
                'landing': r['TIME DOWN'].strftime('%H:%M'),
                'tow_cn': tow,
                'source': 'AL'
            })
        return flights
