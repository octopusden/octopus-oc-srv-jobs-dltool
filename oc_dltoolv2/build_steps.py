from collections import namedtuple

from oc_pyfs import SvnFS, NexusFS
from fs import copy as fs_copy
from fs.tempfs import TempFS

from oc_sql_helpers.wrapper import PLSQLWrapper
from .archiver import DeliveryArchiver
from .local_load import download_resource
from .resolver import BuildRequestResolver
from .resources import RequestContext
from .wrapper import Wrapper
from .delivery_exceptions import DeliveryDeniedException
from hashlib import md5
import logging

# Tuple representing working directory and ConnectionManager used to retrieve external connections
BuildContext = namedtuple("BuildContext", ("local_fs", "conn_mgr"))

def collect_sources(branch_url, delivery_list, context):
    """ Collects source files included to delivery to local folder
    :param branch_url: URL of branch to load SVN files from
    :param delivery_list: DeliveryList instance
    :param context: BuildContext instance
    :return: list of DeliveryResource loaded locally """
    logging.info("Starting to collect sources from branch_url: %s", branch_url)
    local_fs, conn_mgr = context
    svn_client = conn_mgr.get_svn_client("SVN")
    branch_fs = SvnFS.SvnFS(branch_url, svn_client)
    nexus_client = conn_mgr.get_mvn_client("MVN", readonly=True)
    nexus_fs = NexusFS.NexusFS(nexus_client)

    request_context = RequestContext(branch_fs, nexus_fs)  # RequestContext is a NamedTuple

    logging.debug("Resolving delivery request using BuildRequestResolver")
    resources = BuildRequestResolver().resolve_request(delivery_list, request_context)

    logging.debug("Downloading resources to local filesystem")
    cached_resources = [download_resource(resource, local_fs)
                        for resource in resources]
    logging.info("Completed collecting sources. Total resources: %d", len(cached_resources))
    return cached_resources

def build_delivery(resources, delivery_params, context):
    """ Packages delivery resources into archive performing required obfuscation
    :param resources: DeliveryResource list
    :param delivery_params: delivery parameters (parsed as ConfigObj)
    :param context: BuildContext instance
    :return: path to archive in local_fs """
    logging.info("Starting to build delivery with %d resources", len(resources))
    local_fs, conn_mgr = context
    svn_client = conn_mgr.get_svn_client("SVN")
    branch_fs = SvnFS.SvnFS(delivery_params["mf_tag_svn"], svn_client)

    with TempFS(temp_dir=".") as workdir_fs:
        logging.debug("Wrapping resources")
        wrapper = Wrapper(PLSQLWrapper())
        wrapped_resources = wrapper.get_wrapped_resources(resources, branch_fs)
        svn_prefix = branch_fs.getsyspath("/")
        logging.debug("Creating delivery archive")
        archiver = DeliveryArchiver(workdir_fs, delivery_params)
        temp_archive_name = archiver.build_archive(wrapped_resources, svn_prefix)
        logging.debug("Copying archive to local filesystem")
        fs_copy.copy_file(workdir_fs, temp_archive_name, local_fs, temp_archive_name)

    logging.info("Delivery build completed: %s", temp_archive_name)
    return temp_archive_name


def upload_delivery(archive_path, gav, context):
    """ Uploads delivery archive to Nexus under given name
    :param archive_name: path to delivery archive in local_fs
    :param gav: NexusAPI's gav of delivery to save 
    :param context: BuildContext instance
    """
    logging.info("Starting upload of delivery archive: %s", archive_path)
    local_fs, conn_mgr = context
    upload_repo = conn_mgr.get_credential("MVN_UPLOAD_REPO")
    nexus_client = conn_mgr.get_mvn_client("MVN")
    gav_str = "%s:%s:%s:zip" % tuple(gav[key] for key in ["g", "a", "v"])
    logging.debug("Uploading archive to Nexus with GAV: %s", gav_str)
    with local_fs.openbin(archive_path) as zip_file:
        nexus_client.upload(gav_str, data=zip_file, repo=upload_repo)
    logging.info("Upload completed for: %s", archive_path)

def calculate_and_check_checksums(resources, api_client):
    """
    Calculate checksum for each file in resources list and check if the
    distributive is allowed for delivering using Distributives Mongo API
    :param resources: DeliveryResource list
    :param api_client: DistributivesAPIClient object
    :return: list, paths and checksums within separate dicts
    """
    logging.info("Starting checksum calculation and distributive check")
    calculated_checksums = []
    for resource in resources:
        location_stub, resource_data = resource
        logging.debug("Calculating checksum for: %s", location_stub.path)

        with resource_data.get_content() as content_handle:
            hmd5 = md5()
            while True:
                chunk = content_handle.read(1 * 1024 * 1024)  # read in 1M chunks, 16M was too much
                if not chunk: break
                hmd5.update(chunk)

            str_md5 = hmd5.hexdigest()
            loc_type = str(location_stub.location_type).split(":")[0]

            logging.debug("Checking allowance for checksum: %s", str_md5)
            if not api_client.check_distributive_allowance(str_md5):
                logging.error("Delivery denied for path: %s, checksum: %s", location_stub.path, str_md5)
                raise DeliveryDeniedException("{} is forbidden for delivery".format(location_stub.path))
    
            calculated_checksums.append({"path": location_stub.path, "checksum": str_md5})
            logging.debug("Checksum accepted: %s", str_md5)

    logging.info("Checksum calculation and validation completed. Total: %d", len(calculated_checksums))
    return calculated_checksums

