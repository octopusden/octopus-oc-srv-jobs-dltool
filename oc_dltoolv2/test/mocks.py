import json
from fs.memoryfs import MemoryFS
from oc_dltoolv2.dlbuild_worker import DLBuildWorker
from oc_cdt_queue2.test.synchron.mocks.queue_application import QueueApplication
import posixpath

class MockConnectionManager(object):

    def get_svn_client(self, resource):
        pass

    def get_svn_connection(self):
        pass

    def get_credential(self, full_name, required=True):
        pass

    def get_smtp_connection(self, **kwargs):
        return self.get_smtp_client("SMTP", **kwargs)

    def get_smtp_client(self, resource, **kwargs):
        client = "SMTP_client"
        return client

    def get_mvn_fs_client(self, resource, **kwargs):
        NexusFS = "NexusFS"
        return NexusFS

    def get_svn_fs_client(self, resource, *args, **kwargs):
        svn_fs = MemoryFS()
        svn_fs.makedirs(u"Russia/RUSTEST/data")
        return svn_fs

    def get_ftp_fs_client(self, resource, **kwargs):
        pass

class DLBuildWorkerMock(DLBuildWorker, QueueApplication):
    connect = QueueApplication.connect
    run = QueueApplication.run
    main = QueueApplication.main
    _connect_and_run = QueueApplication._connect_and_run

def mocked_requests(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code
            self.text = json_data

        def json(self):
            return self.json_data

    if 'client_counterparty' in args[0].split(posixpath.sep):
        _client_code = args[0].split(posixpath.sep).pop() 
        if _client_code == '_TEST_ORG_CLIENT':
            return MockResponse({_client_code: "org"}, 200)
        if _client_code == '_TEST_COM_CLIENT':
            return MockResponse({_client_code: "com"}, 200)
        return MockResponse({}, 200)

    if posixpath.basename(args[0]) != 'artifact_deliverable':
        return MockResponse("Not found", 404)

    checksum = kwargs.get("json").get("checksum")

    return MockResponse([checksum not in["e003299939fdaffbfff4273117ec5399", "4d9d318f41ca659e7721360847058e29", "e003299939fdaffbfff4273117fd1236"]], 200)
