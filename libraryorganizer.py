#!/usr/bin/python2

# library_organizer.py
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

import twisted
from twisted import logger
from twisted.application import service
from twisted.internet import inotify
from twisted.python import filepath
from zope.interface import provider

class LibraryOrganizerService(service.Service):

    log = logger.Logger('LibraryOrganizerService')
    default_matcher = re.compile('(.*)(s\d+e\d+|\d+x\d+)')
    shield_matcher = re.compile('(.*)(s.h.i.e.l.d.).*(s\d+e\d+|\d+x\d+)')

    def __init__(self, library_dir, watch_dirs):
        self.library_dir = library_dir
        self.watch_dirs = watch_dirs

    def startService(self):
        mask = inotify.IN_CREATE | inotify.IN_DELETE
        self.notifier = inotify.INotify()
        self.notifier.startReading()
        for directory in self.watch_dirs:
            self.notifier.watch(filepath.FilePath(directory),
                                mask=mask,
                                callbacks=[self.onChange])
        self.sync()

    def stopService(self):
        self.notifier.stopReading()

    def onChange(self, ignored, path, mask):
        self.log.debug('{path}: {mask}',
                       path=path.path,
                       mask=inotify.humanReadableMask(mask))

        if mask == inotify.IN_CREATE:
            self.processCreate(path)
        elif mask == inotify.IN_DELETE:
            self.processDelete(path)

    def getSeries(self, path):
        normalized_path= path.basename().lower()

        # special case: 's.h.i.e.l.d.'
        match = self.shield_matcher.search(normalized_path)
        if match:
            series_name = ' '.join([match.group(1).replace('.', ' ').strip(), 
                                    match.group(2)])
            return series_name

        match = self.default_matcher.search(normalized_path)
        if match:
            series_name = match.group(1).replace('.', ' ').strip()
            return series_name

        return None

    def processCreate(self, path):
        if not path.isfile():
            return
        self.log.debug('Processing {path}', path=path.path)
        series_name = self.getSeries(path)
        if not series_name:
            return

        series_path = os.path.join(self.library_dir, series_name)
        if not os.path.exists(series_path):
            self.log.debug('Create directory {path}', path=series_path)
            os.mkdir(series_path)
        episode_path = os.path.join(series_path, path.basename())
        if not os.path.exists(episode_path):
            self.log.debug('Linking {orig} : {link}', 
                           orig=path.path,
                           link=episode_path)
            os.link(path.path, episode_path)

    def processDelete(self, path):
        series_name = self.getSeries(path)
        if not series_name:
            return

        series_path = os.path.join(self.library_dir, series_name)
        episode_path = os.path.join(series_path, path.basename())
        if os.path.exists(series_path):
            if os.path.exists(episode_path):
                self.log.debug('Deleting {path}', path=episode_path)
                os.remove(episode_path)
            if len(os.listdir(series_path)) == 0:
                self.log.debug('Deleting {path}', path=series_path)
                os.rmdir(series_path)

    def sync(self):
        for directory in self.watch_dirs:
            for name in os.listdir(directory):
                self.processCreate(
                        filepath.FilePath(os.path.join(directory, name)))
        for dirpath, dirnames, filenames in os.walk(self.library_dir):
            for episode in filenames:
                found = False
                for directory in self.watch_dirs:
                    if os.path.exists(os.path.join(directory, episode)):
                        found = True
                if not found:
                    self.processDelete(
                        filepath.FilePath(os.path.join(dirpath, episode)))


consoleLogger = logger.FileLogObserver(
    sys.stdout, 
    lambda event: logger.formatEventAsClassicLogText(event))
observer = logger.FilteringLogObserver(
    consoleLogger,
    [logger.LogLevelFilterPredicate(defaultLogLevel=logger.LogLevel.debug)])

application = service.Application('libraryorganizer')
organizer_service = LibraryOrganizerService(
    '/media/video/tv',
    ['/media/video/seedbox', '/media/video/expanded'])
organizer_service.setServiceParent(application)
application.setComponent(twisted.python.log.ILogObserver, observer)
