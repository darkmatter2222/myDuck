# 100 ideas for myDuck Studio

Status is explicit: **Implemented** means present in this release, not GPU-validated; **Planned** is unimplemented product work; **Research** needs experiments before adoption. These are 100 concrete ideas, not a claim that 100 features have shipped.

## Workspace foundations

| # | Idea | Status |
|---|---|---|
| 1 | One-command Linux web startup without frontend installation | Implemented |
| 2 | WSL-hosted app controlled from the Windows browser | Implemented |
| 3 | Server access through SSH port forwarding | Implemented |
| 4 | Consistent dark interface | Implemented |
| 5 | Responsive layouts for narrow displays | Implemented |
| 6 | Host/platform identity in the dashboard | Implemented |
| 7 | Separate queued, starting, running, paused and failed states | Implemented |
| 8 | Visible recognized simulator process inventory | Implemented |
| 9 | HTTP-readiness checks for viewer and TensorBoard | Implemented |
| 10 | No-checkpoint empty state that prevents viewer launch | Implemented |

## Experiment control

| # | Idea | Status |
|---|---|---|
| 11 | Persistent FIFO job queue | Implemented |
| 12 | Finite update/block budgets | Implemented |
| 13 | Repeat a configured pipeline until stopped | Implemented |
| 14 | Chain multiple training stages | Implemented |
| 15 | Start a new branch from a selected checkpoint | Implemented |
| 16 | Clone a previous experiment configuration | Implemented |
| 17 | Immutable configuration and provenance snapshots | Implemented |
| 18 | Explicit experiment seed control | Implemented |
| 19 | Named reusable training presets | Implemented |
| 20 | Reconnect to recognized workers after web-server restart | Implemented |

## Model management

| # | Idea | Status |
|---|---|---|
| 21 | Parent/descendant checkpoint tree grouped by runs | Implemented |
| 22 | Index existing local training runs | Implemented |
| 23 | Retain history when weight files are deleted | Implemented |
| 24 | Pin important checkpoints against deletion | Implemented |
| 25 | Organize checkpoints in logical collections | Implemented |
| 26 | Give checkpoints readable labels | Implemented |
| 27 | Search by run, label and collection | Implemented |
| 28 | Select multiple checkpoints | Implemented |
| 29 | Preview deletion paths and byte totals | Implemented |
| 30 | Protect active/queued job dependencies from deletion | Implemented |

## Training configuration

| # | Idea | Status |
|---|---|---|
| 31 | Configure environment count for different GPUs | Implemented |
| 32 | Configure checkpoint save frequency | Implemented |
| 33 | Override PPO learning rate per stage | Implemented |
| 34 | Override PPO entropy coefficient per stage | Implemented |
| 35 | Override the supported reward weights per stage | Implemented |
| 36 | Override forward/lateral/yaw command ranges | Implemented |
| 37 | Configure evaluation worlds, seeds and episode duration | Implemented |
| 38 | Configure learning-stall pause limit, including explicit disable | Implemented |
| 39 | Run a short GPU training/evaluation preflight | Implemented |
| 40 | Preserve checkpoints and back off on recognized memory failures | Implemented |

## Inspection and comparison

| # | Idea | Status |
|---|---|---|
| 41 | Overlay sampled training curves for selected runs | Implemented |
| 42 | Compare curves by elapsed time or saved step | Implemented |
| 43 | Select available TensorBoard metric tags | Implemented |
| 44 | Compare fixed-command evaluation outcomes | Implemented |
| 45 | Inspect parameter configurations alongside outcomes | Implemented |
| 46 | Download a training evidence bundle | Implemented |
| 47 | Include raw TensorBoard events in evidence exports | Implemented |
| 48 | Export unsampled scalar CSV when TensorBoard is installed | Implemented |
| 49 | Inspect/download job logs and configuration JSON | Implemented |
| 50 | Export a selected checkpoint to ONNX as a separate job | Implemented |

## Operations

| # | Idea | Status |
|---|---|---|
| 51 | Install and verify simulation dependencies from the app | Implemented |
| 52 | Show current GPU utilization | Implemented |
| 53 | Show used and total GPU memory | Implemented |
| 54 | Show GPU temperature | Implemented |
| 55 | Show free disk space | Implemented |
| 56 | Provide official simulator/runtime resource links | Implemented |
| 57 | Stop recognized viewer/TensorBoard services | Implemented |
| 58 | Reset only the bounded runtime directory | Implemented |
| 59 | Persist an operation audit trail | Implemented |
| 60 | Reject unsupported configuration keys and unsafe model paths | Implemented |

## Better experiments

| # | Idea | Status |
|---|---|---|
| 61 | Parameter grid sweeps with a total GPU-hour budget | Planned |
| 62 | Bayesian hyperparameter optimization with held-out validation | Planned |
| 63 | Paired multi-seed comparisons with confidence intervals | Planned |
| 64 | Automatically detect reward-scale changes in chart overlays | Planned |
| 65 | A/B comparison reports with effect-size estimates | Planned |
| 66 | Reorder queued jobs through drag and drop | Planned |
| 67 | Duplicate a pipeline across multiple seeds in one action | Planned |
| 68 | Time-based budgets in addition to update-based budgets | Planned |
| 69 | Structured optimizer KL/entropy health alerts | Planned |
| 70 | Automated plateau diagnosis that explains its evidence | Planned |

## Learning research

| # | Idea | Status |
|---|---|---|
| 71 | Validate a compatible vendor policy as a dynamics control | Research |
| 72 | Capture a scripted alternating gait as demonstration data | Research |
| 73 | Reference-motion imitation combined with task reward | Research |
| 74 | Teacher-policy distillation into the deployable actor | Research |
| 75 | A staged stand-to-walk curriculum driven by evaluation | Research |
| 76 | Progressive command-range expansion with regression checks | Research |
| 77 | Gradual domain-randomization ramps | Research |
| 78 | Learn fall recovery as a separate task | Research |
| 79 | Train a high-level router across separately validated skills | Research |
| 80 | Compare symmetric and asymmetric gait priors | Research |

## Physical and numerical validation

| # | Idea | Status |
|---|---|---|
| 81 | Per-foot contact timing and stride symmetry reports | Research |
| 82 | Foot-slip analysis tied to forward displacement | Research |
| 83 | Actuator torque/speed saturation diagnostics | Research |
| 84 | Automatic joint-limit violation reports | Research |
| 85 | Body-height and tilt distributions across held-out rollouts | Research |
| 86 | Contact geometry and mass/inertia consistency checks | Research |
| 87 | Calibration against measured servo response | Research |
| 88 | Long-duration holdouts to detect slow divergence | Research |
| 89 | Terrain and perturbation robustness test suites | Research |
| 90 | A distinct hardware-readiness checklist with measured evidence | Research |

## Scale and polish

| # | Idea | Status |
|---|---|---|
| 91 | Recorded rollout clips associated with each checkpoint | Planned |
| 92 | Side-by-side synchronized simulation playback | Planned |
| 93 | Interactive node-and-edge lineage canvas | Planned |
| 94 | Portable experiment packages with selected weight files | Planned |
| 95 | Verified restore/import with artifact checksums | Planned |
| 96 | Remote worker agents managed by one studio | Planned |
| 97 | Multi-GPU scheduling with exclusive device leases | Planned |
| 98 | Authenticated multi-user hosting with scoped access | Planned |
| 99 | Automatic HTML experiment reports for sharing | Planned |
| 100 | Distill complementary policies instead of arbitrary weight merging | Planned |

## Research starting points

- XGO-Duck robot-specific simulator and export workflow: https://github.com/LuwuDynamics/xgoduck_rl
- Robot runtime and deployed-policy context: https://github.com/LuwuDynamics/xgoduck_runtime_arduino
- DeepMimic explores combining motion imitation with task objectives: https://arxiv.org/abs/1804.02717

MicroDuck and XGO-Duck differ in geometry/inertia. A reference policy must match the robot and observation/action conventions before it is useful as a teacher. DeepMimic is methodological evidence, not a ready-made XGO-Duck solution. Arbitrary model-weight merging does not establish combined skills.
