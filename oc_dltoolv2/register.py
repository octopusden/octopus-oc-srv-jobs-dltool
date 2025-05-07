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
    logging.debug("Registering delivery resource for path: %s", location_stub.path)

    precalculated_checksum = None
    
    if checksums_list:
        logging.debug("Looking for precalculated checksum in checksums list")
        precalculated_checksum = next((distributive["checksum"] for distributive in checksums_list if distributive["path"] == location_stub.path), None)
    
    if precalculated_checksum:
        logging.debug("Found precalculated checksum: %s", precalculated_checksum)
        checksum = precalculated_checksum
    else:
        logging.debug("No precalculated checksum found, calculating manually")
        with resource_data.get_content() as content_handle:
            hmd5 = md5()
            while True:
                chunk = content_handle.read(1 * 1024 * 1024)  # read in 1M chunks, 16M was too much
                if not chunk: break
                hmd5.update(chunk)
            checksum = hmd5.hexdigest()
    logging.debug("Calculated checksum: %s", checksum)

    file_location = FileLocation(location_stub.path, location_stub.location_type.code, location_stub.revision)
    logging.debug("Registering checksum for file location: %s", file_location)

    registration_client.register_checksum(file_location, checksum, citype=location_stub.citype.code)
    logging.info("Registered checksum for resource: %s", location_stub.path)

def register_delivery_content(local_fs, archive_path, gav, registration_client):
    """ 
    Registers delivery archive and files included in it.
    :param local_fs: pyfilesystem-like object
    :param archive_path: path to delivery archive in local_fs
    :param gav: NexusAPI's GAV to register under
    """
    gav_str = "%s:%s:%s:zip" % tuple(gav[key] for key in ["g", "a", "v"])
    logging.debug("Registering delivery content for GAV: %s", gav_str)
    try:
        if local_fs.getinfo(archive_path, namespaces=["details"]).size == 0:
            logging.error("File %s for %s is empty", archive_path, gav_str)
            raise RegisterError("File %s for %s is empty" % (archive_path, gav_str))
        file_location = FileLocation(gav_str, "NXS", None)
        logging.debug("Registering file with location: %s", file_location)
        registration_client.register_file(file_location, "DELIVERY", 1)
        logging.info("Registered delivery content for GAV: %s", gav_str)
    except ResourceNotFound:
        logging.error("File %s not found for %s", archive_path, gav_str)
        raise RegisterError("File %s not found for %s" % (archive_path, gav_str))


class RegisterError(Exception):
    pass
