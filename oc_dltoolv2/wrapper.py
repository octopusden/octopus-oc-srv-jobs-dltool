import logging
import os, posixpath
from io import BytesIO
#from itertools import ifilter, ifilterfalse
from itertools import filterfalse as ifilterfalse

from fs.errors import ResourceNotFound
from fs.tempfs import TempFS

from oc_dltoolv2.SqlWrapper import WrappingError
from oc_dltoolv2.resources import ResourceData, DeliveryResource



class Wrapper(object):
    """ Performs obfuscation of given resources (currently only SQL scripts wrapping) """

    def __init__(self, wrap_client):
        """  :param wrap_client: object with SqlWrapper interface """
        self._wrap_client = wrap_client
        self.WRAPPER_C_OWNER_LOC = '\x63\x61\x72ds/o\x77s_\x77ork/db/scripts/inst\x61ll/o\x77so\x77ner'
        self.WRAPPER_D_OWNER_LOC = 'd\x77h/o\x77s_\x77ork/db/scripts/inst\x61ll/o\x77so\x77ner'
        self.WRAPPER_C_OWNER_LOC_HOME = '\x63\x61\x72ds/o\x77s_home/db/scripts/inst\x61ll/o\x77so\x77ner'
        self.WRAPPER_D_OWNER_LOC_HOME = 'd\x77h/o\x77s_home/db/scripts/install/o\x77so\x77ner'
        self.WRAPPER_C_PREFIX = '\x63\x61\x72ds'
        self.WRAPPER_D_PREFIX = 'd\x77h'

    def get_wrapped_resources(self, resources, svn_fs):
        """ Wraps some of SVN resources. Files being wrapped are:
        1) custs specified in wrap.txt 
        2) package bodies in owner folders 
        Rules are case-insensitive.
        :param resources: list of DeliveryResource. Non-SVN resources are kept unchanged
        :param svn_fs: SvnFS pointing to root of branch. Used to determine wrap list 
        :return: list of DeliveryResource where files to wrap are replaced with its wrapped versions """
        selected, skipped = self._split_resources(resources, svn_fs)
        logging.info("To be wrapped: " + ", ".join([resource.location_stub.path
                                                   for resource in selected]))
        wrapped_resources = list (map(self._wrap_resource, selected) )
        resulting_resources = wrapped_resources + skipped
        return resulting_resources

    def _split_resources(self, resources, svn_fs):
        is_svn_resource = lambda resource: resource.location_stub.location_type.code == "SVN"
        wrap_list = self._get_files_to_wrap(svn_fs)
        # endswith because path starts with client branch url
        should_wrap = lambda resource: any(resource.location_stub.path.endswith(path)
                                           for path in wrap_list)
        is_selected = lambda resource: is_svn_resource(resource) and should_wrap(resource)
        skipped = list(ifilterfalse(is_selected, resources))
        selected = list(filter(is_selected, resources))
        return selected, skipped

    def _wrap_resource(self, resource):
        try:
            wrapped_data = WrappedResourceData(resource.resource_data, self._wrap_client)
        except WrappingError:
            logging.exception("Wrapping failed for %s" % resource.location_stub.path)
            raise
        # wrapping is transparent - location_stub still points to svn
        wrapped_resource = DeliveryResource(resource.location_stub, wrapped_data)
        return wrapped_resource

    def _get_files_to_wrap(self, svn_fs):
        c_owner_loc = self.WRAPPER_C_OWNER_LOC
        d_owner_loc = self.WRAPPER_D_OWNER_LOC
        c_custs_loc = posixpath.join(c_owner_loc, 'cust')
        d_custs_loc = posixpath.join(d_owner_loc, 'cust')
        c_owner_loc_home = self.WRAPPER_C_OWNER_LOC_HOME
        d_owner_loc_home = self.WRAPPER_D_OWNER_LOC_HOME
        c_prefix = self.WRAPPER_C_PREFIX
        d_prefix = self.WRAPPER_D_PREFIX

        place_in_folder = lambda files, folder: [_join_path(folder, path)
                                                 for path in files]

        c_custs = self._read_wrap_file(_join_path(c_prefix, "wrap.txt"), c_custs_loc, svn_fs)
        d_custs = self._read_wrap_file(_join_path(d_prefix, "wrap.txt"), d_custs_loc, svn_fs)

        c_scripts = self._list_private_scripts(_join_path(c_owner_loc), svn_fs)
        d_scripts = self._list_private_scripts(_join_path(d_owner_loc), svn_fs)
        c_scripts_from_home = self._list_private_scripts(_join_path(c_owner_loc_home), svn_fs)
        d_scripts_from_home = self._list_private_scripts(_join_path(d_owner_loc_home), svn_fs)

        files_to_wrap = (place_in_folder(c_custs, c_custs_loc) +
                         place_in_folder(d_custs, d_custs_loc) +
                         place_in_folder(c_scripts, c_owner_loc) +
                         place_in_folder(d_scripts, d_owner_loc) +
                         place_in_folder(c_scripts_from_home, c_owner_loc_home) +
                         place_in_folder(d_scripts_from_home, d_owner_loc_home))
        return files_to_wrap

    def _read_wrap_file(self, file_url, folder_url, svn_fs):
        try:
            with svn_fs.open(file_url) as wrap_file:
                requested_custs = list(filter(lambda y: bool(y), list(map(lambda x: x.strip(), wrap_file.readlines()))))
            existing_custs = svn_fs.listdir(folder_url)
            resulting_custs = [cust for cust in existing_custs
                               if cust.lower() in requested_custs]
            return resulting_custs
        except ResourceNotFound as err:
            return []  # no wrap file - no custs to wrap

    def _list_private_scripts(self, folder_url, svn_fs):
        is_private = lambda filename: filename.lower().endswith("_b.sql")
        try:
            all_scripts = svn_fs.listdir(folder_url)
            privates = list (filter(is_private, all_scripts) )
            return privates
        except ResourceNotFound:
            return []  # no owner dir - no files to wrap


class WrappedResourceData(ResourceData):

    def __init__(self, data, wrap_client):
        super(ResourceData, self).__init__()
        # assume file is quite small, so wrapped content can be stored in memory
        self._wrapped_content = self._wrap_data(data, wrap_client)

    def _wrap_data(self, data, wrap_client):
        with TempFS() as temp_fs:
            with data.get_content() as content_handle:
                temp_fs.upload("filename", content_handle)
                wrap_client.wrap_file(temp_fs, "filename")
                wrapped_content = temp_fs.readbytes("filename")
        return wrapped_content

    def get_content(self):
        return BytesIO(self._wrapped_content)


def _join_path(*args):
    return os.path.join(*[token.strip("/")
                          for token in args])
