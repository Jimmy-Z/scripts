#!/usr/bin/python
# vim: set fileencoding=utf-8 :

from os import listdir, rename
from os.path import join
from sys import argv

# according to http://support.microsoft.com/kb/177506
not_allowed = ur'\/:*?"<>|'
translate = dict(zip([ord(c) for c in not_allowed], ur'＼／：＊？＂＜＞｜'))

path = argv[1].decode('utf-8')

for filename in listdir(path):
	need_rename = False
	for c in filename:
		if c in not_allowed:
			print u'character \'%s\' is not allowed in "%s"\n' % (c, filename),
			need_rename = True
	if need_rename:
		to_filename = filename.translate(translate)
		print u'will rename "%s" to "%s"\n' % (filename, to_filename),
		rename(join(path, filename), join(path, to_filename))

