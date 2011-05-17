from plone.app.registry.browser import controlpanel
from collective.xsendfile.interfaces import IxsendfileSettings, _

class xsendfileSettingsEditForm(controlpanel.RegistryEditForm):

    schema = IxsendfileSettings
    label = _(u"xsendfile settings")
    description = _(u"""""")

    def updateFields(self):
        super(xsendfileSettingsEditForm, self).updateFields()


    def updateWidgets(self):
        super(xsendfileSettingsEditForm, self).updateWidgets()

class xsendfileSettingsControlPanel(controlpanel.ControlPanelFormWrapper):
    form = xsendfileSettingsEditForm