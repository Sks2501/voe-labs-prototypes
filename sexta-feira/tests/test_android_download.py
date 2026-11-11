import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from sexta_feira.storage import Storage
from sexta_feira.server import AssistantServer


class AndroidDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        data=Path(self.temp.name)
        self.release=data/'android-release';self.release.mkdir()
        self.apk=b'PK\x03\x04TEST-INSTALLER-NOT-A-REAL-APK'
        (self.release/'sexta-feira-android-1.0.0.apk').write_bytes(self.apk)
        self.meta={'version':'1.0.0','filename':'sexta-feira-android-1.0.0.apk','package':'online.teambike.sextafeira',
                   'min_sdk':26,'bytes':len(self.apk),'sha256':hashlib.sha256(self.apk).hexdigest(),'certificate_sha256':'a'*64}
        self.write_meta()
        self.server=AssistantServer(('127.0.0.1',0),'android-test-token-private','small',Storage(data/'memory.sqlite3'))
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':0.05},daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(5);self.temp.cleanup()

    def write_meta(self):
        (self.release/'android-release.json').write_text(json.dumps(self.meta),encoding='utf-8')

    def call(self,path,method='GET'):
        connection=HTTPConnection('127.0.0.1',self.server.server_address[1],timeout=5)
        connection.request(method,path)
        response=connection.getresponse();status=response.status;headers=dict(response.getheaders());data=response.read();connection.close()
        return status,headers,data

    def test_public_installer_get_head_and_private_api_boundary(self):
        status,headers,data=self.call('/downloads/sexta-feira-android.apk')
        self.assertEqual((status,data),(200,self.apk))
        self.assertEqual(headers['Content-Type'],'application/vnd.android.package-archive')
        self.assertIn('attachment;',headers['Content-Disposition'])
        status,headers,data=self.call('/downloads/sexta-feira-android.apk','HEAD')
        self.assertEqual((status,data),(200,b''))
        self.assertEqual(int(headers['Content-Length']),len(self.apk))
        self.assertEqual(self.call('/api/v1/health')[0],401)
        self.assertNotEqual(self.call('/downloads/access.token')[0],200)

    def test_landing_metadata_and_icon_are_public_without_private_paths(self):
        status,_,data=self.call('/android')
        self.assertEqual(status,200)
        self.assertIn(self.meta['sha256'].encode(),data)
        self.assertNotIn(b'{{VERSION}}',data)
        status,_,data=self.call('/android/release.json')
        meta=json.loads(data)
        self.assertEqual(status,200)
        self.assertNotIn('filename',meta)
        self.assertEqual(self.call('/android-icon.svg')[0],200)

    def test_tamper_missing_release_and_path_escape_fail_closed(self):
        (self.release/'sexta-feira-android-1.0.0.apk').write_bytes(b'changed')
        self.assertEqual(self.call('/downloads/sexta-feira-android.apk')[0],503)
        self.meta['filename']='../access.token';self.write_meta()
        self.assertEqual(self.call('/android')[0],503)
        (self.release/'android-release.json').unlink()
        self.assertEqual(self.call('/android')[0],503)

    def test_manifest_requests_no_microphone_files_or_paid_services(self):
        manifest=ET.parse(Path(__file__).resolve().parents[1]/'android/app/src/main/AndroidManifest.xml').getroot()
        attr='{http://schemas.android.com/apk/res/android}'
        self.assertEqual([p.attrib[attr+'name'] for p in manifest.findall('uses-permission')],['android.permission.INTERNET'])
        application=manifest.find('application')
        self.assertEqual(application.attrib[attr+'usesCleartextTraffic'],'false')
        self.assertEqual(application.attrib[attr+'allowBackup'],'false')
