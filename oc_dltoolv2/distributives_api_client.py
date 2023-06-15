import requests
import logging
import os
import posixpath

class DistributivesAPIClient:
    """
    A client for Distributives API 
    """
    def __init__(self, api_url=None):
        self.url = api_url
        if not self.url:
            self.url = os.getenv("DISTRIBUTIVES_API_URL")
    
        if not self.url:
            raise ValueError("Distributives API url was not provided")

    def check_distributive_allowance(self, checksum):
        """
        Check if distributive is allowed for delivering using its checksum
        :param checksum: str
        :return: bool
        """
        response = requests.get(posixpath.join(self.url, "artifact_deliverable"), json={"checksum": checksum})
        if response.status_code != 200:
            # something goes wrong, report it but allow distributive to be deliveried
            logging.error("Wrong response from distributives_api: %d\n%s" % (response.status_code, response.text))
            return True

        try:
            # the return value is a boolean packed in the list, try to return it
            return response.json().pop()
        except Exception as _e:
            # something goes wrong, report it but allow distributive to be deliveried
            logging.exception(_e)
            pass

        return True

