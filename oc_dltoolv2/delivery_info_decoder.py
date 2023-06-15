import json
import logging
import fs
from oc_dltoolv2.delivery_info_helper import DeliveryInfoHelper

## this may be necessary in the future if we enable 'deliveryArea' tag
## currently it is disabled due to absence of evidence in Copyright regulations
#import urlparse

class DeliveryInfoDecoder(DeliveryInfoHelper):
    def __init__(self, delivery_params, delivery_resources, separators=None):
        """
        :param delivery_params: delivery parameters
        :type delivery_params: configObj
        :param delivery_resources: resources layout
        :type delivery_resources: ResourcesLayout
        :param separators: separators for JSON pretty-print
        :type separators: Tuple
        """
        super(DeliveryInfoDecoder, self).__init__(delivery_params)
        logging.debug("Creating new DeliveryInfoDecoder")
        self._delivery_resources = delivery_resources
        self._seps = separators
        self._output = dict()

        # set default separators for pretty-print
        if not self._seps:
            self._seps = (',', ': ')

        # we do not want to fail if something goes wrong
        try:
            self._convert_files_list()
            self._id_keys()
            self._resources_keys()
        except Exception as e:
            logging.exception(e)

    def _id_keys(self):
        """
        Convert our keys to required by technical task
        """
        ### Keys necessary:
        ## deliveryId - a part of GAV: 'CLIENT:artifactId:version'
        ## deliveryArea- last two tokens from hostname from SVN url 
        logging.debug("Constructing delivery ID")
        self._output["deliveryId"] = ':'.join(
                [self._find_customer_code()] + list(self._delivery_params[_k] for _k in ["artifactid", "version"]))
        logging.debug("Constructed delivery ID: '%s'" % self._output.get("deliveryId"))

        ## construction of 'deliveryArea' parameter is temporary disabled
        #logging.debug("Constructing delivery area")
        #_delivery_area = self._delivery_params.get("mf_source_svn")

        #if not _delivery_area:
        #    logging.error("unable to determine delivery area: No 'mf_source_svn' key in delivery parameters.")
        #    return

        #_delivery_area = urlparse.urlparse(_delivery_area).hostname
        #self._output["deliveryArea"] = unicode('.'.join(_delivery_area.split('.')[-2:]))


    def _resources_keys(self):
        """
        Append file-related keys from delivery_resources
        """
        ## Keys appended:
        ## deliveryFiles - JSONized delivery_resources
        ## sub-components:
        ##   path - path INSIDE delivery
        ##   type - CI Type Code
        ##   NOT IMPLEMENTED: checksum - MD5 checksum
        self._output["deliveryFiles"] = list(map(lambda x: {
            "path": x[1],
            "citype": x[0].location_stub.citype.code,
            }, self._delivery_resources))

    def _convert_files_list(self):
        """
        Convert "mf_delivery_files_specified" to a list instead of multi-lined string
        """
        logging.debug("Converting delivery files list")
        _key = "mf_delivery_files_specified"

        # this will raise "KeyError" if no files specified in the delivery
        # it is OK since this is a crime
        _kv = self._delivery_params[_key]
        if isinstance(_kv, str):
            self._delivery_params[_key] = list(map(lambda x: x.strip(), _kv.splitlines()))
        elif isinstance(_kv, list):
            self._delivery_params[_key] = []
            for _df in _kv: self._delivery_params[_key].extend(_df.splitlines())

    def write_to_file(self, dst_fs, dst_path):
        """
        Convert all information to single JSON-string as unicode object
        :param dst_fs: destination filesystem
        :type write_to: path to the file inside the destination filesystem
        """
        # we do not want to fail if something goes wrong
        logging.debug("Trying to save delivery_info to '%s'" % dst_path)
        try:
            with dst_fs.open(dst_path, mode="w") as _fl_out:
                _fl_out.write(json.dumps(self._output, sort_keys=False, 
                    indent=4, ensure_ascii=False, separators=self._seps))
        except Exception as e:
            logging.exception(e)
