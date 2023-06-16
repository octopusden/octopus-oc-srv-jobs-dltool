import os
from setuptools import setup

def list_recursive(app, directory, extension="*"):
    """
    it's the only way to include dir recursively
    MANIFEST file can be used but is does not includes to binary distribution 
    """
    dir_to_walk = os.path.join(app, directory)
    found = [result for (cur_dir, subdirs, files) in os.walk(dir_to_walk)
             for result in glob.glob(os.path.join(cur_dir, '*.' + extension))]
    found_in_package = map(lambda x: x.replace(app + "/", "", 1), found)
    return found_in_package


included_packages = ["oc_dltoolv2"]

__version = '3.10.3'

spec = { "name": "oc-dltool",
         "version": __version,
         "description": "Includes tools for delivery build and release",
         "long_description": "",
         "long_description_content_type": "text/plain",
         "install_requires": [
           "oc-checksumsq",
           "oc-connections",
           "oc-cdt_queue2",
           "oc-dlinterface",
           "oc-portal-commons",
           "oc-delivery-apps",
           "oc-orm-initializator",
           "oc-mailer",
           "oc-sql-helpers",
           "requests",
           "mock",
           "coverage",
           "django",
           "django_tests"
         ],
         "packages": included_packages
      }

setup (**spec)
