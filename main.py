#!/usr/bin/env python3
"""
OrientationFieldCollectorV2 - compact prototype
Features: CSV<->JSON converter, validator, merger, diagnostics, examples, tests.
No external dependencies.
"""
import sys, json, csv, math, argparse, datetime, statistics
from collections import defaultdict

# --- JSON schema (informative) ---
JSON_SCHEMA = {
    "dataset": {
        "metadata": {
            "experiment": "string",
            "frame": "string",
            "quaternion_convention": "qx,qy,qz,qw (unit)",
            "generated_by": "string"
        },
        "modules": [
            {
                "module_id": "string",
                "records": [
                    {"timestamp": "ISO8601 UTC string", "position": [0.0,0.0,0.0], "quaternion": [0.0,0.0,0.0,1.0], "confidence": 1.0}
                ]
            }
        ]
    }
}

# --- Utilities ---
def parse_iso(ts):
    try:
        if ts.endswith('Z'):
            ts = ts[:-1]
        return datetime.datetime.fromisoformat(ts)
    except Exception:
        raise ValueError('Bad timestamp: %s' % ts)

def iso_now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

def read_csv(path):
    rows = []
    with open(path, newline='') as f:
        rd = csv.DictReader(f)
        for r in rd:
            rows.append(r)
    return rows

def write_csv(path, rows, fieldnames):
    with open(path, 'w', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        for r in rows:
            wr.writerow(r)

# --- Converter CSV -> JSON ---
def csv_to_json(path):
    rows = read_csv(path)
    modules = defaultdict(list)
    for r in rows:
        ts = r.get('timestamp')
        mid = r.get('module_id','unknown')
        pos = [float(r.get('x') or 0), float(r.get('y') or 0), float(r.get('z') or 0)]
        q = [float(r.get('qx') or 0), float(r.get('qy') or 0), float(r.get('qz') or 0), float(r.get('qw') or 1)]
        conf = float(r.get('confidence') or 1.0)
        modules[mid].append({'timestamp': ts, 'position': pos, 'quaternion': q, 'confidence': conf})
    out = {'dataset': {'metadata': {'generated_by': 'OrientationFieldCollectorV2', 'generated_at': iso_now()}, 'modules': []}}
    for mid, recs in modules.items():
        out['dataset']['modules'].append({'module_id': mid, 'records': sorted(recs, key=lambda x: x['timestamp'])})
    return out

# --- JSON -> CSV ---
def json_to_csv(path):
    j = json.load(open(path))
    rows = []
    for m in j.get('dataset',{}).get('modules',[]):
        mid = m.get('module_id')
        for r in m.get('records',[]):
            row = {'timestamp': r['timestamp'], 'module_id': mid, 'x': r['position'][0], 'y': r['position'][1], 'z': r['position'][2], 'qx': r['quaternion'][0], 'qy': r['quaternion'][1], 'qz': r['quaternion'][2], 'qw': r['quaternion'][3], 'confidence': r.get('confidence',1.0)}
            rows.append(row)
    fieldnames = ['timestamp','module_id','x','y','z','qx','qy','qz','qw','confidence']
    return rows, fieldnames

# --- Validator ---
def validate_json(path):
    j = json.load(open(path))
    problems = []
    if 'dataset' not in j:
        problems.append('Missing top-level dataset')
        return problems
    for m in j['dataset'].get('modules',[]):
        if 'module_id' not in m:
            problems.append('Module missing id')
        for r in m.get('records',[]):
            try:
                parse_iso(r['timestamp'])
            except Exception as e:
                problems.append('Bad timestamp %r: %s' % (r.get('timestamp'), e))
            if len(r.get('position',[]))!=3:
                problems.append('Position not length 3 for %s' % m.get('module_id'))
            q = r.get('quaternion',[])
            if len(q)!=4:
                problems.append('Quaternion not length 4 for %s' % m.get('module_id'))
            else:
                norm = math.sqrt(sum([float(x)**2 for x in q]))
                if abs(norm-1.0)>0.1:
                    problems.append('Quaternion magnitude off (%.3f) for %s' % (norm, m.get('module_id')))
    return problems

# --- Merge (time-align) ---
def merge_csvs(paths, tol_ms=50):
    # Read all CSVs into module series
    series = {}
    for p in paths:
        rows = read_csv(p)
        mid = None
        recs = []
        for r in rows:
            mid = r.get('module_id')
            recs.append({'t': parse_iso(r['timestamp']), 'pos':[float(r.get('x') or 0), float(r.get('y') or 0), float(r.get('z') or 0)], 'quat':[float(r.get('qx') or 0), float(r.get('qy') or 0), float(r.get('qz') or 0), float(r.get('qw') or 1)]})
        if mid is None:
            mid = p
        series[mid] = sorted(recs, key=lambda x: x['t'])
    # Build merged timeline by union of timestamps
    all_times = sorted({rec['t'] for recs in series.values() for rec in recs})
    tol = datetime.timedelta(milliseconds=tol_ms)
    merged = []
    for t in all_times:
        row = {'timestamp': t.isoformat()+'Z'}
        for mid, recs in series.items():
            # find nearest within tol
            best = None
            best_dt = None
            for r in recs:
                dt = abs(r['t'] - t)
                if best is None or dt < best_dt:
                    best = r; best_dt = dt
            if best is not None and best_dt <= tol:
                row[f'{mid}_x'], row[f'{mid}_y'], row[f'{mid}_z'] = best['pos']
                q = best['quat']; row[f'{mid}_qx'], row[f'{mid}_qy'], row[f'{mid}_qz'], row[f'{mid}_qw'] = q
            else:
                row[f'{mid}_x'] = row[f'{mid}_y'] = row[f'{mid}_z'] = ''
                row[f'{mid}_qx'] = row[f'{mid}_qy'] = row[f'{mid}_qz'] = row[f'{mid}_qw'] = ''
        merged.append(row)
    return merged

# --- Diagnostics ---
def diagnostics_from_json(path):
    j = json.load(open(path))
    stats = {}
    for m in j['dataset'].get('modules',[]):
        mid = m['module_id']
        recs = m.get('records',[])
        times = [parse_iso(r['timestamp']) for r in recs]
        if len(times)<2:
            stats[mid] = {'n':len(times)}
            continue
        dtsecs = [(t2-t1).total_seconds() for t1,t2 in zip(times, times[1:])]
        pos = [r['position'] for r in recs]
        vel = []
        for (p1,p2,dt) in zip(pos, pos[1:], dtsecs):
            if dt==0: vel.append(0.0); continue
            dist = math.sqrt(sum((p2[i]-p1[i])**2 for i in range(3)))
            vel.append(dist/dt)
        stats[mid] = {'n':len(times), 'median_dt': statistics.median(dtsecs), 'median_speed': statistics.median(vel) if vel else 0.0}
    return stats

# --- Synthetic example generator ---
EX_CSV = 'examples/synthetic.csv'
EX_MOD1 = 'examples/mod1.csv'
EX_MOD2 = 'examples/mod2.csv'

def write_examples():
    import os
    os.makedirs('examples', exist_ok=True)
    # synthetic single-file with two modules interleaved
    fieldnames = ['timestamp','module_id','x','y','z','qx','qy','qz','qw','confidence']
    start = datetime.datetime.utcnow()
    rows = []
    for i in range(10):
        t = (start + datetime.timedelta(milliseconds=100*i)).isoformat()+'Z'
        rows.append({'timestamp':t,'module_id':'A','x':i*0.01,'y':0,'z':0,'qx':0,'qy':0,'qz':0,'qw':1,'confidence':1})
        # module B lags slightly
        t2 = (start + datetime.timedelta(milliseconds=100*i+30)).isoformat()+'Z'
        rows.append({'timestamp':t2,'module_id':'B','x':0,'y':i*0.02,'z':0,'qx':0,'qy':0,'qz':0,'qw':1,'confidence':1})
    write_csv(EX_CSV, rows, fieldnames)
    # per-module files
    write_csv(EX_MOD1, [r for r in rows if r['module_id']=='A'], fieldnames)
    write_csv(EX_MOD2, [r for r in rows if r['module_id']=='B'], fieldnames)

# --- Simple tests ---
def run_tests():
    write_examples()
    j = csv_to_json(EX_CSV)
    assert 'dataset' in j
    # write temp json
    open('examples/tmp.json','w').write(json.dumps(j))
    probs = validate_json('examples/tmp.json')
    assert isinstance(probs, list)
    merged = merge_csvs([EX_MOD1, EX_MOD2], tol_ms=50)
    assert len(merged)>0
    stats = diagnostics_from_json('examples/tmp.json')
    assert 'A' in stats and 'B' in stats
    print('All tests passed')

# --- CLI ---
def main(argv):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd')
    sp = sub.add_parser('convert')
    sp.add_argument('--in', dest='infile', required=True)
    sp.add_argument('--out', dest='outfile', required=True)
    spv = sub.add_parser('validate'); spv.add_argument('--in', dest='infile', required=True)
    spm = sub.add_parser('merge'); spm.add_argument('--in', dest='infiles', nargs='+', required=True); spm.add_argument('--out', dest='outfile', required=True); spm.add_argument('--tol', type=int, default=50)
    spd = sub.add_parser('diagnostics'); spd.add_argument('--in', dest='infile', required=True)
    spt = sub.add_parser('test')
    spc = sub.add_parser('csv2json'); spc.add_argument('--in', dest='infile', required=True)
    args = p.parse_args(argv)
    if args.cmd in ('convert','csv2json'):
        j = csv_to_json(args.infile)
        open(args.outfile,'w').write(json.dumps(j, indent=2))
        print('Wrote', args.outfile)
    elif args.cmd=='validate':
        probs = validate_json(args.infile)
        if probs:
            print('Problems:');
            for x in probs: print(' -', x)
            sys.exit(2)
        else:
            print('OK')
    elif args.cmd=='merge':
        merged = merge_csvs(args.infiles, tol_ms=args.tol)
        if merged:
            f = args.outfile
            fn = sorted(merged[0].keys())
            write_csv(f, merged, fn)
            print('Merged to', f)
    elif args.cmd=='diagnostics':
        stats = diagnostics_from_json(args.infile)
        print(json.dumps(stats, indent=2))
    elif args.cmd=='test':
        run_tests()
    else:
        p.print_help()

if __name__=='__main__':
    main(sys.argv[1:])
