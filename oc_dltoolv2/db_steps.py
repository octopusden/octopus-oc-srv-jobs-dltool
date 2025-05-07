from oc_pyfs.SvnFS import SvnFS
from django.db.models import Q
from oc_delivery_apps.dlmanager.models import Delivery
import logging


from .errors import BuildError


def delivery_is_in_db(delivery_params):
    logging.info("Checking if delivery is in DB for GAV: %s:%s:%s",
                 delivery_params["groupid"],
                 delivery_params["artifactid"],
                 delivery_params["version"])

    group_criterion = Q(groupid=delivery_params["groupid"])
    artifact_criterion = Q(artifactid=delivery_params["artifactid"])
    version_criterion = Q(version=delivery_params["version"])

    delivery_number = Delivery.objects.filter(group_criterion &
                                              artifact_criterion &
                                              version_criterion).count()
    logging.info("Deliveries in db: %d" % delivery_number)

    return bool(delivery_number)


def save_delivery_to_db(delivery_params, resources, context):
    logging.info("Saving delivery to DB with GAV: %s:%s:%s",
                 delivery_params["groupid"],
                 delivery_params["artifactid"],
                 delivery_params["version"])

    svn_client = context.conn_mgr.get_svn_client("SVN")
    branch_url = delivery_params["mf_tag_svn"]
    branch_fs = SvnFS(branch_url, svn_client)
    svn_prefix = branch_fs.getsyspath("/")

    logging.debug("Generating list of resource names from SVN prefix: %s", svn_prefix)
    expanded_list = [_get_resource_name(resource, svn_prefix)
                     for resource in resources]
    delivery_params["mf_delivery_files_specified"] = "\n".join(expanded_list)

    delivery = Delivery()
    for param, value in delivery_params.items():
        setattr(delivery, param, value)
    delivery.save()

    logging.info("Delivery saved to DB successfully")
    return delivery


def _get_resource_name(resource, svn_prefix):
    logging.debug("Getting resource name for: %s", resource.location_stub.path)
    loc_type_code = resource.location_stub.location_type.code
    full_path = resource.location_stub.path
    if loc_type_code == "SVN":
        name = full_path.replace(svn_prefix, "", 1).strip("/")
    elif loc_type_code == "NXS":
        name = full_path
    else:
        logging.error("Unknown location type code: %s", loc_type_code)
        raise BuildError("Cannot get name for resource %s(%s)" %
                         (full_path, loc_type_code))
    logging.debug("Resolved resource name: %s", name)
    return name
