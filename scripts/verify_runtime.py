#!/usr/bin/env python3
print('[VERIFY 1/4] Importing PyTorch...',flush=True)
import torch
print(f'[VERIFY 2/4] torch={torch.__version__}, CUDA runtime={torch.version.cuda}',flush=True)
assert torch.cuda.is_available(),'Torch CUDA unavailable. Check Windows NVIDIA driver and WSL GPU access.'
print('[VERIFY 3/4] Running GPU matrix multiply on '+torch.cuda.get_device_name(0),flush=True)
x=torch.ones((64,64),device='cuda')
print('CUDA result:',(x@x).sum().item(),flush=True)
print('[VERIFY 4/4] Importing simulator and registering XGO-Duck task...',flush=True)
import mjlab.tasks
from mjlab.tasks.registry import list_tasks
assert 'Mjlab-Velocity-Flat-XgoDuck' in list_tasks(),'XGO-Duck task not registered'
print('[VERIFY] GPU and task registry passed.',flush=True)
