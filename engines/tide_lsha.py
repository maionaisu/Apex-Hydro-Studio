import pandas as pd
import numpy as np
from utils.math_accel import calculate_lsha

class TideAnalyzerEngine:
    @staticmethod
    def extract_harmonics(df, col_time, col_z):
        """
        Parses time-series water elevation and runs LSHA.
        Returns a dictionary of constituents and MSL.
        """
        df_clean = df.dropna(subset=[col_time, col_z]).copy()
        df_clean['parsed_time'] = pd.to_datetime(df_clean[col_time], errors='coerce', infer_datetime_format=True)
        df_clean = df_clean.dropna(subset=['parsed_time']).sort_values('parsed_time')
        
        if len(df_clean) < 24:
            raise ValueError("Data elevasi pasang surut tidak memadai (< 24 jam).")
            
        t_hours = (df_clean['parsed_time'] - df_clean['parsed_time'].iloc[0]).dt.total_seconds().values / 3600.0
        z = pd.to_numeric(df_clean[col_z], errors='coerce').fillna(0).values
        
        # Standard Tidal Constituents (Angular frequencies in rad/hour)
        freqs = {
            'M2': 0.505868, 'S2': 0.523599, 'N2': 0.496367, 
            'K1': 0.262516, 'O1': 0.243352, 'P1': 0.261083, 
            'SA': 0.000114, 'SSA': 0.000228
        }
        
        # Fast execution via Numba-accelerated logic
        res = calculate_lsha(t_hours, z, freqs)
        
        msl = res[0]
        constituents = {}
        
        for i, name in enumerate(freqs.keys()):
            A_c = res[1 + 2*i]
            A_s = res[2 + 2*i]
            
            amp = np.sqrt(A_c**2 + A_s**2)
            phase = np.degrees(np.arctan2(A_s, A_c)) % 360
            
            constituents[name] = {'amp': amp, 'pha': phase}
            
        return msl, constituents
