from z3c.form import interfaces
from zope import schema
from zope.interface import Interface
from zope.i18nmessageid import MessageFactory
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

_ = MessageFactory('collective.xsendfile')
http_response_headers = SimpleVocabulary(
    [#SimpleTerm(value=u'', title=_(u'disable')),
     SimpleTerm(value=u'X-Sendfile', title=_(u'X-Sendfile (Apache, LHTTPd)')),
     SimpleTerm(value=u'X-Accel-Redirect', title=_(u'X-Accel-Redirect (nginx, needs path rewriting)')),]
     )


class IxsendfileSettings(Interface):
    """Global xsendfile settings. This describes records stored in the
    configuration registry and obtainable via plone.registry.
    """

    xsendfile_responseheader = schema.Choice(
        title=_(u"HTTP Response Header"),
        vocabulary=http_response_headers,
        required=False,
        )

    xsendfile_enable_fallback = schema.Bool(
        title=_(u"Enable fallback based on HTTP_X_FORWARDED_FOR proxy header"),
        description=_(u"Check if REQUEST header contains HTTP_X_FORWARDED_FOR and re-enable fallback (zope) file delivery if no proxy is detected."),
        default=True,
        required=False,
        )

    xsendfile_pathregex_search = schema.TextLine(
        title=_(u"Blob-path rewriting regex"),
        description=_(u"This regex will be used to modify the files path, in case you are using a different mountpoint on the xsendfile Server. If you are using nginx you have to prepend the id of the location you configured."),
        default=u"(.*)",
        required=False,
        )

    xsendfile_pathregex_substitute = schema.TextLine(
        title=_(u"Blob-path rewriting substitution"),
        description=_(u"This regex will be used to modify the files path, in case you are using a different mountpoint on the xsendfile Server. If you are using nginx you have to prepend the id of the location you configured."),
        default=u"\\1",
        required=False,
        )
