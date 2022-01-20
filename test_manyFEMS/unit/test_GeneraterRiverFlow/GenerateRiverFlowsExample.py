import numpy as np
from datetime import date
import os
import sys

projectPath = os.path.abspath(os.path.join((os.path.split(os.path.realpath(__file__))[0]), '../../../'))
generateRiverFlowsPath = os.path.join(projectPath, 'GenerateRiverFlows')

sys.path.append(generateRiverFlowsPath)
import GenerateRiverFlows

t0 = date.toordinal(date(2010, 1, 1)) + 366


GefsDataFile = os.path.join(generateRiverFlowsPath, 'GEFSdata.xlsx')
sheetNum = 16
gefsData = GenerateRiverFlows.excel_to_matrix(GefsDataFile, sheetNum)



InitialConditionFilePath = os.path.join(generateRiverFlowsPath, 'RainfallRunoffModelInitialConditions.csv')
parametersFilePath = os.path.join(generateRiverFlowsPath, 'RainfallRunoffModelParameters.csv')
F0 = np.loadtxt(open(InitialConditionFilePath), delimiter=",", usecols=range(3))
riverFlowsData = GenerateRiverFlows.GenerateRiverFlows(t0, gefsData, F0, parametersFilePath)

# "riverFlowsData" is a data tuple, which:
# riverFlowsData[0] ====> Q
# riverFlowsData[1] ====> F0
# riverFlowsData[2] ====> t
# riverFlowsData[3] ====> qp
# riverFlowsData[1] ====> Ep
Q = riverFlowsData[1]
print(Q)