import logging
import os
import re
from collections import Counter
from itertools import chain, groupby

from oc_cdtapi.NexusAPI import parse_gav, gav_to_filename
from oc_delivery_apps.checksums.models import CiTypes, LocTypes, Locations
from oc_delivery_apps.dlmanager.DLModels import DeliveryList
from oc_delivery_apps.dlmanager.models import PrivateFile

from .enhancements import ReleasenotesEnhancement
from .resources import FSLocation, FileBasedResourceData, DeliveryResource, LocationStub


class BuildRequestResolver(object):
    """ Converts DeliveryList given by user (see DLModels) to list of concrete files from repositories.
    Assigns LocTypes and other location info to requested resources; this information is used further by other modules """

    def __init__(self):
        """ LocTypes from database are used, so we need to ensure that they exist """
        _find_loc_type = lambda code: LocTypes.objects.get(code=code)
        try:
            self._at_svn = _find_loc_type("SVN")
            self._at_nexus = _find_loc_type("NXS")
            self._svn_citype = CiTypes.objects.get(code="SVNFILE")
            self._rn_citype = CiTypes.objects.get(code="RELEASENOTES")
            self._fallback_citype = CiTypes.objects.get(code="FILE")
        except LocTypes.DoesNotExist as err:
            logging.error("Database setup missing: %s" % err)
            raise EnvironmentError("Set up is required: \n 1) LocTypes with codes SVN and NXS\n"
                                   "2) SVNFILE, RELEASENOTES and FILE CiTypes")

    def resolve_request(self, raw_delivery_list, request_context):
        """ Connects to external repositories (specified by request context), checks existence of requested files and performs some manipulations:
        1) replaces SVN directories with list of its contents 
        2) adds release notes if available 
        :param raw_delivery_list: DeliveryList instance
        :param request_context: RequestContext instance
        :return: list of DeliveryResource pointing to files at external repositories """
        delivery_list = self._preprocess_delivery_list(raw_delivery_list)
        if not delivery_list.filelist:
            logging.error("Empty delivery list passed")
            raise ResolutionError("Delivery list should not be empty")
        logging.info("Initial delivery list: " + ", ".join(delivery_list.filelist))

        svn_resources = self._resolve_svn_resources(delivery_list.svn_files, request_context.svn_fs)
        mvn_resources = self._resolve_mvn_resources(delivery_list.mvn_files, request_context.nexus_fs)

        portal_rn_enabled = os.environ.get('PORTAL_RELEASE_NOTES_ENABLED')
        logging.debug("PORTAL_RELEASE_NOTES_ENABLED: %s" % portal_rn_enabled)

        if portal_rn_enabled == 'False' or not portal_rn_enabled:
            logging.debug("Release notes enhancement is enabled")
            additional_resources = ReleasenotesEnhancement().enhance_resources(svn_resources + mvn_resources,
                                                                               request_context)
            all_resources = svn_resources + mvn_resources + additional_resources
        else:
            all_resources = svn_resources + mvn_resources
        resources = _extract_unique_resources(all_resources)
        describe_resource = lambda resource: resource.location_stub.path
        if len(all_resources) > len(resources):
            full_list = ", ".join(map(describe_resource, all_resources))
            logging.warning("Some duplicates were removed from: %s" % full_list)
        private_files = self._detect_private_files(all_resources)
        if private_files:
            full_list = ", ".join(map(describe_resource, private_files))
            logging.error("Private files detected: %s" % full_list)
            raise ResolutionError("The following files should not be sent to client: %s" % full_list)

        logging.info("To be included into delivery: " + ", ".join(map(describe_resource, resources)))
        return list(resources)

    def _resolve_svn_resources(self, svn_pathes, svn_fs):
        logging.debug("Resolving SVN resources: %s" % svn_pathes)
        svn_filenames = list(chain(*(self._expand_svn_path(path, svn_fs) for path in svn_pathes)))
        logging.debug("Expanded SVN filenames: %s" % svn_filenames)
        svn_resources = [self._create_svn_resource(path, svn_fs)
                         for path in svn_filenames]
        return svn_resources

    def _resolve_mvn_resources(self, gavs, nexus_fs):
        logging.debug("Resolving Maven resources: %s" % gavs)
        for gav in gavs:
            self._check_artifact_existence(gav, nexus_fs)
        artifact_resources = [self._create_nexus_resource(gav, nexus_fs, self._citype_by_gav(gav))
                              for gav in gavs]
        return artifact_resources

    def _expand_svn_path(self, svn_path, svn_fs):
        logging.debug("Expanding SVN path: %s" % svn_path)
        if svn_fs.exists(svn_path):
            if svn_fs.isdir(svn_path):
                dir_listing = svn_fs.opendir(svn_path).walk.files()
                listing = [_join_path(svn_path, filename) for filename in dir_listing]
            else:
                listing = [svn_path, ]
            logging.debug("Expanded path %s to: %s" % (svn_path, listing))
            return listing
        else:
            logging.error("SVN file not found: %s" % svn_path)
            raise ResolutionError("SVN file not found: %s" % svn_path)

    def _check_artifact_existence(self, gav, nexus_fs):
        if not nexus_fs.exists(gav):
            logging.error("Artifact not found in Nexus: %s" % gav)
            raise ResolutionError("Artifact not found: %s" % gav)
        logging.debug("Artifact exists: %s" % gav)

    def _get_artifact_delivery_path(self, target_gav, all_gavs):
        make_basename = lambda gav: gav_to_filename(gav)
        basenames = map(make_basename, all_gavs)
        conflicting_names = [value for value, count in Counter(basenames).items()
                             if count > 1]
        target_basename = make_basename(target_gav)
        if target_basename in conflicting_names:
            full_path = "%s/%s" % (parse_gav(target_gav)["g"], target_basename)
        else:
            full_path = target_basename
        logging.debug("Resolved delivery path for %s: %s" % (target_gav, full_path))
        return full_path

    def _create_svn_resource(self, path, svn_fs):
        revision = str(svn_fs.getinfo("/", ["svn"]).get("svn", "revision"))
        # currently 'SVNFILE' is used as common CiType for all files from SVN
        get_svn_location = lambda path: LocationStub(self._at_svn, self._svn_citype,
                                                     svn_fs.getsyspath(path), revision)
        get_svn_resource_data = lambda path: FileBasedResourceData(FSLocation(svn_fs, path))
        resource = DeliveryResource(get_svn_location(path), get_svn_resource_data(path))
        logging.debug("Created SVN resource for path: %s" % path)
        return resource

    def _create_nexus_resource(self, gav, nexus_fs, citype):
        get_artifact_location = lambda gav: LocationStub(self._at_nexus, citype, gav, None)
        get_artifact_resource_data = lambda gav: FileBasedResourceData(FSLocation(nexus_fs, gav))
        resource = DeliveryResource(get_artifact_location(gav), get_artifact_resource_data(gav))
        logging.debug("Created Nexus resource for GAV: %s" % gav)
        return resource

    def _preprocess_delivery_list(self, raw_delivery_list):
        cleaned_filelist = raw_delivery_list.filelist
        cleaned_deliverylist = DeliveryList(cleaned_filelist)
        return cleaned_deliverylist

    def _citype_by_gav(self, gav):
        citype = Locations.objects.get(loc_type__code="NXS", path=gav).file.ci_type
        if citype:
            logging.debug("Resolved CiType for %s: %s" % (gav, citype))
            return citype
        else:
            logging.warning("Cannot determine CiType for %s, using default %s" % (gav, self._fallback_citype))
            return self._fallback_citype

    def _detect_private_files(self, resources):
        prohibited_regexps = PrivateFile.objects.all().values_list("regexp", flat=True)
        is_private = lambda resource: any(re.search(pattern, resource.location_stub.path)
                                          for pattern in prohibited_regexps)
        return list (filter(is_private, resources) )


class ResolutionError(Exception):
    pass


def _join_path(*args):
    return os.path.join(*[token.strip("/")
                          for token in args])


def _extract_unique_resources(resources):
    """ Removes resources with repeating locations (may occur e.g. on release notes resolution).
    First entry is kept, others are dropped """
    # sort is required to group resources by location next
    get_key = lambda resource: resource.location_stub.path
    sorted_resources = sorted(resources, key=get_key)
    grouped_resources = groupby(sorted_resources, key=get_key)
    kept_resources = [next(group) for location, group in grouped_resources]
    return kept_resources
