#!/usr/bin/python3

import sys
import io
from socket import socket, AF_INET, SOCK_DGRAM
from struct import pack, unpack
from rsclib.autosuper import autosuper
from afu.adif import ADIF
from afu.dxcc import DXCC_File
from argparse import ArgumentParser

class Protocol_Element :
    """ A single protocol element to be parsed from binary format or
        serialized to binary format.
    """

    def __init__ (self, value) :
        self.value = value
    # end def __init__

    @classmethod
    def deserialize (cls, bytes, length = 0) :
        raise NotImplementedError ("Needs to be define in sub-class")
    # end def deserialize

    def serialize (self) :
        raise NotImplementedError ("Needs to be define in sub-class")
    # end def serialize

    @property
    def serialization_size (self) :
        raise NotImplementedError ("Needs to be define in sub-class")
    # end def serialization_size

# end class Protocol_Element

class UTF8_String (Protocol_Element) :
    """ An UTF-8 string consisting of a length and the string
        Special case is a null string (different from an empty string)
        which encodes the length as 0xffffffff
    >>> v = UTF8_String.deserialize (b'\\x00\\x00\\x00\\x04abcd')
    >>> v.value
    'abcd'
    >>> v.serialize ()
    b'\\x00\\x00\\x00\\x04abcd'
    >>> s = UTF8_String (None)
    >>> s.serialize ()
    b'\\xff\\xff\\xff\\xff'
    """

    @classmethod
    def deserialize (cls, bytes, length = 0) :
        offset = 4
        length = unpack ('!L', bytes [:offset]) [0]
        # Special case empty (None?) string
        if length == 0xFFFFFFFF :
            value = None
            return cls (value)
        value  = unpack ('%ds' % length, bytes [offset:offset+length]) [0]
        return cls (value.decode ('utf-8'))
    # end def deserialize

    def serialize (self) :
        if self.value is None :
            return pack ('!L', 0xFFFFFFFF)
        length = len (self.value)
        value  = self.value.encode ('utf-8')
        return pack ('!L', length) + pack ('%ds' % length, value)
    # end def serialize

    @property
    def serialization_size (self) :
        if self.value is None :
            return 4
        return 4 + len (self.value.encode ('utf-8'))
    # end def serialization_size

# end class UTF8_String

class Optional_Quint (Protocol_Element) :
    """ A quint which is optional, length in deserialize is used
        We encode a missing value as None
    """

    formats = dict \
        (( (1, '!B')
        ,  (4, '!L')
        ,  (8, '!Q')
        ))

    @classmethod
    def deserialize (cls, bytes, length = 1) :
        if len (bytes) == 0 :
            value = None
        else :
            value = unpack (self.formats [length], bytes) [0]
        object = cls (value)
        object.size = length
        if value is None :
            object.size = 0
        return object
    # end def deserialize

    def serialize (self) :
        if self.value is None :
            return b''
        return pack (self.formats [self.size], self.value)
    # end def serialize

    @property
    def serialization_size (self) :
        if self.value is None :
            return 0
        return self.size
    # end def serialization_size

# end class Optional_Quint

class QDateTime (Protocol_Element) :
    """ A QT DateTime object
        The case with a timezone is not used
    """

    def __init__ (self, date, time, timespec, offset = None) :
        self.date     = date
        self.time     = time
        self.timespec = timespec
        self.offset   = offset
        assert self.offset is None or self.timespec == 2
        if self.timespec == 2 and self.offset is not None :
            raise ValueError ("Offset required when timespec=2")
    # end def __init__

    @classmethod
    def deserialize (cls, bytes, length = 0) :
        date, time, timespec = unpack ('!qLB', bytes [:13])
        offset = None
        if timespec == 2 :
            offset = unpack ('!l', bytes [13:17]) [0]
        return cls (date, time, timespec, offset)
    # end def deserialize

    def serialize (self) :
        r = [pack ('!qLB', self.date, self.time, self.timespec)]
        if self.offset is not None :
            r.append (pack ('!l', self.offset))
        return b''.join (r)
    # end def serialize

    @property
    def serialization_size (self) :
        if self.offset is None :
            return 13
        return 13 + 4
    # end def serialization_size

    @property
    def value (self) :
        return self
    # end def value

    def __str__ (self) :
        s = ( 'QDatTime(date=%(date)s time=%(time)s '
            + 'timespec=%(timespec)s offset=%(offset)s)'
            )
        return s % self.__dict__
    # end def __str__
    __repr__ = __str__

# end class QDateTime

class QColor (Protocol_Element) :
    """ A QT color object
        We support only RGB type or invalid
    """

    fmt          = '!BHHHHH'
    spec_rgb     = 1
    spec_invalid = 0
    cmax         = 0xFFFF
    serialization_size = 11

    def __init__ \
        (self, red = 0, green = 0, blue = 0, alpha = cmax, spec = spec_rgb) :
        self.spec     = spec
        self.red      = red
        self.green    = green
        self.blue     = blue
        self.alpha    = alpha
    # end def __init__

    @classmethod
    def deserialize (cls, bytes, length = 0) :
        b = bytes [:cls.serialization_size]
        s, a, r, g, b, dummy = unpack (cls.fmt, b)
        return cls (spec = s, alpha = a, red = r, green = g, blue = b)
    # end def deserialize

    def serialize (self) :
        return pack \
            ( self.fmt
            , self.spec
            , self.alpha
            , self.red
            , self.green
            , self.blue
            , 0
            )
    # end def serialize

    @property
    def value (self) :
        return self
    # end def value

    def __str__ (self) :
        if self.spec != self.spec_rgb :
            return 'QColor(Invalid)'
        s = ( 'QColor(alpha=%(alpha)s, red=%(red)s, '
            + 'green=%(green)s, blue=%(blue)s)'
            )
        return s % self.__dict__
    # end def __str__
    __repr__ = __str__

# end class QColor
color_red   = QColor (red = QColor.cmax)
color_green = QColor (green = QColor.cmax)
color_blue  = QColor (blue = QColor.cmax)
color_white = QColor (QColor.cmax, QColor.cmax, QColor.cmax)
color_black = QColor ()
color_cyan  = QColor (0, 0xFFFF, 0xFFFF)
color_cyan1 = QColor (0x9999, 0xFFFF, 0xFFFF)
color_pink  = QColor (0xFFFF, 0, 0xFFFF)
color_pink1 = QColor (0xFFFF, 0xAAAA, 0xFFFF)

color_invalid = QColor (spec = QColor.spec_invalid)

# Shortcuts for used data types, also for consistency
quint8     = ('!B', 1)
quint32    = ('!L', 4)
quint64    = ('!Q', 8)
qint32     = ('!l', 4)
qbool      = quint8
qutf8      = (UTF8_String, 0)
qdouble    = ('!d', 8)
opt_quint8 = (Optional_Quint, 1)
qtime      = quint32
qdatetime  = (QDateTime, 0)
qcolor     = (QColor, 0)

statusmsg = b'\xad\xbc\xcb\xda\x00\x00\x00\x02\x00\x00\x00\x01\x00\x00\x00\x14WSJT-X - TS590S-klbg\x00\x00\x00\x00\x00k\xf0\xd0\x00\x00\x00\x03FT8\x00\x00\x00\x06XAMPLE\x00\x00\x00\x02-2\x00\x00\x00\x03FT8\x00\x00\x01\x00\x00\x02\xcb\x00\x00\x04n\x00\x00\x00\x06OE3RSU\x00\x00\x00\x06JN88DG\x00\x00\x00\x04JO21\x00\xff\xff\xff\xff\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\x00\x00\x00\x0bTS590S-klbg\x00\x00\x00%XAMPLE OE3RSU 73                     '
clearmsg = b'\xad\xbc\xcb\xda\x00\x00\x00\x03\x00\x00\x00\x03\x00\x00\x00\x14WSJT-X - TS590S-klbg'

class WSJTX_Telegram (autosuper) :
    """ Base class of WSJTX Telegram
        Note that we a list of (name, format, len) tuples as the format
        specification. The name is the name of the variable, the format
        is either a struct.pack compatible format specifier or an
        instance of Protocol_Element which knows how to deserialize (or
        serialize) itself. The len is the length to parse from the
        string. If 0 the Protocol_Element will know its serialization
        size.
    >>> WSJTX_Telegram.from_bytes (statusmsg)
    Status dial_frq=7074000 mode=FT8 dx_call=XAMPLE report=-2 tx_mode=FT8 tx_enabled=0 xmitting=0 decoding=1 rx_df=715 tx_df=1134 de_call=OE3RSU de_grid=JN88DG dx_grid=JO21 tx_watchdog=0 sub_mode=None fast_mode=0 special_op=0 frq_tolerance=4294967295 t_r_period=4294967295 config_name=TS590S-klbg tx_message=XAMPLE OE3RSU 73
    >>> WSJTX_Telegram.from_bytes (clearmsg)
    Clear window=None
    """

    schema_version_number = 3
    magic  = 0xadbccbda
    type   = None
    format = \
        [ ('magic',          quint32)
        , ('version_number', quint32)
        , ('type',           quint32)
        , ('id',             qutf8)
        ]
    defaults = dict (magic = magic, version_number = 3, id = 'wsjt-server')
    suppress = dict.fromkeys (('magic', 'version_number', 'id', 'type'))

    # Individual telegrams register here:
    type_registry = {}

    def __init__ (self, **kw) :
        params = {}
        params.update (self.defaults)
        params.update (kw)
        if 'type' not in params :
            params ['type'] = self.type
        assert params ['magic'] == self.magic
        assert self.schema_version_number >= params ['version_number']
        # Thats for sub-classes, they have their own format
        for name, (a, b) in self.format :
            setattr (self, name, params [name])
        if self.__class__.type is not None :
            assert self.__class__.type == self.type
        self.__super.__init__ (** params)
    # end def __init__

    @classmethod
    def from_bytes (cls, bytes) :
        kw   = cls.deserialize (bytes)
        type = kw ['type']
        self = cls (** kw)
        if type in cls.type_registry :
            c = cls.type_registry [type]
            kw.update (c.deserialize (bytes))
            return c (** kw)
        else :
            return self
    # end def from_bytes

    @classmethod
    def deserialize (cls, bytes) :
        b  = bytes
        kw = {}
        for name, (format, length) in cls.format :
            if isinstance (format, type ('')) :
                kw [name] = unpack (format, b [:length]) [0]
                b = b [length:]
            else :
                value = format.deserialize (b, length)
                b = b [value.serialization_size:]
                kw [name] = value.value
        return kw
    # end def deserialize

    def as_bytes (self) :
        r = []
        for name, (fmt, length) in self.format :
            v = getattr (self, name)
            if isinstance (v, Protocol_Element) :
                r.append (v.serialize ())
            elif isinstance (fmt, type ('')) :
                r.append (pack (fmt, v))
            else :
                r.append (fmt (v).serialize ())
        return b''.join (r)
    # end def as_bytes

    def __str__ (self) :
        r = [self.__class__.__name__.split ('_', 1) [-1]]
        for n, (fmt, length) in self.format :
            if n not in self.suppress :
                r.append ('%s=%s' % (n, getattr (self, n)))
        return ' '.join (r)
    # end def __str__
    __repr__ = __str__

    @property
    def serialization_size (self) :
        return 16 + len (self.id.encode ('utf-8'))
    # end def serialization_size

# end class WSJTX_Telegram

class WSJTX_Heartbeat (WSJTX_Telegram) :

    type   = 0

    format = WSJTX_Telegram.format + \
        [ ('max_schema',     quint32)
        , ('version',        qutf8)
        , ('revision',       qutf8)
        ]
    defaults = dict \
        ( max_schema = 3
        , version    = ''
        , revision   = ''
        , ** WSJTX_Telegram.defaults
        )
# end class WSJTX_Heartbeat
WSJTX_Telegram.type_registry [WSJTX_Heartbeat.type] = WSJTX_Heartbeat

class WSJTX_Status (WSJTX_Telegram) :

    type   = 1
    format = WSJTX_Telegram.format + \
        [ ('dial_frq',       quint64)
        , ('mode',           qutf8)
        , ('dx_call',        qutf8)
        , ('report',         qutf8)
        , ('tx_mode',        qutf8)
        , ('tx_enabled',     qbool)
        , ('xmitting',       qbool)
        , ('decoding',       qbool)
        , ('rx_df',          quint32)
        , ('tx_df',          quint32)
        , ('de_call',        qutf8)
        , ('de_grid',        qutf8)
        , ('dx_grid',        qutf8)
        , ('tx_watchdog',    qbool)
        , ('sub_mode',       qutf8)
        , ('fast_mode',      qbool)
        , ('special_op',     quint8)
        , ('frq_tolerance',  quint32)
        , ('t_r_period',     quint32)
        , ('config_name',    qutf8)
        , ('tx_message',     qutf8)
        ]

# end class WSJTX_Status
WSJTX_Telegram.type_registry [WSJTX_Status.type] = WSJTX_Status

class WSJTX_Decode (WSJTX_Telegram) :

    type   = 2
    format = WSJTX_Telegram.format + \
        [ ('is_new',         qbool)
        , ('time',           qtime)
        , ('snr',            qint32)
        , ('delta_t',        qdouble)
        , ('delta_f',        quint32)
        , ('mode',           qutf8)
        , ('message',        qutf8)
        , ('low_confidence', qbool)
        , ('off_air',        qbool)
        ]

# end class WSJTX_Decode
WSJTX_Telegram.type_registry [WSJTX_Decode.type] = WSJTX_Decode

class WSJTX_Clear (WSJTX_Telegram) :

    type     = 3
    format   = WSJTX_Telegram.format + [('window', opt_quint8)]
    defaults = dict (window = None, **WSJTX_Telegram.defaults)

# end class WSJTX_Clear
WSJTX_Telegram.type_registry [WSJTX_Clear.type] = WSJTX_Clear

class WSJTX_Reply (WSJTX_Telegram) :

    type   = 4
    format = WSJTX_Telegram.format + \
        [ ('time',           qtime)
        , ('snr',            qint32)
        , ('delta_t',        qdouble)
        , ('delta_f',        quint32)
        , ('mode',           qutf8)
        , ('message',        qutf8)
        , ('low_confidence', qbool)
        , ('modifiers',      quint8)
        ]

# end class WSJTX_Reply
WSJTX_Telegram.type_registry [WSJTX_Reply.type] = WSJTX_Reply

class WSJTX_QSO_Logged (WSJTX_Telegram) :

    type   = 5
    format = WSJTX_Telegram.format + \
        [ ('time_off',       qdatetime)
        , ('dx_call',        qutf8)
        , ('dx_grid',        qutf8)
        , ('tx_frq',         quint64)
        , ('mode',           qutf8)
        , ('report_sent',    qutf8)
        , ('report_recv',    qutf8)
        , ('tx_power',       qutf8)
        , ('comments',       qutf8)
        , ('name',           qutf8)
        , ('time_on',        qdatetime)
        , ('operator_call',  qutf8)
        , ('my_call',        qutf8)
        , ('my_grid',        qutf8)
        , ('exchange_sent',  qutf8)
        , ('exchange_recv',  qutf8)
        , ('adif_propmode',  qutf8)
        ]

# end class WSJTX_QSO_Logged
WSJTX_Telegram.type_registry [WSJTX_QSO_Logged.type] = WSJTX_QSO_Logged

class WSJTX_Close (WSJTX_Telegram) :

    type   = 6

# end class WSJTX_Close
WSJTX_Telegram.type_registry [WSJTX_Close.type] = WSJTX_Close

class WSJTX_Replay (WSJTX_Telegram) :

    type   = 7

# end class WSJTX_Replay
WSJTX_Telegram.type_registry [WSJTX_Replay.type] = WSJTX_Replay

class WSJTX_Halt_TX (WSJTX_Telegram) :

    type   = 8
    format = WSJTX_Telegram.format + [('auto_tx_only', qbool)]

# end class WSJTX_Halt_TX
WSJTX_Telegram.type_registry [WSJTX_Halt_TX.type] = WSJTX_Halt_TX

class WSJTX_Free_Text (WSJTX_Telegram) :

    type   = 9
    format = WSJTX_Telegram.format + \
        [ ('text',   qutf8)
        , ('send',   qbool)
        ]
    defaults = dict (send = False, **WSJTX_Telegram.defaults)

# end class WSJTX_Free_Text
WSJTX_Telegram.type_registry [WSJTX_Free_Text.type] = WSJTX_Free_Text

class WSJTX_WSPR_Decode (WSJTX_Telegram) :

    type   = 10
    format = WSJTX_Telegram.format + \
        [ ('is_new',         qbool)
        , ('time',           qtime)
        , ('snr',            qint32)
        , ('delta_t',        qdouble)
        , ('frq',            quint64)
        , ('drift',          qint32)
        , ('callsign',       qutf8)
        , ('grid',           qutf8)
        , ('power',          qint32)
        , ('off_air',        qbool)
        ]

# end class WSJTX_WSPR_Decode
WSJTX_Telegram.type_registry [WSJTX_WSPR_Decode.type] = WSJTX_WSPR_Decode

class WSJTX_Location (WSJTX_Telegram) :

    type   = 11
    format = WSJTX_Telegram.format + [('location', qutf8)]

# end class WSJTX_Location
WSJTX_Telegram.type_registry [WSJTX_Location.type] = WSJTX_Location

class WSJTX_Logged_ADIF (WSJTX_Telegram) :

    type   = 12
    format = WSJTX_Telegram.format + [('adif_txt', qutf8)]

# end class WSJTX_Logged_ADIF
WSJTX_Telegram.type_registry [WSJTX_Logged_ADIF.type] = WSJTX_Logged_ADIF

class WSJTX_Highlight_Call (WSJTX_Telegram) :
    """ Highlight a callsign in WSJTX
    >>> kw = dict (id = 'test', version_number = 2)
    >>> whc = WSJTX_Highlight_Call \\
    ...     ( callsign = 'OE3RSU'
    ...     , bg_color = color_white
    ...     , fg_color = color_red
    ...     , highlight_last = 1
    ...     , **kw
    ...     )
    >>> b = whc.as_bytes ()
    >>> WSJTX_Telegram.from_bytes (b)
    Highlight_Call callsign=OE3RSU bg_color=QColor(alpha=65535, red=65535, green=65535, blue=65535) fg_color=QColor(alpha=65535, red=65535, green=0, blue=0) highlight_last=1
    """

    type   = 13
    format = WSJTX_Telegram.format + \
        [ ('callsign',       qutf8)
        , ('bg_color',       qcolor)
        , ('fg_color',       qcolor)
        , ('highlight_last', qbool)
        ]
    defaults = dict \
        ( fg_color       = color_black
        , bg_color       = color_white
        , highlight_last = False
        , ** WSJTX_Telegram.defaults
        )

# end class WSJTX_Highlight_Call
WSJTX_Telegram.type_registry [WSJTX_Highlight_Call.type] = WSJTX_Highlight_Call

class WSJTX_Switch_Config (WSJTX_Telegram) :

    type   = 14
    format = WSJTX_Telegram.format + [('adif_txt', qutf8)]

# end class WSJTX_Switch_Config
WSJTX_Telegram.type_registry [WSJTX_Switch_Config.type] = WSJTX_Switch_Config

class WSJTX_Configure (WSJTX_Telegram) :

    type   = 15
    format = WSJTX_Telegram.format + \
        [ ('mode',           qutf8)
        , ('frq_tolerance',  quint32)
        , ('sub_mode',       qutf8)
        , ('fast_mode',      qbool)
        , ('t_r_period',     quint32)
        , ('rx_df',          quint32)
        , ('dx_call',        qutf8)
        , ('dx_grid',        qutf8)
        , ('gen_messages',   qbool)
        ]

# end class WSJTX_Configure
WSJTX_Telegram.type_registry [WSJTX_Configure.type] = WSJTX_Configure

class UDP_Connector :

    def __init__ (self, wbf, ip = '127.0.0.1', port = 2237, id = None) :
        self.band   = '40m' # FIXME
        self.ip     = ip
        self.port   = port
        self.socket = socket (AF_INET, SOCK_DGRAM)
        self.socket.bind ((self.ip, self.port))
        self.wbf  = wbf
        self.peer = {}
        self.adr  = None
        self.id   = id
        if id is None :
            self.id = WSJTX_Telegram.defaults ['id']
        self.heartbeat_seen = False
        self.color_by_call  = {}
        self.pending_color  = {}
    # end def __init__

    def color (self, callsign, **kw) :
        tel = WSJTX_Highlight_Call (callsign = callsign, **kw)
        self.socket.sendto (tel.as_bytes (), self.adr)
    # end def color

    def handle (self, tel) :
        """ Handle given telegram.
            We send a heartbeat whenever we receive one.
            In addition we parse Decode messages, extract the call sign
            and determine worked-before and coloring.
        """
        if not self.heartbeat_seen or isinstance (tel, WSJTX_Heartbeat) :
            self.heartbeat ()
        if isinstance (tel, WSJTX_Status) :
            self.handle_status (tel)
        if isinstance (tel, WSJTX_Decode) :
            self.handle_decode (tel)
    # end def handle

    def handle_decode (self, tel) :
        if tel.off_air or not tel.is_new :
            return
        call  = self.parse_message (tel) or ''
        call  = call.lstrip ('<').rstrip ('>')
        if not call or call == '...' :
            return
        color = self.wbf.lookup_color (self.band, call)
        if call in self.color_by_call :
            if self.color_by_call [call] != color :
                self.update_color (call, color)
        else :
            self.update_color (call, color)
    # end def handle_decode

    def handle_status (self, tel) :
        """ Handle pending coloring
        """
        if not tel.decoding :
            for call in self.pending_color :
                fg = self.pending_color [call][0]
                bg = self.pending_color [call][1]
                self.color (call, fg_color = fg, bg_color = bg)
            self.pending_color = {}
    # end def handle_status

    def heartbeat (self, **kw) :
        tel = WSJTX_Heartbeat (version = '4711', **kw)
        self.socket.sendto (tel.as_bytes (), self.adr)
    # end def heartbeat

    def parse_message (self, tel) :
        """ Parse the message property of a decode which includes the
            callsign(s). Note that we try to use only the second
            (sender) callsign.
        >>> u = UDP_Connector (port = 4711, wbf = None)
        >>> class t :
        ...     message = None
        >>> t.message = 'JA1XXX YL2XXX R-18'
        >>> u.parse_message (t)
        'YL2XXX'
        >>> t.message = 'UB9XXX OH1XXX KP20'
        >>> u.parse_message (t)
        'OH1XXX'
        >>> t.message = 'RZ6XXX DL9XXX -06'
        >>> u.parse_message (t)
        'DL9XXX'
        >>> t.message = 'IZ7XXX EW4XXX 73'
        >>> u.parse_message (t)
        'EW4XXX'
        >>> t.message = 'CQ II0XXXX'
        >>> u.parse_message (t)
        'II0XXXX'
        >>> t.message = 'CQ PD0XXX JO22'
        >>> u.parse_message (t)
        'PD0XXX'
        >>> t.message = 'CQ NA PD0XXX JO22'
        >>> u.parse_message (t)
        'PD0XXX'
        >>> t.message = 'OK1XXX F4IXXX -07'
        >>> u.parse_message (t)
        'F4IXXX'
        >>> t.message = 'TM50XXX <F6XXX> RR73'
        >>> u.parse_message (t)
        '<F6XXX>'
        >>> t.message = 'CQ E73XXX JN94     a1'
        >>> u.parse_message (t)
        'E73XXX'
        """
        if not tel.message :
            print ("Empty message: %s" % tel)
            return None
        l = tel.message.split ()
        # Strip off marginal decode info
        if l [-1].startswith ('a') :
            l = l [:-1]
        if l [0] in ('CQ', 'QRZ') :
            # CQ DX or similar
            if len (l) == 4 :
                return l [2]
            return l [1]
        if len (l) == 2 :
            return l [1]
        if len (l) < 2 :
            print ("Unknown message: %s" % tel.message)
            return None
        if len (l) == 3 :
            return l [1]
        print ("Unknown message: %s" % tel.message)
        return None
    # end def parse_message

    def receive (self) :
        bytes, address = self.socket.recvfrom (4096)
        tel = WSJTX_Telegram.from_bytes (bytes)
        if tel.id not in self.peer :
            self.peer [tel.id] = address
        if not self.adr :
            self.adr = address
        self.handle (tel)
        return tel
    # end def receive

    def set_peer (self, peername) :
        if peername in self.peer :
            self.adr = self.peer [peername]
    # end def set_peer

    def update_color (self, call, color) :
        self.color_by_call [call] = color
        self.pending_color [call] = color
    # end def update_color

# end class UDP_Connector

class WBF (autosuper) :
    """ Worked before info
    """

    def __init__ (self, band, always_match = False) :
        self.band         = band
        self.wbf          = {}
        self.always_match = always_match
    # end def __init__

    def add_item (self, item, record = 1) :
        self.wbf [item] = record
    # end def add_item

    def lookup (self, item) :
        if self.always_match :
            return None
        return self.wbf.get (item, None)
    # end def lookup

# end class WBF

class Worked_Before :
    """ This parses an ADIF log file and extracts worked-before info
        This can then be used by the UDP_Connector to color calls by
        parsing calls from incoming Decode packets.
        We have a WBF per band and a WBF per known DXCC.
        if we cannot determine the dxcc info for a record (unfortunately
        not provided by wsjtx currently) all records will be colored
        only in the color for "new call" or "new call on band".
        By default we import the DXCC list from ARRL and look up the
        callsign there. This is fuzzy matching and a single call can
        match more than one entity. Only if there is an exact match do
        we use the match for determining worked-before status.
    """

    # defaults (fg color, bg color)
    color_wbf           = (color_invalid, color_invalid)
    color_dxcc          = (color_black,   color_pink)
    color_dxcc_band     = (color_black,   color_pink1)
    color_new_call      = (color_black,   color_cyan)
    color_new_call_band = (color_black,   color_cyan1)

    def __init__ (self, adif = None, args = None, **kw) :
        # Color override
        for k in kw :
            if k.startswith ('color_') :
                setattr (self, k, kw [k])
        self.dxcc_list = DXCC_File ()
        self.dxcc_list.parse ()
        self.dxcc_list = self.dxcc_list.by_type ['CURRENT']
        self.band_info = {}
        self.dxcc_info = {} # by dxcc number
        self.band_info ['ALL'] = WBF ('ALL')
        self.dxcc_info ['ALL'] = WBF ('ALL')
        if adif :
            with io.open (adif, 'r', encoding = args.encoding) as f :
                adif = ADIF (f)
                for rec in adif :
                    if not rec.band :
                        continue
                    if rec.band not in self.band_info :
                        self.band_info [rec.band] = WBF (rec.band)
                    self.band_info [rec.band].add_item (rec.call, rec)
                    self.band_info ['ALL'].   add_item (rec.call, rec)
                    self.match_dxcc (rec)
    # end def __init__

    def fuzzy_match_dxcc_code (self, call, only_one = False) :
        """ Use prefix info from dxcc list to fuzzy match the call
        >>> w = Worked_Before ()
        >>> w.fuzzy_match_dxcc_code ('OE3RSU')
        ['206']
        >>> w.fuzzy_match_dxcc_code ('OE3RSU', only_one = True)
        '206'
        >>> w.fuzzy_match_dxcc_code ('RK3LG', only_one = True)
        >>> w.fuzzy_match_dxcc_code ('RK3LG')
        ['054', '015']
        """
        entities = self.dxcc_list.callsign_lookup (call)
        if entities :
            if only_one and len (entities) == 1 :
                return entities [0].code
            elif not only_one :
                return [e.code for e in entities]
    # end def fuzzy_match_dxcc_code

    def match_dxcc (self, rec) :
        """ Match the dxcc for this adif record
            Note that we're using the standard ADIF DXCC entity code in
            the ADIF field DXCC *or* the COUNTRY field (in ASCII) or the
            COUNTRY_INTL field (in utf-8). Since all entity names are in
            english, all the COUNTRY_INTL should be in ASCII (a subset
            of utf-8) anyway. We match country to code and vice-versa
            via the ARRL dxcc list. If all this fails we do a fuzzy
            match on the prefix of the call.

            Note that you may want to code your own dxcc lookup for
            calls: You may want to treat dxcc entities for which you
            worked someone but do not have a QSL (or no LOTW QSL) as not
            worked before. So in that case you can override this
            routine.
        """
        dxcc_code = None
        if getattr (rec, 'dxcc', None) :
            dxcc_code = '%03d' % int (rec.dxcc, 10)
        elif getattr (rec, 'country', None) :
            dxcc = self.dxcc_list.by_name [rec.country]
            dxcc_code = dxcc.code
        elif getattr (rec, 'country_intl', None) :
            dxcc = self.dxcc_list.by_name [rec.country_intl]
            dxcc_code = dxcc.code
        else :
            dxcc_code = self.fuzzy_match_dxcc_code (rec.call, only_one = 1)
        if dxcc_code :
            if rec.band not in self.dxcc_info :
                self.dxcc_info [rec.band] = WBF (rec.band)
            self.dxcc_info [rec.band].add_item (dxcc_code)
            self.dxcc_info ['ALL'].   add_item (dxcc_code)
    # end def match_dxcc

    def lookup_color_new_call (self, call) :
        """ Look up a call and decide if new on band or global
        >>> w = Worked_Before ()
        >>> w.lookup_color_new_call ('SX4711TEST') [1]
        QColor(alpha=65535, red=0, green=65535, blue=65535)
        """
        r = self.band_info ['ALL'].lookup (call)
        if r :
            return self.color_new_call_band
        return self.color_new_call
    # end def lookup_color_new_call

    def lookup_color (self, band, call) :
        """ Look up the color for this call for this band
            Involves checking of a new DXCC (on band or globally)
            and the check of a new call (on band or globally)
            The following test looks up RK0 which matches both, European
            Russia and Asiatic Russia.
        >>> w = Worked_Before ()
        >>> w.band_info ['40m'] = WBF ('40m')
        >>> w.dxcc_info ['40m'] = WBF ('40m')
        >>> w.dxcc_info ['ALL'] = WBF ('ALL')
        >>> for code in ('054', '015') :
        ...     w.dxcc_info ['40m'].add_item (code)
        ...     w.dxcc_info ['ALL'].add_item (code)
        >>> w.lookup_color ('40m', 'RK0') [1]
        QColor(alpha=65535, red=0, green=65535, blue=65535)
        """
        if band not in self.band_info :
            return self.color_dxcc
        r = self.band_info [band].lookup (call)
        if r :
            return self.color_wbf
        dxccs = self.fuzzy_match_dxcc_code (call)
        if not dxccs :
            return self.color_dxcc
        r2 = 1
        for dxcc in dxccs :
            r2 = r2 and self.dxcc_info ['ALL'].lookup (dxcc)
        # Matched for *all* dxccs; not new on any band
        if r2 :
            return self.lookup_color_new_call (call)
        r3 = 1
        for dxcc in dxccs :
            r3 = r3 and self.dxcc_info [band].lookup (dxcc)
        # Matched for *all* dxccs; not new dxcc on this band
        if r3 :
            return self.color_dxcc
        return self.color_dxcc_band
    # end def lookup_color

# end class Worked_Before

def get_wbf () :
    cmd = ArgumentParser ()
    cmd.add_argument \
        ( "adif"
        , help  = 'ADIF file to parse, should be specified'
        )
    cmd.add_argument \
        ( "-e", "--encoding"
        , help    = 'ADIF file character encoding, default=%(default)s'
        , default = 'utf-8'
        )
    args = cmd.parse_args ()
    wbf = Worked_Before (args = args, adif = args.adif)
    return wbf
# end def get_wbf

def main (get_wbf = get_wbf) :
    wbf = get_wbf ()
    uc  = UDP_Connector (wbf)
    while 1 :
        tel = uc.receive ()
        if not isinstance (tel, (WSJTX_Decode,)):
            print (tel)
# end def main

__all__ = [ "main", "QDateTime", "QColor", "color_red", "color_green"
          , "color_blue", "color_white", "color_black"
          , "color_cyan", "color_cyan1", "color_pink", "color_pink1"
          , "WSJTX_Heartbeat", "WSJTX_Status", "WSJTX_Decode"
          , "WSJTX_Clear", "WSJTX_Reply", "WSJTX_QSO_Logged"
          , "WSJTX_Close", "WSJTX_Replay", "WSJTX_Halt_TX"
          , "WSJTX_Free_Text", "WSJTX_WSPR_Decode", "WSJTX_Location"
          , "WSJTX_Logged_ADIF", "WSJTX_Highlight_Call"
          , "WSJTX_Switch_Config", "WSJTX_Configure", "UDP_Connector"
          , "WBF", "Worked_Before"
          ]

if __name__ == '__main__' :
    main ()
