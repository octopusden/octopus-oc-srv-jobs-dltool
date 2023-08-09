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
    _version = parse_gav(gav).get("v")
    _version_regexp = re.compile("[\.\-]")
    _versions = list()

    while _version:
        _versions.append(_version)
        _version = _version[:-len(_version_regexp.split(_version).pop())].rstrip(".").rstrip("-")

    _csc = CheckSumsController()
    citype_code = _csc.ci_type_by_path(gav, "NXS")
    possible_releasenotes_gavs = list(map(lambda x: _csc.get_rn_gav(citype_code, x), _versions))

    # many components have artifactid like 'CODE-postfix'
    # where CODE is artifactid of releasenotes
    artifactid = parse_gav(gav).get("a")
    component_code = artifactid.rsplit("-", 1).pop(0)
    test_group = CiTypeGroups(code="tmp", name="tmp", rn_artifactid=component_code)
    component_releasenotes_gav = list(map(lambda x: test_group.get_rn_gav(x), _versions))
    possible_releasenotes_gavs.extend(component_releasenotes_gav)
    return list(filter(lambda x: bool(x), possible_releasenotes_gavs))
