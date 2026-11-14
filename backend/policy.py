from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_SCHEDULE = {'timezone':'Asia/Kolkata','days':[0,1,2,3,4,5],'start':'08:00','end':'20:00','holidays':[]}

def validate_schedule(value):
    if not isinstance(value,dict): raise ValueError('Choose a valid access schedule.')
    ZoneInfo(value.get('timezone','Asia/Kolkata'))
    days=value.get('days',[])
    if not days or any(type(d) is not int or d not in range(7) for d in days): raise ValueError('Choose at least one valid day.')
    for key in ('start','end'):
        datetime.strptime(value.get(key,''),'%H:%M')
    if value['start']==value['end']: raise ValueError('Opening and closing times must differ.')
    holidays=value.get('holidays',[])
    if not isinstance(holidays,list) or len(holidays)>100: raise ValueError('Too many closed dates.')
    for day in holidays: datetime.strptime(day,'%Y-%m-%d')
    return {k:value[k] for k in ('timezone','days','start','end')} | {'holidays':holidays}

def schedule_decision(person, campus, now=None):
    if not person or not person.get('active'): return {'outcome':'deny','reason':'This identity is suspended.'}
    schedule=person.get('schedule') or campus
    try:
        schedule=validate_schedule(schedule)
        local=(now or datetime.now(timezone.utc)).astimezone(ZoneInfo(schedule['timezone']))
        day=local.strftime('%Y-%m-%d')
        if person.get('validUntil') and day>person['validUntil']: return {'outcome':'deny','reason':'This identity has expired.'}
        if day in campus.get('holidays',[]) or day in schedule.get('holidays',[]): return {'outcome':'deny','reason':'Campus is closed today.'}
        minute=local.hour*60+local.minute
        def minutes(s):
            h,m=map(int,s.split(':'));return h*60+m
        start,end=minutes(schedule['start']),minutes(schedule['end'])
        days=schedule['days']
        opened=(local.weekday() in days and start<=minute<end) if start<end else ((minute>=start and local.weekday() in days) or (minute<end and (local.weekday()-1)%7 in days))
        if not opened:
            return {'outcome':'stepup' if person.get('afterHours')=='review' else 'deny','reason':'Outside permitted campus hours.','schedule':f"{schedule['start']}–{schedule['end']} · {schedule['timezone']}"}
        return {'outcome':'eligible','reason':'Within campus access hours.','schedule':f"{schedule['start']}–{schedule['end']} · {schedule['timezone']}"}
    except (ValueError,KeyError,TypeError):
        return {'outcome':'stepup','reason':'Access schedule needs an administrator review.'}

IR_MAX_AGE_MS=1500
IR_MIN_SAMPLES=3

def ir_evidence(value):
    """Classify kiosk IR presence evidence sent by the browser.

    The sensor can only make a decision stricter: 'absent' turns a match into Deny,
    and a missing or stale reading is recorded (or blocks when the kiosk requires the sensor).
    It never turns any result into Allow.
    """
    if value is None:return {'irStatus':'not-connected'}
    if not isinstance(value,dict):return {'irStatus':'invalid'}
    try:
        samples=int(value.get('samples',0));ratio=float(value.get('presentRatio',-1));age=float(value.get('ageMs',1e12))
        raw=value.get('rawMedian');raw=int(raw) if raw is not None else None
    except (TypeError,ValueError,OverflowError):return {'irStatus':'invalid'}
    if value.get('status')!='ok' or samples<IR_MIN_SAMPLES or not 0<=age<=IR_MAX_AGE_MS or not 0<=ratio<=1:return {'irStatus':'stale'}
    out={'irStatus':'present' if ratio>=.5 else 'absent','irPresentRatio':round(ratio,2),'irSamples':min(samples,1000)}
    if raw is not None and 0<=raw<=1023:out['irRaw']=raw
    return out
