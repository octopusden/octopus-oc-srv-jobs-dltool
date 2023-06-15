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
        raise NotImplementedError("Subclasses must implement it")


class FileBasedResourceData(ResourceData):
    """ Implements content retrieval via access to some pyFS file """

    def __init__(self, fs_location):
        self.fs_location = fs_location

    def get_content(self):
        fs, location = self.fs_location
        # file descriptor
        content_handle = fs.openbin(location)
        return content_handle


# Represents single file to be included into delivery
DeliveryResource = namedtuple("DeliveryResource",
                              ["location_stub",
                               "resource_data",
                               ])

# Contains data which allows to resolve requested filenames to concrete files from various sources
RequestContext = namedtuple("RequestContext", ["svn_fs", "nexus_fs"])
