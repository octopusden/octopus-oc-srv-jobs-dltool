import re

from oc_cdtapi.NexusAPI import parse_gav
from oc_delivery_apps.checksums.controllers import CheckSumsController
from oc_delivery_apps.checksums.models import CiTypeGroups


def get_possible_releasenotes_gavs(gav):
    """
    gets release notes by gav
    :param gav:
    :return: array of found release notes for specified GAV
    """
    version = parse_gav(gav)["v"]
    if re.search("-\d+$", version):
        build_independent_version = version.rsplit("-", 1)[0]
        build_independent_gav = gav.replace(version, build_independent_version)
        get_searched_gavs = lambda initial_gav: [initial_gav, initial_gav.replace(version, build_independent_version)]
    else:
        get_searched_gavs = lambda initial_gav: [initial_gav, ]
    possible_releasenotes_gavs = []
    citype_code = CheckSumsController().ci_type_by_path(gav, "NXS")
    if citype_code:
        group_releasenotes_gav = CheckSumsController().get_rn_gav(citype_code, version)
        if group_releasenotes_gav:
            possible_releasenotes_gavs.extend(get_searched_gavs(group_releasenotes_gav))
    # many components have artifactid like 'CODE-postfix'
    # where CODE is artifactid of releasenotes
    artifactid = parse_gav(gav)["a"]
    component_code = artifactid.rsplit("-", 1)[0]
    test_group = CiTypeGroups(code="tmp", name="tmp", rn_artifactid=component_code)
    component_releasenotes_gav = test_group.get_rn_gav(version)
    possible_releasenotes_gavs.extend(get_searched_gavs(component_releasenotes_gav))
    return possible_releasenotes_gavs
