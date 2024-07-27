# -*- coding: utf-8 -*-
# vim:fileencoding=utf-8

# chkren r3, rewritten in python

import re
import os.path

# since i don't wanna depend on the big pywin32 package ...
from ctypes import windll, create_unicode_buffer, byref, c_int, POINTER
from ctypes.wintypes import *

MAX_PATH_LEN = 32768
FILE_ATTRIBUTE_DIRECTORY = 0x10

FindFirstFile = windll.kernel32.FindFirstFileW
FindFirstFile.argtypes = (LPCWSTR, POINTER(WIN32_FIND_DATAW))
FindFirstFile.restype = HANDLE

FindNextFile = windll.kernel32.FindNextFileW
FindNextFile.argtypes = (HANDLE, POINTER(WIN32_FIND_DATAW))
FindNextFile.restype = BOOL

FindClose = windll.kernel32.FindClose
FindClose.argtypes = (HANDLE,)
FindClose.restype = BOOL

MoveFile = windll.kernel32.MoveFileW
MoveFile.argtypes = (LPCWSTR, LPCWSTR)
MoveFile.restype = BOOL

WideCharToMultiByte = windll.kernel32.WideCharToMultiByte
WideCharToMultiByte.argtypes = (UINT, DWORD, LPCWSTR, INT, LPSTR, INT, LPCSTR, POINTER(BOOL))
WideCharToMultiByte.restype = INT
WC_NO_BEST_FIT_CHARS = 0x400

GetCurrentDirectory = windll.kernel32.GetCurrentDirectoryW
GetCurrentDirectory.argtypes = (DWORD, LPWSTR)
GetCurrentDirectory.restype = DWORD

# i have to use MessageBox since print will crash for non-ACP characters...
MessageBox = windll.user32.MessageBoxW
MessageBox.argtypes = (HWND, LPCWSTR, LPCWSTR, UINT)
MessageBox.restype = INT
MB_OK = 0
MB_OKCANCEL = 1
MB_YESNO = 4
MB_ICONQUESTION = 0x20
MB_ICONEXCLAMATION = 0x30
MB_ICONINFORMATION = 0x40
MB_SETFOREGROUD = 0x1000
ID_OK = 1
ID_CANCEL = 2
ID_YES = 6
ID_NO = 7

UTF8BOM = '\xef\xbb\xbf'

# unfortunately iconv cp932/cp936 is not fully compatible with windows code pages
def codec_test(u, cp):
    try:
        s = u.encode(cp)
        return True
    except:
        return False

def find_incompatible_chars(from_code = 'cp932', to_code = 'cp936'):
    all_uchars = map(unichr, range(1, 0x10000))
    f_chars = filter(lambda c:codec_test(c, from_code), all_uchars)
    t_chars = filter(lambda c:codec_test(c, to_code), all_uchars)
    incompatible_chars = filter(
        lambda c:codec_test(c, from_code) and not codec_test(c, to_code),
        all_uchars)
    print len(all_uchars), len(f_chars), len(t_chars), len(incompatible_chars)
    
# well, the win32 way
def codec_test_win32(u, cp):
    used_default_char = c_int()
    c = WideCharToMultiByte(cp, WC_NO_BEST_FIT_CHARS, u, len(u), None, 0, None, byref(used_default_char))
    # print c, used_default_char.value
    if used_default_char.value > 0:
        return False
    else:
        return True
        
def find_incompatible_chars_win32(from_code, to_code):
    all_uchars = map(unichr, range(1, 0x10000))
    # f_chars = filter(lambda c:codec_test_win32(c, from_code), all_uchars)
    # t_chars = filter(lambda c:codec_test_win32(c, to_code), all_uchars)
    incompatible_chars = filter(
        lambda c:codec_test_win32(c, from_code) and not codec_test_win32(c, to_code),
        all_uchars)
    # print len(all_uchars), len(f_chars), len(t_chars), len(incompatible_chars)
    # print u''.join(incompatible_chars)
    return incompatible_chars

def print_codepage(codepage, width = 0x10):
    all_uchars = map(unichr, range(1, 0x10000))
    chars = filter(lambda c:codec_test_win32(c, codepage), all_uchars)
    d = u''
    remain_chars = chars
    while len(remain_chars) > 0:
        d += u''.join(remain_chars[:width]) + '\n'
        remain_chars = remain_chars[width:]
    used_default_char = c_int()
    c = WideCharToMultiByte(codepage, 0, d, len(d), None, 0, None, byref(used_default_char))
    print len(all_uchars), len(chars), used_default_char.value
    return d

class chkren():
    cfg_re = re.compile(r'^(.*)\(0x([0-9A-F]{4})\)->(.*)$')
    
    def __init__(self, progdir, fcode, tcode, verbose = False):
        try:
            cfg = open(os.path.join(progdir, 'cp%d-cp%d.cfg' % (fcode, tcode)), 'r').read()
        except:
            MessageBox(0, u'error reading config file', u'Error', MB_ICONEXCLAMATION)
            return
        if cfg[:3] != UTF8BOM:
            MessageBox(0, u'config file must be utf-8 encoded', u'Error', MB_ICONEXCLAMATION)
            return
        self.incompatible_chars = find_incompatible_chars_win32(fcode, tcode)
        self.trans0 = {}
        self.trans1 = dict(zip(map(ord, self.incompatible_chars), [None] * len(self.incompatible_chars)))
        for l in map(lambda l:l.strip(), cfg[3:].decode('utf-8').split('\n')):
            m = self.cfg_re.match(l)
            if not m:
                continue
            chr0, ord0, str1 = m.group(1), int(m.group(2), 16), m.group(3)
            if ord(chr0) != ord0:
                MessageBox(
                    0,
                    u'invalid config line ignored: %s\n\nReason:\n\t%s = 0x%04X != 0x%04X' % (l, chr0, ord(chr0), ord0),
                    u'Warning',
                    MB_ICONEXCLAMATION
                )
                continue
            if not codec_test_win32(str1, tcode):
                MessageBox(
                    0,
                    u'invalid config line ignored: %s\n\nReason:\n\t%s absent in cp%d' %(l, str1, tcode),
                    u'Warning',
                    MB_ICONEXCLAMATION
                )
                continue
            if str1 == u'':
                continue
            self.trans0[ord0] = str1 or u' ' # default to space if empty
            try:
                del self.trans1[ord0]
            except:
                pass
        
        self.trans2 = dict(zip(self.trans1.keys(), [u' '] * len(self.trans1)))
        
        self.missing_chars = self.trans1.keys()
        self.missing_chars.sort()
        
        if not verbose:
            return
        
        MessageBox(0,
            u'chkren cp%d -> cp%d, %d incompatible characters\n\n'
            u'%d entries found in cfg\n%d characters not specified(some may not be display-able):\n%s\n' \
            u'they will be replaced by space' % (
                fcode,
                tcode,
                len(self.incompatible_chars),
                len(self.trans0),
                len(self.trans1),
                u''.join(map(unichr, self.missing_chars))
            ),
            u'chkren initialized successfully',
            MB_ICONEXCLAMATION
        )
    
    def trans(self, src):
        s0 = src.translate(self.trans0)
        return len(s0) - len(s0.translate(self.trans1)), s0.translate(self.trans2)
    
    def chkdir(self, path, recursive = False, rename_dirs_too = False, verbose = False):
        if path == None:
            p = create_unicode_buffer(MAX_PATH_LEN)
            GetCurrentDirectory(MAX_PATH_LEN, p)
            path = p.value
        wfd = WIN32_FIND_DATAW()
        hff = FindFirstFile(u'\\\\?\\' + path + u'\\*', byref(wfd))
        files = []
        dirs = []
        while(True):
            if wfd.cFileName not in (u'.', u'..'):
                if wfd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY:
                    dirs.append(wfd.cFileName)
                else:
                    files.append(wfd.cFileName)
            if not FindNextFile(hff, byref(wfd)):
                break
        if rename_dirs_too:
            files += dirs
        if len(files) > 0:
            spaces, new_names = zip(*map(self.trans, files))
            spaces_used = sum(spaces)
            pairs = filter(lambda p: p[0] != p[1], zip(files, new_names))
            if len(pairs) > 0:
                if verbose:
                    msg = u'rename %d file(s)/directorie(s)?\n\n%s' % (
                        len(pairs),
                        u'\n'.join(map(u' -> '.join, pairs))
                    )
                    if spaces_used > 0:
                        msg += u'\n\nCAUTION: %d character(s) is/are not specified in cfg file, use space instead' % spaces_used
                    ret = MessageBox(0, msg, u'rename?', MB_YESNO | MB_ICONQUESTION)
                else:
                    ret = ID_YES
                if ret == ID_YES:
                    map(lambda p:
                        MoveFile(
                            u'\\\\?\\' + path + u'\\' + p[0],
                            u'\\\\?\\' + path + u'\\' + p[1]
                        ), pairs)
        if len(dirs) > 0 and recursive:
            if rename_dirs_too:
                rename_dict = dict(pairs)
                dirs == map(lambda d:rename_dict.get(d) or d, dirs)
            for dir in dirs:
                self.chkdir(path + u'\\' + dir)
                
def chkren_main(*args):
    #default values
    action = 'chkren'
    fcode = 932 # shift-jis, actually, cp932 in windows
    tcode = 936 # gbk, actually, cp936 in windows
    recursive = False
    rename_dirs_too = False
    verbose = True
    path = None
    
    progdir = os.path.dirname(args[0])
    
    if len(args) >= 2 and args[1] in ('print-codepage', 'p',
                                      'find-incompatible-chars', 'f',
                                      'chkren', 'c',
                                      '--help', '-h'):
        action = args[1]
        i = 2
    else:
        i = 1
    while i < len(args):
        if args[i] in ('-f', '--from-codepage') and i + 1 < len(args):
            fcode = int(args[i + 1])
            i += 2
        elif args[i] in ('-t', '--to-codepage') and i + 1 < len(args):
            tcode = int(args[i + 1])
            i += 2
        elif args[i] in ('-r', '--recursive'):
            recursive = True
            i += 1
        elif args[i] in ('-d', '--rename-dirs-too'):
            rename_dirs_too = True
            i += 1
        elif args[i] in ('-q', '--quiet'):
            verbose = False
            i += 1
        else:
            path = os.path.abspath(args[i])
            i += 1
    
    if action in ('p', 'print-codepage'):
        d = print_codepage(tcode)
        f = open('cp%s.txt' % tcode, 'w')
        f.write(UTF8BOM)
        f.write(d.encode('utf-8'))
        f.close()
    elif action in ('f', 'find-incompatible-chars'):
        ret = find_incompatible_chars_win32(fcode, tcode)
        d = u'\n'.join(map(lambda c:u'%s(0x%04X)->' % (c, ord(c)), ret))
        f = open('cp%d-cp%d.log' % (fcode, tcode), 'w')
        f.write('\xef\xbb\xbf')
        f.write(d.encode('utf-8'))
        f.close()
    elif action in ('c', 'chkren'):
        cr = chkren(progdir, fcode, tcode, verbose = True)
        cr.chkdir(path, recursive, rename_dirs_too, verbose)
    else:
        print 'chkren - rename files from one code page to another.\n' \
            '\tdue to programmer`s stupidity, ' \
            'there are still so many programs that won`t support unicode, ' \
            'that`s why chkren is born.\n\n' \
            'Usage:\n' \
            '\t chkren.py [c|p|f] [-f fcode] [-t tcode] [-r] [-d] [-q] [path]\n\n' \
            'Options:\n' \
            '\tc, chkren\t\t\t(default)check and rename files\n' \
            '\tp, print-codepage\t\tprint all available characters in tcode\n' \
            '\tf, find-incompatible-chars\tfind all characters that present in fcode but absent in tcode\n' \
            '\t-f, --from-codepage\t\tspecify fcode\n' \
            '\t-t, --to-codepage\t\tspecify tcode\n' \
            '\t-r, --recursive\t\t\trecursively work on sub directories\n' \
            '\t-d, --rename-dirs-too\t\twork on directory names too\n' \
            '\t-q, --quiet\t\t\tdo not prompt for rename\n' \
            '\tpath\t\t\t\tuse current directory if omitted'
        return
    
if __name__ == '__main__':
    import sys
    chkren_main(*sys.argv)