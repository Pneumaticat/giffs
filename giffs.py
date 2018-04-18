#!/usr/bin/env python3
# SPDX-License-Header: GPL-3.0+

import base64
import logging

from errno import EACCES
from os.path import realpath
from sys import argv, exit
from threading import Lock

import os
import argparse

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

# GIF file header
FILE_HEADER = base64.b64decode("R0lGODlhAQABAIAAAAUEBAAAACwAAAAAAQABAAACAkQBADs=")

class GIFFS(LoggingMixIn, Operations):
    def __init__(self, root):
        self.root = realpath(root)
        self.rwlock = Lock()

    def __call__(self, op, path, *args):
        return super(GIFFS, self).__call__(op, self.root + path, *args)

    def access(self, path, mode):
        if not os.access(path, mode):
            raise FuseOSError(EACCES)

    chmod = os.chmod
    chown = os.chown

    def create(self, path, mode):
        fh = os.open(path, os.O_RDWR | os.O_CREAT | os.O_TRUNC, mode)
        os.write(fh, FILE_HEADER)
        return fh
    
    def flush(self, path, fh):
        return os.fsync(fh)

    def fsync(self, path, datasync, fh):
        if datasync != 0:
          return os.fdatasync(fh)
        else:
          return os.fsync(fh)

    def getattr(self, path, fh=None):
        st = os.lstat(path)
        dictionary = dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
            'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
        if os.path.isfile(path):
            dictionary['st_size'] = dictionary['st_size'] - len(FILE_HEADER)
        return dictionary

    getxattr = None

    def link(self, target, source):
        return os.link(source, target)

    listxattr = None
    mkdir = os.mkdir
    mknod = os.mknod
    open = os.open

    def read(self, path, size, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset + len(FILE_HEADER), 0)
            return os.read(fh, size)

    def readdir(self, path, fh):
        return ['.', '..'] + os.listdir(path)

    readlink = os.readlink

    def release(self, path, fh):
        return os.close(fh)

    def rename(self, old, new):
        return os.rename(old, self.root + new)

    rmdir = os.rmdir

    def statfs(self, path):
        stv = os.statvfs(path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))
        

    def symlink(self, target, source):
        return os.symlink(source, target)

    def truncate(self, path, length, fh=None):
        with open(path, 'r+') as f:
            f.truncate(length + len(FILE_HEADER))

    unlink = os.unlink
    utimens = os.utime

    def write(self, path, data, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset + len(FILE_HEADER), 0)
            return os.write(fh, data)
        

class GIFFSReverse(LoggingMixIn, Operations):
    def __init__(self, root):
        self.root = realpath(root)
        self.rwlock = Lock()

    def __call__(self, op, path, *args):
        return super(GIFFSReverse, self).__call__(op, self.root + path, *args)

    def access(self, path, mode):
        if not os.access(path, mode):
            raise FuseOSError(EACCES)

    def getattr(self, path, fh=None):
        st = os.lstat(path)
        dictionary = dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
            'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
        if os.path.isfile(path):
            dictionary['st_size'] = dictionary['st_size'] + len(FILE_HEADER)
        return dictionary
    
    open = os.open

    def read(self, path, size, offset, fh):
        if offset < len(FILE_HEADER):
            data = FILE_HEADER[offset:offset + size]
            with self.rwlock:
                # now offset = size of bytes not taken from FILE_HEADER
                os.lseek(fh, 0, 0)
                data += os.read(fh, size - (len(FILE_HEADER) - offset))
                return data
        else:
            with self.rwlock:
                os.lseek(fh, offset - len(FILE_HEADER), 0)
                return os.read(fh, size)

    def readdir(self, path, fh):
        return ['.', '..'] + os.listdir(path)

    readlink = os.readlink

    def release(self, path, fh):
        return os.close(fh)
    
    def statfs(self, path):
        stv = os.statvfs(path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))
        
    utimens = os.utime


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("mountpoint")
    parser.add_argument("-o", "--options", help="options", type=str)
    args = parser.parse_args()

    options = [i for i in args.options.split(',')]

    if "reverse" in options:
        fuse = FUSE(GIFFSReverse(args.root), args.mountpoint, foreground=False, nothreads=True, allow_other=("allow_other" in options))
    else:
        fuse = FUSE(GIFFS(args.root), args.mountpoint, foreground=False, nothreads=True, allow_other=("allow_other" in options))
