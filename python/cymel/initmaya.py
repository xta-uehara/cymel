# -*- coding: utf-8 -*-
u"""
スタンドアロン python (mayapy) からの Maya の初期化。

cymel 内の Maya に依存するモジュールがインポートされる際に
`initialize` が呼び出されるため、
このモジュールを明示的に使用する必要はほとんどないが、
初期化プロセスをカスタマイズしたい場合などに利用できる。
"""
import sys
import os
import os.path as _os_path
import re
from .pyutils import (
    USER_DOC_PATH as _USER_DOC_PATH,
    insertEnvPath as _insertEnvPath,
    execfile as _execfile,
)

__all__ = [
    'MAYA_PRODUCT_VERSION',
    'MAYA_VERSION',
    'MAYA_VERSION_STR',
    'IS_UIMODE',
    'warning',

    'initialize',
    'initCymelPluginsPath',
    'isMayaInitialized',
    'initMaya',
    'callUserSetupMel',
]

_os_path_join = _os_path.join
#_os_path_split = _os_path.split
_os_path_isdir = _os_path.isdir
_os_path_isfile = _os_path.isfile
_os_path_normpath = _os_path.normpath
_os_path_dirname = _os_path.dirname


#------------------------------------------------------------------------------
def initialize():
    u"""
    必要な初期化を全て行う。

    以下が行われる。

    初期化済みなら何もされないので、
    繰り返し呼び出しても問題はない。

    - `initCymelPluginsPath`
    - `initMaya` and `callUserSetupMel`
    - `initApiImmutables`
    """
    global _NOT_INITIALIZED
    if _NOT_INITIALIZED:
        initCymelPluginsPath()
        initMaya() and callUserSetupMel()
        initApiImmutables()
        _NOT_INITIALIZED = False
_NOT_INITIALIZED = True


def initCymelPluginsPath():
    u"""
    cymel が同梱する Maya プラグインのパスを設定する。

    繰り返し呼び出しても重複して設定されることはない。
    """
    path = _os_path_join(_os_path_dirname(__file__), 'plugins')
    _insertEnvPath(path, 'MAYA_PLUG_IN_PATH', noCheck=True, noUpdate=True)


def isMayaInitialized():
    u"""
    Maya が初期化済みかどうか。

    :rtype: `bool`
    """
    try:
        import maya.cmds as cmds
        cmds.about
    except:
        return False
    return True


def initMaya():
    u"""
    Maya が未初期化なら初期化し True を返す。

    いずれにせよ、
    `MAYA_VERSION` などの cymel の定数は初期化される。

    初期化時に、パス上の全ての ``userSetup.py`` が呼び出されるが、
    ``userSetup.mel`` は呼び出されない。

    繰り返し呼び出しても問題はない。

    :rtype: `bool`
    """
    ret = not isMayaInitialized()
    if ret:
        _initMayaAppDir()
        _initMayaLocation()
        _initMayaStandalone()
    _initCymelConstants()
    return ret


def callUserSetupMel():
    u"""
    最優先の MEL パスに在る ``userSetup.mel`` を呼び出す。
    """
    from maya.mel import eval as mel_eval
    if mel_eval('exists userSetup'):
        mel_eval('source userSetup')
        print('# userSetup.mel is done.')


def initApiImmutables():
    u"""
    Maya API の数学クラスを `.immutable` ラップのための定義をする。
    """
    from .pyutils.immutable import OPTIONAL_MUTATOR_DICT
    import maya.api.OpenMaya as api2
    import maya.OpenMaya as api1

    def setApiNames(name, attrs, api1ignores=None):
        cls = getattr(api2, name)
        #for x in attrs:
        #    if not hasattr(cls, x):
        #        warning("API2 %s does not have '%s'" % (name, x))
        OPTIONAL_MUTATOR_DICT[cls] = attrs

        cls = getattr(api1, name)
        if api1ignores:
            attrs = [x for x in attrs if x not in api1ignores]
        #for x in attrs:
        #    if not hasattr(cls, x):
        #        warning("API1 %s does not have '%s'" % (name, x))
        OPTIONAL_MUTATOR_DICT[cls] = attrs

    setApiNames('MVector', (
        'normalize',
    ))
    setApiNames('MPoint', (
        'cartesianize',
        'rationalize',
        'homogenize',
    ))
    setApiNames('MEulerRotation', (
        'boundIt',
        'incrementalRotateBy',
        'invertIt',
        'reorderIt',
        'setToAlternateSolution',
        'setToClosestCut',
        'setToClosestSolution',
        'setValue',
    ))
    setApiNames('MQuaternion', (
        'conjugateIt',
        'invertIt',
        'negateIt',
        'normalizeIt',
        'setToXAxis',
        'setToYAxis',
        'setToZAxis',
        'setValue',
    ), ('setValue',))
    setApiNames('MMatrix', (
        'setElement',
        'setToIdentity',
        'setToProduct',
    ), ('setElement',))


#------------------------------------------------------------------------------
def _initMayaAppDir():
    u"""
    環境変数 MAYA_APP_DIR を設定する。
    """
    path = os.environ.get('MAYA_APP_DIR')
    if path:
        return path

    path = _os_path_join(_USER_DOC_PATH, 'maya')
    print('# Set MAYA_APP_DIR: ' + path)
    os.environ['MAYA_APP_DIR'] = path
    return path


def _initMayaLocation():
    u"""
    環境変数 MAYA_LOCATION を設定する。
    """
    # mayapy であれば MAYA_LOCATION は設定されている。
    path = os.environ.get('MAYA_LOCATION')
    if path and _os_path_isdir(_os_path_join(path, 'scripts/AETemplates')):
        # mayapy だけ抜き出した無効な環境でないかも調べている。
        return path

    # maya モジュールのパスは通っているものとして、そこから MAYA_LOCATION を推定。
    import maya
    path = _os_path_normpath(_os_path_join(_os_path_dirname(maya.__file__), '../../../..'))
    print('# Set MAYA_LOCATION: ' + path)
    os.environ['MAYA_LOCATION'] = path
    return path


def _initMayaStandalone():
    u"""
    Maya standalone を初期化する。
    """
    # 2020以前なら、この時点の sys.path に在る userSetup.py が先頭から順に _execfile される。
    print('# Initializing Maya...')
    import maya.standalone as _maya_standalone
    _maya_standalone.initialize(name='cymel')

    # Python終了時の uninitialize の呼び出しを設定。
    uninitialize = getattr(_maya_standalone, 'uninitialize', None)
    if uninitialize:
        def _uninitialize():
            try:
                uninitialize()
            except:
                pass
        import atexit
        atexit.register(_uninitialize)

    # 2021以降の場合は userSetup.py を呼び出す。
    try:
        import maya.cmds as cmds
        v = int(cmds.about(mjv=True))
    except:
        pass
    else:
        if v >= 2021:
            _call_userSetup_pys()

    print('# OK, done.')


def _call_userSetup_pys():
    u"""
    userSetup.py を全てコールする。
    """
    for path in list(sys.path):
        file = _os_path_join(path, 'userSetup.py')
        if _os_path_isfile(file):
            try:
                _execfile(file)
            except:
                pass


def _initCymelConstants():
    u"""
    Mayaの状態を表す cymel の定数を初期化する。
    """
    global MAYA_PRODUCT_VERSION, MAYA_VERSION, MAYA_VERSION_STR, IS_UIMODE, warning

    import maya.cmds as cmds

    _about = cmds.about

    MAYA_PRODUCT_VERSION = re.search(r'.+/(\d+(?:\.\d+)?)', str(cmds.internalVar(upd=True))).group(1)
    try:
        # 2019.1 以降で利用できるオプション。
        v = (int(_about(mjv=True)), int(_about(mnv=True)), int(_about(pv=True)))
    except:
        v = float(MAYA_PRODUCT_VERSION)
        if v >= 2018.:
            # 2018nnpp: 2018.n.p
            v = _about(api=True)
            v = (v / 10000, (v - v / 10000 * 10000) / 100, v - v / 100 * 100)
        elif v == 2017.:
            # 2017xx: 2017.?
            v = _about(api=True) - 201700
            if v < 1:
                # 201700: 2017
                v = (2017, 0, 0)
            elif v < 20:
                # 201701: 2017update1
                v = (2017, 1, v - 1)
            else:
                # 201720: 2017update2
                # 201740: 2017update3
                # 201760: 2017update4
                # 201780: 2017update5
                v -= 20
                x = v / 20
                v = (2017, x + 2, v - x * 20)
                del x
        else:
            v = tuple([int(x) for x in MAYA_PRODUCT_VERSION.split('.')])
            v += (0,) * (3 - len(v))
    MAYA_VERSION = v  #: Mayaバージョンを表すタプル。アップデートを判別できるのは2017以降。 (majorVersion, minorVersion, patchVersion)
    v = 2
    while not MAYA_VERSION[v]:
        v -= 1
    MAYA_VERSION_STR = '.'.join([str(v) for v in MAYA_VERSION[:v + 1]]) #: Mayaバージョンの表記。
    del v

    IS_UIMODE = not _about(b=True)  #: MayaがUIモードかどうか。

    import maya.OpenMaya as _api1
    warning = _api1.MGlobal.displayWarning

MAYA_VERSION = None  #: Mayaバージョンを表すタプル。アップデートを判別できるのは2017以降。 (majorVersion, minorVersion, patchVersion)
MAYA_VERSION_STR = ''  #: Mayaバージョンの表記。
MAYA_PRODUCT_VERSION = None  #: 別々に存在できるMayaバージョン名（ '2020' や '2016.5' など）。
IS_UIMODE = False  #: MayaがUIモードかどうか。

if isMayaInitialized():
    _initCymelConstants()

