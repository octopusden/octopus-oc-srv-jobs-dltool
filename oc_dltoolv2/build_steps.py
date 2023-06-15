from collections import namedtuple

from oc_pyfs import SvnFS, NexusFS
from fs import copy as fs_copy
from fs.tempfs import TempFS

from oc_dltoolv2.SqlWrapper import SqlWrapper
from oc_dltoolv2.archiver import DeliveryArchiver
from oc_dltoolv2.local_load import download_resource
from oc_dltoolv2.resolver import BuildRequestResolver
from oc_dltoolv2.resources import RequestContext
from oc_dltoolv2.wrapper import Wrapper
from oc_dltoolv2.delivery_exceptions import DeliveryDeniedException
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
    local_fs, conn_mgr = context
    svn_client = conn_mgr.get_svn_client("SVN")
    branch_fs = SvnFS.SvnFS(branch_url, svn_client)
    nexus_client = conn_mgr.get_mvn_client("MVN", readonly=True)
    nexus_fs = NexusFS.NexusFS(nexus_client)

    request_context = RequestContext(branch_fs, nexus_fs)  # RequestContext is a NamedTuple
    resources = BuildRequestResolver().resolve_request(delivery_list, request_context)
    cached_resources = [download_resource(resource, local_fs)
                        for resource in resources]
    return cached_resources

def build_delivery(resources, delivery_params, context):
    """ Packages delivery resources into archive performing required obfuscation
    :param resources: DeliveryResource list
    :param delivery_params: delivery parameters (parsed as ConfigObj)
    :param context: BuildContext instance
    :return: path to archive in local_fs """
    local_fs, conn_mgr = context
    svn_client = conn_mgr.get_svn_client("SVN")
    branch_fs = SvnFS.SvnFS(delivery_params["mf_tag_svn"], svn_client)

    with TempFS(temp_dir=".") as workdir_fs:
        wrapper = Wrapper(SqlWrapper())
        wrapped_resources = wrapper.get_wrapped_resources(resources, branch_fs)
        svn_prefix = branch_fs.getsyspath("/")
        archiver = DeliveryArchiver(workdir_fs, delivery_params)
        temp_archive_name = archiver.build_archive(wrapped_resources, svn_prefix)
        fs_copy.copy_file(workdir_fs, temp_archive_name, local_fs, temp_archive_name)
    return temp_archive_name


def upload_delivery(archive_path, gav, context):
    """ Uploads delivery archive to Nexus under given name
    :param archive_name: path to delivery archive in local_fs
    :param gav: NexusAPI's gav of delivery to save 
    :param context: BuildContext instance
    """
    local_fs, conn_mgr = context
    upload_repo = conn_mgr.get_credential("MVN_UPLOAD_REPO")
    nexus_client = conn_mgr.get_mvn_client("MVN")
    gav_str = "%s:%s:%s:zip" % tuple(gav[key] for key in ["g", "a", "v"])
    with local_fs.openbin(archive_path) as zip_file:
        nexus_client.upload(gav_str, data=zip_file, repo=upload_repo)

def calculate_and_check_checksums(resources, api_client):
    """
    Calculate checksum for each file in resources list and check if the
    distributive is allowed for delivering using Distributives Mongo API
    :param resources: DeliveryResource list
    :param api_client: DistributivesAPIClient object
    :return: list, paths and checksums within separate dicts
    """
    calculated_checksums = []
    for resource in resources:
        location_stub, resource_data = resource

        with resource_data.get_content() as content_handle:
            hmd5 = md5()
            while True:
                chunk = content_handle.read(1 * 1024 * 1024)  # read in 1M chunks, 16M was too much
                if not chunk: break
                hmd5.update(chunk)

            str_md5 = hmd5.hexdigest()
            loc_type = str(location_stub.location_type).split(":")[0]

            if not api_client.check_distributive_allowance(str_md5):
                raise DeliveryDeniedException("{} is forbidden for delivery".format(location_stub.path))
    
            calculated_checksums.append({"path": location_stub.path, "checksum": str_md5})

    return calculated_checksums

