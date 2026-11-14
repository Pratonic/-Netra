import sys, pathlib, unittest, json, time, base64
from datetime import datetime,timezone
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'backend'))
from service import App,MemoryStore,password_hash
from policy import schedule_decision,validate_schedule,DEFAULT_SCHEDULE

class ScheduleTests(unittest.TestCase):
    def check(self,schedule,when,person=None):return schedule_decision({'active':True,**(person or {})},schedule,datetime.fromisoformat(when))['outcome']
    def test_open_boundary(self):self.assertEqual(self.check(DEFAULT_SCHEDULE,'2026-11-16T08:00:00+05:30'),'eligible')
    def test_close_boundary(self):self.assertEqual(self.check(DEFAULT_SCHEDULE,'2026-11-16T20:00:00+05:30'),'deny')
    def test_closed_day(self):self.assertEqual(self.check(DEFAULT_SCHEDULE,'2026-11-15T12:00:00+05:30'),'deny')
    def test_after_hours_review(self):self.assertEqual(self.check(DEFAULT_SCHEDULE,'2026-11-16T21:00:00+05:30',{'afterHours':'review'}),'stepup')
    def test_expired(self):self.assertEqual(self.check(DEFAULT_SCHEDULE,'2026-11-16T12:00:00+05:30',{'validUntil':'2026-11-15'}),'deny')
    def test_suspended(self):self.assertEqual(self.check(DEFAULT_SCHEDULE,'2026-11-16T12:00:00+05:30',{'active':False}),'deny')
    def test_overnight_previous_day(self):self.assertEqual(self.check({**DEFAULT_SCHEDULE,'days':[0],'start':'22:00','end':'06:00'},'2026-11-17T05:59:00+05:30'),'eligible')
    def test_overnight_end(self):self.assertEqual(self.check({**DEFAULT_SCHEDULE,'days':[0],'start':'22:00','end':'06:00'},'2026-11-17T06:00:00+05:30'),'deny')
    def test_holiday_overrides_custom(self):self.assertEqual(self.check({**DEFAULT_SCHEDULE,'holidays':['2026-11-16']},'2026-11-16T12:00:00+05:30',{'schedule':DEFAULT_SCHEDULE}),'deny')
    def test_invalid_fail_safe(self):self.assertEqual(self.check({'days':[]},'2026-11-16T12:00:00+05:30'),'stepup')
    def test_timezone(self):self.assertEqual(self.check(DEFAULT_SCHEDULE,'2026-11-16T02:30:00+00:00'),'eligible')

class APItests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.fromisoformat('2026-11-16T12:00:00+05:30').timestamp();self.store=MemoryStore();self.config={'gateway':'gateway-test','salt':'test-salt','admin_hash':password_hash('admin','test-salt'),'access_hash':password_hash('AWS','test-salt'),'stream_role':'test'};self.app=App(self.store,self.config,clock=lambda:self.now);self.cookie=None;self.csrf=None
    def call(self,path,method='GET',body=None,**headers):
        h={'x-aegis-gateway':'gateway-test','x-aegis-viewer':'viewer-test',**headers}
        if self.csrf:h['x-csrf-token']=self.csrf
        if self.cookie:h['cookie']=self.cookie
        r=self.app.handle({'rawPath':'/api/'+path,'headers':h,'body':json.dumps(body) if body is not None else None,'requestContext':{'http':{'method':method}}});return r,json.loads(r['body'])
    def login(self,role='admin'):
        name='admin' if role=='admin' else 'AWS';r,b=self.call('login','POST',{'role':role,'username':name,'password':name});self.assertEqual(r['statusCode'],200);self.cookie=r['cookies'][0].split(';')[0];self.csrf=b['csrf'];return r,b
    def person(self):
        p={'pk':'PEOPLE','sk':'person-1','id':'person-1','name':'Test identity','active':True,'descriptors':[[0]*128],'photo':'data:image/jpeg;base64,/9g=','created':int(self.now*1000),'afterHours':'deny'};self.store.put(p);return p
    def test_login_and_http_only(self):
        r,b=self.login();self.assertIn('HttpOnly',r['cookies'][0]);self.assertIn('Secure',r['cookies'][0]);self.assertNotIn('password',b)
    def test_wrong_password(self):self.assertEqual(self.call('login','POST',{'role':'admin','username':'admin','password':'wrong'})[0]['statusCode'],401)
    def test_access_cannot_edit_schedule(self):self.login('access');self.assertEqual(self.call('schedule','PUT',DEFAULT_SCHEDULE)[0]['statusCode'],403)
    def test_csrf(self):self.login();self.csrf='wrong';self.assertEqual(self.call('schedule','PUT',DEFAULT_SCHEDULE)[0]['statusCode'],403)
    def test_session_expiry(self):self.login();self.now+=28801;self.assertEqual(self.call('state')[0]['statusCode'],401)
    def test_session_bound_to_viewer(self):self.login();self.assertEqual(self.call('state',**{'x-aegis-viewer':'another'})[0]['statusCode'],401)
    def test_login_rate_limit(self):
        for _ in range(13):r,_=self.call('login','POST',{'role':'admin','username':'admin','password':'wrong'})
        self.assertEqual(r['statusCode'],429)
    def test_precheck_cannot_allow(self):self.login('access');self.person();r,b=self.call('precheck','POST',{'personId':'person-1','outcome':'allow','liveness':True});self.assertEqual(b['outcome'],'stepup')
    def test_liveness_unavailable_cannot_allow(self):self.login('access');self.person();self.assertEqual(self.call('liveness/start','POST',{'personId':'person-1'})[0]['statusCode'],503)
    def test_unknown_denied(self):self.login('access');self.assertEqual(self.call('precheck','POST',{'personId':'missing'})[1]['outcome'],'deny')
    def test_offline_sync_idempotent(self):
        self.login('access');item={'id':'12345678-1234-1234-1234-123456789012','timestamp':int(self.now*1000),'outcome':'stepup','reason':'offline'}
        self.call('sync','POST',{'records':[item]});self.call('sync','POST',{'records':[item]});self.assertEqual(len(self.store.query('EVENTS')),1);self.assertEqual(self.store.query('EVENTS')[0]['outcome'],'stepup')
    def test_offline_allow_rejected(self):
        self.login('access');item={'id':'12345678-1234-1234-1234-123456789012','timestamp':int(self.now*1000),'outcome':'allow','reason':'offline'};self.assertEqual(self.call('sync','POST',{'records':[item]})[1]['accepted'],[])
    def test_expired_offline_record_discarded(self):
        self.login('access');item={'id':'12345678-1234-1234-1234-123456789012','timestamp':int((self.now-86401)*1000),'outcome':'stepup','reason':'offline'};self.assertEqual(self.call('sync','POST',{'records':[item]})[1]['accepted'],[])
    def test_gateway_required(self):self.assertEqual(self.call('session',**{'x-aegis-gateway':'wrong'})[0]['statusCode'],403)
    def test_log_out_invalidates_session(self):self.login();self.call('logout','POST',{});self.assertEqual(self.call('session')[0]['statusCode'],401)
    def test_kiosk_does_not_receive_portraits(self):self.login('access');self.person();p=self.call('state')[1]['people'][0];self.assertNotIn('photo',p)
    def test_delete_removes_named_history(self):
        self.login();self.person();self.app.record('person-1','stepup','A test record');self.app.record(None,'stepup','Anonymous fallback');self.call('people/person-1','DELETE');self.assertIsNone(self.store.get('PEOPLE','person-1'));self.assertEqual(len(self.store.query('EVENTS')),1);self.assertIsNone(self.store.query('EVENTS')[0]['name'])
    def test_live_session_replay_rejected(self):
        self.login('access');s=self.store.query('SESSION#unavailable');self.assertEqual(self.call('liveness/result','POST',{'sessionId':'forged'})[0]['statusCode'],409)

if __name__=='__main__':unittest.main()
