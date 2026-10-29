"""Dependency-free statistics for independent evaluation observations."""
import math,random,statistics

def finite(values):
    if not isinstance(values,list) or not 1<=len(values)<=10000:raise ValueError('Provide 1–10000 observations')
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in values):raise ValueError('Observations must be finite numbers')
    return values

def quantile(values,p):
    a=sorted(values);position=(len(a)-1)*p;lo=int(position);hi=min(lo+1,len(a)-1)
    return a[lo]+(a[hi]-a[lo])*(position-lo)

def summarize(values):
    a=finite(values);n=len(a);rng=random.Random(48017)
    means=sorted(statistics.fmean(rng.choices(a,k=n)) for _ in range(1000)) if n>1 else []
    return dict(n=n,mean=statistics.fmean(a),median=statistics.median(a),minimum=min(a),maximum=max(a),q25=quantile(a,.25),q75=quantile(a,.75),stddev=statistics.stdev(a) if n>1 else None,mean_ci95=[quantile(means,.025),quantile(means,.975)] if means else None,warning='Bootstrap assumes independent observations. Correlated training updates are not independent trials.')

def paired(a,b):
    a=finite(a);b=finite(b)
    if len(a)!=len(b):raise ValueError('Paired scenarios require equal sample counts and matching order')
    delta=[y-x for x,y in zip(a,b)];result=summarize(delta);sd=result['stddev'];result['paired_standardized_effect']=result['mean']/sd if sd else None
    result['interpretation']='B minus A; positive means B is numerically larger, not necessarily better.'
    return result

def flatten(value,prefix=''):
    result={}
    if isinstance(value,dict):
        for key,item in value.items():result.update(flatten(item,prefix+'.'+key if prefix else key))
    elif isinstance(value,list):
        for i,item in enumerate(value):result.update(flatten(item,f'{prefix}[{i}]'))
    else:result[prefix]=value
    return result

def differences(configs):
    if not isinstance(configs,list) or not 2<=len(configs)<=6:raise ValueError('Compare 2–6 configurations')
    rows=[flatten(c) for c in configs];keys=sorted(set().union(*(r.keys() for r in rows)))
    return [{'parameter':k,'values':[r.get(k) for r in rows]} for k in keys if len({repr(r.get(k)) for r in rows})>1]

def analyze(body):
    kind=body.get('kind')
    if kind=='plan':return plan(body.get('config'))
    if kind=='summary':return summarize(body.get('values'))
    if kind=='paired':return paired(body.get('a'),body.get('b'))
    if kind=='configuration_diff':return differences(body.get('configs'))
    raise ValueError('Unknown analysis operation')


def plan(raw):
    from .schema import training
    config=training(raw)
    stages=[]
    for index,stage in enumerate(config['stages']):
        updates=stage['updates']*stage['blocks']
        stages.append(dict(stage=index+1,profile=stage['profile'],updates=updates,evaluations=stage['blocks'],estimated_saves=stage['blocks']*(1+stage['updates']//config['save_every']),overrides=stage['overrides']))
    return dict(config=config,stages=stages,updates_per_sequence=sum(s['updates'] for s in stages),evaluations_per_sequence=sum(s['evaluations'] for s in stages),repeats_until_stopped=config['forever'],notes=['Save count is an estimate; final saves may overlap scheduled saves.','Runtime and disk estimates require measured throughput and checkpoint sizes.','Preflight updates are additional. Each block continues from the previous checkpoint.'])
