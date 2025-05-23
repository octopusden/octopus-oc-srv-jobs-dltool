"""
These classes are used to:
1) retrieve delivery params in dict-like object by client country, code and gav
2) request delivery creation by delivery params in dict-like object and local fs with files which only present locally
"""

import os
import re
import locale
import pika
import pysvn
from oc_cdtapi.JenkinsAPI import JenkinsError
from oc_pyfs.SvnFS import SvnFS
from configobj import ConfigObj
from oc_delivery_apps.dlmanager.DLModels import DeliveryList
from fs.copy import copy_file
from fs.errors import ResourceNotFound
from fs.tempfs import TempFS
import logging

from .delivery_attributes import get_tag_delivery_name


class SvnDeliveryChannel(object):
    """
    This channel allows to create tag for delivery.
    Tag URL is based on delivery GAV.
    Also upon tag creation file with delivery parameters is added;
    parameters retrieval is based on this file's content.    
    """
    locale.setlocale(locale.LC_ALL, 'C') # We're setting this parameter to avoid issues with unicode literals in SVN files' names. SI-9667
    params_file_path = "delivery_info.txt"

    def __init__(self, clients_repo_url, svn_client):
        self.clients_repo_url = clients_repo_url
        self.svn_client = svn_client
    
    def _check_svn_url(self, url):
        """
        Changes the SVN url according to a configurated one 
        """
        url = re.sub('^http(.+)?://.*svn/.+?/', self.clients_repo_url, url)
        return url

    def read_delivery_params(self, country, client, gav):
        # we don't know exact name of tag but we can filter tags matching (hf-/mig-/prj-)aid-ver
        # there should be only one tag
        logging.info("Starting read_delivery_params with country=%s, client=%s, gav=%s", country, client, gav)
        client_url = os.path.join(self.clients_repo_url, country, client)
        tag_url = self._find_delivery_tag(client_url, gav)
        conf = self.read_delivery_at_branch(tag_url)
        logging.info("Completed read_delivery_params")
        return conf

    def _find_delivery_tag(self, client_repo_url, gav):
        logging.info("Starting _find_delivery_tag with client_repo_url=%s, gav=%s", client_repo_url, gav)
        client_tags_url = os.path.join(client_repo_url, "tags")
        tags_fs = SvnFS(client_tags_url, self.svn_client)
        all_tags = tags_fs.listdir("/")
        tag_name_pattern = get_tag_delivery_name(gav["a"], gav["v"])
        matches_pattern = lambda tag: tag.endswith(tag_name_pattern)
        matching_tags = list(filter(matches_pattern, all_tags))
        if len(matching_tags) != 1:
            raise ChannelError("There are %d tags matching pattern %s at %s - exactly 1 expected"
                               % (len(matching_tags), tag_name_pattern, client_tags_url))
        tag_name = matching_tags[0]
        tag_url = os.path.join(client_tags_url, tag_name)
        logging.info("Completed _find_delivery_tag with tag_url=%s", tag_url)
        return tag_url

    def read_delivery_at_branch(self, url):
        """
        :param url: url to read parms from
        :return: dict of delivery attributes (keys are equal to db model fields)
        """
        logging.debug('Reached read_delivery_at_branch')
        logging.debug('url = [%s]' % url)
        logging.debug('self.svn_client = [%s]' % self.svn_client)
        logging.info("Starting read_delivery_at_branch with url=%s", url)
        branch_fs = SvnFS(url, self.svn_client)
        if not url.startswith(self.clients_repo_url):
            raise ValueError("Target URL must start with %s" % self.clients_repo_url)
        try:
            with branch_fs.open(self.params_file_path) as params_file:
                conf = ConfigObj(params_file, default_encoding="UTF8", encoding="UTF8")
                revision = self.svn_client.info2(url, recurse=False)[0][1].rev.number
                conf["mf_delivery_revision"] = revision
                logging.info("Completed read_delivery_at_branch")
                return conf
        except ResourceNotFound:
            logging.error("No delivery params file at %s" % url)
            raise ChannelError("No delivery params file at %s" % url)

    def save_delivery_params(self, delivery_params, local_fs):
        """
        Save delivery parms to TempFS
        :param delivery_params: parsed delivery parms
        :param local_fs: TODO who is that
        """
        logging.info("Starting save_delivery_params")
        source_branch = self._check_svn_url(delivery_params["mf_source_svn"])
        tag_url = self._check_svn_url(delivery_params["mf_tag_svn"])
        gav = ":".join(delivery_params[key] for key in
                       ["groupid", "artifactid", "version"])

        tag_name_pattern = get_tag_delivery_name(delivery_params["artifactid"],
                                                 delivery_params["version"])
        # assure that we'll able to find it later
        if not tag_url.strip("/").endswith(tag_name_pattern):
            raise ValueError("Tag url for %s must end with %s"
                             % (gav, tag_name_pattern))
        message = "Creating tag from base branch %s" % source_branch
        self.svn_client.callback_get_log_message = lambda: (True, message)
        configobj = ConfigObj(delivery_params, default_encoding="UTF8", encoding="UTF8")
        with TempFS() as temp_fs:
            temp_dir = temp_fs._temp_dir
            self.svn_client.checkout(source_branch, temp_dir, recurse=False)

            filelist = DeliveryList(configobj["mf_delivery_files_specified"]).filelist
            local_files = [path.strip("/") for path in local_fs.walk.files()
                           if path.strip("/") in filelist]  # add only explicitly included files
            if local_files:
                configobj["generated_files"] = local_files
                for local_path in local_files:
                    self._checkout_nested_dir(temp_dir, os.path.dirname(local_path))
                    copy_file(local_fs, local_path, temp_fs, local_path)
                    self.svn_client.add(os.path.join(temp_dir, local_path))

            if temp_fs.exists(self.params_file_path):
                # ignore existing delivery info and replace it with new one
                self.svn_client.remove(os.path.join(temp_dir, self.params_file_path))

            with temp_fs.openbin(self.params_file_path, "w") as info_file:
                configobj.write(info_file)
            self.svn_client.add(os.path.join(temp_dir, self.params_file_path))
            self.svn_client.copy(temp_dir, tag_url)
        logging.info("Completed save_delivery_params")

    def _checkout_nested_dir(self, local_svn_root, dir_path):
        """
         Sequence of partial checkouts
        :param local_svn_root
        :param dir_path: target dir
        """
        logging.info("Starting _checkout_nested_dir with dir_path=%s", dir_path)
        path_elements = dir_path.split(os.sep)
        dirs_sequence = [os.sep.join(path_elements[:limit]) for limit in range(1, len(path_elements) + 1)]
        for path in dirs_sequence:
            self.svn_client.update(os.path.join(local_svn_root, path), depth=pysvn.depth.immediates)
        logging.info("Completed _checkout_nested_dir")


class CiSvnDeliveryChannel(object):
    """
    This channel wraps svn save functionality and adds Jenkins call
    which builds this delivery.
    This algorithm requires that corresponding tag was successfully created
    """

    def __init__(self, svn_channel, build_job, jenkins_client):
        self.svn_channel = svn_channel
        self.jenkins_client = jenkins_client
        self.build_job = build_job

    def read_delivery_params(self, country, client, gav):
        logging.info("Starting read_delivery_params in CiSvnDeliveryChannel")
        result = self.svn_channel.read_delivery_params(country, client, gav)
        logging.info("Completed read_delivery_params in CiSvnDeliveryChannel")
        return result

    def save_delivery_params(self, delivery_params, local_fs):
        logging.info("Starting save_delivery_params in CiSvnDeliveryChannel")
        self.svn_channel.save_delivery_params(delivery_params, local_fs)
        tag_url = delivery_params["mf_tag_svn"]
        client_code = delivery_params["groupid"].split(".")[-1]
        try:
            result = self.jenkins_client.run_job(self.build_job, {"tag_url": tag_url,
                                                                  "client": client_code})
            logging.info("Completed save_delivery_params in CiSvnDeliveryChannel")
            return result

        except JenkinsError:
            raise ChannelError("Unable to start build for %s" % tag_url)

class AmqpDeliveryChannel(object):
    """
    This channel sends a message with build parameters to the Rabbit's dlbuild queue
    """

    def __init__(self, svn_channel):
        self.svn_channel = svn_channel

    def build_delivery_from_tag(self, delivery_params, local_fs, amqp_client):
        logging.info("Starting build_delivery_from_tag")
        self.svn_channel.save_delivery_params(delivery_params, local_fs)
        tag_url = delivery_params["mf_tag_svn"]
        try:
            amqp_client.build_delivery(tag_url)
            logging.info("Completed build_delivery_from_tag")
        except pika.exceptions.ConnectionClosed:
            raise ChannelError("Unable to start build for %s" % tag_url)


class ChannelError(Exception):
    pass
