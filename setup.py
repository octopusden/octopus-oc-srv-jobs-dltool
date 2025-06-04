from setuptools import setup

included_packages = ["oc_dltoolv2"]

__version = '4.0.3'

spec = { "name": "oc-dltool",
         "version": __version,
         "description": "Includes tools for delivery build and release",
         "long_description": "",
         "long_description_content_type": "text/plain",
         "python_requires": ">=3.6",
         "install_requires": [
           "oc-checksumsq",
           "oc-connections",
           "oc-cdt-queue2",
           "oc-dlinterface",
           "oc-portal-commons",
           "oc-delivery-apps",
           "oc-orm-initializator",
           "oc-mailer",
           "oc-sql-helpers",
           "requests",
           "oc-logging"
         ],
         "packages": included_packages,
         "python_requires": ">=3.6"
      }

setup (**spec)
