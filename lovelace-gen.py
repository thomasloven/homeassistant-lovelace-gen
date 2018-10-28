#!/usr/bin/env python3

# The MIT License (MIT)

# Copyright (c) 2018 Thomas Lovén

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Generate ui-lovelace.yaml from lovelace/main.yaml
"""

import sys
import os
import yaml
import shutil
import time
import jinja2
import requests
import json

indir = "lovelace"
infile = "main.yaml"
secretsfile = "secrets.yaml"

outfile = "ui-lovelace.yaml"

wwwdir = "www"
resourcedir = "lovelace"
timestamp = time.time();
states = {}

helpstring = """
usage: lovelace-gen.py
    Generates ui-lovelace.yaml from lovelace/main.yaml

Special commands:
  !include <filename>
    Is replaced by the contents of the file lovelace/<filename>
  !secret <identifier>
    Is replaced by the value from secrets.yaml for <identifier>.
  !resource [<path>/]<filename>
    Copies the file lovelace/<path><filename> to www/lovelace/<filename> and is replaced with /local/lovelace/<filename>
"""

def include_statement(loader, node):
    global indir, states
    filename = loader.construct_scalar(node)
    with open("{}/{}".format(indir, filename), 'r') as fp:
        data = fp.read()
    template = jinja2.Template(data)
    retval = yaml.load(template.render(states=states))
    return retval
yaml.add_constructor('!include', include_statement)

def secret_statement(loader, node):
    with open(secretsfile, 'r') as fp:
        data = fp.read()
    data = yaml.load(data)
    if not node.value in data:
        raise yaml.scanner.ScannerError('Could not find secret {}'. format(node.value))
    return data[node.value]
yaml.add_constructor('!secret', secret_statement)

def resource_statement(loader, node):
    global indir, wwwdir, resourcedir, timestamp
    version = ''
    path = os.path.join(indir, loader.construct_scalar(node))
    if '?' in path:
        version = '&'+path.split('?')[1]
        path = path.split('?')[0]
    if not os.path.exists(path):
        raise yaml.scanner.ScannerError('Could not find resource file {}'. format(path))
    basename = os.path.basename(path)
    newpath = os.path.join(wwwdir, resourcedir, basename)
    includepath = os.path.join('/local/', resourcedir, basename)

    os.makedirs(os.path.join(wwwdir, resourcedir), exist_ok=True)
    shutil.copyfile(path, newpath)
    return includepath + '?' + str(timestamp) + version

yaml.add_constructor('!resource', resource_statement)

def get_states(base_url, password=""):
    global states
    headers = {}
    if password:
        headers['x-ha-access'] = password
    r = requests.get(base_url+"/api/states", headers=headers)
    if r.status_code != 200:
        print("Could not fetch states", file=sys.stderr);
        return
    states = {}
    for s in r.json():
        domain = s['entity_id'].split('.')[0]
        entity = s['entity_id'].split('.')[1]
        if not domain in states:
            states[domain] = {}
        states[domain][entity] = s


def main(argv):
    global infile, outfile, indir, states

    if len(argv) > 1:
        if len(argv) > 3:
            print(helpstring)
            sys.exit(1)
        base_url = argv[1]
        password = argv[2] if len(argv) > 2 else ""
        get_states(base_url, password)

    infile = "{}/{}".format(indir, infile)

    if not os.path.isdir(indir):
        print("Directory {} not found.".format(indir), file=sys.stderr)
        print("Run `{} help` for help.".format(argv[0]), file=sys.stderr)
        sys.exit(2)
    if not os.path.exists(infile):
        print("File {} does not exist.".format(infile), file=sys.stderr)
        print("Run `{} help` for help.".format(argv[0]), file=sys.stderr)
        sys.exit(2)


    try:
        with open(infile, 'r') as fp:
            data = fp.read()
        template = jinja2.Template(data)
        data = yaml.load(template.render(states=states))
    except Exception as e:
        print("Something went wrong.", file=sys.stderr)
        print(e, file=sys.stderr)
        print("Run `{} help` for help.".format(argv[0]), file=sys.stderr)
        sys.exit(3)

    try:
        with open(outfile, 'w') as fp:
            fp.write("""
# This file is automatically generated by lovelace-gen.py
# https://github.com/thomasloven/homeassistant-lovelace-gen
# Any changes made to it will be overwritten the next time the script is run.

""")
            fp.write(yaml.dump(data, allow_unicode=True))
    except:
        print("Could not write to output file.", file=sys.stderr)
        print("Run {} -h for help.".format(argv[0]), file=sys.stderr)
        sys.exit(4)


if __name__ == '__main__':
    main(sys.argv)
