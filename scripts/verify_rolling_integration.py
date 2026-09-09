"""Qualify guarded rolling models on the unchanged legacy gates and fresh controls."""
import argparse
import json
import math
import random

from detection_quality_check import build_scenario, evaluate, production_quality_failures
from verify_harmonic_integration import holdout_failures
from app.canonical import build_raw_point, score_points
from app.models import RuleConfig


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-start',type=int,default=454011)
    args=parser.parse_args()
    failures=[]
    for algorithm in ('zscore','mad'):
        rule=RuleConfig(name='rolling',query='fixture',algorithm=algorithm,threshold=4,baseline_window=12)
        def predict(values):
            return {i for i,p in enumerate(score_points(rule,'fixture',{},
                    [build_raw_point(i*60.,v) for i,v in enumerate(values)])) if p.is_anomaly}
        results={}
        for scenario,values in [('clear',build_scenario(noise=.8,spike=20,shift=14)),('hard',build_scenario(noise=2.5,spike=12,shift=8))]:
            metrics=evaluate(algorithm,values)
            results[scenario]={algorithm:metrics}
            print(json.dumps(dict(algorithm=algorithm,scenario=scenario,**metrics)),flush=True)
            if metrics['warmup_breaches']:failures.append(f'{algorithm}/{scenario}: warmup')
            if metrics['points_per_second']<10000:failures.append(f'{algorithm}/{scenario}: throughput')
        failures.extend(production_quality_failures(results))
        # Nonseasonal models do not promise to learn repeating square/sawtooth
        # discontinuities. The four common controls and AR controls remain gated.
        print(json.dumps(dict(algorithm=algorithm,seed_start=args.seed_start)),flush=True)
        failures.extend(f'{algorithm}/{f}' for f in holdout_failures(args.seed_start,predict,False))
        for rho in (0.,.5,.9,.98):
            fp=hits=0
            for seed in range(args.seed_start+1000,args.seed_start+1005):
                rng=random.Random(seed);error=0;values=[]
                for i in range(1440):
                    error=rho*error+math.sqrt(1-rho*rho)*rng.gauss(0,.8)
                    values.append(100+error)
                fp+=len(predict(values)&set(range(400,1440)))
                for i,delta in ((600,20),(900,-20),(1200,20)):values[i]+=delta
                hits+=len(predict(values)&{600,900,1200})
            print(json.dumps(dict(algorithm=algorithm,rho=rho,normal_fp=fp,eligible=5200,spikes=hits,total_spikes=15)),flush=True)
            if fp/5200>.02 or hits/15<.9:failures.append(f'{algorithm}/AR{rho}: FP/recall')
    print(json.dumps(dict(passed=not failures,failures=failures)),flush=True)
    return bool(failures)


if __name__=='__main__':raise SystemExit(main())
