import os
import sys
import numpy as np

projectPath = os.path.abspath(
    os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../../")
)
generateRiverFlowsPath = os.path.join(projectPath, "GenerateRiverFlows")
dataFileDirPath = os.path.join(projectPath, "Data")
sys.path.append(generateRiverFlowsPath)

from GenerateRiverFlowsExample import riverFlowsData


def test_GenerateRiverFlows():
    # import the output result of 'GenerateRiverFlows' python code.
    Q = riverFlowsData[0]
    qp = riverFlowsData[1]
    Ep = riverFlowsData[2]
    F0 = riverFlowsData[3]

    # import benchmark result of 'GenerateRiverFlows.m' matlab code.
    Qbenchmark = np.loadtxt(
        open(os.path.join(dataFileDirPath, "Q_Benchmark.csv")),
        delimiter=",",
        usecols=range(100),
    )
    F0benchmark = np.loadtxt(
        open(os.path.join(dataFileDirPath, "F0_Benchmark.csv")), usecols=range(3),
    )
    qpbenchmark = np.loadtxt(
        open(os.path.join(dataFileDirPath, "qp_Benchmark.csv")),
        delimiter=",",
        usecols=range(1),
    )
    Eqbenchmark = np.loadtxt(
        open(os.path.join(dataFileDirPath, "Eq_Benchmark.csv")),
        delimiter=",",
        usecols=range(1),
    )

    # calculate error between output and benchmark result, which below 0.01% is pass.
    aerr = np.absolute((Q - Qbenchmark) / Qbenchmark)
    qpErr = np.absolute(qp - qpbenchmark)
    epErr = np.absolute((Ep - Eqbenchmark) / Eqbenchmark)
    F0Err = np.absolute((F0 - F0benchmark) / F0benchmark)

    assert (np.max(aerr) < 0.0001).all()
    assert (np.max(qpErr) < 0.0001).all()
    assert (np.max(epErr) < 0.0001).all()
    assert (np.max(F0Err) < 0.0001).all()
