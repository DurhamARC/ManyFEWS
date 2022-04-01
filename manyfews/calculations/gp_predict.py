import tifffile as tif
import numpy as np
import os


def depthLoader():

    # set zero threshold value
    zeroThreshold = 0.00001

    # all tif files are in "Data/tif/" directory.
    projectPath = os.path.abspath(
        os.path.join((os.path.split(os.path.realpath(__file__))[0]), "../../")
    )
    tifPath = os.path.join(projectPath, "Data/tif/")

    # number of tif files
    tifNum = len(
        [
            lists
            for lists in os.listdir(tifPath)
            if os.path.isfile(os.path.join(tifPath, lists))
        ]
    )

    indexList = []

    for i in range(1, (tifNum + 1)):
        tifFileName = "Run" + str(i) + ".tif"

        # extract depths data from HEC-RAS
        currentDepths = tif.imread(os.path.join(tifPath, tifFileName))

        # dry pixels returned as -9999 in tif files, change to 0
        currentDepths[currentDepths <= -9999.0] = 0

        # finds the index of non-zero pixels for each run
        index = np.where(currentDepths > zeroThreshold)

        indexList.extend(index)

    return indexList
