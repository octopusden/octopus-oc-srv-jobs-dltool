import uuid

from .resources import DeliveryResource, ResourceData


def download_resource(resource, work_fs):
    """ Caches resource locally for faster access 
    :param resource: DeliveryResource to be cached 
    :param work_fs: pyfilesystem2-like object used to place cached content 
    :return: DeliveryResource with same location_stub and LocallyCachedResourceData with cached content """
    cached_data = LocallyCachedResourceData(resource.resource_data, work_fs)
    cached_resource = DeliveryResource(resource.location_stub, cached_data)
    return cached_resource


class LocallyCachedResourceData(ResourceData):

    def __init__(self, wrapped_data, cache_fs):
        self.cache_fs = cache_fs
        self.cache_filename = "cache_%s" % uuid.uuid4()
        with wrapped_data.get_content() as content_handle:
            cache_fs.upload(self.cache_filename, content_handle)

    def get_content(self):
        return self.cache_fs.openbin(self.cache_filename)
