from itertools import chain

from oc_delivery_apps.checksums.models import LocTypes, CiTypes
from django.core.exceptions import ObjectDoesNotExist
import logging

from .releasenotes import get_possible_releasenotes_gavs
from .resources import LocationStub, FSLocation, FileBasedResourceData, DeliveryResource


class DeliveryListEnhancement(object):
    """
    Abstract class for any delivery list enhancements
    """

    def enhance_resources(self, resources, context):
        """ Returns additional resources which should be shipped along with original ones
        :param resources: list of DeliveryResource objects
        :param context: RequestContext """
        raise NotImplementedError("Subclasses should implement it")


class ReleasenotesEnhancement(DeliveryListEnhancement):

    def __init__(self):
        logging.debug("Initializing ReleasenotesEnhancement")
        try:
            self._at_nexus = LocTypes.objects.get(code="NXS")
            logging.debug("Loaded LocType with code 'NXS': %s", self._at_nexus)
            self._releasenotes_citype = CiTypes.objects.get(code="RELEASENOTES")
            logging.debug("Loaded CiType with code 'RELEASENOTES': %s", self._releasenotes_citype)
        except ObjectDoesNotExist as err:
            logging.exception("Required DB entries not found")
            raise EnvironmentError("DB setup is required: \n 1) NXS LocTypes\n"
                                   "2) RELEASENOTES CiType")

    def enhance_resources(self, resources, context):
        artifacts = list(filter(lambda resource: resource.location_stub.location_type.code == "NXS", resources))
        releasenotes = list(chain(*[self._resolve_releasenote(artifact, context.nexus_fs)
                                    for artifact in artifacts]))
        logging.debug("Resolved %d release notes", len(releasenotes))
        return releasenotes

    def _resolve_releasenote(self, nexus_resource, nexus_fs):
        # check if release notes from citype group are available
        gav = nexus_resource.location_stub.path
        existing_gavs = list(filter(nexus_fs.exists, get_possible_releasenotes_gavs(gav)))
        if existing_gavs:
            logging.debug("Using release note GAV: %s", existing_gavs[0])
            return [self._create_releasenote_resource(existing_gavs[0], nexus_fs)]
        else:
            logging.debug("No release notes found for GAV: %s", gav)
            return []

    def _create_releasenote_resource(self, gav, nexus_fs):
        logging.debug("Creating DeliveryResource for GAV: %s", gav)
        location = LocationStub(self._at_nexus, self._releasenotes_citype, gav, None)
        resource_data = FileBasedResourceData(FSLocation(nexus_fs, gav))
        resource = DeliveryResource(location, resource_data)

        logging.debug("Created DeliveryResource: %s", resource)
        return resource
