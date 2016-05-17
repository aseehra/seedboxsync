#!/usr/bin/python2

# organizefiles.py
# Part of SeedboxSync

# Copyright (c) 2016, Arun Seehra
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. All advertising materials mentioning features or use of this software must
#    display the following acknowledgement:
#    This product includes software developed by Arun Seehra.
# 4. Neither the name of Arun Seehra nor the names of its contributors may be
#    used to endorse or promote products derived from this software without
#    specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY Arun Seehra ''AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL Arun Seehra BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import re
import sys

matcher = re.compile('(.*)(s\d+e\d+|\d+x\d+)')
library_path = '/media/video/tv'

def process_add_file(filename):
    base = os.path.basename(filename)
    match = matcher.search(base.lower())
    if match:
        series = match.group(1).replace('.', ' ').strip()
        series_path = os.path.join(library_path, series)
        if not os.path.exists(series_path):
            os.mkdir(series_path)
        link_path = os.path.join(series_path, base)
        if not os.path.exists(link_path):
            os.link(filename, os.path.join(series_path, base))

def process_delete_file(filename):
    base = os.path.basename(filename)
    match = matcher.search(base.lower())
    if match:
        series = match.group(1).replace('.', ' ').strip()
        series_path = os.path.join(library_path, series)
        link_path = os.path.join(series_path, base)
        if os.path.exists(series_path):
            if os.path.exists(link_path):
                os.remove(link_path)
            if len(os.listdir(series_path)) == 0:
                os.rmdir(series_path)

def add_directory(path):
    if not os.path.isdir(path):
        return

    for name in os.listdir(path):
        fullname = os.path.join(path, name)
        if os.path.isfile(fullname):
            process_add_file(fullname)

def sync(dirs):
    for directory in dirs:
        add_directory(directory)
    for dirpath, dirnames, filenames in os.walk(library_path):
        for filename in filenames:
            found = False
            for directory in dirs:
                if os.path.exists(os.path.join(directory, filename)):
                    found = True
            if not found:
                os.remove(os.path.join(dirpath, filename))

if __name__ == '__main__':
    sync(['/media/video/expanded', '/media/video/seedbox'])
