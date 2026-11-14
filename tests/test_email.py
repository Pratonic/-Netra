import pathlib, sys, unittest, json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'backend'))
import test_service as base
from service import SesMailer
from test_liveness import Rekognition, STS

class Outbox:
    def __init__(self):self.messages=[]
    def send_code(self,address,code):self.messages.append((address,code))

class EmailTests(unittest.TestCase):
    setUp=base.APItests.setUp
    call=base.APItests.call
    login=base.APItests.login
    person=base.APItests.person
    def prepare(self):
        self.login('access');p=self.person();p['email']='student@example.edu';self.store.put(p)
        self.outbox=Outbox();self.app.mailer=self.outbox
        return self.call('precheck','POST',{'personId':p['id']})[1]['reviewId']
    def start(self):
        review=self.prepare();r,b=self.call('email/start','POST',{'reviewId':review});self.assertEqual(r['statusCode'],200);return b
    def verify(self,b,code=None):return self.call('email/verify','POST',{'challengeId':b['challengeId'],'code':code or self.outbox.messages[-1][1]})
    def test_code_only_confirms_email_not_gate_access(self):
        b=self.start();r,checked=self.verify(b);self.assertEqual(r['statusCode'],200);self.assertTrue(checked['emailVerified']);self.assertEqual(checked['outcome'],'stepup')
    def test_code_not_in_response_store_or_events(self):
        b=self.start();code=self.outbox.messages[0][1];self.assertEqual(len(code),6);self.assertNotIn(code,json.dumps(b));self.assertNotIn(code,json.dumps(list(self.store.rows.values())))
    def test_code_single_use(self):
        b=self.start();self.verify(b);self.assertEqual(self.verify(b)[0]['statusCode'],409)
    def test_expired_even_if_ttl_has_not_deleted(self):
        b=self.start();self.now+=180;self.assertEqual(self.verify(b)[0]['statusCode'],409)
    def test_wrong_code_attempt_limit(self):
        b=self.start();wrong='000000' if self.outbox.messages[-1][1]!='000000' else '111111'
        for _ in range(5):self.assertEqual(self.verify(b,wrong)[0]['statusCode'],400)
        self.assertEqual(self.verify(b)[0]['statusCode'],429);self.assertEqual(self.verify(b)[0]['statusCode'],409)
    def test_challenge_bound_to_session(self):
        b=self.start();self.login('access');self.assertEqual(self.verify(b)[0]['statusCode'],409)
    def test_review_cannot_be_forged_from_person_id(self):
        self.prepare();self.assertEqual(self.call('email/start','POST',{'personId':'person-1'})[0]['statusCode'],409)
    def test_review_send_is_single_use(self):
        review=self.prepare();self.call('email/start','POST',{'reviewId':review});self.assertEqual(self.call('email/start','POST',{'reviewId':review})[0]['statusCode'],409)
    def test_suspend_after_send_rejected(self):
        b=self.start();p=self.store.get('PEOPLE','person-1');p['active']=False;self.store.put(p);self.assertEqual(self.verify(b)[0]['statusCode'],409)
    def test_email_change_invalidates_code(self):
        b=self.start();p=self.store.get('PEOPLE','person-1');p['email']='other@example.edu';self.store.put(p);self.assertEqual(self.verify(b)[0]['statusCode'],409)
    def test_deletion_invalidates_code(self):
        b=self.start();self.store.delete('PEOPLE','person-1');self.assertEqual(self.verify(b)[0]['statusCode'],409)
    def test_schedule_rechecked_at_verification(self):
        b=self.start();self.store.put({'pk':'CONFIG','sk':'STATE','schedule':{**base.DEFAULT_SCHEDULE,'holidays':['2026-11-16']}});self.assertEqual(self.verify(b)[0]['statusCode'],409)
    def test_after_hours_has_no_email_review(self):
        self.prepare();p=self.store.get('PEOPLE','person-1');p['afterHours']='review';self.store.put(p);self.now+=10*3600;self.login('access');b=self.call('precheck','POST',{'personId':'person-1'})[1];self.assertEqual(b['outcome'],'stepup');self.assertIsNone(b['reviewId'])
    def test_person_send_limit_across_sessions(self):
        review=self.prepare()
        for i in range(4):
            if i: self.login('access');review=self.call('precheck','POST',{'personId':'person-1'})[1]['reviewId']
            r,b=self.call('email/start','POST',{'reviewId':review})
        self.assertEqual(r['statusCode'],429);self.assertEqual(len(self.outbox.messages),3)
    def test_low_liveness_blocks_existing_email_challenge(self):
        b=self.start();self.app.reko=Rekognition();self.app.sts=STS();self.app.reko.confidence=20
        self.call('liveness/start','POST',{'personId':'person-1'});self.assertEqual(self.call('liveness/result','POST',{'sessionId':'test-live-session'})[1]['outcome'],'deny');self.assertEqual(self.verify(b)[0]['statusCode'],409)
    def test_mail_transport_failure_stays_closed(self):
        review=self.prepare()
        def fail(*args):raise RuntimeError('delivery failure')
        self.app.mailer.send_code=fail;r,b=self.call('email/start','POST',{'reviewId':review});self.assertEqual(r['statusCode'],503);self.assertFalse(any(k[0].startswith('OTP#') for k in self.store.rows))
    def test_unconfigured_email_reports_unavailable(self):
        review=self.prepare();self.app.mailer=None;self.assertEqual(self.call('email/start','POST',{'reviewId':review})[0]['statusCode'],503)
    def test_kiosk_only_gets_masked_email(self):
        self.prepare();p=self.call('state')[1]['people'][0];self.assertNotIn('email',p);self.assertEqual(p['emailMasked'],'s•••@example.edu')

class EnrollmentTests(unittest.TestCase):
    setUp=base.APItests.setUp
    call=base.APItests.call
    login=base.APItests.login
    def enrollment(self,**changes):return {'name':'New Student','email':'student@example.edu','consent':True,'photo':'data:image/jpeg;base64,/9g=','descriptors':[[0]*128,[.01]*128,[.02]*128],**changes}
    def test_multi_view_and_email_saved(self):
        self.login();r,b=self.call('people','POST',self.enrollment());self.assertEqual(r['statusCode'],201);self.assertEqual(len(b['descriptors']),3);self.assertEqual(b['email'],'student@example.edu')
    def test_email_required_and_validated(self):
        self.login()
        for email in ('','invalid','a@b.edu\r\nBcc:foo@bar.edu'):
            self.assertEqual(self.call('people','POST',self.enrollment(email=email))[0]['statusCode'],400)
    def test_more_than_five_views_rejected(self):
        self.login();self.assertEqual(self.call('people','POST',self.enrollment(descriptors=[[0]*128]*6))[0]['statusCode'],400)
    def test_mixed_identities_rejected(self):
        self.login();self.assertEqual(self.call('people','POST',self.enrollment(descriptors=[[0]*128,[.2]*128]))[0]['statusCode'],400)
    def test_duplicate_compares_all_views(self):
        self.login();self.call('people','POST',self.enrollment());r,b=self.call('people','POST',self.enrollment(descriptors=[[.05]*128,[.03]*128]));self.assertEqual(r['statusCode'],409)
    def test_existing_identity_can_add_email(self):
        self.login();p={'pk':'PEOPLE','sk':'old','id':'old','name':'Existing'};self.store.put(p);r,b=self.call('people/old','PATCH',{'email':'old@example.edu'});self.assertEqual(r['statusCode'],200);self.assertEqual(b['email'],'old@example.edu')

class SesTests(unittest.TestCase):
    def test_sender_recipient_and_code(self):
        class Client:
            def send_email(self,**kwargs):self.kwargs=kwargs
        client=Client();SesMailer(client,'campus@example.edu').send_code('student@example.edu','012345')
        self.assertEqual(client.kwargs['Destination']['ToAddresses'],['student@example.edu']);self.assertIn('012345',client.kwargs['Message']['Body']['Text']['Data'])
