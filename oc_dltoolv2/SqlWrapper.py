import os

from oc_sql_helpers.normalizer import PLSQLNormalizer
from oc_dltoolv2.subprocess_wrapper import SubprocessWrapper

# if SubprocessWrapper()._execute_and_get(["which", "wrap"])[2]!=0:
#     raise EnvironmentError("'wrap' utility not found")
from fs.tempfs import TempFS
from fs import copy as fs_copy


class WrappingError(Exception):
    pass


class MissingFileError(Exception):
    pass


class SqlWrapper(object):

    def wrap_file(self, fs, file_path):
        if not fs.exists(file_path):
            raise MissingFileError("%s not found" % file_path)
        source_name = "source.sql"
        wrapped_name = "wrapped.sql"
        with TempFS() as temp_fs:
            fs_copy.copy_file(fs, unicode(file_path),
                              temp_fs, source_name)
            temp_dir = temp_fs._temp_dir
            self._call_wrap(os.path.join(temp_dir, source_name),
                            output_file_name=os.path.join(temp_dir, wrapped_name))
            fs_copy.copy_file(temp_fs, wrapped_name,
                              fs, unicode(file_path), )

    def _call_wrap(self, orig_file_path, output_file_name=None, keep_original_file=False):
        if not os.path.exists(orig_file_path):
            raise MissingFileError("Input file %s does not exists" % orig_file_path)
        if not output_file_name:
            output_file_name = orig_file_path
        call_args = ['wrap', "iname=%s" % orig_file_path, "oname=%s.tmp" % output_file_name]
        cmd_out, cmd_err, code = SubprocessWrapper()._execute_and_get(call_args)
        if code != 0:
            raise WrappingError("Wrapping failed for file %s: %s\n\n%s" %
                                (orig_file_path, cmd_out, cmd_err))
        if not self._was_wrapped(output_file_name + ".tmp"):
            message = ("'wrap' call succeeded, but no actual wrap was performed. "
                       "It may be caused by manual unwrap of source file")
            raise WrappingError(message)
        if not keep_original_file:
            os.remove(orig_file_path)
        os.rename(output_file_name + ".tmp", output_file_name)
        return output_file_name

    def _was_wrapped(self, path):
        with open(path) as output_file:
            return PLSQLNormalizer().object_is_wrapped(output_file)
