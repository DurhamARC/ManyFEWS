import numpy as np
from datetime import date
import os
import sys

projectPath = os.path.abspath(
    os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../")
)
generateRiverFlowsPath = os.path.join(projectPath, "GenerateRiverFlows")
dataFileDirPath = os.path.join(projectPath, "Data")

sys.path.append(generateRiverFlowsPath)

import GenerateRiverFlows

t0 = date.toordinal(date(2010, 1, 1)) + 366


GefsDataFile = os.path.join(dataFileDirPath, "GEFSdata.xlsx")
sheetNum = 16
gefsData = GenerateRiverFlows.excel_to_matrix(GefsDataFile, sheetNum)
InitialConditionFilePath = os.path.join(
    dataFileDirPath, "RainfallRunoffModelInitialConditions.csv"
)
parametersFilePath = os.path.join(dataFileDirPath, "RainfallRunoffModelParameters.csv")
F0 = np.loadtxt(open(InitialConditionFilePath), delimiter=",", usecols=range(3))
riverFlowsData = GenerateRiverFlows.GenerateRiverFlows(
    t0, gefsData, F0, parametersFilePath
)

# "riverFlowsData" is a data tuple, which:
# riverFlowsData[0] ====> Q
# riverFlowsData[1] ====> t
# riverFlowsData[2] ====> qp
# riverFlowsData[3] ====> Ep

# print(riverFlowsData[0])
