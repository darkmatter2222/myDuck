"""Bounded chart data; full raw event history remains available in evidence exports."""
import json,sys
from pathlib import Path
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
from tensorboard.util import tensor_util
request=json.load(sys.stdin);series=[];tags=set();warnings=[]
for run in request['runs'][:6]:
    try:
        acc=EventAccumulator(run,size_guidance={'scalars':500,'tensors':500});acc.Reload()
        available=acc.Tags();alltags=sorted(set(available.get('scalars',[])+available.get('tensors',[])));tags.update(alltags)
        chosen=alltags[:100] if request.get('all') else [request.get('tag') or next((t for t in alltags if 'reward' in t.lower()),alltags[0] if alltags else '')]
        for tag in chosen:
            points=[]
            if tag in available.get('scalars',[]):points=[[e.step,e.value,e.wall_time] for e in acc.Scalars(tag)]
            elif tag in available.get('tensors',[]):
                for event in acc.Tensors(tag):
                    value=tensor_util.make_ndarray(event.tensor_proto)
                    if value.size==1 and value.dtype.kind in 'biuf':points.append([event.step,float(value.item()),event.wall_time])
            series.append({'run':Path(run).name,'tag':tag,'points':sorted(points,key=lambda p:p[2])})
    except Exception as exc:warnings.append(Path(run).name+': '+str(exc))
print(json.dumps({'tags':sorted(tags),'series':series,'warnings':warnings,'sampled':True},allow_nan=True))
