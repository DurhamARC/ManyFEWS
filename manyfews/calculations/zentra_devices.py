"""Unoffical bindings to the Zentra API

This module contains bindings to the Zentra API for retrieving
a list of subscribed devices and their locations

"""
from requests import Session, Request
from zentra.api import ZentraToken
from django.contrib.gis.geos import Point
from calculations.models import ZentraDevice


class ZentraDeviceMap:
    """
    Class representing a map of Zentra devices and their metadata

    The Zentra API does not document a method of getting all devices.
    This class implements undocumented API endpoints which produce a
    list of all device locations and subscriptions for an organisation.

    Parameters
    ----------
    token: ZentraToken
        a ZentraToken access token to use for API login

    Attributes
    ----------
    locs_request: Request
        a Request object for the Zentra API /api/1.0/locations/
    locs_response: Response
        a JSON response from the Zentra server for device locations
    subs_request: Request
        a Request object for the Zentra API for device subscriptions
        /api/3.0/get_payment_subscriptions/
    subs_response: Response
        a JSON response from the Zentra server for device subscriptions
    device_map: dict
        a dict representing a mapping of device serial numbers to device metadata:
        {
            '06-02010': {
                'devtype': 190,
                'site': 'Java',
                'plot': 'Citarum',
                'customersite': 'Durham University',
                'device_name': 'Cikembang',
                'lat': -7.2086765,
                'lon': 107.6725925
            },
            { ...etc }
         }
    """

    def __init__(self, token: ZentraToken = None):
        """Gets a map of devices to properties via 2 GET requests to the Zentra API
        @type token: ZentraToken
        """
        if token is None:
            raise Exception('"token" parameter must be included')
        elif isinstance(token, ZentraToken):
            self.get(token)
        else:
            # Create empty device list
            self.locs_request = None
            self.locs_response = None
            self.subs_request = None
            self.subs_response = None
            self.device_map = {}

    def get(self, token: ZentraToken):
        """
        GET device information for metadata and location from the undocumented Zentra API.
        Wraps build and parse functions.

        Parameters
        ----------

        token: ZentraToken
            The user's access token
        """
        self.build(token)
        self.make_request()
        self.parse()

    def build(self, token):
        """
        Build Request objects to the Zentra API.
        Constructs requests to:
            https://zentracloud.com/api/1.0/locations/
            https://zentracloud.com/api/3.0/get_payment_subscriptions/
        """
        self.locs_request = Request(
            "GET",
            url="https://zentracloud.com/api/1.0/locations/",
            headers={"Authorization": "Token " + token.token},
        ).prepare()

        self.subs_request = Request(
            "GET",
            url="https://zentracloud.com/api/3.0/get_payment_subscriptions/",
            headers={"Authorization": "Token " + token.token},
        ).prepare()

        return self

    def make_request(self):
        """
        Sends requests to the Zentra API and store the response
        """

        # Send the request and get the JSON response
        def action(request):
            resp = Session().send(request)
            if resp.status_code != 200:
                raise Exception(
                    "Incorrectly formatted request. Please ensure the user token is correct."
                )
            return resp.json()

        self.locs_response = action(self.locs_request)
        self.subs_response = action(self.subs_request)

        return self

    def parse(self):
        """
        Parses the response into the device_map datastructure
        """
        self.device_map = {}

        devices = self.locs_response["items"]
        mapping = {
            key["pk"]: {i: key[i] for i in key if i not in ["subscriptions", "pk"]}
            for key in self.subs_response["data"]["devices"]
        }

        for d in devices:
            sensor = mapping[d["pk"]]

            for key in mapping[d["pk"]].keys():
                if sensor["sn"] not in self.device_map:
                    self.device_map[sensor["sn"]] = {}
                if key == "sn":
                    continue

                self.device_map[sensor["sn"]][key] = sensor[key]

            self.device_map[sensor["sn"]]["lat"] = d["lat"]
            self.device_map[sensor["sn"]]["lon"] = d["lon"]

        return self

    def save(self):
        """
        Turn the map of devices into django Models to store in database
        """
        for device in self.device_map:
            zentra_device = ZentraDevice(
                device_sn=device,
                device_name=self.device_map[device]["device_name"],
                location=Point(
                    self.device_map[device]["lon"], self.device_map[device]["lat"]
                ),
                height=1,
            )
            zentra_device.save()


"""
Run test if class run from `python zentra_devices.py`
"""
if __name__ == "__main__":
    from manyfews.manyfews import settings

    token = ZentraToken(username=settings.ZENTRA_UN, password=settings.ZENTRA_PW)
    devmp = ZentraDeviceMap(token=token)
    print(devmp.device_map)
