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

import twisted
from twisted import logger
from twisted.application import service
from twisted.internet import inotify
from twisted.python import filepath


class LibraryOrganizerService(service.Service):

    log = logger.Logger('LibraryOrganizerService')
    default_matcher = re.compile(r'(.*)\D(s\d+e\d+|\d+x\d+)')
    shield_matcher = re.compile(r'(.*)(s.h.i.e.l.d.)')
    date_matcher = re.compile(r'^(seth.meyers)')
    librarians_matcher = re.compile(r'^the.librarians')

    def __init__(self, library_dir, watch_dirs):
        self.library_dir = filepath.FilePath(library_dir)
        self.watch_dirs = [filepath.FilePath(directory) for directory in watch_dirs]
        self.notifier = inotify.INotify()
        self.tv_extensions = ['.mkv']

    def startService(self):  # noqa
        mask = inotify.IN_CREATE | inotify.IN_DELETE
        self.notifier.startReading()
        for directory in self.watch_dirs:
            self.notifier.watch(directory,
                                mask=mask,
                                callbacks=[self.handle_watchdir_change])
        self.sync()

    def stopService(self):  # noqa
        self.notifier.stopReading()

    def handle_watchdir_change(self, _, path, mask):
        self.log.debug('Top level {mask}: {path}',
                       path=path.path,
                       mask=inotify.humanReadableMask(mask))

        if mask & inotify.IN_CREATE:
            self.process_create(path)
        elif mask & inotify.IN_DELETE:
            self.process_delete(path, mask & inotify.IN_ISDIR)

    def get_series_name(self, path):
        normalized_path = path.basename().lower()

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

    def create_link(self, original_path, series_name, rename=None):
        series_dir = self.library_dir.child(series_name)
        if not series_dir.exists():
            self.log.debug('Creating directory {d}', d=series_dir.path)
            series_dir.createDirectory()

        if rename:
            ext = original_path.splitext()[1]
            destination_path = series_dir.child(rename).siblingExtension(ext)
        else:
            destination_path = series_dir.child(original_path.basename())

        if not destination_path.exists():
            self.log.debug('Linking {o} to {d}', o=original_path.path, d=destination_path.path)
            os.link(original_path.path, destination_path.path)

    def process_create(self, path):
        series_name = self.get_series_name(path)
        if not series_name:
            return

        if path.isdir():
            self.log.debug('Processing new subdirectory {p}', p=path.path)
            self.notifier.watch(path,
                                mask=inotify.IN_CREATE | inotify.IN_MOVED_TO,
                                callbacks=[self.handle_subdir_change])
            children = path.globChildren('*.mkv')
            if children:
                self.create_link(children[0], series_name, rename=path.basename())
                try:
                    self.notifier.ignore(path)
                except KeyError as err:
                    self.log.debug(str(err))
        else:
            self.create_link(path, series_name)

    def handle_subdir_change(self, _, path, mask):
        self.log.debug('Sub-directory {mask}: {p}',
                       mask=inotify.humanReadableMask(mask),
                       p=path.path)
        if not path.splitext()[1] in self.tv_extensions:
            return

        series_name = self.get_series_name(path)
        if not series_name:
            return

        self.create_link(path, series_name)
        try:
            self.notifier.ignore(path.parent())
        except KeyError as err:
            self.log.debug(str(err))

    def process_delete(self, path, is_dir):
        series_name = self.get_series_name(path)
        if not series_name:
            return

        series_dir = self.library_dir.child(series_name)
        episode_path = series_dir.child(path.basename())

        if is_dir:
            episode_path = episode_path.siblingExtension('.mkv')
            try:
                self.notifier.ignore(path)
            except KeyError as err:
                self.log.debug(str(err))

        self.log.debug('Deletion of {p} equates to {d}',
                       p=path.path,
                       d=episode_path.path)

        if episode_path.exists():
            self.log.debug('Deleting {path}', path=episode_path.path)
            episode_path.remove()

        # Delete the directory if it's empty
        if series_dir.exists() and not series_dir.listdir():
            self.log.debug('Deleting series directory for {series}', series=series_name)
            series_dir.remove()

    def sync(self):
        for series in self.library_dir.children():
            for episode in series.children():
                episode_base = episode.basename()
                episode_noext = os.path.splitext(episode_base)[0]
                found = False
                for watch_dir in self.watch_dirs:
                    if (watch_dir.child(episode_base).exists() or 
                            watch_dir.child(episode_noext).exists()):
                        found = True
                if not found:
                    self.process_delete(episode, episode.isdir())

        for watch_dir in self.watch_dirs:
            for source in watch_dir.children():
                self.process_create(source)

# pylint: disable=invalid-name
console_logger = logger.FileLogObserver(sys.stdout, logger.formatEventAsClassicLogText)
observer = logger.FilteringLogObserver(
    console_logger,
    [logger.LogLevelFilterPredicate(defaultLogLevel=logger.LogLevel.info)])

application = service.Application('libraryorganizer')
organizer_service = LibraryOrganizerService(
    '/data/media/tv-seedbox',
    ['/data/media/seedbox', '/data/media/expanded'])
organizer_service.setServiceParent(application)
application.setComponent(twisted.python.log.ILogObserver, observer)
