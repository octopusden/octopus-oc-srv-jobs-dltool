import posixpath
import logging
import requests
import os
import json

class DeliveryInfoHelper(object):
    def __init__(self, delivery_params):
        """
        Class initialization
        :param delivery_params: parsed configobj array with delivery parameters
        :type delivery_params: dict
        """
        if not delivery_params:
            # surely a bug, we have to fail
            # THIS SHOULD NEVER HAPPEN
            raise ValueError("Empty delivery parameters provided")

        logging.debug("Constructing new DeliveryInfoHelper")
        self._delivery_params = dict(delivery_params)

    def _find_customer_code(self):
        """
        Try to parse delivery parameters searching for customer code
        """
        if "groupid" in self._delivery_params:
            # most common case
            # groupId is given like this:
            ## com.example.com.dltool.c.CODE
            # so CODE is last one always if line is splitted by dot '.'
            try:
                return self._delivery_params.get("groupid").split('.').pop()
            except Exception as e:
                logging.exception(e)

        # try to find out the code from SVN paths if we fail to do so from groupId
        # this should never happen, but just for occasion insurance
        # SVN paths are like these:
        ## https://vcs-svn.cdt.location.sfx/svn/clients/Country/CODE/tags/tag
        ## https://vcs-svn.cdt.location.sfx/svn/clients/Country/CODE/branches/branch
        # index of CODE is 6 in case of posixpath.sep split
        if "mf_source_svn" in self._delivery_params:
            try:
                return self._delivery_params.get("mf_source_svn").split(posixpath.sep).pop(6)
            except Exception as e:
                logging.exception(e)

        if "mf_tag_svn" in self._delivery_params:
            try:
                return self._delivery_params.get("mf_tag_svn").split(posixpath.sep).pop(6)
            except Exception as e:
                logging.exception(e)

        logging.error("Unable to determine customer code from delivery parameters")
        return None

    def _get_customer_location(self, customer_code):
        """
        Ask ClientProvider service to get customer location tag
        :param customer_code: CDT customer instance code
        :type customer_code: str
        """
        # since we do not have a mistake right - do not catch any exceptions,
        # raise them where they appear to fail a build then
        logging.debug("Fetching customer location for: %s", customer_code)
        _client_provider_url = os.getenv('CLIENT_PROVIDER_URL')

        if not _client_provider_url:
            raise ValueError("'CLIENT_PROVIDER_URL' absent!")

        return requests.get(
                posixpath.join(_client_provider_url, "client_counterparty", customer_code)).json().get(customer_code)

    def _read_artifacts_conf(self, customer_location):
        """
        Read JSON configuration part for location given
        :param customer_location: customer location (at the moment: [inc, com])
        """
        logging.debug("Try to read artifacts configuration")
        _conf_path = os.getenv("DELIVERY_ADD_ARTS_PATH")

        if not _conf_path:
            raise ValueError("'DELIVERY_ADD_ARTS_PATH' is not set!")

        _conf_path = os.path.abspath(_conf_path)
        _conf_path = os.path.join(_conf_path, "config.json")
        logging.debug("Reading config from '%s'" % _conf_path)
        _json_data = dict()

        with open(_conf_path, mode='r') as _fl_in:
            _json_data = json.load(_fl_in)

        return _json_data.get(customer_location)

