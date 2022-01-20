import numpy as np
from datetime import date
import GenerateRiverFlows


t0 = date.toordinal(date(2010, 1, 1)) + 366
# GefsDataFile = u'/Users/abeltu/Desktop/GenerateRiverFlows/GEFSdata.xlsx'
GefsDataFile = u"./GEFSdata.xlsx"
sheetNum = 16
gefsData = GenerateRiverFlows.excel_to_matrix(GefsDataFile, sheetNum)

# Import initial conditions for 100 models
# InitialConditionFile = '/Users/abeltu/Desktop/GenerateRiverFlows/RainfallRunoffModelInitialConditions.csv'

InitialConditionFile = u"./RainfallRunoffModelInitialConditions.csv"
F0 = np.loadtxt(open(InitialConditionFile), delimiter=",", usecols=range(3))
riverFlowsData = GenerateRiverFlows.GenerateRiverFlows(t0, gefsData, F0)

# "riverFlowsData" is a data tuple, which:
# riverFlowsData[0] ====> Q
# riverFlowsData[1] ====> F0
# riverFlowsData[2] ====> t
# riverFlowsData[3] ====> qp
# riverFlowsData[1] ====> Ep
Q = riverFlowsData[1]
print(Q)