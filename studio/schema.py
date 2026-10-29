import math
PROFILES=('gait','gait_more_progress','gait_explore','generalize')
RANGES={'lr':(1e-6,.01),'entropy':(0,.2),'linear':(-50,50),'angular':(-50,50),
 'upright':(-50,50),'pose':(-50,50),'air':(-50,50),'head':(-50,50),'swing':(-50,50),
 'smooth':(-50,50),'progress':(-50,50),'forward_min':(0,1),'forward_max':(.01,1),
 'lateral_max':(0,.5),'yaw_max':(0,2)}
def number(value,lo,hi,name,integer=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi or (integer and int(value)!=value):
        raise ValueError(f'{name} must be {lo}–{hi}'+(' (integer)' if integer else ''))
    return int(value) if integer else float(value)
def overrides(raw):
    if not isinstance(raw,dict) or set(raw)-set(RANGES):raise ValueError('Unknown training override')
    result={k:number(v,*RANGES[k],k) for k,v in raw.items()}
    if result.get('forward_min',.08)>result.get('forward_max',.30):raise ValueError('Forward minimum exceeds maximum')
    return result
def training(raw):
    allowed={'name','parent','environments','save_every','seed','forever','stall_limit','eval_envs','eval_seeds','eval_seconds','stages'}
    if not isinstance(raw,dict) or set(raw)-allowed:raise ValueError('Unknown experiment field')
    name=str(raw.get('name','Untitled experiment')).strip()
    if not name or len(name)>100:raise ValueError('Name must contain 1–100 characters')
    result={'name':name,'parent':raw.get('parent') or None}
    if result['parent'] is not None and not isinstance(result['parent'],str):raise ValueError('Invalid checkpoint ID')
    for key,default,lo,hi in [('environments',4096,128,16384),('save_every',250,50,5000),('seed',48017,0,2147483647),('stall_limit',6,0,100),('eval_envs',2,1,128),('eval_seeds',2,1,20)]:
        result[key]=number(raw.get(key,default),lo,hi,key,True)
    result['eval_seconds']=number(raw.get('eval_seconds',10),2,60,'eval_seconds')
    if not isinstance(raw.get('forever',False),bool):raise ValueError('forever must be Boolean')
    result['forever']=raw.get('forever',False)
    stages=raw.get('stages',[{'profile':'gait','updates':2000,'blocks':5,'overrides':{}}])
    if not isinstance(stages,list) or not 1<=len(stages)<=16:raise ValueError('Provide 1–16 training stages')
    result['stages']=[]
    for stage in stages:
        if not isinstance(stage,dict) or set(stage)-{'profile','updates','blocks','overrides'}:raise ValueError('Unknown stage field')
        if stage.get('profile') not in PROFILES:raise ValueError('Unknown training profile')
        result['stages'].append({'profile':stage['profile'],'updates':number(stage.get('updates',2000),8,50000,'updates',True),
         'blocks':number(stage.get('blocks',1),1,1000,'blocks',True),'overrides':overrides(stage.get('overrides',{}))})
    return result
