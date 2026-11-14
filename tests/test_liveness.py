import sys,pathlib,json,unittest
from datetime import datetime,timezone
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'backend'))
import test_service as base

class Rekognition:
    confidence=99
    similarity=99
    def create_face_liveness_session(self,**kwargs):return {'SessionId':'test-live-session'}
    def get_face_liveness_session_results(self,**kwargs):return {'Status':'SUCCEEDED','Confidence':self.confidence,'ReferenceImage':{'Bytes':b'test-live-frame'}}
    def compare_faces(self,**kwargs):return {'FaceMatches':[{'Similarity':self.similarity}]} if self.similarity>=98 else {'FaceMatches':[]}
class STS:
    def assume_role(self,**kwargs):return {'Credentials':{'AccessKeyId':'test','SecretAccessKey':'test','SessionToken':'test','Expiration':datetime.now(timezone.utc)}}
class TrustedLivenessTests(unittest.TestCase):
    setUp=base.APItests.setUp
    call=base.APItests.call
    login=base.APItests.login
    person=base.APItests.person
    def prepare(self):
        self.login('access');self.person();self.app.reko=Rekognition();self.app.sts=STS();self.call('liveness/start','POST',{'personId':'person-1'})
    def test_trusted_liveness_and_match_allows(self):
        self.prepare();r,b=self.call('liveness/result','POST',{'sessionId':'test-live-session'});self.assertEqual(b['outcome'],'allow')
    def test_completed_session_cannot_replay(self):
        self.prepare();self.call('liveness/result','POST',{'sessionId':'test-live-session'});self.assertEqual(self.call('liveness/result','POST',{'sessionId':'test-live-session'})[0]['statusCode'],409)
    def test_revoked_during_liveness_denied(self):
        self.prepare();p=self.person();p['active']=False;self.store.put(p);self.assertEqual(self.call('liveness/result','POST',{'sessionId':'test-live-session'})[1]['outcome'],'deny')
    def test_low_liveness_denied(self):
        self.prepare();self.app.reko.confidence=40;self.assertEqual(self.call('liveness/result','POST',{'sessionId':'test-live-session'})[1]['outcome'],'deny')
    def test_wrong_live_identity_denied(self):
        self.prepare();self.app.reko.similarity=50;self.assertEqual(self.call('liveness/result','POST',{'sessionId':'test-live-session'})[1]['outcome'],'deny')
    def test_schedule_rechecked_at_result(self):
        self.prepare();self.now+=60;self.store.put({'pk':'CONFIG','sk':'STATE','schedule':{**base.DEFAULT_SCHEDULE,'end':'12:00'}});self.assertEqual(self.call('liveness/result','POST',{'sessionId':'test-live-session'})[1]['outcome'],'deny')
