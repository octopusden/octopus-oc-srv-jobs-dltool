import os
from logging import debug
from oc_dltoolv2 import DeliveryValidations


def generate_version(timestamp, minor=None):
    """ 
    Generates delivery version in format 'vYYYYmmdd_minor'
    Minor is supposed to be used when delivery with same artifactid created in same day
    """
    date_suffix = timestamp.strftime("%Y%m%d")
    minor_postfix = "_%s" % str(minor) if minor else ""
    version = "v%s%s" % (date_suffix, minor_postfix)
    return version


def generate_delivery_groupid(client_code):
    mvn_prefix = os.environ.get("MVN_PREFIX")
    debug("Generating the delivery groupid with the next MVN_PREFIX value: %s" % (mvn_prefix))
    return "%s.cdt.dltool.c.%s" % (mvn_prefix, client_code)


def extract_project_type(branch):
    prefixes = ["prj", "mig", "hf"]
    for prefix in prefixes:
        if branch.startswith("branches/" + prefix):
            return prefix
    # for int and trunk
    return "prj"


def extract_artifactid(branch):
    DeliveryValidations.validate_project_branch(branch)
    branch_name = branch.split("branches/prj-")[-1]
    return branch_name


def generate_client_base_url(repo_url, country, client_code):
    return os.path.join(repo_url, country, client_code)


def generate_branch_url(client_base_url, source_branch):
    return os.path.join(client_base_url, source_branch)


def generate_tag_url(client_base_url, prj_type, artifactid, version):
    delivery_name = get_tag_delivery_name(artifactid, version)
    tag_name = "%s-%s" % (prj_type, delivery_name)
    return os.path.join(client_base_url, "tags", tag_name)


def get_tag_delivery_name(artifactid, version):
    name = "%s-%s" % (artifactid, version)
    return name
