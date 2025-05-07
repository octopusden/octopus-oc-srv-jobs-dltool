import logging
from collections import namedtuple

# utility tuple to hold file location
FSLocation = namedtuple("FSLocation",
                        ["fs",  # pyFS instance
                         "location"  # path to file in given fs
                         ])

# identifies concrete file to be included into delivery
# used to create Location database entry
# note that reading resource info should be done via ResourceData
LocationStub = namedtuple("LocationStub",
                          ["location_type",  # LocType instance (db model to define svn/nexus)
                           "citype",  # file type (e.g. TS, NS, etc)
                           "path",  # full path (similar to Location.path)
                           "revision"  # revision, if applicable
                           ])


class ResourceData(object):
    """ Interface to retrieve delivery resource content """

    def get_content(self):
        """ :return: file-like object pointing to resource content. Should be closed by caller """
        logging.debug("ResourceData.get_content: entering abstract method.")
        raise NotImplementedError("Subclasses must implement it")


class FileBasedResourceData(ResourceData):
    """ Implements content retrieval via access to some pyFS file """

    def __init__(self, fs_location):
        logging.debug("FileBasedResourceData.__init__: initializing with fs_location=%s", fs_location)
        self.fs_location = fs_location
        logging.info("FileBasedResourceData.__init__: initialization complete.")

    def get_content(self):
        logging.debug("FileBasedResourceData.get_content: attempting to get content handle from fs_location=%s", self.fs_location)
        fs, location = self.fs_location
        # file descriptor
        content_handle = fs.openbin(location)
        logging.info("FileBasedResourceData.get_content: content handle obtained for location=%s", location)
        return content_handle


# Represents single file to be included into delivery
DeliveryResource = namedtuple("DeliveryResource",
                              ["location_stub",
                               "resource_data",
                               ])

# Contains data which allows to resolve requested filenames to concrete files from various sources
RequestContext = namedtuple("RequestContext", ["svn_fs", "nexus_fs"])
