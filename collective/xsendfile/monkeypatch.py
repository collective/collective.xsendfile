# -*- coding: utf-8 -*-
"""

    Monkey-patch ZODB to support blob storage FS permissios
    which allows reading them by Apache.
    http://stackoverflow.com/questions/6168566/collective-xsendfile-zodb-blobs-and-unix-file-permissions/6169177#6169177

"""
from ZODB import utils
from ZODB import blob
from ZODB.blob import LAYOUT_MARKER
from ZODB.blob import log

import logging
import os
import stat

logger = logging.getLogger(__name__)


def FilesystemHelper_create(self):
    if not os.path.exists(self.base_dir):
        os.makedirs(self.base_dir, 0o750)
        log('Blob directory \'%s\' does not exist. '
            'Created new directory.' % self.base_dir)
    if not os.path.exists(self.temp_dir):
        os.makedirs(self.temp_dir, 0o750)
        log('Blob temporary directory \'%s\' does not exist. '
            'Created new directory.' % self.temp_dir)

    layout_marker_path = os.path.join(self.base_dir, LAYOUT_MARKER)
    if not os.path.exists(layout_marker_path):
        with open(layout_marker_path, 'w') as layout_marker:
            layout_marker.write(self.layout_name)
    else:
        with open(layout_marker_path, 'r') as layout_marker:
            layout = layout_marker.read().strip()
        if layout != self.layout_name:
            raise ValueError(
                "Directory layout `%s` selected for blob directory %s, but "
                "marker found for layout `%s`" %
                (self.layout_name, self.base_dir, layout))

def FilesystemHelper_isSecure(self, path):
    """Ensure that (POSIX) path mode bits are 0750."""
    return (os.stat(path).st_mode & 0o27) == 0

def FilesystemHelper_getPathForOID(self, oid, create=False):
    """Given an OID, return the path on the filesystem where
    the blob data relating to that OID is stored.

    If the create flag is given, the path is also created if it didn't
    exist already.

    """
    # OIDs are numbers and sometimes passed around as integers. For our
    # computations we rely on the 64-bit packed string representation.
    if isinstance(oid, int):
        oid = utils.p64(oid)

    path = self.layout.oid_to_path(oid)
    path = os.path.join(self.base_dir, path)

    if create and not os.path.exists(path):
        try:
            os.makedirs(path, 0o750)
        except OSError:
            # We might have lost a race.  If so, the directory
            # must exist now
            logger.exception('Error creating blob directory.')
            assert os.path.exists(path)
    return path


def rename_or_copy_blob(f1, f2, chmod=True):
    """Try to rename f1 to f2, fallback to copy.

    Under certain conditions a rename might not work, e.g. because the target
    directory is on a different partition. In this case we try to copy the
    data and remove the old file afterwards.

    """
    try:
        os.rename(f1, f2)
    except OSError:
        logger.debug("Copied blob file %r to %r.", f1, f2)
        file1 = open(f1, 'rb')
        file2 = open(f2, 'wb')
        try:
            utils.cp(file1, file2)
        finally:
            file1.close()
            file2.close()
        blob.remove_committed(f1)

    os.chmod(f2, stat.S_IREAD | stat.S_IRGRP)


blob.rename_or_copy_blob = rename_or_copy_blob
