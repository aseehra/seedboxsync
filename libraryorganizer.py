#!/usr/bin/python2

# library_organizer.py
# Part of SeedboxSync

# Copyright (c) 2016, Arun Seehra
# All rights reserved.

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
import time

import twisted
from twisted import logger
from twisted.application import service
from twisted.internet import inotify
from twisted.python import filepath
from zope.interface import provider

class LibraryOrganizerService(service.Service):

    log = logger.Logger('LibraryOrganizerService')
    default_matcher = re.compile('(.*)\D(s\d+e\d+|\d+x\d+)')
    shield_matcher = re.compile('(.*)(s.h.i.e.l.d.)')
    date_matcher = re.compile('^(seth.meyers)')
    librarians_matcher = re.compile('^the.librarians')

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

        if mask & inotify.IN_CREATE:
            self.processCreate(path)
        elif mask & inotify.IN_DELETE:
            self.processDelete(path, mask & inotify.IN_ISDIR)

    def getSeries(self, path):
        normalized_path= path.basename().lower()

        # special case: 's.h.i.e.l.d.'
        match = self.shield_matcher.search(normalized_path)
        if match:
            series_name = ' '.join([match.group(1).replace('.', ' ').strip(),
                                    match.group(2)])
            return series_name

        # special cases
        if normalized_path.startswith('timeless'):
            return 'timeless 2016'
        if self.librarians_matcher.search(normalized_path):
            return 'the librarians 2014'

        match = self.date_matcher.search(normalized_path)
        if not match:
            match = self.default_matcher.search(normalized_path)
        if match:
            series_name = match.group(1).replace('.', ' ').strip()
            return series_name

        return None

    def getChildMkv(self, path):
        counter = 0
        # XXX: This is really hacky. We are just trying to wait for the children
        # to be transferred
        while (not path.listdir())  and counter < 5:
            counter += 1
            time.sleep(1)
        children = path.globChildren('*.mkv')
        return children[0] if children else None

    def processCreate(self, path):
        series_name = self.getSeries(path)
        if not series_name:
            return
        self.log.debug('CREATE: {p}', p=path.path)

        series_dir = filepath.FilePath(self.library_dir).child(series_name)
        if not series_dir.exists():
            self.log.debug('Creating directory {d}', d=series_dir.path)
            series_dir.createDirectory()

        origin_path = path
        episode_path = series_dir.child(path.basename())

        if path.isdir():
            origin_path = self.getChildMkv(path)
            if not origin_path:
                return
            scene_name = path.siblingExtension('.mkv').basename()
            episode_path = series_dir.child(scene_name)

        if not episode_path.exists():
            self.log.debug('Linking {orig} : {link}',
                    orig=origin_path.path,
                    link=episode_path.path)
            os.link(origin_path.path, episode_path.path)

    def processDelete(self, path, is_dir):
        series_name = self.getSeries(path)
        if not series_name:
            return

        self.log.debug('DELETE: {path}', path=path.path)
        series_dir = filepath.FilePath(self.library_dir).child(series_name)
        episode_path = series_dir.child(path.basename())

        if is_dir:
            episode_path = episode_path.siblingExtension('.mkv')

        self.log.debug('Episode should be {path}', path=episode_path.path)

        if episode_path.exists():
            self.log.debug('Deleting {path}', path=episode_path.path)
            episode_path.remove()

        # Delete the directory if it's empty
        if not series_dir.listdir():
            self.log.debug('Removing series directory for {series}', series=series_name)
            series_dir.remove()

    def sceneDirectory(self, episode_path):
        return os.path.splitext(episode_path)[0]

    def sync(self):
        for dirpath, dirnames, filenames in os.walk(self.library_dir):
            for episode in filenames:
                found = False
                for directory in self.watch_dirs:
                    if os.path.exists(os.path.join(directory, episode)):
                        found = True
                    elif os.path.exists(os.path.join(directory, self.sceneDirectory(episode))):
                        found = True
                if not found:
                    self.log.debug('Could not find {episode}', episode=episode)
                    delete_path = filepath.FilePath(dirpath).child(episode)
                    self.processDelete(delete_path, delete_path.isdir())
        for directory in self.watch_dirs:
            for name in os.listdir(directory):
                self.processCreate(
                        filepath.FilePath(os.path.join(directory, name)))


consoleLogger = logger.FileLogObserver(
    sys.stdout,
    lambda event: logger.formatEventAsClassicLogText(event))
observer = logger.FilteringLogObserver(
    consoleLogger,
    [logger.LogLevelFilterPredicate(defaultLogLevel=logger.LogLevel.info)])

application = service.Application('libraryorganizer')
organizer_service = LibraryOrganizerService(
    '/data/media/tv-seedbox',
    ['/data/media/seedbox', '/data/media/expanded'])
organizer_service.setServiceParent(application)
application.setComponent(twisted.python.log.ILogObserver, observer)
