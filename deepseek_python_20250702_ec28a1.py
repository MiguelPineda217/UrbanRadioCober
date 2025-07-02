# -*- coding: utf-8 -*-
"""
/***************************************************************************
 UrbanRadioCober
                                 A QGIS plugin
 urban radiocober simulator plugin for omnidirectional radio coverage in urban environment
                              -------------------
        begin                : 2015-11-11
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Mario Salazar, Leonardo Cifuentes, Jhon Castaneda
        email                : dlcifuentesl@gmail.com, mario_salazarb@hotmail.com, jhonjaingambiental@gmail.com
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
from qgis.PyQt.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QPushButton
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsField, QgsWkbTypes, 
    QgsVectorFileWriter, QgsExpression, QgsFeatureRequest, QgsDistanceArea,
    QgsMapLayer, QgsMessageLog, Qgis, QgsExpressionContext, QgsExpressionContextUtils
)
from qgis.analysis import QgsNativeAlgorithms
from qgis.gui import QgsMessageBar
import processing

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
import functools

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
        self.plugin_dir = os.path.dirname(__file__)
        
        # initialize locale
        locale = QSettings().value('locale/userLocale', 'en')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            f'UrbanRadioCober_{locale}.qm')

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Create the dialog and keep reference
        self.dlg = UrbanRadioCoberDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr('&Urban RadioCober')
        self.toolbar = self.iface.addToolBar('UrbanRadioCober')
        self.toolbar.setObjectName('UrbanRadioCober')

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
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
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons."""
        icon_path = ':/plugins/UrbanRadioCober/icon.png'
        self.add_action(
            icon_path,
            text=self.tr('Urban RadioCober'),
            callback=self.run,
            parent=self.iface.mainWindow())

        self.inicia_valores()
        self.creadir()

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr('&Urban RadioCober'), action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run(self):
        """Run method that performs all the real work"""
        try:
            active_vl = self.iface.activeLayer()
            if not active_vl:
                self.show_warning(self.tr("Please select a vector layer"))
                return

            if active_vl.type() != QgsMapLayer.VectorLayer:
                self.show_warning(self.tr("Selected layer is not a vector layer"))
                return

            self.dlg.populatedialogue(active_vl.name())
            sel_feats = active_vl.selectedFeatures()
            self.dlg.selectedfeats(1 if sel_feats else 0)
            
            if not self.dlg.exec_():
                return

            self.process_coverage(active_vl)

        except Exception as e:
            self.show_exception(e)

    def process_coverage(self, active_vl):
        """Process the radio coverage analysis"""
        try:
            # Create buffer layer
            buffer_crs = active_vl.crs().authid()
            vl = QgsVectorLayer(f"Polygon?crs={buffer_crs}", "Buffer_Cobertura", "memory")
            vl_pr = vl.dataProvider()
            vl_pr.addAttributes([
                QgsField("FID", QVariant.Int), 
                QgsField("distance", QVariant.Double, "", 10, 3)
            ])
            vl.updateFields()

            id_select = self.captura_id(active_vl)
            sel_feats = list(active_vl.selectedFeatures())
            
            if not sel_feats:
                self.show_warning(self.tr("No features selected"))
                return

            # Create buffers
            buffercompletos = []
            buffercortados = []
            distancias = []
            
            for i in range(3, 0, -1):
                lonbuffer = self.radiomaximobuffer(i)
                distancias.append(lonbuffer)
                
                for feature in sel_feats:
                    geom = feature.geometry()
                    buff = geom.buffer(lonbuffer, 25)
                    new_f = QgsFeature()
                    new_f.setGeometry(buff)
                    buffercompletos.append(new_f)

            # Clip buffers
            geom = sel_feats[0].geometry()
            for j, buffer in enumerate(buffercompletos):
                new_f_geom = buffer.geometry()
                new_f_clipped = new_f_geom.difference(geom)
                new_f2 = QgsFeature()
                new_f2.setGeometry(new_f_clipped)
                new_f2.setAttributes([j, distancias[j]])
                buffercortados.append(new_f2)
                geom = geom.combine(new_f2.geometry())

            vl_pr.addFeatures(buffercortados)
            QgsProject.instance().addMapLayer(vl)

            # Process each buffer level
            for i in range(3):
                buffer_layer = self.splitbuff(vl, i)
                pbuff = self.intersect(active_vl, buffer_layer, i)
                pbuff = self.exporta_capa(pbuff)
                
                if i == 0:
                    layer_final = self.crearlayerfinal(active_vl)
                    layer_final = self.exporta_capa(layer_final)
                
                self.join(layer_final, pbuff, i)
                QgsProject.instance().removeMapLayer(pbuff.id())

            self.post_processing(layer_final, vl, id_select)

        except Exception as e:
            self.show_exception(e)

    def post_processing(self, layer_final, vl, id_select):
        """Final processing steps"""
        self.borra_null(layer_final)
        self.asigna_calidad(layer_final, id_select)
        
        # Load styles
        estilo_path = os.path.join(os.getcwd(), "estilo.qml")
        estilo_buff_path = os.path.join(os.getcwd(), "estilo_buff.qml")
        
        if os.path.exists(estilo_path):
            self.carga_simbol(layer_final, estilo_path)
        if os.path.exists(estilo_buff_path):
            self.carga_simbol(vl, estilo_buff_path)

    def show_warning(self, message):
        """Show a warning message"""
        QMessageBox.warning(self.iface.mainWindow(), "Warning", message)

    def show_exception(self, e):
        """Show exception details"""
        exc_type, exc_value, exc_traceback = sys.exc_info()
        showException(
            exc_type, exc_value, exc_traceback,
            self.tr("An error occurred while processing"),
            messagebar=True
        )

    # Rest of the methods remain largely the same as in the previous conversion,
    # but with added error handling and type hints where appropriate
    
    def inicia_valores(self):
        """Initialize default values in the dialog"""
        try:
            self.dlg.ui.txtcodU_6.setText("31")  # Potencia de Transmisor (dBm)
            self.dlg.ui.txtcodU_5.setText("1900")  # Frecuencia Operación (MHz)
            self.dlg.ui.txtAreaU_8.setText("16")  # Ganancia de antena (dB)
            self.dlg.ui.txtNomU_4.setText("3")  # Perdidas de conectores(dB)
            self.dlg.ui.txtNomU_7.setText("-69")  # Sensibilidad minima (dB)
            self.dlg.ui.txtAreaU_7.setText("3")  # Numero de obstaculos (n)
            self.dlg.ui.txtAreaU_9.setText("3")  # Ganancia de antena (dB)
        except Exception as e:
            self.show_exception(e)

    def radiomaximobuffer(self, num: int) -> float:
        """Calculate maximum buffer radius"""
        try:
            potencia = float(self.dlg.ui.txtcodU_6.text())  # Potencia de Transmisor (dBm)
            frecuencia = float(self.dlg.ui.txtcodU_5.text())  # Frecuencia Operación (MHz)
            ganacia_trans = float(self.dlg.ui.txtAreaU_8.text())  # Ganancia de antena (dB)
            perdida = float(self.dlg.ui.txtNomU_4.text())  # Perdidas de conectores(dB)
            sensibilidad = float(self.dlg.ui.txtNomU_7.text())  # Sensibilidad minima (dB)
            num_obstaculos = float(self.dlg.ui.txtAreaU_7.text())  # Numero de obstaculos (n)
            ganacia_recep = float(self.dlg.ui.txtAreaU_9.text())  # Ganancia de antena (dB)
            tipo = self.dlg.ui.comboBox_5.currentText()

            if tipo == "Residencial":
                nn = 28
                lf = 4 * num_obstaculos
            elif tipo == "Oficinas":
                nn = 30
                lf = 15 + (4 * (num_obstaculos - 1))
            elif tipo == "Comercial/industrial":
                nn = 22
                lf = 6 + (3 * (num_obstaculos - 1))

            rval_positivos = potencia + ganacia_trans + ganacia_recep + 28

            if num == 3:
                rval_negativos = sensibilidad + perdida + 20 * math.log10(frecuencia) + lf
            elif num == 2:
                rval_negativos = sensibilidad * (0.8) + perdida + 20 * math.log10(frecuencia) + lf
            elif num == 1:
                rval_negativos = sensibilidad * (0.5) + perdida + 20 * math.log10(frecuencia) + lf

            radio_base = (rval_positivos - rval_negativos) / nn
            return math.pow(10, radio_base)
        except Exception as e:
            self.show_exception(e)
            return 0.0

    def splitbuff(self, layer_buff, num_id: int) -> QgsVectorLayer:
        """Split buffer layer by ID"""
        try:
            crs = self.iface.activeLayer().crs().authid()
            layer = QgsVectorLayer(f"Polygon?crs={crs}", f"buff{num_id}", "memory")
            layer_pr = layer.dataProvider()
            
            layer.startEditing()
            layer_pr.addAttributes([
                QgsField("FID", QVariant.Int),
                QgsField("distance", QVariant.Double, "", 10, 3)
            ])
            layer.commitChanges()
            
            for feature in layer_buff.getFeatures(QgsFeatureRequest().setFilterExpression(f'"FID" = {num_id}')):
                layer_pr.addFeatures([feature])
                
            return layer
        except Exception as e:
            self.show_exception(e)
            return None

    def intersect(self, layer_predios, buffer, num_id: int) -> QgsVectorLayer:
        """Intersect layers and calculate areas"""
        try:
            output_path = f"D:/multibuffer/predios_buff{num_id}.shp"
            params = {
                'INPUT': layer_predios,
                'OVERLAY': buffer,
                'OUTPUT': output_path
            }
            processing.run("native:intersection", params)
            
            result = QgsVectorLayer(output_path, f"predios_buff{num_id}", "ogr")
            result.startEditing()
            result.addAttribute(QgsField(f"area_buff{num_id}", QVariant.Double, "", 10, 3))
            
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(result))
            expression = QgsExpression('$area')
            expression.prepare(context)
            
            for feature in result.getFeatures():
                context.setFeature(feature)
                value = expression.evaluate(context)
                feature[f"area_buff{num_id}"] = value
                result.updateFeature(feature)
                
            result.commitChanges()
            return result
        except Exception as e:
            self.show_exception(e)
            return None

    def creadir(self):
        """Create working directory"""
        try:
            directory = "D:/multibuffer"
            if not os.path.exists(directory):
                os.makedirs(directory)
        except Exception as e:
            self.show_exception(e)

    def crearlayerfinal(self, layer_predios) -> QgsVectorLayer:
        """Create final output layer"""
        try:
            crs = self.iface.activeLayer().crs().authid()
            result = QgsVectorLayer(f"Polygon?crs={crs}", "Tipo de Cobertura", "memory")
            result.startEditing()
            result.dataProvider().addAttributes(list(layer_predios.dataProvider().fields()))
            
            for feature in layer_predios.getFeatures():
                result.dataProvider().addFeatures([feature])
                
            result.addAttribute(QgsField("area_lote", QVariant.Double, "", 10, 3))
            
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(result))
            expression = QgsExpression('$area')
            expression.prepare(context)
            
            for feature in result.getFeatures():
                context.setFeature(feature)
                value = expression.evaluate(context)
                feature["area_lote"] = value
                result.updateFeature(feature)
                
            result.commitChanges()
            return result
        except Exception as e:
            self.show_exception(e)
            return None

    def join(self, layer_predios, layer_buff, num_id: int):
        """Join attributes from buffer to parcels"""
        try:
            join_info = QgsVectorLayerJoinInfo()
            join_info.setJoinLayerId(layer_buff.id())
            join_info.setJoinFieldName("gid")
            join_info.setTargetFieldName("gid")
            join_info.setUsingMemoryCache(True)
            join_info.setPrefix(f"{layer_buff.name()}_")
            layer_predios.addJoin(join_info)
            
            layer_predios.startEditing()
            layer_predios.addAttribute(QgsField(f"area_buff{num_id}", QVariant.Double, "", 10, 3))
            
            context = QgsExpressionContext()
            context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer_predios))
            expression = QgsExpression(f'"{layer_buff.name()}_area_buff{num_id}"')
            expression.prepare(context)
            
            for feature in layer_predios.getFeatures():
                context.setFeature(feature)
                value = expression.evaluate(context)
                feature[f"area_buff{num_id}"] = value
                layer_predios.updateFeature(feature)
                
            layer_predios.commitChanges()
            layer_predios.removeJoin(layer_buff.id())
        except Exception as e:
            self.show_exception(e)

    def borra_null(self, layer_final):
        """Replace NULL values with 0"""
        try:
            layer_final.startEditing()
            for feature in layer_final.getFeatures():
                for field in ["area_buff0", "area_buff1", "area_buff2"]:
                    if feature[field] is None:
                        feature[field] = 0
                        layer_final.updateFeature(feature)
            layer_final.commitChanges()
        except Exception as e:
            self.show_exception(e)

    def asigna_calidad(self, layer_final, id_selfea: int):
        """Assign signal quality categories"""
        try:
            layer_final.startEditing()
            layer_final.addAttribute(QgsField("Signal", QVariant.String, "", 10))
            
            for feature in layer_final.getFeatures():
                area0 = feature["area_buff0"] or 0
                area1 = feature["area_buff1"] or 0
                area2 = feature["area_buff2"] or 0
                
                if feature["gid"] == id_selfea:
                    feature["Signal"] = "High"
                elif area0 > area1 and area0 > area2:
                    feature["Signal"] = "High"
                elif area1 > area0 and area1 > area2:
                    feature["Signal"] = "Medium"
                elif area2 > area0 and area2 > area1:
                    feature["Signal"] = "Low"
                else:
                    feature["Signal"] = "No signal"
                    
                layer_final.updateFeature(feature)
                
            layer_final.commitChanges()
        except Exception as e:
            self.show_exception(e)

    def exporta_capa(self, capa) -> QgsVectorLayer:
        """Export layer to shapefile"""
        try:
            output_path = f"D:/multibuffer/ly_{capa.name()}.shp"
            QgsVectorFileWriter.writeAsVectorFormat(
                capa, output_path, "utf-8", capa.crs(), "ESRI Shapefile")
            result = QgsVectorLayer(output_path, capa.name(), "ogr")
            QgsProject.instance().addMapLayer(result)
            return result
        except Exception as e:
            self.show_exception(e)
            return None

    def carga_simbol(self, layer, symbol_path: str):
        """Load layer style"""
        try:
            if os.path.exists(symbol_path):
                layer.loadNamedStyle(symbol_path)
        except Exception as e:
            self.show_exception(e)

    def captura_id(self, capa) -> int:
        """Get selected feature ID"""
        try:
            selected = capa.selectedFeatures()
            return selected[0]["gid"] if selected else -1
        except Exception as e:
            self.show_exception(e)
            return -1