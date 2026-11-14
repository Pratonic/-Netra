"""Provision only after approval of AWS-DEPLOYMENT.md. Credentials stay in memory."""
import json, pathlib, time, io, zipfile, secrets
from service import password_hash

def package(root,destination):
    root=pathlib.Path(root)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for name in ('service.py','policy.py'):z.write(root/'backend'/name,name)
        for p in (root/'backend/public').rglob('*'):
            if p.is_file():z.write(p,pathlib.Path('public')/p.relative_to(root/'backend/public'))
    return pathlib.Path(destination).read_bytes()

def deploy(session,root,gateway_secret):
    root=pathlib.Path(root)
    plan=json.loads((root/'backend/iam-plan.json').read_text(encoding='utf-8'))
    iam=session.client('iam');ddb=session.client('dynamodb');lam=session.client('lambda');logs=session.client('logs')
    account=session.client('sts').get_caller_identity()['Account']
    if account!=plan['account']:raise RuntimeError('The AWS account differs from the approved deployment plan.')
    def missing(e,code):return getattr(e,'response',{}).get('Error',{}).get('Code')==code
    def role(definition):
        name=definition['name']
        try:
            r=iam.get_role(RoleName=name)['Role']
            actual=r['AssumeRolePolicyDocument']
            if actual!=definition['trust']:raise RuntimeError('Existing role trust differs from the approved plan: '+name)
        except Exception as e:
            if not missing(e,'NoSuchEntity'):raise
            for attempt in range(6):
                try:
                    r=iam.create_role(RoleName=name,AssumeRolePolicyDocument=json.dumps(definition['trust']),Description='Aegis campus access - scoped service role',Tags=[{'Key':'Application','Value':'AegisCampus'}])['Role']
                    break
                except Exception as create_error:
                    if missing(create_error,'MalformedPolicyDocument') and 'Invalid principal' in str(create_error) and attempt<5:time.sleep(3);continue
                    raise
        iam.put_role_policy(RoleName=name,PolicyName='AegisScopedAccess',PolicyDocument=json.dumps(definition['permissions']))
        return r['Arn']
    service_role=role(plan['service_role']);stream_role=role(plan['stream_role'])
    try:ddb.describe_table(TableName=plan['table']['name'])
    except Exception as e:
        if not missing(e,'ResourceNotFoundException'):raise
        ddb.create_table(TableName=plan['table']['name'],AttributeDefinitions=[{'AttributeName':'pk','AttributeType':'S'},{'AttributeName':'sk','AttributeType':'S'}],KeySchema=[{'AttributeName':'pk','KeyType':'HASH'},{'AttributeName':'sk','KeyType':'RANGE'}],BillingMode='PAY_PER_REQUEST',SSESpecification={'Enabled':True},OnDemandThroughput={'MaxReadRequestUnits':10,'MaxWriteRequestUnits':10},Tags=[{'Key':'Application','Value':'AegisCampus'}])
    ddb.get_waiter('table_exists').wait(TableName=plan['table']['name'])
    if ddb.describe_time_to_live(TableName=plan['table']['name'])['TimeToLiveDescription']['TimeToLiveStatus']=='DISABLED':ddb.update_time_to_live(TableName=plan['table']['name'],TimeToLiveSpecification={'Enabled':True,'AttributeName':'expiresAt'})
    group='/aws/lambda/AegisCampusService'
    try:logs.create_log_group(logGroupName=group,tags={'Application':'AegisCampus'})
    except Exception as e:
        if not missing(e,'ResourceAlreadyExistsException'):raise
    logs.put_retention_policy(logGroupName=group,retentionInDays=3)
    salt=secrets.token_hex(16)
    environment={'AEGIS_GATEWAY_SECRET':gateway_secret,'PASSWORD_SALT':salt,'ADMIN_HASH':password_hash('admin',salt),'ACCESS_HASH':password_hash('AWS',salt),'STREAM_ROLE_ARN':stream_role,'TABLE_NAME':plan['table']['name']}
    code=package(root,root.parent/'Aegis-AWS-function.zip')
    name=plan['function']['name'];exists=False
    try:
        existing=lam.get_function_configuration(FunctionName=name);exists=True
        for key in ('PASSWORD_SALT','ADMIN_HASH','ACCESS_HASH'):
            if key in existing.get('Environment',{}).get('Variables',{}):environment[key]=existing['Environment']['Variables'][key]
    except Exception as e:
        if not missing(e,'ResourceNotFoundException'):raise
    if exists:
        lam.update_function_code(FunctionName=name,ZipFile=code)
        lam.get_waiter('function_updated_v2').wait(FunctionName=name)
        lam.update_function_configuration(FunctionName=name,Role=service_role,Timeout=25,MemorySize=512,Environment={'Variables':environment})
        lam.get_waiter('function_updated_v2').wait(FunctionName=name)
    else:
        for attempt in range(8):
            try:
                lam.create_function(FunctionName=name,Runtime='python3.12',Role=service_role,Handler='service.lambda_handler',Code={'ZipFile':code},Timeout=25,MemorySize=512,Environment={'Variables':environment},Tags={'Application':'AegisCampus'})
                break
            except Exception as e:
                if missing(e,'InvalidParameterValueException') and 'cannot be assumed' in str(e) and attempt<7:time.sleep(5);continue
                raise
        lam.get_waiter('function_active_v2').wait(FunctionName=name)
    lam.put_function_concurrency(FunctionName=name,ReservedConcurrentExecutions=2)
    try:url=lam.get_function_url_config(FunctionName=name)['FunctionUrl']
    except Exception as e:
        if not missing(e,'ResourceNotFoundException'):raise
        url=lam.create_function_url_config(FunctionName=name,AuthType='NONE')['FunctionUrl']
    for args in [
        {'StatementId':'AegisGatewayURL','Action':'lambda:InvokeFunctionUrl','Principal':'*','FunctionUrlAuthType':'NONE'},
        {'StatementId':'AegisGatewayInvocation','Action':'lambda:InvokeFunction','Principal':'*','InvokedViaFunctionUrl':True}
    ]:
        try:lam.add_permission(FunctionName=name,**args)
        except Exception as e:
            if not missing(e,'ResourceConflictException'):raise
    return {'origin':url,'function':name,'table':plan['table']['name'],'region':'us-east-1','roles':[service_role,stream_role],'code_bytes':len(code)}
