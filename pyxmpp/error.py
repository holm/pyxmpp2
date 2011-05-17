#
# (C) Copyright 2003-2010 Jacek Konieczny <jajcus@jajcus.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License Version
# 2.1 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

"""XMPP error handling.

Normative reference:
  - `RFC 6120 <http://xmpp.org/rfcs/rfc6120.html>`__
  - `RFC 3920 <http://xmpp.org/rfcs/rfc3920.html>`__
  - `JEP 86 <http://www.jabber.org/jeps/jep-0086.html>`__
"""

from __future__ import absolute_import

__docformat__="restructuredtext en"

import logging

from xml.etree import ElementTree
from copy import deepcopy

from .xmlextra import common_doc, common_root, common_ns
from . import xmlextra
from .exceptions import ProtocolError
from .constants import STREAM_NS, STANZA_ERROR_NS, STREAM_ERROR_NS
from .constants import STREAM_QNP, STANZA_ERROR_QNP, STREAM_ERROR_QNP
from .constants import PYXMPP_ERROR_NS, STANZA_CLIENT_QNP, STANZA_NAMESPACES

logger = logging.getLogger("pyxmpp.error")

STREAM_ERRORS = {
            u"bad-format":
                ("Received XML cannot be processed",),
            u"bad-namespace-prefix":
                ("Bad namespace prefix",),
            u"conflict":
                ("Closing stream because of conflicting stream being opened",),
            u"connection-timeout":
                ("Connection was idle too long",),
            u"host-gone":
                ("Hostname is no longer hosted on the server",),
            u"host-unknown":
                ("Hostname requested is not known to the server",),
            u"improper-addressing":
                ("Improper addressing",),
            u"internal-server-error":
                ("Internal server error",),
            u"invalid-from":
                ("Invalid sender address",),
            u"invalid-namespace":
                ("Invalid namespace",),
            u"invalid-xml":
                ("Invalid XML",),
            u"not-authorized":
                ("Not authorized",),
            u"not-well-formed":
                ("XML sent by client is not well formed",),
            u"policy-violation":
                ("Local policy violation",),
            u"remote-connection-failed":
                ("Remote connection failed",),
            u"reset":
                ("Stream reset",),
            u"resource-constraint":
                ("Remote connection failed",),
            u"restricted-xml":
                ("Restricted XML received",),
            u"see-other-host":
                ("Redirection required",),
            u"system-shutdown":
                ("The server is being shut down",),
            u"undefined-condition":
                ("Unknown error",),
            u"unsupported-encoding":
                ("Unsupported encoding",),
            u"unsupported-feature":
                ("Unsupported feature",),
            u"unsupported-stanza-type":
                ("Unsupported stanza type",),
            u"unsupported-version":
                ("Unsupported protocol version",),
    }

STREAM_ERRORS_Q = dict([( "{{{0}}}{1}".format(STREAM_ERROR_NS, x[0]), x[1])
                                            for x in STREAM_ERRORS.items()])

UNDEFINED_STREAM_CONDITION = \
        "{urn:ietf:params:xml:ns:xmpp-streams}undefined-condition"
UNDEFINED_STANZA_CONDITION = \
        "{urn:ietf:params:xml:ns:xmpp-stanzas}undefined-condition"

STANZA_ERRORS = {
            u"bad-request":
                ("Bad request",
                "modify", 400),
            u"conflict":
                ("Named session or resource already exists",
                "cancel", 409),
            u"feature-not-implemented":
                ("Feature requested is not implemented",
                "cancel", 501),
            u"forbidden":
                ("You are forbidden to perform requested action",
                "auth", 403),
            u"gone":
                ("Recipient or server can no longer be contacted at this address",
                "modify", 302),
            u"internal-server-error":
                ("Internal server error",
                "wait", 500),
            u"item-not-found":
                ("Item not found"
                ,"cancel", 404),
            u"jid-malformed":
                ("JID malformed",
                "modify", 400),
            u"not-acceptable":
                ("Requested action is not acceptable",
                "modify", 406),
            u"not-allowed":
                ("Requested action is not allowed",
                "cancel", 405),
            u"not-authorized":
                ("Not authorized",
                "auth", 401),
            u"policy-violation":
                ("Policy violation",
                "cancel", 405),
            u"recipient-unavailable":
                ("Recipient is not available",
                "wait", 404),
            u"redirect":
                ("Redirection",
                "modify", 302),
            u"registration-required":
                ("Registration required",
                "auth", 407),
            u"remote-server-not-found":
                ("Remote server not found",
                "cancel", 404),
            u"remote-server-timeout":
                ("Remote server timeout",
                "wait", 504),
            u"resource-constraint":
                ("Resource constraint",
                "wait", 500),
            u"service-unavailable":
                ("Service is not available",
                "cancel", 503),
            u"subscription-required":
                ("Subscription is required",
                "auth", 407),
            u"undefined-condition":
                ("Unknown error",
                "cancel", 500),
            u"unexpected-request":
                ("Unexpected request",
                "wait", 400),
    }

STANZA_ERRORS_Q = dict([( "{{{0}}}{1}".format(STANZA_ERROR_NS, x[0]), x[1])
                                            for x in STANZA_ERRORS.items()])

OBSOLETE_CONDITIONS = {
            # changed between RFC 3920 and RFC 6120
            "{urn:ietf:params:xml:ns:xmpp-streams}xml-not-well-formed": 
                    "{urn:ietf:params:xml:ns:xmpp-streams}not-well-formed",
            "{urn:ietf:params:xml:ns:xmpp-streams}invalid-id": 
                                                UNDEFINED_STREAM_CONDITION,
            "{urn:ietf:params:xml:ns:xmpp-stanzas}payment-required": 
                                                UNDEFINED_STANZA_CONDITION,
}


LEGACY_CODES = {
        302: "{urn:ietf:params:xml:ns:xmpp-stanzas}redirect",
        400: "{urn:ietf:params:xml:ns:xmpp-stanzas}bad-request",
        401: "{urn:ietf:params:xml:ns:xmpp-stanzas}not-authorized",
        402: "{urn:ietf:params:xml:ns:xmpp-stanzas}payment-required",
        403: "{urn:ietf:params:xml:ns:xmpp-stanzas}forbidden",
        404: "{urn:ietf:params:xml:ns:xmpp-stanzas}item-not-found",
        405: "{urn:ietf:params:xml:ns:xmpp-stanzas}not-allowed",
        406: "{urn:ietf:params:xml:ns:xmpp-stanzas}not-acceptable",
        407: "{urn:ietf:params:xml:ns:xmpp-stanzas}registration-required",
        408: "{urn:ietf:params:xml:ns:xmpp-stanzas}remote-server-timeout",
        409: "{urn:ietf:params:xml:ns:xmpp-stanzas}conflict",
        500: "{urn:ietf:params:xml:ns:xmpp-stanzas}internal-server-error",
        501: "{urn:ietf:params:xml:ns:xmpp-stanzas}feature-not-implemented",
        502: "{urn:ietf:params:xml:ns:xmpp-stanzas}service-unavailable",
        503: "{urn:ietf:params:xml:ns:xmpp-stanzas}service-unavailable",
        504: "{urn:ietf:params:xml:ns:xmpp-stanzas}remote-server-timeout",
        510: "{urn:ietf:params:xml:ns:xmpp-stanzas}service-unavailable",
    }

class ErrorElement(object):
    """Base class for both XMPP stream and stanza errors
   
    :Properties:
        - `condition_name`: XMPP-defined condition name
    :Ivariables:
        - `condition`: the condition element
        - `text`: (language, text) pairs with human-readable error description,
          language can be `None` or RFC 3066 language tag
        - `custom_condition`: list of custom condition elements
    :Types:
        - `condition_name`: `unicode`
        - `condition`: `unicode`
        - `text`: `list` of (`unicode`, `unicode`)
        - `custom_condition`: `list` of `ElementTree.Element`

    """
    error_qname = "{unknown}error"
    text_qname = "{unknown}text"
    cond_qname_prefix = "{unknown}"
    def __init__(self, element_or_cond, description = None, lang = None):
        """Initialize an StanzaErrorElement object.

        :Parameters:
            - `element_or_cond`: XML <error/> element to decode or an error
              condition name or element.
            - `description`: optional description to override the default one
            - `lang`: RFC 3066 language tag for the description
        :Types:
            - `element_or_cond`: `ElementTree.Element` or `unicode`
            - `description`: `unicode`
            - `lang`: `unicode`
        """
        self.text = []
        self.custom_condition = []
        if isinstance(element_or_cond, basestring):
            self.condition = ElementTree.Element(self.cond_qname_prefix 
                                                        + element_or_cond)
        elif not isinstance(element_or_cond, ElementTree.Element):
            raise TypeError, "Element or unicode string expected"
        else:
            self._from_xml(element_or_cond)
        if description:
            self.text = [t for t in self.text if t[0] != lang]
            self.text.append(lang, description)

    def _from_xml(self, element):
        """Initialize an ErrorElement object from an XML element.

        :Parameters:
            - `element`: XML element to be decoded.
        :Types:
            - `element`: `ElementTree.Element`
        """
        if element.tag != self.error_qname:
            raise ValueError(u"{0!r} is not a {1!r} element".format(
                                                    element, self.error_qname))
        self.condition = None
        for child in element:
            if child.tag.startswith(self.cond_qname_prefix):
                if self.condition is not None:
                    logger.warning("Multiple conditions in XMPP error node.")
                    continue
                self.condition = deepcopy(child)
            elif child.tag == self.text_qname:
                lang = child.get(XML_LANG_QNAME, None)
                description = child.text.strip()
                self.text.append( (lang, description) )
            else:
                bad = False
                for prefix in (STREAM_QNP, STANZA_CLIENT_QNP, STANZA_SERVER_QNP,
                                            STANZA_ERROR_QNP, STREAM_ERROR_QNP):
                    if child.tag.startswith(prefix):
                        logger.warning("Unexpected stream-namespaced"
                                                        " element in error.")
                        bad = True
                        break
                if not bad:
                    self.custom_condition.append( deepcopy(child) )
        if self.condition is None:
            self.condition = ElementTree.Element(self.cond_qname_prefix
                                                    + "undefined-condition")
        if self.condition.tag in OBSOLETE_CONDITIONS:
            new_cond_name = OBSOLETE_CONDITIONS[condition.tag]

    @property
    def condition_name(self):
        """Return the condition name (condition element name without the
        namespace)."""
        return self.condition.tag.split("}", 1)[1]

    def get_description(self, lang = None):
        """Get the optional description text included in the error element.

        :Parameters:
            - `lang`: the preferred language (RFC 3066 tag)

        :return: (lang, description) tuple, both description and language may
            be None.
        :returntype: (`unicode`, `unicode`)"""
        if not self.text:
            return None, None
        for t_lang, t_descr in self.text:
            if t_lang == lang:
                return t_lang, t_descr
        return self.text[0]

    def add_custom_condition(self, element):
        """Add custom condition element to the error.

        :Parameters:
            - `element`: XML element
        :Types:
            - `element`: `ElementTree.Element`

        """
        self.custom_condition.append(element)

    def serialize(self):
        """Serialize the stanza into a Unicode XML string.

        :return: serialized element.
        :returntype: `unicode`"""
        return serialize(self.as_xml())

    def as_xml(self):
        """Return the XML error representation.

        :returntype: `ElementTree.Element`"""
        result = ElementTree.Element(self.error_qname)
        result.append(deepcopy(self.condition))
        for lang, description in self.text:
            text = ElementTree.SubElement(result, self.text_qname,
                                            { XML_LANG_QNAME: lang } )
            text.text = description
        return result

class StreamErrorElement(ErrorElement):
    """Stream error element."""
    error_qname = STREAM_QNP + "error"
    text_qname = STREAM_QNP + "text"
    cond_qname_prefix = STREAM_ERROR_QNP
    def __init__(self, element_or_cond, description = None, lang = None):
        """Initialize an StanzaErrorElement object.

        :Parameters:
            - `element_or_cond`: XML <error/> element to decode or an error
              condition name or element.
            - `description`: optional description to override the default one
            - `lang`: RFC 3066 language tag for the description
        :Types:
            - `element_or_cond`: `ElementTree.Element` or `unicode`
            - `description`: `unicode`
            - `lang`: `unicode`
        """
        if isinstance(element_or_cond, unicode):
            if element_or_cond not in STREAM_ERRORS:
                raise ValueError("Bad error condition")
        ErrorElement.__init__(self, element_or_cond, description, lang)

    def get_message(self):
        """Get the standard English message for the error.

        :return: the error message.
        :returntype: `unicode`"""
        cond = self.condition_name
        if cond in STREAM_ERRORS:
            return STREAM_ERRORS[cond][0]
        else:
            return None

class StanzaErrorElement(ErrorElement):
    """Stanza error element.
    
    :Ivariables:
        - `error_type`: 'type' of the error, one of: 'auth', 'cancel',
          'continue', 'modify', 'wait'
        - `_legacy_code`: legacy error code
    :Types:
        - `error_type`: `unicode`
        - `_legacy_code`: `int`
    """
    error_qname = STANZA_CLIENT_QNP + "error"
    text_qname = STANZA_CLIENT_QNP + "text"
    cond_qname_prefix = STANZA_ERROR_QNP
    def __init__(self, element_or_cond, description = None, lang = None,
                                                            error_type = None):
        """Initialize an StanzaErrorElement object.

        :Parameters:
            - `element_or_cond`: XML <error/> element to decode or an error
              condition name or element.
            - `description`: optional description to override the default one
            - `lang`: RFC 3066 language tag for the description
            - `error_type`: 'type' of the error, one of: 'auth', 'cancel',
              'continue', 'modify', 'wait'
        :Types:
            - `element_or_cond`: `ElementTree.Element` or `unicode`
            - `description`: `unicode`
            - `lang`: `unicode`
            - `error_type`: `unicode`
        """
        self.error_type = None
        self._legacy_code = None
        if isinstance(element_or_cond, basestring):
            if element_or_cond not in STANZA_ERRORS:
                raise ValueError(u"Bad error condition")
        elif element_or_cond.tag.startswith(u"{"):
            namespace = element_or_cond.tag[1:].split(u"}", 1)[0]
            if namespace not in STANZA_NAMESPACES:
                raise ValueError(u"Bad error namespace {0!r}".format(namespace))
            self.error_qname = u"{{{0}}}error".format(namespace)
            self.text_qname = u"{{{0}}}text".format(namespace)
        else:
            raise ValueError(u"Bad error namespace - no namespace")
        ErrorElement.__init__(self, element_or_cond, description, lang)
        if error_type is not None:
            self.error_type = error_type
        if self.condition.tag in STANZA_ERRORS_Q:
            cond = self.condition.tag
        else:
            cond = UNDEFINED_STANZA_CONDITION
        if not self.error_type:
            self.error_type = STANZA_ERRORS_Q[cond][1]
        if not self._legacy_code:
            self._legacy_code = STANZA_ERRORS_Q[cond][2]

    def _from_xml(self, element):
        """Initialize an ErrorElement object from an XML element.

        :Parameters:
            - `element`: XML element to be decoded.
        :Types:
            - `element`: `ElementTree.Element`
        """
        ErrorElement._from_xml(self, element)
        error_type = element.get(u"type")
        if error_type:
            self.error_type = error_type
        legacy_code = element.get(u"code")
        if legacy_code:
            self._legacy_code = legacy_code
            if self.condition.tag == UNDEFINED_STANZA_CONDITION and (
                                            legacy_code in LEGACY_CODES):
                self.condition = LEGACY_CODES[legacy_code]
 
    def get_message(self):
        """Get the standard English message for the error.

        :return: the error message.
        :returntype: `unicode`"""
        cond = self.condition_name
        if cond in STANZA_ERRORS:
            return STANZA_ERRORS[cond][0]
        else:
            return None

    def as_xml(self, legacy = False):
        """Return the XML error representation.

        :Parameters:
            - `legacy`: if legacy 'code' attribute should be included
        Types:
            - `legacy`: `bool`

        :returntype: `ElementTree.Element`"""
        result = ErrorElement.as_xml(self)
        result.set("type", self.error_type)
        if legacy:
            code = self._legacy_code
            if not code:
                code = STANZA_ERRORS_Q[self.condition.tag][2]
            result.set("code", self._legacy_code)
        return result

# vi: sts=4 et sw=4
