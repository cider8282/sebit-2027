#!/usr/bin/env python3
"""SEBIT classroom rules, executed only in Firebase Cloud Functions."""
import json, secrets, hashlib, hmac, time, copy, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT=Path(__file__).resolve().parent
PRODUCT_CATALOG=json.loads((ROOT/'product-catalog.json').read_text(encoding='utf-8'))
PRODUCT_IMAGES={p['id'] for p in PRODUCT_CATALOG} | set(range(8))

def starter_products():
    return [dict(id=uid(),name=p['label'],price=0,stock=0,image=p['id'],category='간식',description='',active=False) for p in PRODUCT_CATALOG if p['category']=='간식']

KST=timezone(timedelta(hours=9))
def now(): return int(time.time()*1000)
def day(t=None): return datetime.fromtimestamp((t if t is not None else now())/1000,KST).strftime('%Y-%m-%d')
def uid(): return secrets.token_hex(12)
def fail(msg): raise ValueError(msg)
def require(ok,msg='권한이 없거나 처리할 수 없는 요청입니다.'):
    if not ok: fail(msg)
def num(v,lo=-1000000,hi=1000000):
    require(type(v) is int and lo<=v<=hi,'올바른 정수를 입력해 주세요.'); return v
def txt(v,n=200):
    require(isinstance(v,str) and 0<len(v.strip())<=n,'입력 내용의 길이를 확인해 주세요.'); return v.strip()
def date(v):
    require(isinstance(v,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',v),'날짜를 확인해 주세요.')
    datetime.strptime(v,'%Y-%m-%d'); return v

def pw_hash(p):
    salt=secrets.token_hex(16); return salt+':'+hashlib.scrypt(p.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex()
def pw_ok(p,h):
    try:
        salt,d=h.split(':'); return hmac.compare_digest(d,hashlib.scrypt(p.encode(),salt=salt.encode(),n=16384,r=8,p=1).hex())
    except (ValueError,TypeError): return False

def initial():
    return dict(version=1,epoch=uid(),className='',opened=False,teacher='',students=[],ledger=[],items=[],deposits=[],bankEvents=[],activities=[],closures={},activityRates={},rewardSchedule=[{'from':'2000-01-01','morning':[10,5],'reading':[10,5]}],products=starter_products(),discounts={},jobs=[dict(id='merchant',name='상인',role='merchant',checklist=['지급 목록 확인','물건 전달'],reward=[20,10],active=True),dict(id='ranger',name='생활지킴이',role='ranger',checklist=['학급 규칙 살피기','필요한 위반 등록'],reward=[20,10],active=True),dict(id='helper',name='학급 도우미',role='',checklist=['맡은 일 수행'],reward=[20,10],active=True)],jobPeriods=[],jobRecords=[],quests=[],applications=[],categories=[dict(id='safety',name='안전'),dict(id='respect',name='존중'),dict(id='responsibility',name='책임'),dict(id='community',name='공동생활')],rules=[dict(id='r1',category='safety',name='복도와 계단에서 뛰지 않기',lumen=10,xp=0),dict(id='r2',category='respect',name='친구에게 욕하거나 놀리지 않기',lumen=10,xp=5),dict(id='r3',category='responsibility',name='공동 물건 사용 후 정리하기',lumen=5,xp=0)],violations=[],citizens=[],citizenReward=[30,10],violationSince=now(),thermo=dict(total=0,round=uid(),events=['학급 놀이','자유 놀이','학급 이벤트','특별 활동','목표 달성 축하'],done=[]),donations=[],threads=[],notifications=[],schedule={},ranks=[dict(name=n,xp=x) for n,x in zip(['알','아기','사춘기','에너지','위엄'],[0,100,300,600,1000])])
def get(rows,id):
    row=next((r for r in rows if r['id']==id),None); require(row is not None,'자료를 찾을 수 없어요.'); return row
def student(s,id): return get(s['students'],id)
def rank(s,p): return max(i for i,r in enumerate(s['ranks']) if p['xp']>=r['xp'])
def notify(s,sid,body,menu='home'):
    s['notifications'].append(dict(id=uid(),student=sid,body=body,menu=menu,time=now(),read=False))
def change(s,sid,l,x,reason,kind,key=None,ref=None):
    if key and any(r.get('key')==key and not r.get('cancelled') for r in s['ledger']): return None
    p=student(s,sid); before=rank(s,p); actual=max(0,p['xp']+x)-p['xp']; p['lumen']+=l; p['xp']+=actual
    if rank(s,p)!=before: p['character']='default'
    r=dict(id=uid(),student=sid,lumen=l,xp=actual,balance=p['lumen'],xpBalance=p['xp'],reason=reason,kind=kind,key=key,ref=ref,time=now(),cancelled=False)
    s['ledger'].append(r); notify(s,sid,reason+f' · {l:+}루멘 / {actual:+}XP','history'); return r

def reward(s,sid,amount,reason,key): return change(s,sid,amount[0],amount[1],reason,'reward',key)
def rate(v): require(isinstance(v,list) and len(v)==2); return [num(v[0],0),num(v[1],0)]
def tick(s,t=None):
    t=t or now()
    for i in s['items']:
        if i['status']=='pending' and i['until']<=t:
            i['status']='pocket'; notify(s,i['student'],'지급 요청 시간이 지나 다시 요청할 수 있어요.','pocket')
    for d in s['deposits']:
        if d['status']=='active' and d['due']<=t:
            d['status']='matured'; interest=d['amount']*3//100
            change(s,d['student'],d['amount']+interest,0,'예금 만기 지급','bank','maturity:'+d['id'])
            s['bankEvents'].append(dict(id=uid(),student=d['student'],type='만기',amount=d['amount'],interest=interest,time=t))
    today=day(t)
    if today not in s['discounts'] or s['discounts'][today] is None:
        eligible=[p for p in s['products'] if p.get('active',True) and p['stock']>0]
        s['discounts'][today]=secrets.choice(eligible)['id'] if eligible else None

def pricing(s,p): return (p['price']*85+50)//100 if s['discounts'].get(day())==p['id'] else p['price']
def jobperiod(s): return next((p for p in reversed(s['jobPeriods']) if p['status']=='active'),None)
def role(s,sid):
    p=jobperiod(s)
    if not p: return ''
    j=p['assignments'].get(sid)
    return p['jobs'].get(j,{}).get('role','')
def activity_rate(s,d,kind):
    if d not in s['activityRates']:
        options=[x for x in s['rewardSchedule'] if x['from']<=d]; r=max(options,key=lambda x:x['from'])
        s['activityRates'][d]=dict(morning=r['morning'][:],reading=r['reading'][:])
    return s['activityRates'][d][kind]
def eligible(s,c):
    ids=[]
    for p in s['students']:
        if not p['active'] or p['joined']>c['end']: continue
        bad=any(v['student']==p['id'] and not v.get('cancelled') and c['start']<=v['time']<=c['end'] for v in s['violations'])
        decision=c.get('overrides',{}).get(p['id'])
        if decision['include'] if decision else not bad: ids.append(p['id'])
    return ids

def project_view(s,a):
    out=copy.deepcopy(s); out.pop('teacher',None)
    for p in out['students']:
        p.pop('pin',None)
        if a!='teacher': p.pop('tempPin',None)
    if a=='teacher':
        for ci in out['citizens']:
            if ci.get('end'): ci['eligible']=eligible(s,ci)
    else:
        me=student(s,a); out['me']=copy.deepcopy(next(p for p in out['students'] if p['id']==a)); out['myRole']=role(s,a)
        out['students']=[{k:p[k] for k in ['id','number','name','active']} for p in out['students'] if p['active']] if role(s,a) in ['ranger','merchant'] else []
        for field in ['ledger','deposits','bankEvents','activities','jobRecords','applications','donations','notifications']:
            out[field]=[r for r in out[field] if r['student']==a]
        out['items']=[i for i in out['items'] if i['student']==a or (role(s,a)=='merchant' and i['status']=='pending')]
        out['violations']=[v for v in out['violations'] if v['student']==a and v['time']>=s['violationSince']]
        out['threads']=[r for r in out['threads'] if r['student']==a]
        out['citizens']=[dict(id=ci['id'],start=ci['start'],end=ci.get('end'),status=ci['status'],reward=ci['reward'],eligible=a in eligible(s,ci) if ci.get('end') else None,paid=any(l.get('key')==f"citizen:{ci['id']}:{a}" and not l['cancelled'] for l in s['ledger'])) for ci in out['citizens'] if ci['status']!='archived']
        out['jobPeriods']=[dict(id=p['id'],start=p['start'],end=p.get('end'),status=p['status'],jobs={p['assignments'][a]:p['jobs'][p['assignments'][a]]},assignments={a:p['assignments'][a]},adjustments={a:p['adjustments'][a]} if a in p.get('adjustments',{}) else {}) for p in out['jobPeriods'] if a in p['assignments']]
        out['quests']=[q for q in out['quests'] if q['status']!='draft' and not q.get('listRemoved',False)]
    out['actor']=a; out['serverTime']=now(); return out

def dispatch(s,c,a,cmd,b):
    teacher=a=='teacher'; me=None if teacher else student(s,a)
    def T(): require(teacher,'교사만 사용할 수 있어요.')
    def S(): require(not teacher,'학생 화면에서 이용해 주세요.')
    def ids():
        T(); v=b['students']; require(isinstance(v,list) and v and len(v)==len(set(v)))
        for x in v: student(s,x)
        return v
    def owner(row): require(teacher or row['student']==a)
    if cmd=='pin':
        S(); p=txt(b['pin'],12); require(re.fullmatch(r'\d{4,8}',p),'PIN은 숫자 4~8자리예요.'); require(not pw_ok(p,me['pin']),'임시 PIN과 다르게 정해 주세요.')
        me.update(pin=pw_hash(p),mustChange=False,tempPin=None); return
    if cmd=='character':
        S(); v=b['value']; require(v=='default' or v in [f'{rank(s,me)}-{i}' for i in range(4)]); me['character']=v; return
    if cmd=='open':
        T(); s['opened']=bool(b['value'])
        if not s['opened']: c.revoke_students()
        return
    if cmd=='roster':
        T(); rows=b['rows']; require(isinstance(rows,list) and 0<len(rows)<=100); seen={p['number'] for p in s['students']}; pins={p.get('tempPin') for p in s['students']}
        for r in rows:
            n=num(r['number'],1,999); require(n not in seen,'이미 사용한 번호가 있어요.'); seen.add(n); pin=str(secrets.randbelow(900000)+100000)
            while pin in pins: pin=str(secrets.randbelow(900000)+100000)
            pins.add(pin); s['students'].append(dict(id=uid(),number=n,login=f'S{n:02}',name=txt(r['name'],30),pin=pw_hash(pin),tempPin=pin,mustChange=True,active=True,joined=now(),lumen=0,xp=0,character='default'))
        return
    if cmd in ['student','resetPin']:
        T(); p=student(s,b['id'])
        if cmd=='student':
            p['name']=txt(b.get('name',p['name']),30); p['active']=bool(b.get('active',p['active']))
        else:
            pin=str(secrets.randbelow(900000)+100000)
            while any(q.get('tempPin')==pin for q in s['students']): pin=str(secrets.randbelow(900000)+100000)
            p.update(pin=pw_hash(pin),tempPin=pin,mustChange=True)
        c.revoke_actor(p['id']); return
    if cmd=='points':
        for sid in ids(): change(s,sid,num(b['lumen']),num(b['xp']),b.get('reason') or '교사 직접 조정','manual')
        return
    if cmd=='reverse':
        T(); r=get(s['ledger'],b['id']); require(r['kind'] in ['reward','manual','penalty'] and not r['cancelled'],'이미 취소되었거나 취소할 수 없는 거래예요.')
        r['cancelled']=True; change(s,r['student'],-r['lumen'],-r['xp'],'취소: '+r['reason'],'reversal',ref=r['id'])
        for v in s['violations']:
            if v['ledger']==r['id']: v['cancelled']=True
        return
    if cmd=='product':
        T(); image=num(b.get('image',0),0,100); require(image in PRODUCT_IMAGES,'준비된 상품 그림을 선택해 주세요.')
        category=b.get('category') or next((p['category'] for p in PRODUCT_CATALOG if p['id']==image),'문구' if image in [0,1,2,4,5] else '간식')
        require(category in ['간식','문구','쿠폰','특별'],'상품 분류를 확인해 주세요.')
        values=dict(name=txt(b['name'],60),price=num(b['price'],0),stock=num(b['stock'],0),image=image,category=category,description=txt(b['description'],500) if b.get('description','').strip() else '',active=bool(b.get('active',True)))
        if b.get('id'): get(s['products'],b['id']).update(values)
        else: s['products'].append(dict(id=uid(),**values))
        return
    if cmd=='buy':
        S(); require(len([i for i in s['items'] if i['student']==a and i['status']!='delivered'])<6,'주머니가 꽉 차서 물건을 구매할 수 없어요. 상품을 지급받은 뒤 다시 구매해 주세요.')
        p=get(s['products'],b['id']); require(p['active'] and p['stock']>0,'품절된 상품이에요.'); price=pricing(s,p)
        require(b['price']==price,'가격이 바뀌었어요. 다시 확인해 주세요.'); require(me['lumen']>=price,'루멘이 부족해요.')
        p['stock']-=1; change(s,a,-price,0,p['name']+' 구매','purchase')
        s['items'].append(dict(id=uid(),student=a,product=p['id'],name=p['name'],image=p['image'],price=price,status='pocket',time=now())); return
    if cmd=='request':
        S(); i=get(s['items'],b['id']); require(i['student']==a and i['status']=='pocket'); i.update(status='pending',until=now()+3600000); return
    if cmd in ['deliver','undoDelivery']:
        require(teacher or role(s,a)=='merchant'); i=get(s['items'],b['id'])
        if cmd=='deliver': require(i['status']=='pending','요청이 만료되었거나 이미 지급했어요.'); i.update(status='delivered',deliveredAt=now(),deliveredBy=a); notify(s,i['student'],i['name']+' 지급 완료','pocket')
        else:
            T(); require(i['status']=='delivered'); require(len([x for x in s['items'] if x['student']==i['student'] and x['status']!='delivered'])<6,'주머니에 빈 칸이 있어야 정정할 수 있어요.')
            i.setdefault('corrections',[]).append(dict(time=now(),reason=txt(b['reason']))); i['status']='pocket'
        return
    if cmd=='deposit':
        S(); amount=num(b['amount'],100); require(amount%100==0 and me['lumen']>=amount,'100루멘 단위와 잔액을 확인해 주세요.'); require(not any(d['student']==a and d['status']=='active' for d in s['deposits']),'진행 중인 예금이 있어요.')
        s['deposits'].append(dict(id=uid(),student=a,amount=amount,time=now(),due=now()+864000000,status='active')); change(s,a,-amount,0,'예금 가입','bank'); s['bankEvents'].append(dict(id=uid(),student=a,type='가입',amount=amount,interest=0,time=now())); return
    if cmd=='withdraw':
        d=get(s['deposits'],b['id']); owner(d); require(d['status']=='active','이미 처리된 예금이에요.'); d['status']='withdrawn'; change(s,d['student'],d['amount'],0,'예금 중도 해지','bank'); s['bankEvents'].append(dict(id=uid(),student=d['student'],type='중도 해지',amount=d['amount'],interest=0,time=now())); return
    if cmd=='donate':
        S(); amount=num(b['amount'],1,100); used=sum(d['amount'] for d in s['donations'] if d['student']==a and d['date']==day()); remaining=10000-s['thermo']['total']
        require(remaining>0,'최종 목표를 달성했어요.'); require(amount<=remaining,'남은 기부 금액이 바뀌었어요. 다시 확인해 주세요.'); require(used+amount<=100,'하루 기부 한도는 100루멘이에요.'); require(me['lumen']>=amount,'루멘이 부족해요.')
        s['thermo']['total']+=amount; s['donations'].append(dict(id=uid(),student=a,date=day(),amount=amount,time=now(),round=s['thermo']['round'])); change(s,a,-amount,0,'학급 온도계 기부','donation'); return
    if cmd=='thermo':
        T()
        if b.get('reset'): s['thermo'].update(total=0,round=uid(),done=[])
        elif 'events' in b: require(len(b['events'])==5); s['thermo']['events']=[txt(x,80) for x in b['events']]
        else:
            stage=num(b['stage'],1,5); require(s['thermo']['total']>=stage*2000); s['thermo']['done']=list(set(s['thermo']['done']+[stage]))
        return
    if cmd=='activity':
        kind=b['kind']; require(kind in ['morning','reading']); d=date(b.get('date',day())); sid=b.get('student',a) if teacher else a; student(s,sid)
        require(d<=day(),'미래 날짜는 기록할 수 없어요.')
        if not teacher: require(d==day() and not s['closures'].get(kind+':'+d),'오늘 기록만 가능하며 마감 후에는 교사에게 문의해 주세요.')
        rows=[x for x in s['activities'] if x['student']==sid and x['date']==d and x['kind']==kind]
        require(len(rows)<(1 if kind=='morning' else 3),'하루 기록 횟수를 확인해 주세요.'); activity_rate(s,d,kind)
        r=dict(id=uid(),student=sid,date=d,kind=kind,time=now())
        if kind=='reading': r.update(title=txt(b['title'],120),start=num(b['start'],1,100000),end=num(b['end'],1,100000)); require(r['end']>=r['start'],'마지막 쪽을 확인해 주세요.')
        s['activities'].append(r); return
    if cmd=='activityEdit':
        T(); r=get(s['activities'],b['id']); r.setdefault('edits',[]).append(dict(time=now(),before={k:v for k,v in r.items() if k!='edits'}))
        if r['kind']=='reading': r.update(title=txt(b['title'],120),start=num(b['start'],1),end=num(b['end'],1)); require(r['end']>=r['start'])
        return
    if cmd=='closeActivity':
        T(); selected=b['students']; require(isinstance(selected,list) and len(selected)==len(set(selected))); [student(s,x) for x in selected]; kind=b['kind']; require(kind in ['morning','reading']); d=date(b['date']); require(d<=day()); amount=activity_rate(s,d,kind)
        s['closures'][kind+':'+d]=dict(time=now(),students=selected)
        for sid in selected: reward(s,sid,amount,('아침 활동' if kind=='morning' else '독서')+' '+d,f'activity:{kind}:{d}:{sid}')
        return
    if cmd=='job':
        T(); values=dict(name=txt(b['name'],50),checklist=[txt(x,100) for x in b['checklist']],reward=rate(b['reward']),active=bool(b.get('active',True)))
        if b.get('id'): get(s['jobs'],b['id']).update(values)
        else: s['jobs'].append(dict(id=uid(),role='',**values))
        return
    if cmd=='jobStart':
        T(); require(not any(p['status'] in ['active','ended'] for p in s['jobPeriods']),'이전 직업 기간을 먼저 정산해 주세요.'); assignments=b['assignments']; require(isinstance(assignments,dict) and assignments)
        for sid,j in assignments.items(): require(student(s,sid)['active'] and get(s['jobs'],j)['active'])
        s['jobPeriods'].append(dict(id=uid(),start=now(),status='active',assignments=assignments,jobs={j['id']:copy.deepcopy(j) for j in s['jobs']},adjustments={})); return
    if cmd=='jobAssignment':
        T(); p=get(s['jobPeriods'],b['id']); require(p['status']=='active'); sid=b['student']; student(s,sid); job=b['job']; require(job in p['jobs']); require(not any(r['student']==sid and r['period']==p['id'] for r in s['jobRecords']),'이미 수행 기록이 있어요. 기간 종료 후 인정일로 정정해 주세요.')
        p.setdefault('assignmentCorrections',[]).append(dict(student=sid,before=p['assignments'].get(sid),after=job,reason=txt(b['reason']),time=now())); p['assignments'][sid]=job; return
    if cmd=='jobComplete':
        S(); p=jobperiod(s); require(p and a in p['assignments'],'배정된 진행 직업이 없어요.'); require(not any(r['period']==p['id'] and r['student']==a and r['date']==day() for r in s['jobRecords']),'오늘 이미 완료했어요.')
        j=p['jobs'][p['assignments'][a]]; require(b['checks']==list(range(len(j['checklist']))),'모든 수행 항목을 확인해 주세요.'); s['jobRecords'].append(dict(id=uid(),student=a,period=p['id'],date=day(),checks=b['checks'],memo=b.get('memo','')[:500],checklist=j['checklist'][:])); return
    if cmd in ['jobEnd','jobAdjust','jobPay']:
        T(); p=get(s['jobPeriods'],b['id'])
        if cmd=='jobEnd': require(p['status']=='active'); p.update(status='ended',end=now())
        elif cmd=='jobAdjust':
            require(p['status']=='ended'); sid=b['student']; require(sid in p['assignments']); days=sorted(set(date(d) for d in b['dates'])); require(all(day(p['start'])<=d<=day(p['end']) for d in days)); p['adjustments'][sid]=days; p.setdefault('reasons',{})[sid]=txt(b['reason'])
        else:
            require(p['status']=='ended')
            for sid,jid in p['assignments'].items():
                days=p['adjustments'].get(sid,sorted({r['date'] for r in s['jobRecords'] if r['student']==sid and r['period']==p['id']})); amount=p['jobs'][jid]['reward']; reward(s,sid,[x*len(days) for x in amount],p['jobs'][jid]['name']+f' {len(days)}일 정산',f"job:{p['id']}:{sid}")
            p['status']='paid'
        return
    if cmd=='quest':
        T()
        if b.get('id') and b.get('action'):
            q=get(s['quests'],b['id']); action=b['action']
            if action=='copy': q=copy.deepcopy(q); q.update(id=uid(),name=q['name']+' (복사)',status='draft'); q.pop('listRemoved',None); s['quests'].append(q)
            elif action=='remove':
                require(q['status']=='ended' or q['end']<day(),'종료된 퀘스트만 목록에서 제거할 수 있어요.')
                require(not any(x['quest']==q['id'] and x['status']=='pending' for x in s['applications']),'승인 대기 신청을 먼저 처리해 주세요.')
                q['listRemoved']=True
            elif action=='delete': require(not any(x['quest']==q['id'] for x in s['applications']),'신청 내역이 있어 숨김으로 처리해 주세요.'); s['quests'].remove(q)
            else: require(action in ['hidden','ended','published']); q['status']=action
        else:
            value=dict(name=txt(b['name'],80),description=txt(b.get('description') or b['name'],1000),start=date(b['start']),end=date(b['end']),reward=rate(b['reward']),status='published'); require(value['end']>=value['start'])
            if b.get('id'):
                q=get(s['quests'],b['id']); require(q['status']=='draft' or q['reward']==value['reward'],'공개한 보상은 변경할 수 없어요. 복사해 주세요.'); value['status']='published' if q['status']=='draft' else q['status']; q.update(value)
            else:
                s['quests'].append(dict(id=uid(),**value))
                for p in s['students']:
                    if p['active']: notify(s,p['id'],'새 퀘스트: '+value['name'],'quests')
        return
    if cmd=='applyQuest':
        S(); q=get(s['quests'],b['id']); require(not q.get('listRemoved',False) and q['status']=='published' and q['start']<=day()<=q['end'],'신청 기간이 아니에요.'); require(not any(r['student']==a and r['quest']==q['id'] and r['status'] in ['pending','approved'] for r in s['applications']),'이미 신청하거나 지급받았어요.'); s['applications'].append(dict(id=uid(),student=a,quest=q['id'],status='pending',time=now())); return
    if cmd=='reviewQuest':
        T(); app=get(s['applications'],b['id']); require(app['status']=='pending'); q=get(s['quests'],app['quest'])
        if b['approve']: app['status']='approved'; reward(s,app['student'],q['reward'],q['name']+' 보상',f"quest:{q['id']}:{app['student']}")
        else: app.update(status='rejected',reason=txt(b['reason'])); notify(s,app['student'],q['name']+' 반려: '+app['reason'],'quests')
        return
    if cmd=='category':
        T()
        if b.get('delete'):
            cat=get(s['categories'],b['id']); s['categories'].remove(cat); s['rules']=[r for r in s['rules'] if r['category']!=cat['id']]
        elif b.get('id'): get(s['categories'],b['id'])['name']=txt(b['name'],40)
        else: s['categories'].append(dict(id=uid(),name=txt(b['name'],40)))
        return
    if cmd=='rule':
        T()
        if b.get('delete'): s['rules'].remove(get(s['rules'],b['id']))
        else:
            get(s['categories'],b['category']); value=dict(category=b['category'],name=txt(b['name']),lumen=num(b['lumen'],0),xp=num(b['xp'],0))
            if b.get('id'): get(s['rules'],b['id']).update(value)
            else: s['rules'].append(dict(id=uid(),**value))
        return
    if cmd=='violate':
        require(teacher or role(s,a)=='ranger'); r=get(s['rules'],b['rule']); cat=get(s['categories'],r['category']); selected=b['students']; require(isinstance(selected,list) and selected and len(set(selected))==len(selected)); number=[x['id'] for x in s['rules'] if x['category']==r['category']].index(r['id'])+1
        for sid in selected:
            require(student(s,sid)['active']); tr=change(s,sid,-r['lumen'],-r['xp'],r['name'],'penalty'); s['violations'].append(dict(id=uid(),student=sid,rule=r['id'],name=r['name'],category=cat['name'],number=number,lumen=-tr['lumen'],xp=-tr['xp'],configuredLumen=r['lumen'],configuredXp=r['xp'],ledger=tr['id'],time=now(),by=a,cancelled=False))
        return
    if cmd=='citizen':
        T(); action=b['action']; current=next((x for x in reversed(s['citizens']) if x['status']!='archived'),None)
        if action=='start':
            require(current is None,'이전 회차를 초기화해 주세요.'); s['citizenReward']=rate(b['reward']); s['citizens'].append(dict(id=uid(),start=now(),status='active',reward=s['citizenReward'][:],overrides={}))
        else:
            require(current is not None,'진행 회차가 없어요.')
            if action=='end': require(current['status']=='active'); current.update(end=now(),status='ended')
            elif action=='override': require(current.get('end')); student(s,b['student']); current['overrides'][b['student']]=dict(include=bool(b['include']),reason=txt(b['reason']))
            elif action=='pay':
                require(current.get('end'))
                for sid in eligible(s,current): reward(s,sid,current['reward'],'모범시민 보상',f"citizen:{current['id']}:{sid}")
                current['status']='paid'
            elif action=='reset': current['status']='archived'; s['violationSince']=now()
            else: fail('처리할 수 없는 동작이에요.')
        return
    if cmd=='message':
        content=txt(b['body'],3000)
        if b.get('id'):
            th=get(s['threads'],b['id']); owner(th); require(not th['closed'],'완료된 대화예요.')
        else:
            S(); th=dict(id=uid(),student=a,title=txt(b['title'],100),closed=False,messages=[]); s['threads'].append(th)
        th['messages'].append(dict(id=uid(),by=a,body=content,time=now())); th['lastBy']=a
        if teacher: notify(s,th['student'],'선생님의 새 답장이 도착했어요.','messages')
        return
    if cmd=='threadDelete':
        T(); th=get(s['threads'],b['id']); require(th['closed'],'대화를 완료한 후 삭제해 주세요.'); s['threads'].remove(th); return
    if cmd=='thread': T(); get(s['threads'],b['id'])['closed']=bool(b['closed']); return
    if cmd=='read':
        S()
        for n in s['notifications']:
            if n['student']==a: n['read']=True
        return
    if cmd=='schedule': T(); s['schedule'][date(b['date'])]=dict(events=b.get('events','')[:3000],meal=b.get('meal','')[:1000]); return
    if cmd=='settings':
        T()
        if 'className' in b: s['className']=txt(b['className'],50)
        if 'ranks' in b:
            rr=b['ranks']; require(len(rr)==5); rr=[dict(name=txt(r['name'],30),xp=num(r['xp'],0)) for r in rr]; require(rr[0]['xp']==0 and all(rr[i]['xp']<rr[i+1]['xp'] for i in range(4)))
            old={p['id']:rank(s,p) for p in s['students']}; s['ranks']=rr
            for p in s['students']:
                if rank(s,p)!=old[p['id']]: p['character']='default'
        if 'morning' in b:
            tomorrow=day(now()+86400000); r=dict(from_=tomorrow); r={'from':tomorrow,'morning':rate(b['morning']),'reading':rate(b['reading'])}; s['rewardSchedule']=[x for x in s['rewardSchedule'] if x['from']!=tomorrow]+[r]
        if b.get('password'): require(len(b['password'])>=8,'교사 비밀번호는 8자 이상이에요.'); s['teacher']=pw_hash(b['password']); c.revoke_actor('teacher')
        return
    if cmd=='repay':
        T(); r=get(s['ledger'],b['id']); require(r['kind']=='reward' and r['cancelled']); reward(s,r['student'],[r['lumen'],r['xp']],r['reason'],r['key']); return
    if cmd=='newYear':
        T(); require(b.get('confirm')==s['className'],'학급 이름을 정확히 입력해 주세요.'); fresh=initial()
        for field in ['className','teacher','jobs','categories','rules','ranks','products','citizenReward']: fresh[field]=copy.deepcopy(s[field])
        fresh['rewardSchedule']=[dict(s['rewardSchedule'][-1],**{'from':'2000-01-01'})]; fresh['thermo']['events']=s['thermo']['events'][:]
        for p in fresh['products']: p['stock']=0
        s.clear(); s.update(fresh); c.revoke_all(); return dict(ok=True,logout=True)
    fail('지원하지 않는 요청이에요.')

# Backup integrity checks run before any state replacement.
def validate_backup(data):
    require(isinstance(data,dict) and data.get('format')=='SEBIT-1','SEBIT 백업 파일이 아니에요.'); s=data.get('state'); require(isinstance(s,dict) and s.get('version')==1)
    require(hashlib.sha256(json.dumps(s,sort_keys=True,ensure_ascii=False).encode()).hexdigest()==data.get('checksum'),'백업 파일이 손상되었어요.')
    base=initial(); require(set(s)==set(base),'백업 구조가 일치하지 않아요.')
    for k,v in base.items(): require(type(s[k]) is type(v),'백업 자료 형식이 잘못됐어요.')
    for value in s.values():
        if isinstance(value,list):
            for row in value:
                if isinstance(row,dict) and 'id' in row: require(isinstance(row['id'],str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',row['id']),'백업 식별자가 잘못됐어요.')
    seen=set()
    for p in s['students']:
        require(p['id'] not in seen); seen.add(p['id']); num(p['lumen'],-10**12,10**12); num(p['xp'],0,10**12); require(isinstance(p['pin'],str) and ':' in p['pin']); require(type(p['active']) is bool)
    for field in ['ledger','items','deposits','bankEvents','activities','jobRecords','applications','violations','donations','threads','notifications']:
        require(all(r.get('student') in seen for r in s[field]),'학생 참조가 잘못됐어요.')
    for p in s['students']: require(len([i for i in s['items'] if i['student']==p['id'] and i['status']!='delivered'])<=6)
    require(len(s['ranks'])==5 and s['ranks'][0]['xp']==0 and all(s['ranks'][i]['xp']<s['ranks'][i+1]['xp'] for i in range(4)))
    # A checksum alone cannot validate a backup's structure and relationships.
    required={
        'students':['id','number','login','name','pin','mustChange','active','joined','lumen','xp','character'],
        'products':['id','name','price','stock','image','active'],
        'ledger':['id','student','lumen','xp','balance','xpBalance','reason','kind','key','ref','time','cancelled'],
        'items':['id','student','product','name','image','price','status','time'],
        'deposits':['id','student','amount','time','due','status'],
        'bankEvents':['id','student','type','amount','interest','time'],
        'activities':['id','student','date','kind','time'],
        'jobs':['id','name','role','checklist','reward','active'],
        'jobPeriods':['id','start','status','assignments','jobs','adjustments'],
        'jobRecords':['id','student','period','date','checks','memo','checklist'],
        'quests':['id','name','description','start','end','reward','status'],
        'applications':['id','student','quest','status','time'],
        'categories':['id','name'],
        'rules':['id','category','name','lumen','xp'],
        'violations':['id','student','rule','name','category','number','lumen','xp','ledger','time','by','cancelled'],
        'citizens':['id','start','status','reward','overrides'],
        'donations':['id','student','date','amount','round'],
        'threads':['id','student','title','closed','messages','lastBy'],
        'notifications':['id','student','body','menu','time','read']
    }
    for field,keys in required.items():
        rows=s[field]
        require(all(isinstance(r,dict) and all(k in r for k in keys) for r in rows),'백업의 필수 항목이 빠졌어요: '+field)
        require(len({r['id'] for r in rows})==len(rows),'중복 식별자가 있어요: '+field)
    require(len({p['number'] for p in s['students']})==len(s['students']) and len({p['login'] for p in s['students']})==len(s['students']),'학생 번호나 아이디가 중복돼요.')
    for p in s['students']:
        num(p['number'],1,999); txt(p['name'],30)
        require(type(p['mustChange']) is bool and (p['character']=='default' or p['character'] in [f'{rank(s,p)}-{i}' for i in range(4)]),'학생 캐릭터나 PIN 상태를 확인해 주세요.')
    for p in s['products']:
        txt(p['name'],60); num(p['price'],0); num(p['stock'],0)
        require(type(p['image']) is int and p['image'] in PRODUCT_IMAGES and type(p['active']) is bool,'상품 자료를 확인해 주세요.')
    product_ids={p['id'] for p in s['products']}
    ledger_ids={r['id'] for r in s['ledger']}
    for r in s['ledger']:
        for k in ['lumen','xp','balance']:num(r[k],-10**12,10**12)
        num(r['xpBalance'],0,10**12); require(type(r['cancelled']) is bool)
        require(r['ref'] is None or r['ref'] in ledger_ids,'거래 취소 관계가 잘못됐어요.')
    for i in s['items']:
        require(i['product'] in product_ids and i['status'] in ['pocket','pending','delivered'],'주머니 자료가 잘못됐어요.')
        require(type(i['image']) is int and i['image'] in PRODUCT_IMAGES)
        if i['status']=='pending':num(i.get('until'),0,10**15)
        if i['status']=='delivered':num(i.get('deliveredAt'),0,10**15)
    for d in s['deposits']:
        require(d['status'] in ['active','matured','withdrawn']);num(d['amount'],100);require(d['amount']%100==0);num(d['due'],0,10**15)
    for sid in seen:require(sum(d['student']==sid and d['status']=='active' for d in s['deposits'])<=1,'진행 예금이 중복돼요.')
    for r in s['activities']:
        date(r['date']);require(r['kind'] in ['morning','reading'])
        if r['kind']=='reading':txt(r.get('title'),120);num(r.get('start'),1);num(r.get('end'),r['start'])
    for p in s['jobPeriods']:
        require(isinstance(p['assignments'],dict) and isinstance(p['jobs'],dict) and isinstance(p['adjustments'],dict))
        require(all(sid in seen and jid in p['jobs'] for sid,jid in p['assignments'].items()))
    for q in s['quests']:require(type(q.get('listRemoved',False)) is bool,'퀘스트 목록 상태를 확인해 주세요.');date(q['start']);date(q['end']);rate(q['reward']);require(q['end']>=q['start'])
    require(all(a['quest'] in {q['id'] for q in s['quests']} for a in s['applications']))
    require(all(v['ledger'] in ledger_ids for v in s['violations']))
    require(all(r['category'] in {c['id'] for c in s['categories']} for r in s['rules']))
    for t in s['threads']:
        require(type(t['closed']) is bool and isinstance(t['messages'],list) and t['messages'])
        for m in t['messages']:
            require(isinstance(m,dict) and all(k in m for k in ['id','by','body','time']) and m['by'] in ['teacher',t['student']]);txt(m['body'],3000)
    require(isinstance(s['thermo'].get('events'),list) and len(s['thermo']['events'])==5 and isinstance(s['thermo'].get('done'),list));num(s['thermo'].get('total'),0,10000)
    require(s['rewardSchedule'] and all(all(k in r for k in ['from','morning','reading']) for r in s['rewardSchedule']))
    for r in s['rewardSchedule']:date(r['from']);rate(r['morning']);rate(r['reading'])
    return s

