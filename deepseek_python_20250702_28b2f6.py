# -*- coding: utf-8 -*-
"""
/***************************************************************************
 UrbanRadioCober
                                 A QGIS plugin
 urban radiocober simulator plugin for omnidirectional radio coverage in urban enviroment
                              -------------------
        begin                : 2015-11-11
        git sha              : $Format:%H$
        copyright            : (C) 2015 by  Mario Salazar, Leonardo Cifuentes, Jhon Castaneda
        email                : dlcifuentesl@gmail.com, mario_salazarb@hotmail.com, jhonjaingambiental@gmail.com.
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QVariant
from PyQt5.QtWidgets import QAction, QMessageBox
from PyQt5.QtGui import QIcon
from qgis.core import *
# Initialize Qt resources from file resources.py
import resources_rc
import resources

# Import the code for the dialog
from urban_radiocober_dialog import UrbanRadioCoberDialog
from PyQt5.QtCore import *
import os.path
import time
import math
import numpy
from qgis.analysis import *
import os
import sys

class UrbanRadioCober:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'UrbanRadioCober_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = UrbanRadioCoberDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Urban RadioCober')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'UrbanRadioCober')
        self.toolbar.setObjectName(u'UrbanRadioCober')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('UrbanRadioCober', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/UrbanRadioCober/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Urban RadioCober'),
            callback=self.run,
            parent=self.iface.mainWindow())

        self.inicia_valores()
        #create the directory that will store the temporal layers
        self.creadir()


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Urban RadioCober'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar


    def run(self):
        # Plugin uses selected layer, hope to add layer selection later.
        global vl, vl
        active_vl = self.iface.activeLayer()
        # We check for selected features to auto-populate the "use selected feature" box in the dialog.
        sel_feats = ''
        if active_vl is not None:
            sel_feats = active_vl.selectedFeatures()
        result = 0
        """Run method that performs all the real work"""
        # Logic if to run the dialog
        if active_vl is None:
            sel_feats = ''
            QMessageBox.warning(self.iface.mainWindow(), "Warning",
                "Seleccione un Layer.", QMessageBox.Ok)
            result = 0
        elif active_vl.type() == QgsMapLayer.RasterLayer:
            sel_feats = ''
            QMessageBox.warning(self.iface.mainWindow(), "Warning",
                "Raster layer selected.", QMessageBox.Ok)
            result = 0
        elif active_vl.type() == QgsMapLayer.PluginLayer:
            sel_feats = ''
            QMessageBox.warning(self.iface.mainWindow(), "Warning",
                "Plugin layer selected, please save as a regular layer and try again.", QMessageBox.Ok)
            result = 0
        elif active_vl is not None:
            self.dlg.populatedialogue(active_vl.name())
            if len(sel_feats) == 0:
                # If selected layer has selected features populate the box.
                # If not make it impossible to populate the box.
                self.dlg.selectedfeats(1)
            else:
                self.dlg.selectedfeats(1)
            self.dlg.show()
            result = self.dlg.exec_()
        else:
            sel_feats = ''
            QMessageBox.warning(self.iface.mainWindow(), "Warning",
                "Could not process layer.", QMessageBox.Ok)
            result = 0

        # If ok was clicked in the dialog, continue:
        if result == 1:

            buffer_crs_object = self.iface.activeLayer().crs()
            # Check the current CRS of the layer
            buffer_crs = buffer_crs_object.authid()
            # Apply that to the created layer if recognised
            buffer_input_crs = "Polygon?crs=%s" % buffer_crs
            # Create empty memory vector layer for buffers

            # store rhe id of the selected feature
            id_select=self.captura_id(self.iface.activeLayer())

            vl = QgsVectorLayer(buffer_input_crs, "Buffer_Cobertura", "memory")
            vl_pr = vl.dataProvider()
            # Distance feature for buffer distance
            vl_pr.addAttributes([QgsField("FID", QVariant.Int),QgsField("distance", QVariant.Double,"",10,3)])
            vl.updateFields()


            lonbuffer= self.radiomaximobuffer(1)# calculate the maximun radio of the buffer
            lon_segmento=lonbuffer

            buffer_distance =lon_segmento

            # store the selected features for the buffer
            iterate = active_vl.selectedFeatures()
            sel_feats = []
            for feature in iterate:
                sel_feats.append(feature)

            # set the number of rings of the buffer and the segmentation
            num_of_rings=3
            segments_to_approximate =25

            # Run if there are features in the layer
            if len(sel_feats) > 0:

            # do the buffer
                buffercompletos = []
                buffercortados = []
                distancias=[]
                j=0
                distance = buffer_distance
                while num_of_rings > 0:
                    #stores the 3 buffers
                    distancias.append(lonbuffer)
                    for each_feat in sel_feats:
                        geom = each_feat.geometry()
                        buff = geom.buffer(distance, segments_to_approximate)
                        new_f = QgsFeature()
                        new_f.setGeometry(buff)
                        #new_f.setAttributes([lonbuffer])
                        buffercompletos.append(new_f)


                        num_of_rings = num_of_rings - 1

                        if num_of_rings==2:
                            #d = QgsDistanceArea() # crea el objeto de medicion
                            lonbuffer= self.radiomaximobuffer(2)# calculate the maximun radio of the buffer
                            lon_segmento=lonbuffer
                            distance=lon_segmento


                        elif num_of_rings==1:
                            #d = QgsDistanceArea() # crea el objeto de medicion
                            lonbuffer= self.radiomaximobuffer(3)# calculate the maximun radio of the buffer
                            lon_segmento=lonbuffer
                            distance=lon_segmento


                for buffer in buffercompletos:
                    new_f_geom = buffer.geometry()
                    new_f_clipped = new_f_geom.difference(geom)
                    new_f2 = QgsFeature()
                    new_f2.setGeometry(new_f_clipped)
                    new_f2.setAttributes([j,distancias[j]])
                    buffercortados.append(new_f2)
                    geom=geom.combine(new_f2.geometry())
                    j=j+1


                vl_pr.addFeatures(buffercortados)

                QgsMapLayerRegistry.instance().addMapLayer(vl)


            self.iface.messageBar().clearWidgets()

        #crea un layer con el buffer 1
        buffer1 = self.splitbuff(vl,0)
        # clip parcels layers using the buffer1 layer
        pbuff1=self.intersect(active_vl,buffer1,0)
        pbuff1=self.exporta_capa(pbuff1) #convierte esta capa  a que es temporal a real

        #crea un layer con el buffer 2
        buffer2 = self.splitbuff(vl,1)
        # clip parcels layers using the buffer2 layer
        pbuff2=self.intersect(active_vl,buffer2,1)
        pbuff2=self.exporta_capa(pbuff2) #convierte esta capa  a que es temporal a real

        #crea un layer con el buffer 3
        buffer3 = self.splitbuff(vl,2)
        # clip parcels layers using the buffer3 layer
        pbuff3=self.intersect(active_vl,buffer3,2)
        pbuff3=self.exporta_capa(pbuff3)#convierte esta capa  a que es temporal a real

        #materializa la capa de buffers
        buff_anillos=self.exporta_capa(vl)

        #duplica el layer d elos predios y crea un layer temporal
        layer_final=self.crearlayerfinal(active_vl)
        layer_final=self.exporta_capa(layer_final)

        #hace el join sobre las capas layer final y el buf 1
        self.join(layer_final,pbuff1,0)

        #hace el join sobre las capas layer final y el buf 2
        self.join(layer_final,pbuff2,1)

        #hace el join sobre las capas layer final y el buf 3
        self.join(layer_final,pbuff3,2)

        #borra los nulls que están en el campo de area
        self.borra_null(layer_final)

        #asigna el valor de la señal
        self.asigna_calidad(layer_final,id_select)

        #carga la simbologia
        self.carga_simbol(layer_final,str(os.getcwd())+"\estilo.qml")
        self.carga_simbol(buff_anillos,str(os.getcwd())+"\estilo_buff.qml")

        #quita los layers intermedios
        QgsMapLayerRegistry.instance().removeMapLayers( [pbuff3.id(),pbuff2.id(),pbuff1.id(),vl.id()] )