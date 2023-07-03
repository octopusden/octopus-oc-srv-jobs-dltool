import os
import logging
import random
import re
import string
from collections import Counter

from oc_cdtapi.NexusAPI import parse_gav, gav_to_filename
from oc_delivery_apps.checksums.controllers import CheckSumsController
from fs.compress import write_zip
from fs.errors import DirectoryExists
from fs.tempfs import TempFS
import json
from .delivery_info_decoder import DeliveryInfoDecoder
from .delivery_copyright_appender import DeliveryCopyrightAppender


class DeliveryArchiver(object):
    """ Packages given resources to single zip archive. Resources are placed according to their types """

    def __init__(self, work_fs, delivery_params):
        """ :param work_fs: pyfilesystem2-like object. Will be used as work directory. Should be cleaned by calling code """
        self._work_fs = work_fs
        self._delivery_params = delivery_params

    def build_archive(self, resources, svn_prefix):
        """ Creates zip archive with given resources. Due to big size of archive result is returned via filename, not as content itself. 
        :param resources: list of DeliveryResource. Should be prepared for delivery already (e.g. wrapped)
        :param svn_prefix: URL of branch which SVN resources are belong to. Used to extract relative path in branch from full SVN url (specified in resource.location_stub.path) 
        :return: path to built archive in work_fs. It is a random name, not artifactid-version.zip; caller should rename it itself """
        logging.info("Start building the delivery from '%s'" % svn_prefix)
        if not resources:
            raise ArchivationError("Delivery archive cannot be empty")

        build_id = ''.join(random.sample(string.ascii_lowercase,10))
        archive_name = "%s.zip" % build_id
        resources_layout = self._get_resources_layout(resources, svn_prefix)

        with TempFS(temp_dir=".") as temp_fs:
            for resource, delivery_path in resources_layout:
                self._write_resource(resource.resource_data, delivery_path, temp_fs)

            DeliveryInfoDecoder(self._delivery_params, resources_layout).write_to_file(temp_fs, "delivery_info.json")

            if os.getenv('COUNTERPARTY_ENABLED', 'false').lower() in ['true', 'yes', 'y']:
                DeliveryCopyrightAppender(self._delivery_params).write_to_file(temp_fs, "Copyright")

            with self._work_fs.open(archive_name, "wb") as zip_file:
                write_zip(temp_fs, zip_file)

        return archive_name

    def _get_resources_layout(self, resources, svn_prefix):
        """
        rule to put files of various types into archive
        :param resources:
        :param svn_prefix:
        :return: resource + name in archive
        """
        check_loc_type = lambda code: lambda resource: resource.location_stub.location_type.code == code
        from_svn, from_nexus, remaining = _split_by_conditions(resources, check_loc_type("SVN"),
                                                               check_loc_type("NXS"))
        svn_mapping = [(resource, self._get_svn_file_layout_path(resource, svn_prefix))
                       for resource in from_svn]
        nexus_mapping = self._get_artifacts_layout(from_nexus)
        if remaining:
            resources_description = ", ".join([resource.location_stub.path for resource in remaining])
            raise ArchivationError("No layout rules are known for: " + resources_description)
        return svn_mapping + nexus_mapping

    def _get_svn_file_layout_path(self, resource, svn_prefix):
        """ All svn files go to path similar one in repository. 
        Because resource path is full URL, we need to strip it first """
        full_path = resource.location_stub.path
        if not full_path.startswith(svn_prefix):
            raise ArchivationError("SVN resources should start with %s; got %s"
                                   % (full_path, svn_prefix))
        relative_path = full_path.replace(svn_prefix, "", 1).strip("/")
        return relative_path

    def _get_artifacts_layout(self, resources):
        """ Different artifacts are treated differently:
        1) release notes are placed to separate directory
        2) artifacts with same artifactid and version are placed to directories with name equal to their groupids 
        3) other artifacts are placed at root of archive """
        get_gav = lambda resource: resource.location_stub.path
        make_basename = lambda resource: gav_to_filename(get_gav(resource))
        make_separated_name = lambda resource: "/".join([parse_gav(get_gav(resource))["g"],
                                                         make_basename(resource)])
        make_unversioned_name = lambda resource: "%(a)s.%(p)s" % parse_gav(get_gav(resource))
        basenames = map(make_basename, resources)
        conflicting_names = [value for value, count in Counter(basenames).items()
                             if count > 1]
        is_conflicts = lambda resource: make_basename(resource) in conflicting_names
        is_installer = lambda resource: re.match(r"^.+?:load_sql:.+?:ssp$", get_gav(resource))
        releasenotes, conflicting, installers, regular = _split_by_conditions(resources, self._is_releasenotes,
                                                                              is_conflicts, is_installer)
        place_resources = lambda mapper, resources: [(resource, mapper(resource)) for resource in resources]
        releasenotes_mapping = place_resources(self._get_releasenotes_location, releasenotes)
        separated_mapping = place_resources(make_separated_name, conflicting)
        installers_mapping = place_resources(make_unversioned_name, installers)
        regular_mapping = place_resources(make_basename, regular)
        return releasenotes_mapping + separated_mapping + installers_mapping + regular_mapping

    def _is_releasenotes(self, resource):
        citype = resource.location_stub.citype.code # Locations.objects.get(loc_type__code="NXS", path=resource.location_stub.path).file.ci_type
        return citype == "RELEASENOTES"

    def _get_releasenotes_location(self, resource):
        path_template = "Release Notes/Release notes %s-%s.%s"
        parsed_gav = parse_gav(resource.location_stub.path)
        path = path_template % (parsed_gav["a"], parsed_gav["v"], parsed_gav["p"])
        return path

    def _guess_citype_code(self, resource):
        guesser = CheckSumsController()
        full_path = resource.location_stub.path
        loc_type_code = resource.location_stub.location_type.code
        ci_type = guesser.ci_type_by_path(full_path, loc_type_code)
        return ci_type

    def _write_resource(self, resource_data, delivery_path, temp_fs):
        if temp_fs.exists(delivery_path):
            raise ArchivationError("Path %s already exists in delivery" % delivery_path)
        resource_dir = os.path.dirname(delivery_path)
        try:
            temp_fs.makedirs(resource_dir)
        except DirectoryExists:
            pass
        with resource_data.get_content() as content_handle:
            temp_fs.upload(delivery_path, content_handle)


class ArchivationError(Exception):
    pass


def _split_by_conditions(iterable, *conditions):
    remaining = iterable
    chunks = []
    for condition in conditions:
        chunk = list(filter(condition, remaining))
        remaining = list(filter(lambda item: not condition(item), remaining))
        chunks.append(chunk)
    chunks.append(remaining)
    return chunks
