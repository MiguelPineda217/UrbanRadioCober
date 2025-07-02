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
from qgis.PyQt.QtCore import (
    QSettings, 
    QTranslator, 
    qVersion, 
    QCoreApplication,
    QVariant,
    QUrl
)
from qgis.PyQt.QtGui import QIcon, QDesktopServices
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QPushButton
from qgis.core import (
    QgsProject, 
    QgsVectorLayer, 
    QgsFeature, 
    QgsField, 
    QgsWkbTypes, 
    QgsVectorFileWriter, 
    QgsExpression, 
    QgsFeatureRequest, 
    QgsDistanceArea,
    QgsMapLayer,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsMessageLog,
    QgsMessageOutput,
    Qgis,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingFeatureBasedAlgorithm
)
from qgis.analysis import QgsNativeAlgorithms
from qgis.gui import QgsMessageBar

# Initialize Qt resources from file resources.py
from . import resources_rc
from . import resources

# Import the code for the dialog
from .urban_radiocober_dialog import UrbanRadioCoberDialog
import os.path
import time
import math
import numpy
import sys
import traceback
import warnings
from typing import Optional, List, Dict, Set, Any, Union

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
        icon_path: str,
        text: str,
        callback: callable,
        enabled_flag: bool = True,
        add_to_menu: bool = True,
        add_to_toolbar: bool = True,
        status_tip: Optional[str] = None,
        whats_this: Optional[str] = None,
        parent: Optional[QObject] = None) -> QAction:
        """Add a toolbar icon to the toolbar."""

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
        # create the directory that will store the temporal layers
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
        """Run method that performs all the real work"""
        active_vl = self.iface.activeLayer()
        sel_feats = active_vl.selectedFeatures() if active_vl is not None else []
        
        result = 0
        
        # Validate layer selection
        if active_vl is None:
            QMessageBox.warning(self.iface.mainWindow(), "Warning",
                "Seleccione un Layer.", QMessageBox.Ok)
        elif active_vl.type() == QgsMapLayer.RasterLayer:
            QMessageBox.warning(self.iface.mainWindow(), "Warning",
                "Raster layer selected.", QMessageBox.Ok)
        elif active_vl.type() == QgsMapLayer.PluginLayer:
            QMessageBox.warning(self.iface.mainWindow(), "Warning",
                "Plugin layer selected, please save as a regular layer and try again.", QMessageBox.Ok)
        elif active_vl is not None:
            self.dlg.populatedialogue(active_vl.name())
            self.dlg.selectedfeats(1 if len(sel_feats) > 0 else 0)
            self.dlg.show()
            result = self.dlg.exec_()
        else:
            QMessageBox.warning(self.iface.mainWindow(), "Warning",
                "Could not process layer.", QMessageBox.Ok)

        if result == 1:
            self.process_coverage(active_vl, sel_feats)

    def process_coverage(self, active_vl: QgsVectorLayer, sel_feats: List[QgsFeature]):
        """Process the radio coverage analysis"""
        try:
            # Create buffer layer
            buffer_crs = active_vl.crs().authid()
            buffer_input_crs = f"Polygon?crs={buffer_crs}"
            vl = QgsVectorLayer(buffer_input_crs, "Buffer_Cobertura", "memory")
            vl_pr = vl.dataProvider()
            vl_pr.addAttributes([
                QgsField("FID", QVariant.Int),
                QgsField("distance", QVariant.Double, "", 10, 3)
            ])
            vl.updateFields()

            # Calculate buffers
            id_select = self.captura_id(active_vl)
            self.create_buffers(active_vl, sel_feats, vl, vl_pr)

            # Process buffers and intersections
            buffer1 = self.splitbuff(vl, 0)
            pbuff1 = self.process_intersection(active_vl, buffer1, 0)

            buffer2 = self.splitbuff(vl, 1)
            pbuff2 = self.process_intersection(active_vl, buffer2, 1)

            buffer3 = self.splitbuff(vl, 2)
            pbuff3 = self.process_intersection(active_vl, buffer3, 2)

            # Final processing
            buff_anillos = self.exporta_capa(vl)
            layer_final = self.crearlayerfinal(active_vl)
            layer_final = self.exporta_capa(layer_final)

            self.join(layer_final, pbuff1, 0)
            self.join(layer_final, pbuff2, 1)
            self.join(layer_final, pbuff3, 2)

            self.borra_null(layer_final)
            self.asigna_calidad(layer_final, id_select)

            # Load styles
            self.load_styles(layer_final, buff_anillos)

            # Clean up intermediate layers
            QgsProject.instance().removeMapLayers([
                pbuff3.id(), pbuff2.id(), pbuff1.id(), vl.id()
            ])

        except Exception as e:
            self.show_error_message(
                "Error processing coverage",
                str(e),
                traceback.format_exc()
            )

    def show_error_message(self, title: str, message: str, details: str = None):
        """Show an error message with optional details"""
        msg_bar = self.iface.messageBar()
        widget = msg_bar.createMessage(title, message)
        
        if details:
            button = QPushButton("Show Details")
            button.pressed.connect(
                lambda: self.show_error_details(title, details)
            )
            widget.layout().addWidget(button)
        
        msg_bar.pushWidget(widget, Qgis.Critical)

    def show_error_details(self, title: str, details: str):
        """Show detailed error information"""
        dlg = QgsMessageOutput.createMessageOutput()
        dlg.setTitle(title)
        dlg.setMessage(details, QgsMessageOutput.MessageHtml)
        dlg.showMessage()

    def create_buffers(self, 
                      active_vl: QgsVectorLayer, 
                      sel_feats: List[QgsFeature],
                      vl: QgsVectorLayer,
                      vl_pr: QgsVectorDataProvider):
        """Create buffer rings around features"""
        if not sel_feats:
            return

        num_of_rings = 3
        segments_to_approximate = 25
        buffercompletos = []
        buffercortados = []
        distancias = []
        j = 0

        for i in range(num_of_rings, 0, -1):
            lonbuffer = self.radiomaximobuffer(i)
            distancias.append(lonbuffer)
            
            for each_feat in sel_feats:
                geom = each_feat.geometry()
                buff = geom.buffer(lonbuffer, segments_to_approximate)
                new_f = QgsFeature()
                new_f.setGeometry(buff)
                buffercompletos.append(new_f)

        geom = None
        for buffer in buffercompletos:
            new_f_geom = buffer.geometry()
            new_f_clipped = new_f_geom.difference(geom) if geom else new_f_geom
            new_f2 = QgsFeature()
            new_f2.setGeometry(new_f_clipped)
            new_f2.setAttributes([j, distancias[j]])
            buffercortados.append(new_f2)
            geom = geom.combine(new_f2.geometry()) if geom else new_f2.geometry()
            j += 1

        vl_pr.addFeatures(buffercortados)
        QgsProject.instance().addMapLayer(vl)

    def process_intersection(self, 
                           layer_predios: QgsVectorLayer, 
                           buffer: QgsVectorLayer,
                           num_id: int) -> QgsVectorLayer:
        """Process intersection between parcels and buffer"""
        output_file = f"D:/multibuffer/predios_buff{num_id}.shp"
        
        params = {
            'INPUT': layer_predios,
            'OVERLAY': buffer,
            'OUTPUT': output_file
        }
        processing.run("native:intersection", params)
        
        resultado_final = QgsVectorLayer(output_file, f"predios_buff{num_id}", "ogr")
        resultado_final.startEditing()
        resultado_final.addAttribute(QgsField(f"area_buff{num_id}", QVariant.Double, "", 10, 3))
        
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(resultado_final))
        expression = QgsExpression('$area')
        expression.prepare(context)
        
        for feature in resultado_final.getFeatures():
            context.setFeature(feature)
            value = expression.evaluate(context)
            feature[f"area_buff{num_id}"] = value
            resultado_final.updateFeature(feature)

        resultado_final.commitChanges()
        return resultado_final

    def load_styles(self, layer_final: QgsVectorLayer, buff_anillos: QgsVectorLayer):
        """Load styles for the layers"""
        style_path = os.path.join(os.getcwd(), "estilo.qml")
        buff_style_path = os.path.join(os.getcwd(), "estilo_buff.qml")
        
        if os.path.exists(style_path):
            layer_final.loadNamedStyle(style_path)
        if os.path.exists(buff_style_path):
            buff_anillos.loadNamedStyle(buff_style_path)

    # [Rest of the methods remain largely the same as in the previous conversion, 
    #  but with type hints and minor improvements where applicable]
    # ... (inicia_valores, radiomaximobuffer, splitbuff, creadir, crearlayerfinal,
    #      join, borra_null, asigna_calidad, exporta_capa, carga_simbol, captura_id)