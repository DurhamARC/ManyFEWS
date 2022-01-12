"""
This python script is converted from Professor Simon Mathias(Professor of Environmental Engineering)'s
script, which is used to generate river flows.
                                                            Created by Jiada Tu
                                                            13/01/2022
"""


# WARNING： The latest version of xlrd only supports .xls files.
# Installing the older version 1.2.0 worked for me to open .xlsx files.

import numpy as np
import xlrd
import csv
from datetime import date

# here is converted from part of "GenerateRiverFlowsExample.m", which is used to read data from csv and xlsx files.
# Specify start time
t0 = date.toordinal(date(2010,1,1))+366

# Import GEFS weather data. (please notice here, the start sheet‘s number is "0")
def excel_to_matrix(path, sheetNum):
    table = xlrd.open_workbook(path).sheets()[sheetNum]
    row = table.nrows
    col = table.ncols
    datamatrix = np.zeros((row, col)) # ignore the first title row.
    for x in range(1,row):
        row = np.matrix(table.row_values(x))
        datamatrix[x, :] = row
    datamatrix = np.delete(datamatrix, 0, axis=0)
    return datamatrix

datafile = u'/Users/abeltu/Desktop/GenerateRiverFlows/GEFSdata.xlsx'
sheetNum = 0
gefsData = excel_to_matrix(datafile,sheetNum)

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
    dt = 0.25

    # Determine number of data points
    N = np.size(GEFSdata,1)

    # Specify date-time in days of each data point


