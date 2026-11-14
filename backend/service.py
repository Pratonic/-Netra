import base64, hashlib, hmac, json, math, mimetypes, os, re, secrets, time, uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from http.cookies import SimpleCookie
from policy import DEFAULT_SCHEDULE, validate_schedule, schedule_decision

SESSION_SECONDS=8*60*60
def password_hash(password,salt):return hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),210000).hex()
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def email_address(value):
    value=str(value or '').strip()
    if len(value)>254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}",value) or '..' in value:raise HTTPError(400,'Enter a valid email address.')
    local,domain=value.rsplit('@',1)
    return local+'@'+domain.lower()
def masked_email(value):
    if not value:return None
    local,domain=value.rsplit('@',1)
    return local[:1]+'•••@'+domain

class SesMailer:
    def __init__(self,client,sender):self.client,self.sender=client,sender
    def send_code(self,address,code):
        self.client.send_email(Source=self.sender,Destination={'ToAddresses':[address]},Message={'Subject':{'Data':'त्रिNetra verification code','Charset':'UTF-8'},'Body':{'Text':{'Data':f'Your त्रिNetra code is {code}. It expires in 3 minutes. Only enter it at the campus kiosk where you requested it. This confirms your email for an attended ID check; it does not unlock the gate. If you did not request it, ignore this message.','Charset':'UTF-8'}}})
def jsonable(value):
    if isinstance(value,Decimal):return int(value) if value%1==0 else float(value)
    if isinstance(value,dict):return {k:jsonable(v) for k,v in value.items()}
    if isinstance(value,list):return [jsonable(v) for v in value]
    return value

class MemoryStore:
    def __init__(self):self.rows={}
    def get(self,pk,sk='STATE'):return self.rows.get((pk,sk))
    def put(self,item,unique=False):
        key=(item['pk'],item.get('sk','STATE'))
        if unique and key in self.rows:return False
        self.rows[key]=dict(item);return True
    def delete(self,pk,sk='STATE'):self.rows.pop((pk,sk),None)
    def purge_identity_events(self,identifier):
        for key,row in list(self.rows.items()):
            if key[0]=='EVENTS' and row.get('personId')==identifier:del self.rows[key]
    def query(self,pk,limit=200):return sorted([v for (p,s),v in self.rows.items() if p==pk],key=lambda x:x['sk'],reverse=True)[:limit]
    def consume(self,pk):
        row=self.get(pk)
        if not row or row.get('used'):return False
        row['used']=True;return True
    def increment(self,pk,expires):
        row=self.get(pk) or {'pk':pk,'sk':'STATE','count':0,'expiresAt':expires}
        row['count']+=1;self.put(row);return row['count']

class DynamoStore:
    def __init__(self,table):self.table=table
    def get(self,pk,sk='STATE'):return jsonable(self.table.get_item(Key={'pk':pk,'sk':sk},ConsistentRead=True).get('Item'))
    def put(self,item,unique=False):
        args={'Item':json.loads(json.dumps(item),parse_float=Decimal)}
        if unique:args['ConditionExpression']='attribute_not_exists(pk) AND attribute_not_exists(sk)'
        try:self.table.put_item(**args);return True
        except Exception as e:
            if getattr(e,'response',{}).get('Error',{}).get('Code')=='ConditionalCheckFailedException':return False
            raise
    def delete(self,pk,sk='STATE'):self.table.delete_item(Key={'pk':pk,'sk':sk})
    def purge_identity_events(self,identifier):
        args={'KeyConditionExpression':'pk = :pk','ExpressionAttributeValues':{':pk':'EVENTS'},'ConsistentRead':True,'Limit':100}
        while True:
            page=self.table.query(**args)
            for row in page.get('Items',[]):
                if row.get('personId')==identifier:self.delete('EVENTS',row['sk'])
            if not page.get('LastEvaluatedKey'):break
            args['ExclusiveStartKey']=page['LastEvaluatedKey']
    def query(self,pk,limit=200):
        return jsonable(self.table.query(KeyConditionExpression='pk = :pk',ExpressionAttributeValues={':pk':pk},Limit=limit,ScanIndexForward=False,ConsistentRead=True).get('Items',[]))
    def consume(self,pk):
        try:self.table.update_item(Key={'pk':pk,'sk':'STATE'},UpdateExpression='SET used = :yes',ConditionExpression='attribute_exists(pk) AND attribute_not_exists(used)',ExpressionAttributeValues={':yes':True});return True
        except Exception as e:
            if getattr(e,'response',{}).get('Error',{}).get('Code')=='ConditionalCheckFailedException':return False
            raise
    def increment(self,pk,expires):
        r=self.table.update_item(Key={'pk':pk,'sk':'STATE'},UpdateExpression='SET expiresAt = :exp ADD #count :one',ExpressionAttributeNames={'#count':'count'},ExpressionAttributeValues={':exp':expires,':one':1},ReturnValues='UPDATED_NEW')
        return int(r['Attributes']['count'])

class HTTPError(Exception):
    def __init__(self,status,message):self.status,self.message=status,message

class App:
    def __init__(self,store,config,reko=None,sts=None,clock=time.time,mailer=None):self.store,self.config,self.reko,self.sts,self.clock,self.mailer=store,config,reko,sts,clock,mailer
    def reply(self,status,data,cookie=None):
        response={'statusCode':status,'headers':{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'},'body':json.dumps(jsonable(data))}
        if cookie:response['cookies']=[cookie]
        return response
    def data(self,event):
        try:
            raw=event.get('body') or '{}'
            if event.get('isBase64Encoded'):raw=base64.b64decode(raw).decode()
            if len(raw)>350000:raise HTTPError(413,'Request is too large.')
            data=json.loads(raw)
            if not isinstance(data,dict):raise ValueError()
            return data
        except (ValueError,UnicodeError):raise HTTPError(400,'Invalid request.')
    def auth(self,event,admin=False,mutate=False):
        headers=event.get('headers',{})
        cookie=SimpleCookie()
        try:cookie.load('; '.join(event.get('cookies',[])) or headers.get('cookie',''))
        except Exception:raise HTTPError(401,'Sign in again.')
        token=cookie.get('aegis_session')
        session=self.store.get('SESSION#'+digest(token.value)) if token else None
        if not session or session['expiresAt']<=self.clock() or session['viewer']!=headers.get('x-aegis-viewer'):raise HTTPError(401,'Sign in to continue.')
        if admin and session['role']!='admin':raise HTTPError(403,'Administrator access required.')
        if mutate and not hmac.compare_digest(session['csrf'],headers.get('x-csrf-token','')):raise HTTPError(403,'Refresh this page and try again.')
        return session
    def campus(self):return (self.store.get('CONFIG') or {}).get('schedule',DEFAULT_SCHEDULE)
    def person(self,identifier):return self.store.get('PEOPLE',identifier)
    def person_public(self,p,admin=False):
        keys=('id','name','team','reference','active','created','validUntil','afterHours','schedule','descriptors') + (('photo','email') if admin else ())
        return {**{k:p[k] for k in keys if k in p},'emailMasked':masked_email(p.get('email'))}
    def record(self,identifier,outcome,reason,**extra):
        now=self.clock();person=self.person(identifier) if identifier else None
        row={'pk':'EVENTS','sk':f'{int(now*1000):013d}#{uuid.uuid4()}','id':str(uuid.uuid4()),'timestamp':int(now*1000),'outcome':outcome,'reason':reason,'personId':identifier,'name':person.get('name') if person else None,'expiresAt':int(now)+7*86400,**extra}
        self.store.put(row);return {k:v for k,v in row.items() if k not in ('pk','sk','expiresAt')}
    def email_review(self,event,path):
        s=self.auth(event,mutate=True);b=self.data(event);now=int(self.clock())
        if not self.mailer:raise HTTPError(503,'Email delivery is not connected. Ask an attendant.')
        if path.endswith('/start'):
            review=self.store.get('REVIEW#'+str(b.get('reviewId','')))
            if not review or review['session']!=s['pk'] or review['expiresAt']<=now or review.get('used'):raise HTTPError(409,'Scan again to request a fresh verification code.')
            p=self.person(review['personId'])
            if schedule_decision(p,self.campus(),datetime.fromtimestamp(now,timezone.utc))['outcome']!='eligible':raise HTTPError(409,'Current access rules require an attended check.')
            if not p.get('email'):raise HTTPError(409,'Ask an administrator to add this person’s email.')
            blocked=self.store.get('PAD_BLOCK#'+digest(s['pk']+p['id']))
            if blocked and blocked['expiresAt']>now:raise HTTPError(403,'Live verification was denied. Contact security.')
            if self.store.increment(f'EMAIL_SEND#{p["id"]}#{now//900}',now+1800)>3:raise HTTPError(429,'Email request limit reached. Ask an attendant.')
            if self.store.increment('EMAIL_VIEWER#'+digest(s['viewer'])+f'#{now//900}',now+1800)>10:raise HTTPError(429,'Email request limit reached. Ask an attendant.')
            if not self.store.consume(review['pk']):raise HTTPError(409,'Scan again to request a fresh verification code.')
            identifier=secrets.token_urlsafe(24);code=f'{secrets.randbelow(1000000):06d}'
            code_hash=hmac.new(self.config['gateway'].encode(),('email-otp:'+identifier+':'+code).encode(),'sha256').hexdigest()
            row={'pk':'OTP#'+identifier,'sk':'STATE','session':s['pk'],'personId':p['id'],'emailHash':digest(p['email']),'codeHash':code_hash,'expiresAt':now+180,'startedAt':now*1000}
            self.store.put(row)
            try:self.mailer.send_code(p['email'],code)
            except Exception:
                self.store.delete(row['pk']);raise HTTPError(503,'Email could not be sent. Scan again or ask an attendant.')
            return self.reply(200,{'challengeId':identifier,'emailMasked':masked_email(p['email']),'expiresAt':row['expiresAt'],'digits':6})
        identifier=str(b.get('challengeId',''));challenge=self.store.get('OTP#'+identifier)
        if not challenge or challenge['session']!=s['pk'] or challenge['expiresAt']<=now or challenge.get('used'):raise HTTPError(409,'Code expired or was already used. Scan again.')
        attempts=self.store.increment('OTP_TRIES#'+identifier,challenge['expiresAt'])
        total=self.store.increment(f'OTP_PERSON_TRIES#{challenge["personId"]}#{now//3600}',now+7200)
        if attempts>5 or total>10:
            self.store.consume(challenge['pk']);raise HTTPError(429,'Too many attempts. Ask an attendant.')
        code=str(b.get('code',''))
        expected=hmac.new(self.config['gateway'].encode(),('email-otp:'+identifier+':'+code).encode(),'sha256').hexdigest()
        if not re.fullmatch(r'\d{6}',code) or not hmac.compare_digest(challenge['codeHash'],expected):raise HTTPError(400,'Code is incorrect. Try again.')
        p=self.person(challenge['personId'])
        blocked=self.store.get('PAD_BLOCK#'+digest(s['pk']+challenge['personId']))
        if not p or digest(p.get('email',''))!=challenge['emailHash'] or schedule_decision(p,self.campus(),datetime.fromtimestamp(now,timezone.utc))['outcome']!='eligible' or (blocked and blocked['expiresAt']>now):
            self.store.consume(challenge['pk']);raise HTTPError(409,'Access details changed. Contact security.')
        if not self.store.consume(challenge['pk']):raise HTTPError(409,'Code was already used.')
        return self.reply(200,self.record(p['id'],'stepup','Email confirmed. Present your campus ID to an attendant.',stage='email',emailVerified=True,elapsed=now*1000-challenge['startedAt']))
    def handle(self,event):
        headers={k.lower():v for k,v in event.get('headers',{}).items()};event['headers']=headers
        if not hmac.compare_digest(headers.get('x-aegis-gateway',''),self.config['gateway']) or not headers.get('x-aegis-viewer'):return self.reply(403,{'error':'Forbidden'})
        path=event.get('rawPath','/');method=event.get('requestContext',{}).get('http',{}).get('method','GET')
        try:
            if not path.startswith('/api/'):
                return self.static(path)
            if path=='/api/login' and method=='POST':
                body=self.data(event);role=body.get('role');expected='admin' if role=='admin' else 'AWS' if role=='access' else None
                if not expected:raise HTTPError(400,'Choose an entrance.')
                now=int(self.clock());window=now//600
                count=self.store.increment('RATE#'+digest(headers['x-aegis-viewer'])+f'#{role}#{window}',now+1200)
                if count>12:raise HTTPError(429,'Too many sign-in attempts. Try again in ten minutes.')
                password=str(body.get('password',''))[:256];name=str(body.get('username',''))[:80]
                valid=hmac.compare_digest(password_hash(password,self.config['salt']),self.config[role+'_hash'])
                if name!=expected or not valid:raise HTTPError(401,'Username or password is incorrect.')
                token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
                row={'pk':'SESSION#'+digest(token),'sk':'STATE','role':role,'viewer':headers['x-aegis-viewer'],'csrf':csrf,'expiresAt':now+SESSION_SECONDS}
                self.store.put(row)
                return self.reply(200,{'role':role,'csrf':csrf,'expiresAt':row['expiresAt']},f'aegis_session={token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age={SESSION_SECONDS}')
            if path=='/api/session':
                s=self.auth(event)
                return self.reply(200,{k:s[k] for k in ('role','csrf','expiresAt')})
            if path=='/api/logout' and method=='POST':
                s=self.auth(event,mutate=True);self.store.delete(s['pk'])
                return self.reply(200,{'ok':True},'aegis_session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0')
            if path=='/api/state' and method=='GET':
                s=self.auth(event);people=self.store.query('PEOPLE')
                return self.reply(200,{'people':[self.person_public(p,s['role']=='admin') for p in people],'schedule':self.campus(),'events':[{k:v for k,v in e.items() if k not in ('pk','sk','expiresAt')} for e in (self.store.query('EVENTS',100) if s['role']=='admin' else []) if e.get('expiresAt',0)>self.clock()],'serverTime':int(self.clock()*1000),'livenessEnabled':bool(self.reko and self.sts),'emailEnabled':bool(self.mailer),'region':'us-east-1'})
            if path=='/api/people' and method=='POST':
                self.auth(event,True,True);body=self.data(event)
                name=str(body.get('name','')).strip()[:80]
                if len(name)<2 or not body.get('consent'):raise HTTPError(400,'Add a name and confirm consent.')
                email=email_address(body.get('email'))
                descriptors=body.get('descriptors')
                if not isinstance(descriptors,list) or not 1<=len(descriptors)<=5 or any(not isinstance(d,list) or len(d)!=128 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>5 for x in d) for d in descriptors):raise HTTPError(400,'Capture between one and five valid face references.')
                if any(math.dist(descriptors[0],d)>.55 for d in descriptors[1:]):raise HTTPError(400,'The captured views do not appear to be the same person. Capture again.')
                photo=body.get('photo','')
                if not isinstance(photo,str) or not photo.startswith('data:image/jpeg;base64,') or len(photo)>220000:raise HTTPError(400,'Use a valid JPEG reference.')
                try:raw=base64.b64decode(photo.split(',')[1],validate=True)
                except ValueError:raise HTTPError(400,'Invalid reference image.')
                if not raw.startswith(b'\xff\xd8'):raise HTTPError(400,'Invalid reference image.')
                if len(self.store.query('PEOPLE',251))>=250:raise HTTPError(409,'This campus has reached its enrollment limit.')
                for old in self.store.query('PEOPLE',250):
                    if min(math.dist(d,n) for d in old['descriptors'] for n in descriptors)<.45:raise HTTPError(409,'This face is already enrolled.')
                schedule=validate_schedule(body['schedule']) if body.get('schedule') else None
                validUntil=str(body.get('validUntil',''))
                if validUntil:datetime.strptime(validUntil,'%Y-%m-%d')
                identifier=str(uuid.uuid4());row={'pk':'PEOPLE','sk':identifier,'id':identifier,'name':name,'team':str(body.get('team',''))[:60],'reference':str(body.get('reference',''))[:40],'descriptors':descriptors,'photo':photo,'created':int(self.clock()*1000),'active':True,'consent':True,'validUntil':validUntil,'schedule':schedule,'afterHours':'review' if body.get('afterHours')=='review' else 'deny'}
                row['email']=email
                self.store.put(row);return self.reply(201,self.person_public(row,True))
            if path.startswith('/api/people/') and method in ('PATCH','DELETE'):
                self.auth(event,True,True);identifier=path.rsplit('/',1)[-1];p=self.person(identifier)
                if not p:raise HTTPError(404,'Identity not found.')
                if method=='DELETE':
                    self.store.delete('PEOPLE',identifier)
                    self.store.purge_identity_events(identifier)
                    return self.reply(200,{'ok':True})
                b=self.data(event)
                if 'email' in b:p['email']=email_address(b['email'])
                if 'active' in b:p['active']=bool(b['active'])
                if 'schedule' in b:p['schedule']=validate_schedule(b['schedule']) if b['schedule'] else None
                if 'afterHours' in b:p['afterHours']='review' if b['afterHours']=='review' else 'deny'
                if 'validUntil' in b:
                    expiry=str(b['validUntil'])
                    if expiry:datetime.strptime(expiry,'%Y-%m-%d')
                    p['validUntil']=expiry
                self.store.put(p);return self.reply(200,self.person_public(p,True))
            if path=='/api/schedule' and method=='PUT':
                self.auth(event,True,True);schedule=validate_schedule(self.data(event));self.store.put({'pk':'CONFIG','sk':'STATE','schedule':schedule,'updatedAt':int(self.clock()*1000)})
                return self.reply(200,{'schedule':schedule})
            if path=='/api/precheck' and method=='POST':
                s=self.auth(event,mutate=True);b=self.data(event);p=self.person(b.get('personId',''))
                if not p:return self.reply(200,self.record(None,'deny','Identity not recognized.',stage='initial'))
                decision=schedule_decision(p,self.campus(),datetime.fromtimestamp(self.clock(),timezone.utc))
                review_id=None
                if decision['outcome']=='eligible':
                    review_id=secrets.token_urlsafe(24)
                    self.store.put({'pk':'REVIEW#'+review_id,'sk':'STATE','session':s['pk'],'personId':p['id'],'expiresAt':int(self.clock())+300})
                    decision={'outcome':'stepup','reason':'Confirm live presence, or request an attended check.'}
                return self.reply(200,{**self.record(p['id'],decision['outcome'],decision['reason'],stage='initial',elapsed=min(max(float(b.get('elapsed',0)),0),60000)),'reviewId':review_id})
            if path in ('/api/email/start','/api/email/verify') and method=='POST':return self.email_review(event,path)
            if path=='/api/liveness/start' and method=='POST':
                s=self.auth(event,mutate=True);b=self.data(event);p=self.person(b.get('personId',''))
                decision=schedule_decision(p,self.campus(),datetime.fromtimestamp(self.clock(),timezone.utc))
                if decision['outcome']!='eligible':return self.reply(409,{'error':decision['reason'],'outcome':decision['outcome']})
                if not self.reko or not self.sts:raise HTTPError(503,'Cloud liveness is not connected. Ask security for verification.')
                now=int(self.clock());attempts=self.store.increment('LIVE_RATE#'+digest(s['pk'])+f'#{now//600}',now+1200)
                if attempts>10:raise HTTPError(429,'Live-check limit reached. Ask security for verification.')
                r=self.reko.create_face_liveness_session(Settings={'AuditImagesLimit':0})
                sid=r['SessionId'];self.store.put({'pk':'LIVE#'+sid,'sk':'STATE','personId':p['id'],'session':s['pk'],'expiresAt':now+180,'startedAt':int(self.clock()*1000)})
                c=self.sts.assume_role(RoleArn=self.config['stream_role'],RoleSessionName='AegisLiveness',DurationSeconds=900)['Credentials']
                return self.reply(200,{'sessionId':sid,'region':'us-east-1','credentials':{'accessKeyId':c['AccessKeyId'],'secretAccessKey':c['SecretAccessKey'],'sessionToken':c['SessionToken'],'expiration':c['Expiration'].isoformat()}})
            if path=='/api/liveness/result' and method=='POST':
                s=self.auth(event,mutate=True);b=self.data(event);sid=str(b.get('sessionId',''));live=self.store.get('LIVE#'+sid)
                if not live or live['session']!=s['pk'] or live['expiresAt']<self.clock() or live.get('used'):raise HTTPError(409,'Live check expired or was already used. Start again.')
                r=self.reko.get_face_liveness_session_results(SessionId=sid)
                if r.get('Status') in ('CREATED','IN_PROGRESS'):return self.reply(202,{'pending':True})
                if not self.store.consume('LIVE#'+sid):raise HTTPError(409,'Live check was already used.')
                p=self.person(live['personId']);decision=schedule_decision(p,self.campus(),datetime.fromtimestamp(self.clock(),timezone.utc))
                confidence=float(r.get('Confidence',0));similarity=0
                if r.get('Status')!='SUCCEEDED':decision={'outcome':'stepup','reason':'Live check incomplete. Ask security for verification.'}
                elif confidence<95:decision={'outcome':'deny','reason':'Live presence could not be confirmed.'}
                elif decision['outcome']=='eligible':
                    image=r.get('ReferenceImage',{}).get('Bytes')
                    if not image:decision={'outcome':'stepup','reason':'A usable live reference was not returned.'}
                    else:
                        match=self.reko.compare_faces(SourceImage={'Bytes':base64.b64decode(p['photo'].split(',')[1])},TargetImage={'Bytes':image},SimilarityThreshold=98,QualityFilter='AUTO')
                        similarity=max([float(m['Similarity']) for m in match.get('FaceMatches',[])] or [0])
                        decision={'outcome':'allow','reason':'Live identity confirmed. Campus schedule permits access.'} if similarity>=98 else {'outcome':'deny','reason':'Live face does not match the enrolled identity.'}
                if decision['outcome']=='deny':self.store.put({'pk':'PAD_BLOCK#'+digest(s['pk']+live['personId']),'sk':'STATE','expiresAt':int(self.clock())+600})
                return self.reply(200,self.record(live['personId'],decision['outcome'],decision['reason'],stage='cloud',livenessConfidence=round(confidence,2),similarity=round(similarity,2),elapsed=int(self.clock()*1000)-live['startedAt']))
            if path=='/api/sync' and method=='POST':
                s=self.auth(event,mutate=True);records=self.data(event).get('records',[])
                if not isinstance(records,list) or len(records)>100:raise HTTPError(400,'Invalid offline queue.')
                accepted=[];now=int(self.clock()*1000)
                for item in records:
                    if not isinstance(item,dict):continue
                    identifier=str(item.get('id',''));timestamp=item.get('timestamp')
                    if len(identifier)!=36 or type(timestamp) not in (int,float) or not now-86400000<=timestamp<=now+300000:continue
                    if item.get('outcome')!='stepup' or item.get('reason')!='offline':continue
                    key='SYNC#'+digest(s['viewer']+'#'+identifier)
                    if self.store.put({'pk':key,'sk':'STATE','expiresAt':int(self.clock())+2*86400},True):self.record(None,'stepup','Offline attendant verification requested.',stage='offline',offlineId=identifier,clientTimestamp=int(timestamp))
                    accepted.append(identifier)
                return self.reply(200,{'accepted':accepted,'serverTime':now})
            raise HTTPError(404,'Not found.')
        except HTTPError as e:return self.reply(e.status,{'error':e.message})
        except (ValueError,TypeError,KeyError):return self.reply(400,{'error':'Check the entered details and try again.'})
        except Exception as e:
            code=getattr(e,'response',{}).get('Error',{}).get('Code',type(e).__name__)
            print(json.dumps({'event':'request_failed','path':path,'code':code}))
            return self.reply(503,{'error':'Service is unavailable. No access has been granted. Ask security for verification.'})
    def static(self,path):
        root=Path(__file__).parent/'public'
        relative='index.html' if path in ('','/') else path.lstrip('/')
        file=(root/relative).resolve()
        if not file.is_relative_to(root.resolve()) or not file.is_file():return self.reply(404,{'error':'Not found.'})
        mime=mimetypes.guess_type(file.name)[0] or ('text/javascript' if file.suffix=='.mjs' else 'application/octet-stream')
        return {'statusCode':200,'headers':{'Content-Type':mime,'Cache-Control':'no-cache' if file.name=='index.html' or file.suffix in ('.js','.mjs','.css') else 'public, max-age=3600','X-Content-Type-Options':'nosniff','Service-Worker-Allowed':'/'},'isBase64Encoded':True,'body':base64.b64encode(file.read_bytes()).decode()}

_app=None
def lambda_handler(event,context):
    global _app
    if _app is None:
        import boto3
        config={'gateway':os.environ['AEGIS_GATEWAY_SECRET'],'salt':os.environ['PASSWORD_SALT'],'admin_hash':os.environ['ADMIN_HASH'],'access_hash':os.environ['ACCESS_HASH'],'stream_role':os.environ['STREAM_ROLE_ARN']}
        sender=os.environ.get('SES_FROM_ADDRESS')
        mailer=SesMailer(boto3.client('ses',region_name=os.environ.get('SES_REGION','us-east-1')),sender) if sender else None
        _app=App(DynamoStore(boto3.resource('dynamodb').Table(os.environ['TABLE_NAME'])),config,boto3.client('rekognition',region_name='us-east-1'),boto3.client('sts'),mailer=mailer)
    return _app.handle(event)
