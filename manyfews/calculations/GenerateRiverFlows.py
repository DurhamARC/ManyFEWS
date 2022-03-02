import os
import xlrd
import math
import numpy as np
from django.contrib.gis.geos import Point
from datetime import datetime, timedelta, timezone, date
from .models import NoaaForecast, InitialCondition


def ModelFun(qp, Ep, dt, CatArea, X, F0):

    # qp - rainfall (mm/day)
    # Ep - potential evapotranspiration (mm/day)
    # dt - time-step (day)
    # CatArea - catchment area (km2)
    # X - array containing model parameters
    # F0 - array containing initial condition of state variables
    # Q - river flow rate (m3/s)
    Q = np.zeros(((np.size(Ep[:])), (np.size(X[:, 1]))))  # initialize the matrix Q

    for n in range(np.size(X[:, 1])):
        # Extract parameters
        Smax = X[n, 0]  # (mm)
        qmax = X[n, 1]  # (mm/day)
        k = X[n, 2]  # (mm/day)
        Tr = X[n, 3]  # (days)

        # Extract initial conditions
        S0 = F0[n, 0]  # initial storage level for PDM (mm)
        qSLOW0 = F0[n, 1]  # initial slow flow rate (mm/day)
        qFAST0 = F0[n, 2]  # initial fast flow rate (mm/day)

        # Determine surface runoff and drainage
        pdOutputData = PDMmodel(qp, Ep, Smax, 1, k, dt, S0)

        # "pdOutputData" is a data tuple, which:
        # pdOutputData[0] ====> qro
        # pdOutputData[1] ====> qd
        # pdOutputData[2] ====> Ea
        # pdOutputData[3] ====> S
        qro = pdOutputData[0]
        qd = pdOutputData[1]
        Ea = pdOutputData[2]
        S = pdOutputData[3]

        # Determine slow flow
        qSLOW = RoutingFun(qd, Tr, 1, dt, qSLOW0)

        # Determine fast flow
        qFAST = RoutingFun(qro, qmax, 5 / 3, dt, qFAST0)

        # Determine river flow
        q = qFAST + qSLOW

        # Covert to m3/s
        Q[:, n] = (q * CatArea * (1e3) / 24) / (3600)

        # Update initial condition vector with final values of state variables
        F0[n, :] = [(S[-1]), (qSLOW[-1]), (qFAST[-1])]
    return Q, F0


def RoutingFun(qs, X, b, dt, q0):

    numPoint = np.size(qs)  # Determine number of data points

    # Specify input parameters:
    # b=5/3 Exponent in q=a*vˆb
    # Initialisation steps:

    if b == 1:
        # This means it's a linear store
        # so X is the residence time in days
        Tr = X
        a = 1 / Tr
        vmax = float("inf")

    else:
        # This means it's a non-linear store
        # so X is qmax in mm/day
        qmax = X
        dtDAY = 1  # this is needed because qmax is determine with daily data
        a = (math.pow(qmax, (1 - b))) * (math.pow((b * dtDAY), (-b)))
        vmax = math.pow((a * b * dt), (1 / (1 - b)))  # Limit on v for stability

    # Initialise vectors
    try:
        q0
    except NameError:
        q0 = 2  # Estimate initial value

    q = np.full((numPoint + 1), q0)
    v = np.power((q / a), (1 / b))

    for i in range(numPoint):  # Step through each day
        # Trial values for q and v:
        qtrial = a * math.pow(v[i], b)
        vtrial = v[i] + ((qs[i] - qtrial) * dt)

        if vtrial < vmax:  # Ordinarily use trial values
            q[i] = qtrial  # River flow (mm/day)
            v[i + 1] = vtrial  # River storage (mm)
        else:  # Force v<=vmax
            q[i] = qs[i] - ((vmax - v[i]) / dt)
            v[i + 1] = vmax

    q = q[:-1]

    return q


def PDMmodel(qp, Ep, Smax, gamma, k, dt, S0):

    # Specify input parameters:
    # Smax=80; %Maximum storage for PDM (mm)
    # gamma=0.1; %Exponent for Pareto distribution
    # Initialisation steps:
    numPoint = np.size(qp)

    # Initialise vectors
    qd = np.zeros(numPoint)
    qro = np.zeros(numPoint)
    Ea = np.zeros(numPoint)

    try:
        S0
    except NameError:
        S0 = Smax / 20  # Estimate initial value

    S = np.full((numPoint + 1), S0)

    for i in range(numPoint):
        # Pareto CDF
        F = 1 - (math.pow((1 - (S[i]) / Smax), gamma))

        # Determine drainage rate
        qd[i] = k * S[i] / Smax

        # Trial value for S
        Strial = S[i] + (((1 - F) * qp[i] - Ep[i] - qd[i]) * dt)

        # To start with try the following:
        S[i + 1] = Strial  # Catchment storage
        qro[i] = F * qp[i]  # River flow contribution
        Ea[i] = Ep[i]  # Actual evapotranspiration

        if Strial <= 0:
            S[i + 1] = 0
            qd[i] = 0
            Ea[i] = ((1 - F) * qp[i]) + (S[i] / dt)
        elif Strial >= Smax:  # Force S<=Smax
            S[i + 1] = Smax
            qro[i] = qp[i] - Ep[i] - ((Smax - S[i]) / dt) - qd[i]
    S = S[:-1]

    return qro, qd, Ea, S


def FAO56(t, dt, Tmin, Tmax, alt, lat, T, u2, RH):

    # Ensure Tmax > Tmin
    Tmax = np.maximum(Tmax, Tmin)
    Tmin = np.minimum(Tmax, Tmin)

    # u2 (m/s)
    # P (kPa)
    # ea (kPa)
    # Rn (MJ/m2/day)

    try:
        T
    except NameError:
        T = (Tmin + Tmax) / 2

    # This is based on FAO56 Example 20 for the estimation of evapotranspiration
    try:
        u2
    except NameError:
        u2 = np.zeros(np.shape(T))  # create an undefined array
        u2[:] = 2  # Assume wind speed of 2 m/s

    # Slope of saturation curve (Del) from Eq. 13
    Del = (4098 * (0.6108 * (np.exp(((17.27 * T) / (T + 237.3)))))) / np.square(
        T + 237.3
    )

    # Atmospheric pressure (P) from Eq. 7
    P = 101.3 * (math.pow(((293 - 0.0065 * alt) / 293), 5.26))

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
    es = (eoTmax + eoTmin) / 2

    try:
        ea = (RH / 100) * es
    except NameError:
        # Dewpoint temperature (Tdew) from Eq. 48
        Tdew = Tmin  # This might need to be increased for tropical conditions SAM 14 / 09 / 2019
        # Actual vapour pressure (ea) from Eq. 14
        ea = 0.6108 * (np.exp((17.27 * Tdew) / (Tdew + 237.3)))

    # Convert latitude from degrees to radians from Eq. 22
    varphi = (lat * math.pi) / 180

    # Determine day of the year as a number from 1 to 365
    beginDate = date(2010, 1, 1)
    beginDateNum = (beginDate - date(beginDate.year - 1, 12, 31)).days
    J = beginDateNum + np.arange(0, ((np.size(t[:])) / 4), dt)
    # J = beginDateNum + np.arange(0, 16, dt)

    # Inverse relative distance Earth-Sun from Eq. 23
    dr = 1 + (0.033 * np.cos(((2 * math.pi) / 365) * J))

    # Solar declination from Eq. 24
    delta = 0.409 * np.sin((((2 * math.pi) / 365) * J) - 1.39)

    # Sunset hour angle from Eq. 25
    ws = np.arccos((-math.tan(varphi)) * (np.tan(delta)))

    # Extraterrestrial radiation from Eq. 21
    Gsc = 0.0820
    Ra = (
        (((24 * 60) / (math.pi)) * Gsc)
        * dr
        * (
            ws * (math.sin(varphi)) * (np.sin(delta))
            + (math.cos(varphi)) * (np.cos(delta)) * np.sin(ws)
        )
    )

    # Incoming solar radiation from Eq. 50
    kRS = 0.16

    try:
        Rs
    except NameError:
        Rs = kRS * (np.sqrt(Tmax - Tmin)) * Ra

    # Clear-sky solar radiation from Eq. 37
    Rso = ((0.75 + (2e-5) * alt)) * Ra

    # Net solar radiation from Eq. 38
    alpha = 0.23
    Rns = (1 - alpha) * Rs

    # Outgoing net longwave radiation from Eq. 39
    sig = 4.903e-9
    sigTmax4 = sig * (np.power((Tmax + 273.15), 4))
    sigTmin4 = sig * (np.power((Tmin + 273.15), 4))
    sigT4 = (sigTmax4 + sigTmin4) / 2
    RsRso = Rs / Rso
    RsRso[RsRso > 1] = 1
    Rnl = sigT4 * (0.34 - (0.14 * np.sqrt(ea))) * (1.35 * RsRso - 0.35)

    # Rnl = sigT4 * (0.56- (0.25 * np.sqrt(ea))) * ( 1.35 * RsRso - 0.35) [This is what you need for UK instead]
    # Net radiation from Eq. 40
    Rn = Rns - Rnl

    # Assume zero soil heat flux
    G = 0
    # Calculate reference evapotranspiration from Eq. 6
    T1 = 0.408 * Del * (Rn - G)
    T2 = ((gam * 900) / (T + 273)) * u2 * (es - ea)
    T3 = Del + (gam * (1 + 0.34 * u2))
    ETo = (T1 + T2) / T3

    #   Determine open water evaporation
    alpha = 0.05  # Albedo for wet bare soil (p. 43)
    Rns = (1 - alpha) * Rs
    Rn = Rns - Rnl
    T1 = 0.408 * Del * (Rn - G)
    T3 = Del + gam  # (i.e., rs=0)
    E0 = (T1 + T2) / T3

    return ETo, E0


def GenerateRiverFlows(t0, gefsData, F0, parametersFilePath):
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
    N = np.size(gefsData[:, 1])

    # Specify date number
    t = t0 + np.arange(0, N / 4, dt)

    # Get relative humidity (%)
    RH = gefsData[:, 0]

    # Convert temperature to deg C
    TempMax = gefsData[:, 1] - 273.15
    TempMin = gefsData[:, 2] - 273.15

    # Estimate average temperature
    T = (TempMin + TempMax) / 2

    # Determine daily minimum temperature of each hour
    MinTemPerHour = (
        np.array(TempMin).reshape((int(N / 4)), 4).min(axis=1)
    )  # Min Temperature of each hour(at 4 time points).
    Tmin = np.repeat(MinTemPerHour, 4)

    # Determine daily maximum temperature of each hour
    MaxTemPerHour = (
        np.array(TempMax).reshape((int(N / 4)), 4).max(axis=1)
    )  # Max Temperature of each hour(at 4 time points).
    Tmax = np.repeat(MaxTemPerHour, 4)

    # Determine magnitude of wind speed at 10 m
    u10 = np.sqrt((gefsData[:, 3]) ** 2 + (gefsData[:, 4]) ** 2)

    # Estimate wind speed at 2 m
    z0 = 0.006247  # m(surface roughness equivalent to FAO56 reference crop)
    z2 = 2  # m
    z10 = 10  # m
    u0 = 0  # m/s
    uTAU = ((u10 - u0) / 2.5) / (math.log(z10 / z0))
    u2 = 2.5 * uTAU * (math.log(z2 / z0)) + u0

    # Extract precipitation data (mm)
    precip = gefsData[:, 5]

    # Convert preiciptation to (mm/day)
    qp = precip / dt

    # Details specific for Majalaya catchment
    lat = -7.125  # mean latutude (degrees)
    alt = 1157  # mean altitude (m above sea level)
    CatArea = 212.2640  # Catchment area (km2)

    # Get model parameters for Majalaya catchment
    X = np.loadtxt(open(parametersFilePath), delimiter=",", usecols=range(4))

    # Determine reference crop evapotranspiration (mm/day)
    fa056OutputData = FAO56(t, dt, Tmin, Tmax, alt, lat, T, u2, RH)

    # "fa056OutputData" is a data tuple, which:
    # fa056OutputData[0] ====> Ep
    # fa056OutputData[1] ====> E0
    Ep = fa056OutputData[0]
    E0 = fa056OutputData[1]

    # Determine flow rate, Q (m3/s)
    modelfunOutputData = ModelFun(qp, Ep, dt, CatArea, X, F0)

    # "modelfunOutputData " is a data tuple, which:
    # modelfunOutputData [0] ====> Q
    # modelfunOutputData [1] ====> F0
    Q = modelfunOutputData[0]
    F0 = modelfunOutputData[1]

    return Q, t, qp, Ep


def excel_to_matrix(path, sheetNum):
    table = xlrd.open_workbook(path).sheets()[sheetNum]
    row = table.nrows
    col = table.ncols
    datamatrix = np.zeros((row, col))  # ignore the first title row.
    for x in range(1, row):
        #        row = np.matrix(table.row_values(x))
        #        print(type(row))
        row = np.array(table.row_values(x))
        datamatrix[x, :] = row
    datamatrix = np.delete(
        datamatrix, 0, axis=0
    )  # Delete the first blank line.(Its elements are all zero)
    return datamatrix


def prepare_test_GEFS():
    """
    This function is used to import test GEFS data into database.
    It will read data from GEFS xlrd file.
    """

    projectPath = os.path.abspath(
        os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
    )

    dataFileDirPath = os.path.join(projectPath, "Data")
    GefsDataFile = os.path.join(dataFileDirPath, "GEFSdata.xlsx")
    sheetNum = 16
    gefsData = excel_to_matrix(GefsDataFile, sheetNum)
    testDate = datetime(
        year=2010, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    date = datetime.astimezone(testDate, tz=timezone(timedelta(hours=0)))

    for i in range(len(gefsData[:, 0])):
        testGefsData = NoaaForecast(
            date=date,
            location=Point(0, 0),
            relative_humidity=gefsData[i, 0],
            min_temperature=gefsData[i, 2],
            max_temperature=gefsData[i, 1],
            wind_u=gefsData[i, 3],
            wind_v=gefsData[i, 4],
            precipitation=gefsData[i, 5],
        )
        testGefsData.save()


def prepare_test_initialCondition():
    """
    This function is used to import test initial condition data into database.
    It will read data from 'RainfallRunoffModelInitialConditions' file.
    """

    projectPath = os.path.abspath(
        os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
    )
    dataFileDirPath = os.path.join(projectPath, "Data")
    InitialConditionFile = os.path.join(
        dataFileDirPath, "RainfallRunoffModelInitialConditions.csv"
    )
    F0 = np.loadtxt(open(InitialConditionFile), delimiter=",", usecols=range(3))
    testDate = datetime(
        year=2010, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    date = datetime.astimezone(testDate, tz=timezone(timedelta(hours=0)))

    for i in range(len(F0[:, 0])):
        testInitialCondition = InitialCondition(
            date=date,
            location=Point(0, 0),
            storage_level=F0[i, 0],
            slow_flow_rate=F0[i, 1],
            fast_flow_rate=F0[i, 2],
        )

        testInitialCondition.save()


# prepare initial conditions for model.
initialConditions = InitialCondition.objects.filter(date__year=2010).filter(
    location=Point(0, 0)
)

slowFlowRate = list(initialConditions.values("slow_flow_rate"))
fastFlowRate = list(initialConditions.values("fast_flow_rate"))
storageLevel = list(initialConditions.values("storage_level"))

slowFlowRateList = []
fastFlowRateList = []
storageLevelList = []

for i in range(len(initialConditions)):
    slowFlowRateList.append(slowFlowRate[i]["slow_flow_rate"])
    fastFlowRateList.append(fastFlowRate[i]["fast_flow_rate"])
    storageLevelList.append(storageLevel[i]["storage_level"])

initialConditionsList = list(zip(slowFlowRateList, fastFlowRateList, storageLevelList))
intialConditionData = np.array(initialConditionsList)


# prepare testing GEFS data for model.
gefs = NoaaForecast.objects.filter(date__year=2010).filter(location=Point(0, 0))

RH = list(gefs.values("relative_humidity"))
minTemperature = list(gefs.values("min_temperature"))
maxTemperature = list(gefs.values("max_temperature"))
uWind = list(gefs.values("wind_u"))
vWind = list(gefs.values("wind_v"))
precipitation = list(gefs.values("precipitation"))

RHList = []
minTemperaturelist = []
maxTemperatureList = []
uWindList = []
vWindList = []
precipitationList = []

for i in range(len(gefs)):
    RHList.append(RH[i]["relative_humidity"])
    minTemperaturelist.append(minTemperature[i]["min_temperature"])
    maxTemperatureList.append(maxTemperature[i]["max_temperature"])
    uWindList.append(uWind[i]["wind_u"])
    vWindList.append(vWind[i]["wind_v"])
    precipitationList.append(precipitation[i]["precipitation"])

gefsList = list(
    zip(
        RHList,
        maxTemperatureList,
        minTemperaturelist,
        uWindList,
        vWindList,
        precipitationList,
    )
)
gefsData = np.array(gefsList)

projectPath = os.path.abspath(
    os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
)

dataFileDirPath = os.path.join(projectPath, "Data")
parametersFilePath = os.path.join(dataFileDirPath, "RainfallRunoffModelParameters.csv")


t0 = date.toordinal(date(2010, 1, 1)) + 366

riverFlowsData = GenerateRiverFlows(
    t0=t0,
    gefsData=gefsData,
    F0=intialConditionData,
    parametersFilePath=parametersFilePath,
)
