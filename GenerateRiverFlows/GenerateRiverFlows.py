"""
This python script is converted from Professor Simon Mathias (Professor of Environmental Engineering).
                                                            Created by Jiada Tu
                                                            13/01/2022
"""
import numpy as np

def GenerateRiverFlows( t0, GEFSdata, F0):
    """
    Generates 100 river flow time-series for one realisation of GEFS weather data.
    
    Outputs:
    Q - River flow (m3/s)
    F0 - Updated initial conditions for next time-sequence
    t - Times (days)
    qp - Rainfall (mm/day)
    Ep - Potential evapotranspiration (mm/day)
    t0 - Start time of GEFS data (day)

    Inputs:
    GEFSdata - Contains one realisation of GEFS data
    F0 - Initial conditions for state variables

    The GEFS data array contains the following items:
    Column 1 RH (%)	
    Column 2 TempMax (K)	
    Column 3 TempMin (K)	
    Column 4 10 metre U wind (m/s)	
    Column 5 10 metre V wind (m/s)	
    Column 6 precip (mm)	
    Column 7 energy (J/kg)
    """

    # Specify time-step in days
    dt = 0.25;

    # Determine number of data points
    N = np.size(GEFSdata,1);

