from oc_pyfs.SvnFS import SvnFS
from django.db.models import Q
from oc_delivery_apps.dlmanager.models import Delivery
import logging


from oc_dltoolv2.errors import BuildError


def delivery_is_in_db(delivery_params):
    group_criterion = Q(groupid=delivery_params["groupid"])
    artifact_criterion = Q(artifactid=delivery_params["artifactid"])
    version_criterion = Q(version=delivery_params["version"])
    debug_message = "Check if delivery with GAV %s%s%s is in DB" % (delivery_params["groupid"], delivery_params["artifactid"], delivery_params["version"])
    logging.debug(debug_message)

    delivery_number = Delivery.objects.filter(group_criterion &
                                              artifact_criterion &
                                              version_criterion).count()
    if delivery_number != 0:
        logging.debug("Delivery is already stored in DB")
        return True
    else:
        logging.debug("Delivery is NOT in DB")
        return False


def save_delivery_to_db(delivery_params, resources, context):
    svn_client = context.conn_mgr.get_svn_client("SVN")
    branch_url = delivery_params["mf_tag_svn"]
    branch_fs = SvnFS(branch_url, svn_client)
    svn_prefix = branch_fs.getsyspath("/")
    expanded_list = [_get_resource_name(resource, svn_prefix)
                     for resource in resources]
    delivery_params["mf_delivery_files_specified"] = "\n".join(expanded_list)

    delivery = Delivery()
    for param, value in delivery_params.items():
        setattr(delivery, param, value)
    delivery.save()
    return delivery


def _get_resource_name(resource, svn_prefix):
    loc_type_code = resource.location_stub.location_type.code
    full_path = resource.location_stub.path
    if loc_type_code == "SVN":
        name = full_path.replace(svn_prefix, "", 1).strip("/")
    elif loc_type_code == "NXS":
        name = full_path
    else:
        raise BuildError("Cannot get name for resource %s(%s)" %
                         (full_path, loc_type_code))
    return name
