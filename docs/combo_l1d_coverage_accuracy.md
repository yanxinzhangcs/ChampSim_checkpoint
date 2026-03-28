# Combo Result L1D Coverage and Accuracy

This document summarizes the `rl_results_final/*_combo` result set.

Important note: the `_combo` directories only keep summary JSON files, not per-step stats.
To recover `L1D coverage` and `L1D accuracy`, this report uses:

- policy selection and IPC from `rl_results_final/<trace>_combo/experiment_summary.json`
- matching per-step baseline stats from `rl_results_hash/<trace>/baseline/<policy>/iter_XXXX_stats.json`

Metric definition matches `rl_controller/state.py`:

- `L1D coverage = useful_prefetch / total_L1D_misses`
- `L1D accuracy = useful_prefetch / L1D_prefetch_issued`
- `total_L1D_misses` sums `LOAD`, `WRITE`, `TRANSLATION`, `PREFETCH`, and `RFO` misses
- Baseline values are averages over the 100 `iter_XXXX_stats.json` windows for each fixed policy
- `best_policy` is the fixed-policy winner recorded in each combo summary

Full per-trace, per-baseline data is stored in:

- `docs/combo_l1d_coverage_accuracy_all_baselines.csv`
- `docs/combo_l1d_coverage_accuracy_best.csv`

Total traces: 49
Total fixed baseline rows: 392
Unique fixed policies: 8

## Best Fixed Policy Per Combo Trace

| Combo Trace | Source Trace | Best Policy | Best IPC | Avg L1D Coverage | Avg L1D Accuracy |
| --- | --- | --- | ---: | ---: | ---: |
| 400.perlbench-41B_combo | 400.perlbench-41B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 48.185944034216 | 0.037145078106 | 0.279052696212 |
| 401.bzip2-226B_combo | 401.bzip2-226B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 195.834081981755 | 0.088126617485 | 0.559966785243 |
| 403.gcc-16B_combo | 403.gcc-16B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 74.345444451500 | 0.000079603973 | 0.109586292160 |
| 410.bwaves-1963B_combo | 410.bwaves-1963B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 179.667966821269 | 0.446232127369 | 0.125038569902 |
| 416.gamess-875B_combo | 416.gamess-875B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 96.981744912087 | 0.000114754098 | 0.000747330961 |
| 429.mcf-184B_combo | 429.mcf-184B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 5.694427926014 | 0.000000000000 | 0.000000000000 |
| 433.milc-127B_combo | 433.milc-127B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 35.222416333469 | 0.113870624728 | 0.708575407290 |
| 434.zeusmp-10B_combo | 434.zeusmp-10B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 90.744427114703 | 0.043597721252 | 0.019658068856 |
| 435.gromacs-111B_combo | 435.gromacs-111B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 64.394665038308 | 0.005427321093 | 0.018171361645 |
| 436.cactusADM-1804B_combo | 436.cactusADM-1804B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 122.953826083615 | 0.006632875376 | 0.003518568593 |
| 437.leslie3d-134B_combo | 437.leslie3d-134B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 116.214915446474 | 0.055401419969 | 0.036996576213 |
| 444.namd-120B_combo | 444.namd-120B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 168.802830476447 | 0.139253179843 | 0.589817213748 |
| 445.gobmk-17B_combo | 445.gobmk-17B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 62.579808170640 | 0.020977241782 | 0.346019395265 |
| 447.dealII-3B_combo | 447.dealII-3B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 125.853008359161 | 0.523827889968 | 0.666586449710 |
| 450.soplex-247B_combo | 450.soplex-247B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 65.632342284345 | 0.088122237295 | 0.059020580826 |
| 453.povray-252B_combo | 453.povray-252B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 55.385773008864 | 0.042061735739 | 0.149086798010 |
| 454.calculix-104B_combo | 454.calculix-104B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 284.632339199876 | 0.003299585581 | 0.004627526357 |
| 456.hmmer-191B_combo | 456.hmmer-191B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 175.822077057009 | 0.023656590851 | 0.014517099695 |
| 458.sjeng-1088B_combo | 458.sjeng-1088B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 74.001533197869 | 0.000000000000 | 0.000000000000 |
| 459.GemsFDTD-1169B_combo | 459.GemsFDTD-1169B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 131.503715141816 | 0.178736764464 | 0.706808450729 |
| 462.libquantum-1343B_combo | 462.libquantum-1343B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 145.254257217651 | 0.516415182907 | 0.737233775095 |
| 464.h264ref-30B_combo | 464.h264ref-30B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 186.449519597359 | 0.031497177263 | 0.318568481579 |
| 465.tonto-1914B_combo | 465.tonto-1914B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 92.530264579541 | 0.041493475612 | 0.020222550460 |
| 470.lbm-1274B_combo | 470.lbm-1274B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 146.784818252642 | 0.000297472486 | 0.476488095238 |
| 471.omnetpp-188B_combo | 471.omnetpp-188B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 18.249970812029 | 0.029201732491 | 0.238847320515 |
| 473.astar-153B_combo | 473.astar-153B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 64.311269897633 | 0.039371462861 | 0.023942939766 |
| 481.wrf-1170B_combo | 481.wrf-1170B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 95.269461049072 | 0.003861627885 | 0.007935364358 |
| 482.sphinx3-1100B_combo | 482.sphinx3-1100B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 115.606053364101 | 0.173101265801 | 0.057827577908 |
| 483.xalancbmk-127B_combo | 483.xalancbmk-127B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 21.040720911522 | 0.046266035842 | 0.373140327380 |
| 600.perlbench_s-1273B_combo | 600.perlbench_s-1273B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 179.095748601719 | 0.003887948259 | 0.003240793810 |
| 602.gcc_s-1850B_combo | 602.gcc_s-1850B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 92.809362922404 | 0.484117035504 | 0.727675855276 |
| 603.bwaves_s-1080B_combo | 603.bwaves_s-1080B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 192.159536813493 | 0.030137509284 | 0.560557736450 |
| 605.mcf_s-1152B_combo | 605.mcf_s-1152B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-PACIPV` | 14.610483307668 | 0.113420624474 | 0.066513227427 |
| 607.cactuBSSN_s-2421B_combo | 607.cactuBSSN_s-2421B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-PACIPV` | 104.362170348775 | 0.000000000000 | 0.000000000000 |
| 619.lbm_s-2676B_combo | 619.lbm_s-2676B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 100.440726802137 | 0.000774982322 | 0.442939636738 |
| 620.omnetpp_s-141B_combo | 620.omnetpp_s-141B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 13.591166520065 | 0.012804536020 | 0.143315568660 |
| 621.wrf_s-575B_combo | 621.wrf_s-575B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 121.552146553168 | 0.000000000000 | 0.000000000000 |
| 623.xalancbmk_s-10B_combo | 623.xalancbmk_s-10B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 17.254896891956 | 0.032637344495 | 0.242298242849 |
| 625.x264_s-12B_combo | 625.x264_s-12B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 203.962731863519 | 0.015309005601 | 0.008451124421 |
| 627.cam4_s-490B_combo | 627.cam4_s-490B | `l1d_prefetcher-gaze_l1i_prefetcher-entangling_l2c_replacement-PACIPV` | 138.834744339835 | 0.241430995829 | 0.650149024943 |
| 628.pop2_s-17B_combo | 628.pop2_s-17B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 78.815781947095 | 0.097117746100 | 0.083105363183 |
| 631.deepsjeng_s-928B_combo | 631.deepsjeng_s-928B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 76.220393759437 | 0.009187467682 | 0.236758914675 |
| 638.imagick_s-10316B_combo | 638.imagick_s-10316B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 123.871755482797 | 0.142415252142 | 0.042351951444 |
| 641.leela_s-1052B_combo | 641.leela_s-1052B | `l1d_prefetcher-berti_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 72.067291322430 | 0.020497686086 | 0.015102654406 |
| 644.nab_s-12459B_combo | 644.nab_s-12459B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 130.122949821905 | 0.026232804836 | 0.021302311146 |
| 648.exchange2_s-1227B_combo | 648.exchange2_s-1227B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-mockingjay` | 204.537088936095 | 0.067795673861 | 0.709155397061 |
| 649.fotonik3d_s-10881B_combo | 649.fotonik3d_s-10881B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 61.020619858822 | 0.033840242819 | 0.026807943919 |
| 654.roms_s-1007B_combo | 654.roms_s-1007B | `l1d_prefetcher-berti_l1i_prefetcher-entangling_l2c_replacement-mockingjay` | 115.492851697743 | 0.062860599740 | 0.014811530448 |
| 657.xz_s-2302B_combo | 657.xz_s-2302B | `l1d_prefetcher-gaze_l1i_prefetcher-barca_l2c_replacement-PACIPV` | 32.159762439998 | 0.010007327456 | 0.279594110086 |
