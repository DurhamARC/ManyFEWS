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
from datetime import date
import math


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
    datamatrix = np.delete(datamatrix, 0, axis=0) # Delete the first blank line.(Its elements are all zero)
    return datamatrix

GefsDataFile = u'/Users/abeltu/Desktop/GenerateRiverFlows/GEFSdata.xlsx'
sheetNum = 16
gefsData = excel_to_matrix(GefsDataFile,sheetNum)

# Import initial conditions for 100 models
InitialConditionFile = '/Users/abeltu/Desktop/GenerateRiverFlows/RainfallRunoffModelInitialConditions.csv'
F0 = np.loadtxt(open(InitialConditionFile), delimiter=',', usecols=range(3))

# def GenerateRiverFlows( t0, gesfData, F0):
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
N = np.size(gefsData[:,1])

# Specify date-time in days of each data point
t = t0 + np.arange(0,(N/4 - dt),dt)

# Get relative humidity (%)
RH = gefsData[:,0]

# Convert temperature to deg C
TempMax = gefsData[:,1] - 273.15
TempMin = gefsData[:,2] - 273.15

# Estimate average temperature
T = (TempMin+TempMax)/2

# Determine daily minimum temperature of each hour
MinTemPerHour = np.array(TempMin).reshape(16, 4).min(axis=1) #Min Temperature of each hour(at 4 time points).
Tmin = np.repeat(MinTemPerHour,4)

# Determine daily maximum temperature of each hour
MaxTemPerHour = np.array(TempMax).reshape(16, 4).max(axis=1) #Max Temperature of each hour(at 4 time points).
Tmax = np.repeat(MaxTemPerHour,4)

# Determine magnitude of wind speed at 10 m
u10 = np.sqrt((gefsData[:,3])**2 + (gefsData[:,4])**2)

# Estimate wind speed at 2 m
z0 = 0.006247 # m(surface roughness equivalent to FAO56 reference crop)
z2 = 2 # m
z10 = 10 # m
u0 = 0 # m/s
uTAU = ((u10-u0)/2.5) / (math.log(z10/z0))
u2 = 2.5 * uTAU * (math.log(z2/z0)) + u0

# Extract precipitation data (mm)
precip = gefsData[:,5]

# Convert preiciptation to (mm/day)
qp = precip / dt

# Details specific for Majalaya catchment
lat = -7.125 # mean latutude (degrees)
alt = 1157 # mean altitude (m above sea level)
CatArea = 212.2640 # Catchment area (km2)

# Get model parameters for Majalaya catchment
parametersFile = '/Users/abeltu/Desktop/GenerateRiverFlows/RainfallRunoffModelParameters.csv'
X = np.loadtxt(open(parametersFile), delimiter=',', usecols=range(4))

    # Determine reference crop evapotranspiration (mm/day)
#    Ep = FAO56(t,Tmin,Tmax,alt,lat,T,u2,RH,[])

    # Determine flow rate, Q (m3/s)
#    Q = ModelFun(qp,Ep,dt,CatArea,X,F0)

#    return Eq, Q




#####################################################
# def FAO56(t, Tmin, Tmax, alt, lat, T, u2, RH, Rs):

# Ensure Tmax > Tmin
sumTem = np.vstack((Tmax,Tmin))
Tmax = np.amax(sumTem, axis = 0)
Tmin = np.amin(sumTem, axis = 0)

# u2 (m/s)
# P (kPa)
# ea (kPa)
# Rn (MJ/m2/day)

try:
    T = T
except NameError:
    T = (Tmin+Tmax)/2

# This is based on FAO56 Example 20 for the estimation of evapotranspiration
try:
    u2 = u2
except NameError:
    u2 = np.zeros(np.shape(T)) # create an undefined array
    u2[:] = 2 # Assume wind speed of 2 m/s

# Slope of saturation curve (Del) from Eq. 13
Del = (4098*(0.6108*(np.exp(((17.27 * T) / (T + 237.3)))))) / np.square(T + 237.3)

# Atmospheric pressure (P) from Eq. 7
P = 101.3 * (math.pow(((293-0.0065 * alt) / 293), 5.26))

# Psychrimetric constant (gam) from Eq. 8
cp = 1.013e-3
lam = 2.45
eps = 0.622
gam = ((cp * P) / eps) / lam

# Saturation vapor pressure (eo) at Tmax and Tmin from Eq. 11
eoTmax = 0.6108 * (np.exp((17.27 * Tmax) / (Tmax + 237.3)))
eoTmin = 0.6108 * (np.exp((17.27 * Tmin) / (Tmin + 237.3)))
eo = 0.6108 * (np.exp((17.27 * T) / (T + 237.3)))

# Assume saturation vapor pressure is mean
es = (eoTmax+eoTmin) / 2


"""
if isempty(RH)
    %Dewpoint temperature (Tdew) from Eq. 48
    Tdew=Tmin; %This might need to be increased for tropical conditions SAM 14/09/2019
    %Actual vapour pressure (ea) from Eq. 14
    ea=0.6108*exp(17.27*Tdew./(Tdew+237.3));
else
    ea=RH/100.*es;
end
"""