#!/usr/bin/env python

import json
import argparse

parser = argparse.ArgumentParser(description='Process appstore jl file')
parser.add_argument('input', help='the input file')
parser.add_argument('output', help='base name of the output files')

parser.add_argument('--all', help='save all files', action='store_true')
parser.add_argument('--json', help='save json file', action='store_true')
parser.add_argument('--all_ids', help='save all_ids file', action='store_true')
parser.add_argument('--popular_ids', help='save popular_ids file', action='store_true')
parser.add_argument('--sort', help='sort ids', action='store_true')

args = parser.parse_args()

if not (args.all or args.json or args.all_ids or args.popular_ids):
    parser.error('No file will be saved. Add at least one file type')

data = {}
all_popular_apps_ids = set()
all_apps_ids = set()

print('Reading input...')
with open(args.input) as f:
    for line in f:
        jl = json.loads(line)
        category_id = jl['category_id']

        if category_id not in data:
            data[category_id] = {}

        if 'apps' in jl:
            all_apps_ids.update(jl['apps'])
            if 'apps' not in data[category_id]:
                data[category_id]['apps'] = set()
            data[category_id]['apps'].update(jl['apps'])

        elif 'popular-apps' in jl:
            all_popular_apps_ids.update(jl['popular-apps'])
            data[category_id]['popular-apps'] = list(set(jl['popular-apps']))

            # add popular apps also to all apps
            all_apps_ids.update(jl['popular-apps'])
            if 'apps' not in data[category_id]:
                data[category_id]['apps'] = set()
            data[category_id]['apps'].update(jl['popular-apps'])
        else:
            print('Unknown data:', jl)

# convert set to list
for category_id in data:
    try:
        s = data[category_id]['apps']
        data[category_id]['apps'] = list(s)
    except KeyError:
        pass

if args.sort:
    print('Sort...')
    all_popular_apps_ids = sorted(all_popular_apps_ids)
    all_apps_ids = sorted(all_apps_ids)


print('Writing to files...')
if args.json or args.all:
    with open(args.output + '.json', 'w') as f:
        json.dump(data, f, indent=2)

if args.popular_ids or args.all:
    with open(args.output + '_popular_ids', 'w') as f:
        for app_id in all_popular_apps_ids:
            f.write(str(app_id) + '\n')

if args.all_ids or args.all:
    with open(args.output + '_all_ids', 'w') as f:
        for app_id in all_apps_ids:
            f.write(str(app_id) + '\n')
