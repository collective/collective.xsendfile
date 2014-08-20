# -*- coding: utf-8 -*-
import os

from plone.app.registry.browser import controlpanel

from collective.xsendfile.interfaces import IxsendfileSettings
from collective.xsendfile.interfaces import _


if 'XSENDFILE_RESPONSEHEADER' in os.environ:
    DESC = _(
        'WARNING: xsendfile settings configured by environment. These settings '
        'will be ignored.')
else:
    DESC = _(u'')


class xsendfileSettingsEditForm(controlpanel.RegistryEditForm):
    schema = IxsendfileSettings
    label = _(u'xsendfile settings')

    description = DESC

    def updateFields(self):
        super(xsendfileSettingsEditForm, self).updateFields()

    def updateWidgets(self):
        super(xsendfileSettingsEditForm, self).updateWidgets()


class xsendfileSettingsControlPanel(controlpanel.ControlPanelFormWrapper):
    form = xsendfileSettingsEditForm
