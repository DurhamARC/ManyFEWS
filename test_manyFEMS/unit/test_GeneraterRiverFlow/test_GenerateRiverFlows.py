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
    t = riverFlowsData[1]
    qp = riverFlowsData[2]
    Ep = riverFlowsData[3]

    # import benchmark result of 'GenerateRiverFlows.m' matlab code.
    Qbenchmark = np.loadtxt(
        open(os.path.join(dataFileDirPath, "Q_Benchmark.csv")),
        delimiter=",",
        usecols=range(100),
    )
    tbenchmark = np.loadtxt(
        open(os.path.join(dataFileDirPath, "t_Benchmark.csv")),
        delimiter=",",
        usecols=range(1),
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
    terr = np.absolute((t - tbenchmark) / tbenchmark)
    qpErr = np.absolute(qp - qpbenchmark)
    epErr = np.absolute((Ep - Eqbenchmark) / Eqbenchmark)

    assert (np.max(aerr) < 0.0001).all()
    assert (np.max(terr) < 0.0001).all()
    assert (np.max(qpErr) < 0.0001).all()
    assert (np.max(epErr) < 0.0001).all()
