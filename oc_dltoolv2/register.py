import logging
from hashlib import md5

from oc_checksumsq.checksums_interface import FileLocation
from fs.errors import ResourceNotFound

logger = logging.getLogger(__name__)


def register_delivery_resource(resource, registration_client, checksums_list):
    """
    Registers (put checksumms into DB) single delivery source file. Should have proper path as it is used to determine CiType.
    It should be called before register_delivery_content in order to create correct File entries.
    :param resource: DeliveryResource item
    """
    location_stub, resource_data = resource

    precalculated_checksum = None
    
    if checksums_list:
        precalculated_checksum = next((distributive["checksum"] for distributive in checksums_list if distributive["path"] == location_stub.path), None)
    
    if precalculated_checksum:
        checksum = precalculated_checksum
    else:
        with resource_data.get_content() as content_handle:
            hmd5 = md5()
            while True:
                chunk = content_handle.read(1 * 1024 * 1024)  # read in 1M chunks, 16M was too much
                if not chunk: break
                hmd5.update(chunk)
            checksum = hmd5.hexdigest()
    
    file_location = FileLocation(location_stub.path, location_stub.location_type.code, location_stub.revision)
    registration_client.register_checksum(file_location, checksum, citype=location_stub.citype.code)


def register_delivery_content(local_fs, archive_path, gav, registration_client):
    """ 
    Registers delivery archive and files included in it.
    :param local_fs: pyfilesystem-like object
    :param archive_path: path to delivery archive in local_fs
    :param gav: NexusAPI's GAV to register under
    """
    gav_str = "%s:%s:%s:zip" % tuple(gav[key] for key in ["g", "a", "v"])
    try:
        if local_fs.getinfo(archive_path, namespaces=["details"]).size == 0:
            raise RegisterError("File %s for %s is empty" % (archive_path, gav_str))
        file_location = FileLocation(gav_str, "NXS", None)
        registration_client.register_file(file_location, "DELIVERY", 1)
    except ResourceNotFound:
        raise RegisterError("File %s not found for %s" % (archive_path, gav_str))


class RegisterError(Exception):
    pass
