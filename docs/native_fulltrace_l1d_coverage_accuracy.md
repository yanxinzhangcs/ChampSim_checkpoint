# Native Full-Trace L1D Coverage and Accuracy

This document summarizes the `rl_results_native_no_ckpt_20M/*_combo/fulltrace` result set.

Metric definition matches `rl_controller/state.py`:

- `L1D coverage = useful_prefetch / total_L1D_misses`
- `L1D accuracy = useful_prefetch / L1D_prefetch_issued`
- `total_L1D_misses` sums `LOAD`, `WRITE`, `TRANSLATION`, `PREFETCH`, and `RFO` misses
- `total_ipc` and `best_policy` come from each trace's `fulltrace/experiment_summary.json`
- coverage/accuracy come from each baseline's `full_trace_stats.json`

Generated files:

- `docs/native_fulltrace_l1d_coverage_accuracy_all_baselines.csv`
- `docs/native_fulltrace_l1d_coverage_accuracy_best.csv`
- `docs/native_fulltrace_l1d_coverage_accuracy_policy_summary.csv`

Expected traces: 49
Completed traces analyzed: 49
Pending traces: 0
Total fixed baseline rows analyzed: 392
Unique fixed policies: 8

## Policy-Level Aggregate Summary

| Policy | Traces | Avg L1D Coverage | Median L1D Coverage | Avg L1D Accuracy | Median L1D Accuracy | Avg IPC | Best-Policy Wins |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 49 | 0.110589376674 | 0.061736979167 | 0.458691410462 | 0.543364871422 | 1.595775192529 | 8 |
| `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-PACIPV` | 49 | 0.110511250937 | 0.061757260176 | 0.458100649077 | 0.542897081464 | 1.594989359092 | 0 |
| `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 49 | 0.110252081523 | 0.061957388887 | 0.458347896587 | 0.543688459396 | 1.595348387654 | 5 |
| `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 49 | 0.110243886006 | 0.062073501746 | 0.458825381618 | 0.543315099860 | 1.596170013932 | 13 |
| `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 49 | 0.059611613547 | 0.031582484594 | 0.036843507942 | 0.024019340248 | 1.607131542782 | 6 |
| `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-PACIPV` | 49 | 0.059495453961 | 0.031635388740 | 0.037264420135 | 0.025545772517 | 1.606520653903 | 2 |
| `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 49 | 0.059411608255 | 0.029159397077 | 0.036673427451 | 0.025486268593 | 1.608160300810 | 11 |
| `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 49 | 0.059339033017 | 0.029095392639 | 0.037587243392 | 0.025545772517 | 1.607127795668 | 4 |

## Best Fixed Policy Per Completed Trace

| Trace | Source Trace | Best Policy | Best IPC | L1D Coverage | L1D Accuracy |
| --- | --- | --- | ---: | ---: | ---: |
| 400.perlbench-41B_combo | 400.perlbench-41B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 0.820476582801 | 0.053078556263 | 0.271093425867 |
| 401.bzip2-226B_combo | 401.bzip2-226B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 2.435168805293 | 0.023897968553 | 0.728793526684 |
| 403.gcc-16B_combo | 403.gcc-16B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 2.225923685987 | 0.000030015730 | 0.166432584270 |
| 410.bwaves-1963B_combo | 410.bwaves-1963B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 1.934469279374 | 0.486179793779 | 0.123971526337 |
| 416.gamess-875B_combo | 416.gamess-875B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 2.127041148568 | 0.030912609493 | 0.056211510858 |
| 429.mcf-184B_combo | 429.mcf-184B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 0.086422798957 | 0.000000000000 | 0.000000000000 |
| 433.milc-127B_combo | 433.milc-127B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 0.297443743695 | 0.120664460482 | 0.739178136844 |
| 434.zeusmp-10B_combo | 434.zeusmp-10B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 2.355259263970 | 0.044547270190 | 0.018523328959 |
| 435.gromacs-111B_combo | 435.gromacs-111B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 2.107495094806 | 0.014187539694 | 0.209810284573 |
| 436.cactusADM-1804B_combo | 436.cactusADM-1804B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 1.598197137917 | 0.077232433594 | 0.408682882926 |
| 437.leslie3d-134B_combo | 437.leslie3d-134B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 1.949383488101 | 0.082642690233 | 0.045374032789 |
| 444.namd-120B_combo | 444.namd-120B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 2.947101599834 | 0.060455420141 | 0.483884768967 |
| 445.gobmk-17B_combo | 445.gobmk-17B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 1.642271872470 | 0.029159397077 | 0.052505536386 |
| 447.dealII-3B_combo | 447.dealII-3B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 1.690842096684 | 0.415989800744 | 0.688938836671 |
| 450.soplex-247B_combo | 450.soplex-247B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 0.469403427908 | 0.079459235160 | 0.055944195204 |
| 453.povray-252B_combo | 453.povray-252B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 2.000850561404 | 0.000000000000 | 0.000000000000 |
| 454.calculix-104B_combo | 454.calculix-104B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 2.831617868695 | 0.031635388740 | 0.013053097345 |
| 456.hmmer-191B_combo | 456.hmmer-191B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 2.210134726484 | 0.016691629511 | 0.013507069724 |
| 458.sjeng-1088B_combo | 458.sjeng-1088B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 1.485647236332 | 0.000000000000 | 0.000000000000 |
| 459.GemsFDTD-1169B_combo | 459.GemsFDTD-1169B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 0.481387794521 | 0.207610937787 | 0.668530932953 |
| 462.libquantum-1343B_combo | 462.libquantum-1343B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 1.430812387373 | 0.557837876393 | 0.720919552339 |
| 464.h264ref-30B_combo | 464.h264ref-30B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-PACIPV` | 2.103626630731 | 0.049428019124 | 0.057492627271 |
| 465.tonto-1914B_combo | 465.tonto-1914B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 2.147837101623 | 0.123214679731 | 0.569760227226 |
| 470.lbm-1274B_combo | 470.lbm-1274B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 0.852353913487 | 0.016993372575 | 0.969466936572 |
| 471.omnetpp-188B_combo | 471.omnetpp-188B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 0.280613586832 | 0.002106796734 | 0.051173143753 |
| 473.astar-153B_combo | 473.astar-153B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 1.701595253979 | 0.048112786394 | 0.022507258776 |
| 481.wrf-1170B_combo | 481.wrf-1170B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 2.197127212658 | 0.192668954662 | 0.167711141060 |
| 482.sphinx3-1100B_combo | 482.sphinx3-1100B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 1.423986436815 | 0.154660924383 | 0.055461921549 |
| 483.xalancbmk-127B_combo | 483.xalancbmk-127B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 0.271045122596 | 0.062073501746 | 0.383305469822 |
| 600.perlbench_s-1273B_combo | 600.perlbench_s-1273B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 2.383814001519 | 0.037563451777 | 0.072691552063 |
| 602.gcc_s-1850B_combo | 602.gcc_s-1850B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 1.305028849616 | 0.467501726996 | 0.714448393287 |
| 603.bwaves_s-1080B_combo | 603.bwaves_s-1080B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 2.450920620931 | 0.012933415384 | 0.734056502563 |
| 605.mcf_s-1152B_combo | 605.mcf_s-1152B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 0.383434384590 | 0.141555197640 | 0.716566844005 |
| 607.cactuBSSN_s-2421B_combo | 607.cactuBSSN_s-2421B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 1.958788947574 | 0.095013062039 | 0.450318348447 |
| 619.lbm_s-2676B_combo | 619.lbm_s-2676B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 0.550661712217 | 0.009967872499 | 0.586379928315 |
| 620.omnetpp_s-141B_combo | 620.omnetpp_s-141B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 0.267345224356 | 0.000091323979 | 0.060048038431 |
| 621.wrf_s-575B_combo | 621.wrf_s-575B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 1.379078797521 | 0.067010309278 | 0.330788804071 |
| 623.xalancbmk_s-10B_combo | 623.xalancbmk_s-10B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 0.245563294823 | 0.007991976062 | 0.070104001175 |
| 625.x264_s-12B_combo | 625.x264_s-12B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 3.216831974276 | 0.030779252111 | 0.009076318478 |
| 627.cam4_s-490B_combo | 627.cam4_s-490B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 1.936519909119 | 0.200695272855 | 0.704541954221 |
| 628.pop2_s-17B_combo | 628.pop2_s-17B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 2.338607789574 | 0.131005586103 | 0.080066055258 |
| 631.deepsjeng_s-928B_combo | 631.deepsjeng_s-928B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 1.517810443082 | 0.000000000000 | 0.000000000000 |
| 638.imagick_s-10316B_combo | 638.imagick_s-10316B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 3.587561602908 | 0.387815588032 | 0.056636914583 |
| 641.leela_s-1052B_combo | 641.leela_s-1052B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 1.731980114447 | 0.122964618866 | 0.544848670131 |
| 644.nab_s-12459B_combo | 644.nab_s-12459B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 2.626078136325 | 0.073258848597 | 0.640448457881 |
| 648.exchange2_s-1227B_combo | 648.exchange2_s-1227B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 2.922734738321 | 0.000000000000 | 0.000000000000 |
| 649.fotonik3d_s-10881B_combo | 649.fotonik3d_s-10881B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 0.632749527099 | 0.315919225122 | 0.637786201152 |
| 654.roms_s-1007B_combo | 654.roms_s-1007B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 1.220425640507 | 0.093632236330 | 0.008416991286 |
| 657.xz_s-2302B_combo | 657.xz_s-2302B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-PACIPV` | 0.931505483958 | 0.006495541438 | 0.010034391052 |

## Notes

- This report only includes traces with a complete `fulltrace/experiment_summary.json` and all baseline stats present locally.
- All 49 traces are complete in the local result set used for this report.
