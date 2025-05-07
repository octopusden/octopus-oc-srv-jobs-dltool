import logging
import re
from .delivery_info_helper import DeliveryInfoHelper
from .delivery_exceptions import DeliveryDeniedException

class DeliveryArtifactsChecker(DeliveryInfoHelper):
    def check_artifacts_included(self, delivery_resources):
        """
        Check all necessary artifacts are in the delivery
        :param delivery_resources: pre-final resources list
        :type delivery_resources: list
        :return: True or False
        """
        logging.info("Start checking artifacts inclusion in delivery")

        if not delivery_resources:
            # surely a bug, we have to fail
            # THIS SHOULD NEVER HAPPEN
            logging.error("Empty delivery resources list provided")
            raise ValueError("Empty delivery resources list provided")

        _customer_code = self._find_customer_code()
        if not _customer_code:
            # surely a bug, we have to fail
            # THIS SHOULD NEVER HAPPEN
            logging.error("Failed to detect customer code from delivery parameters")
            raise ValueError("Failed to detect customer code from delivery parameters")

        logging.debug("Customer code: '%s'" % _customer_code)

        # ask ClientProvider to give us a location
        _customer_loc = self._get_customer_location(_customer_code)
        logging.debug("Resolved customer location: '%s'" % _customer_loc)

        if not _customer_loc:
            logging.warning("Customer '%s' does not have location tag. Artifacts check skipped" % _customer_code)
            return True

        logging.info("Getting artifacts lineup for location: '%s'" % _customer_loc)
        _artifacts_necessary, _artifacts_denied = self._get_artifacts_lineup(_customer_loc)
        logging.info("Checking delivery resources lineup")
        result = self._check_artifacts_lineup(delivery_resources, _artifacts_necessary, _artifacts_denied)

        logging.info("Finished checking artifacts inclusion in delivery")
        return result

    def _get_artifacts_lineup(self, customer_location):
        """
        Return JSON configuration section with artifacts lineup for a location given
        :param customer_location: customer location (at the moment: [inc, com])
        """
        logging.debug("Try to get artifacts lineup for location '%s'" % customer_location)
        _t = self._read_artifacts_conf(customer_location)
        logging.debug("Artifacts lineup retrieved: necessary=%s, denied=%s" % (_t.get("necessary"), _t.get("denied")))
        return _t.get("necessary"), _t.get("denied")

    def _check_artifacts_lineup(self, delivery_resources, artifacts_necessary, artifacts_denied):
        """
        check delivery resources for artifacts presence/absence
        :param delivery_resources: delivery resources list
        :param artifacts_necessary: list of artifacts necessary to be included into the delivery (python regexps)
        :param artifacts_delined: list of artifacts should never be included into the delivery (python regexps)
        """
        logging.debug("Checking delivery resources lineup")

        if artifacts_necessary:
            logging.debug("Checking presence of necessary artifacts")
            self._check_resources_lineup(delivery_resources, artifacts_necessary, True)

        if artifacts_denied:
            logging.debug("Checking absence of denied artifacts")
            self._check_resources_lineup(delivery_resources, artifacts_denied, False)

        return True

    def _check_resources_lineup(self, delivery_resources, artifacts_list, present):
        """
        Check the resources list for artifacts to be 'present'
        :param delivery_resources: delivery resources list
        :param artifacts_list: aritfac list to filter (python regexps)
        :param present: should artifacts present or not
        """
        logging.debug("Filtering '%s'" % ("necessary" if present else "denied"))

        for _regexp in artifacts_list:
            logging.debug("Checking resources against regexp '%s'" % _regexp)
            _regexp_t = re.compile(_regexp)
            _filtered = list(filter(lambda x: _regexp_t.match(x.location_stub.path), delivery_resources))

            if present and not _filtered:
                logging.error("Absent necessary artifact matching regexp: %s" % _regexp)
                raise DeliveryDeniedException("Absent necessary'%s'" % _regexp)

            if not present and _filtered:
                raise DeliveryDeniedException("Forbidden present (regexp='%s'): '%s'" % 
                        (_regexp, ';'.join(list(map(lambda x: x.location_stub.path, _filtered)))))
