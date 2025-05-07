import logging
import os
from .delivery_info_helper import DeliveryInfoHelper
import fs

class DeliveryCopyrightAppender(DeliveryInfoHelper):
    def write_to_file(self, dst_fs, dst_path):
        """
        Write copyright text to a file given
        :param dst_fs: desitnation filesystem
        :param dst_path: path inside the destination filesystem
        """
        logging.info("Starting to write copyright to '%s'" % dst_path)

        logging.debug("Trying to find customer code")
        _customer_code = self._find_customer_code()
        if not _customer_code:
            # surely a bug, we have to fail
            # THIS SHOULD NEVER HAPPEN
            logging.error("Customer code not found – cannot proceed")
            raise ValueError("Failed to detect customer code from delivery parameters")

        logging.debug("Trying to get customer location for code '%s'" % _customer_code)
        _customer_location = self._get_customer_location(_customer_code)
        logging.info("Customer location for '%s': '%s'" % (_customer_code, _customer_location))

        if not _customer_location:
            logging.warning("Customer '%s' does not have location tag. Copyright appending skipped" % _customer_code)
            return

        logging.debug("Reading artifact configuration for location: '%s'" % _customer_location)
        _t = self._read_artifacts_conf(_customer_location)

        logging.debug("Attempting to retrieve copyright")
        _dom_spec_cpr = _t.get("copyright")
        logging.info("Copyright file name: '%s'" % _dom_spec_cpr)

        if not _dom_spec_cpr:
            logging.warning("Copyright file for location '%s' (customer '%s') not specified in configuration '%s'" %
                    (_customer_location, _customer_code, os.path.abspath(os.getenv('DELIVERY_ADD_ARTS_PATH'))))
            return

        # do not catch an exception - it will be catched outside and transferred as delivery status
        logging.debug("Save file attempt: '%s'" % dst_path)
        with fs.osfs.OSFS(os.path.abspath(os.getenv('DELIVERY_ADD_ARTS_PATH'))) as _src_fs:
            fs.copy.copy_file(_src_fs, _dom_spec_cpr, dst_fs, dst_path)

