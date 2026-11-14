import sys,pathlib,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'backend'))
import test_service as base
import test_liveness as live
from policy import ir_evidence

OK={'status':'ok','samples':30,'presentRatio':.9,'rawMedian':612,'ageMs':40}

class IrEvidenceTests(unittest.TestCase):
    def test_missing_is_not_connected(self):self.assertEqual(ir_evidence(None)['irStatus'],'not-connected')
    def test_present(self):e=ir_evidence(OK);self.assertEqual((e['irStatus'],e['irRaw']),('present',612))
    def test_absent(self):self.assertEqual(ir_evidence({**OK,'presentRatio':.1})['irStatus'],'absent')
    def test_stale_age(self):self.assertEqual(ir_evidence({**OK,'ageMs':5000})['irStatus'],'stale')
    def test_too_few_samples(self):self.assertEqual(ir_evidence({**OK,'samples':2})['irStatus'],'stale')
    def test_nan_ratio_rejected(self):self.assertEqual(ir_evidence({**OK,'presentRatio':float('nan')})['irStatus'],'stale')
    def test_garbage(self):
        self.assertEqual(ir_evidence('x')['irStatus'],'invalid')
        self.assertEqual(ir_evidence({**OK,'samples':'many'})['irStatus'],'invalid')
    def test_out_of_range_raw_dropped(self):self.assertNotIn('irRaw',ir_evidence({**OK,'rawMedian':99999}))

class IrPrecheckTests(unittest.TestCase):
    setUp=base.APItests.setUp
    call=base.APItests.call
    login=base.APItests.login
    person=base.APItests.person
    def precheck(self,ir=None):
        body={'personId':'person-1','elapsed':900}
        if ir is not None:body['ir']=ir
        return self.call('precheck','POST',body)[1]
    def test_without_sensor_unchanged(self):
        self.login('access');self.person();b=self.precheck()
        self.assertEqual(b['outcome'],'stepup');self.assertTrue(b['reviewId']);self.assertEqual(b['irStatus'],'not-connected')
    def test_present_keeps_review_path(self):
        self.login('access');self.person();b=self.precheck(OK)
        self.assertEqual((b['outcome'],b['irStatus']),('stepup','present'));self.assertTrue(b['reviewId'])
    def test_absent_denies_and_blocks_liveness(self):
        self.login('access');self.person();b=self.precheck({**OK,'presentRatio':0})
        self.assertEqual(b['outcome'],'deny');self.assertIsNone(b['reviewId'])
        self.app.reko=live.Rekognition();self.app.sts=live.STS()
        self.assertEqual(self.call('liveness/start','POST',{'personId':'person-1'})[0]['statusCode'],403)
    def test_absent_never_overrides_schedule_deny_reason(self):
        self.now+=10*3600;self.login('access');self.person()  # 22:00, outside hours
        b=self.precheck({**OK,'presentRatio':0});self.assertEqual(b['outcome'],'deny');self.assertIn('hours',b['reason'])
    def test_required_sensor_missing_steps_up(self):
        self.config['require_ir']=True;self.login('access');self.person();b=self.precheck()
        self.assertEqual(b['outcome'],'stepup');self.assertIsNone(b['reviewId'])
        self.app.reko=live.Rekognition();self.app.sts=live.STS()
        self.assertEqual(self.call('liveness/start','POST',{'personId':'person-1'})[0]['statusCode'],409)
    def test_required_sensor_present_allows_liveness_path(self):
        self.config['require_ir']=True;self.login('access');self.person();self.precheck(OK)
        self.app.reko=live.Rekognition();self.app.sts=live.STS()
        self.assertEqual(self.call('liveness/start','POST',{'personId':'person-1'})[0]['statusCode'],200)
        self.assertEqual(self.call('liveness/result','POST',{'sessionId':'test-live-session'})[1]['outcome'],'allow')
