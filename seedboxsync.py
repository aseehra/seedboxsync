#!/usr/bin/python2

# seedboxsync.py
# Part of SeedboxSync

# Copyright (c) 2013, Arun Seehra
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


from daemon.runner import DaemonRunner
import os
import errno
import stat
import atexit
import subprocess
import shlex

class SbsException(Exception):
    """ Base class for SeedboxSync exceptions. """
class SbsOSException(SbsException):
    """ Exception raised when OS environment setup receives error. """

class Syncer(object):
    def __init__(
        self,
        fifo_path=os.path.expanduser('~/.local/tmp/seedboxsync.fifo'),
        log_path=os.path.expanduser('~/.local/var/log/seedboxsync.log'),
        sync_settings=[{'local':'~/expanded','remote':'~/video/sb-expanded','opts':''},
                       {'local':'~/completed','remote':'~/video/sb','opts':'-I *.avi -I *.mp4'}
                       ],
        server='sftp://schrager.thirtyfivemm.com',
        ):

        # set up for DaemonRunner
        self.pidfile_path = os.path.expanduser(
                            '~/.local/var/run/seedboxsync.pid')
        self.pidfile_timeout = -1
        self.stdin_path = os.devnull
        self.stdout_path = os.devnull
        self.stderr_path = os.path.expanduser(
                           '~/.local/var/log/seedboxsync_err.log')

        self.log_path = log_path
        self.fifo_path = fifo_path
        self.sync_settings = sync_settings
        self.server = server

        # make necessary local directories
        if not os.path.isdir(os.path.dirname(self.pidfile_path)):
            os.makedirs(os.path.dirname(self.pidfile_path))
        if not os.path.isdir(os.path.dirname(self.log_path)):
            os.makedirs(os.path.dirname(self.log_path))
        if not os.path.isdir(os.path.dirname(self.fifo_path)):
            os.makedirs(os.path.dirname(self.fifo_path))

        try:
            mode = os.stat(self.fifo_path).st_mode
        except Exception, excp:
            if excp.errno == errno.ENOENT:
                self.make_fifo()
        else:
            if not stat.S_ISFIFO(mode):
                raise SbsOSException(
                      'Could not create IPC file (File exists)')

        atexit.register(self.close)

    def make_fifo(self):
        ''' Try to create a new FIFO '''
        try:
            os.mkfifo(self.fifo_path)
        except Exception, excp:
            raise SbsOSException(
                    'Unable to create IPC file ({:s}).'.format(excp))

    def close(self):
        ''' Clean up after ourselves '''
        try:
            os.remove(self.fifo_path)
        except Exception, excp:
            if excp.errno != errno.ENOENT:
                error = SbsOSException(
                        "Unable to delete IPC file ({:s}).".format(excp))
                raise error

    def run(self):
        while True:
            with open(self.fifo_path, 'r') as fifo:
                fifo.readlines()
                self.execute_sync()

    def execute_sync(self):
        for syncitem in self.sync_settings:
            cmd_base = '''lftp -c "open -e 'mirror -eR -P2 {opts} {local} {remote}' {server}"'''
            cmd_str = cmd_base.format(server=self.server, **syncitem)
            self.log(cmd_str + '\n')
            cmd = shlex.split(cmd_str)
            with open(self.log_path, 'a') as log:
                subprocess.Popen(cmd_str, stderr=subprocess.STDOUT, stdout=log)

    def log(self, msg):
        with open(self.log_path, 'a') as log:
            log.write(msg)

if __name__ == '__main__':
    syncer = Syncer()
    runner = DaemonRunner(syncer)
    runner.do_action()
