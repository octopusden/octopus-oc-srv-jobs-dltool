import logging
import os, posixpath
from io import BytesIO
#from itertools import ifilter, ifilterfalse
from itertools import filterfalse as ifilterfalse

from fs.errors import ResourceNotFound
from fs.tempfs import TempFS

from .resources import ResourceData, DeliveryResource



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
        logging.info("Wrapper initialized with wrap_client: %s" % wrap_client)

    def get_wrapped_resources(self, resources, svn_fs):
        """ Wraps some of SVN resources. Files being wrapped are:
        1) custs specified in wrap.txt 
        2) package bodies in owner folders 
        Rules are case-insensitive.
        :param resources: list of DeliveryResource. Non-SVN resources are kept unchanged
        :param svn_fs: SvnFS pointing to root of branch. Used to determine wrap list 
        :return: list of DeliveryResource where files to wrap are replaced with its wrapped versions """
        logging.info("get_wrapped_resources started")
        selected, skipped = self._split_resources(resources, svn_fs)
        logging.info("To be wrapped: [%s]" % ";".join([resource.location_stub.path
                                                   for resource in selected]))
        wrapped_resources = list(map(self._wrap_resource, selected))
        resulting_resources = wrapped_resources + skipped
        logging.info("get_wrapped_resources completed")
        return resulting_resources

    def _split_resources(self, resources, svn_fs):
        logging.debug("Splitting resources into selected and skipped")
        is_svn_resource = lambda resource: resource.location_stub.location_type.code == "SVN"
        wrap_list = self._get_files_to_wrap(svn_fs)
        # endswith because path starts with client branch url
        should_wrap = lambda resource: any(resource.location_stub.path.lower().endswith(path.lower())
                                           for path in wrap_list)
        is_selected = lambda resource: is_svn_resource(resource) and should_wrap(resource)
        skipped = list(ifilterfalse(is_selected, resources))
        selected = list(filter(is_selected, resources))
        logging.debug("Resources split into selected: %d, skipped: %d" % (len(selected), len(skipped)))
        return selected, skipped

    def _wrap_resource(self, resource):
        logging.info("Wrapping resource: %s" % resource.location_stub.path)
        # there may be an exception - raise it then
        wrapped_data = WrappedResourceData(resource.resource_data, self._wrap_client)
        # wrapping is transparent - location_stub still points to svn
        wrapped_resource = DeliveryResource(resource.location_stub, wrapped_data)
        logging.info("Wrapping completed for %s" % resource.location_stub.path)
        return wrapped_resource

    def _get_files_to_wrap(self, svn_fs):
        logging.info("Getting files to wrap from SVN")
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
        logging.info("Files to wrap retrieved: %d" % len(files_to_wrap))
        return files_to_wrap

    def _read_wrap_file(self, file_url, folder_url, svn_fs):
        logging.debug("Reading wrap file: %s" % file_url)
        try:
            with svn_fs.open(file_url) as wrap_file:
                requested_custs = list(filter(lambda y: bool(y), list(map(lambda x: x.strip().lower(), wrap_file.readlines()))))
            existing_custs = svn_fs.listdir(folder_url)
            logging.debug("Existing custs: [%s]" % (';'.join(existing_custs) if existing_custs else ""))
            logging.debug("Requested custs: [%s]" % (';'.join(requested_custs) if requested_custs else ""))
            resulting_custs = [cust for cust in existing_custs
                               if cust.lower() in requested_custs]
            logging.debug("Wrap file read successfully. Found %d custs to wrap" % len(resulting_custs))
            return resulting_custs
        except ResourceNotFound as err:
            logging.warning("Wrap file not found: %s" % file_url)
            return []  # no wrap file - no custs to wrap

    def _list_private_scripts(self, folder_url, svn_fs):
        logging.debug("Listing private scripts in folder: %s" % folder_url)
        is_private = lambda filename: filename.lower().endswith("_b.sql")
        try:
            all_scripts = svn_fs.listdir(folder_url)
            privates = list (filter(is_private, all_scripts) )
            logging.debug("Found %d private scripts" % len(privates))
            return privates
        except ResourceNotFound:
            logging.warning("No scripts found in folder: %s" % folder_url)
            return []  # no owner dir - no files to wrap


class WrappedResourceData(ResourceData):

    def __init__(self, data, wrap_client):
        super(ResourceData, self).__init__()
        # assume file is quite small, so wrapped content can be stored in memory
        logging.info("Wrapping data using wrap_client")
        self._wrapped_content = self._wrap_data(data, wrap_client)

    def _wrap_data(self, data, wrap_client):
        with TempFS() as temp_fs:
            with data.get_content() as content_handle:
                temp_fs.upload("_f.sql", content_handle)
                wrapped_content = wrap_client.wrap_path(temp_fs.getsyspath("_f.sql"))
        logging.debug("File wrapped successfully")
        return wrapped_content

    def get_content(self):
        logging.debug("Getting wrapped content")
        return BytesIO(self._wrapped_content)


def _join_path(*args):
    joined_path = os.path.join(*[token.strip("/")
                                for token in args])
    logging.debug("Joined path: %s" % joined_path)
    return joined_path

