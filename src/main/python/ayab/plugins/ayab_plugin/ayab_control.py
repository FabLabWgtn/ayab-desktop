# -*- coding: utf-8 -*-
# This file is part of AYAB.
#
#    AYAB is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    AYAB is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with AYAB.  If not, see <http://www.gnu.org/licenses/>.
#
#    Copyright 2013, 2014 Sebastian Oliva, Christian Obersteiner, Andreas Müller, Christian Gerbrandt
#    https://github.com/AllYarnsAreBeautiful/ayab-desktop

from .ayab_communication import AyabCommunication
from . import ayab_image
import math
import logging
import os
import sys
from ayab.plugins.knitting_plugin import KnittingPlugin
from PyQt5 import QtGui, QtWidgets, QtCore
from enum import Enum

from .ayab_options import Ui_DockWidget
import serial.tools.list_ports

import pprint

class KnittingMode(Enum):
    SINGLEBED = 0
    CLASSIC_RIBBER_1 = 1            # Classic Ribber 1
    #CLASSIC_RIBBER_2 = 2            # Classic Ribber 2
    MIDDLECOLORSTWICE_RIBBER = 2    # Middle-Colors-Twice Ribber
    HEARTOFPLUTO_RIBBER = 3         # Heart-of-Pluto Ribber
    CIRCULAR_RIBBER = 4             # Circular Ribber

class AyabPluginControl(KnittingPlugin):

  def onknit(self, e):
    self.__logger.debug("called onknit on AyabPluginControl")

    if self.conf["continuousReporting"] == True:
        self.options_ui.tabWidget.setCurrentIndex(1)

    self.__knitImage(self.__image, self.conf)
    self.finish()

  def onconfigure(self, e):
    self.__logger.debug("called onconfigure on AYAB Knitting Plugin")
    #print ', '.join("%s: %s" % item for item in vars(e).items())
    #FIXME: substitute setting parent_ui from self.__parent_ui
    #self.__parent_ui = e.event.parent_ui
    parent_ui = self.__parent_ui

    #Start to knit with the bottom first
    pil_image = parent_ui.pil_image.rotate(180)

    conf = self.get_configuration_from_ui(parent_ui)
    #TODO: detect if previous conf had the same image to avoid re-generating.

    self.__image = ayab_image.ayabImage(pil_image, self.conf)

    if self.validate_configuration(conf):
        self.__emit_widget_knitcontrol_enabled(True)
        self.__emit_button_knit_enabled(True)

        if conf.get("start_needle") and conf.get("stop_needle"):
            self.__image.setKnitNeedles(conf.get("start_needle"),
                                        conf.get("stop_needle"))
        if conf.get("alignment"):
            self.__image.setImagePosition(conf.get("alignment"))

        self.__image.setStartLine(conf.get("start_line"))
        self.__emit_progress(conf.get("start_line")+1, self.__image.imgHeight())
        self.__emit_color("")
    else:
        self.__emit_widget_knitcontrol_enabled(False)
        self.__emit_button_knit_enabled(False)

    return

  def validate_configuration(self, conf):
    if conf.get("start_needle") and conf.get("stop_needle"):
      if conf.get("start_needle") > conf.get("stop_needle"):
        self.__notify_user("Invalid needle start and end.", "warning")
        return False
    if conf.get("start_line") > self.__image.imgHeight():
      self.__notify_user("Start Line is larger than the image.")
      return False

    if conf.get("portname") == '':
      self.__notify_user("Please choose a valid port.")
      return False

    if conf.get("knitting_mode") == KnittingMode.SINGLEBED.value \
            and conf.get("num_colors") >= 3:
        self.__notify_user("Singlebed knitting currently supports only 2 colors", "warning")
        return False

    if conf.get("knitting_mode") == KnittingMode.CIRCULAR_RIBBER.value \
            and conf.get("num_colors") >= 3:
        self.__notify_user("Circular knitting supports only 2 colors", "warning")
        return False

    return True

  def onfinish(self, e):
    self.__logger.info("Finished Knitting.")
    self.__close_serial()
    self.__parent_ui.resetUI()

  def cancel(self):
    self.__updateNotification("Knitting cancelled")
    self._knitImage = False

  def __close_serial(self):
    self.__ayabCom.close_serial()

  def onerror(self, e):
    #TODO add message info from event
    self.__logger.error("Error while Knitting.")
    self.__close_serial()

  def __wait_for_user_action(self, message="", message_type="info"):
    """Sends the display_blocking_pop_up_signal QtSignal to main GUI thread, blocking it."""
    self.__parent_ui.signalDisplayBlockingPopUp.emit(message, message_type)

  def __notify_user(self, message="", message_type="info"):
    """Sends the display_pop_up_signal QtSignal to main GUI thread, not blocking it."""
    self.__parent_ui.signalDisplayPopUp.emit(message, message_type)

  def __updateNotification(self, message=""):
    """Sends the signalUpdateNotification signal"""
    self.__parent_ui.signalUpdateNotification.emit(message)

  def __emit_progress(self, row, total = 0, repeats = 0):
    """Sends the updateProgress QtSignal."""
    self.__parent_ui.signalUpdateProgress.emit(int(row),
                                               int(total),
                                               int(repeats))

  def __emit_color(self, color):
    """Sends the updateProgress QtSignal."""
    self.__parent_ui.signalUpdateColor.emit(color)

  def __emit_status(self, hall_l, hall_r, carriage_type, carriage_position):
    """Sends the updateStatus QtSignal"""
    self.__parent_ui.signalUpdateStatus.emit(hall_l, hall_r,
                                             carriage_type, carriage_position)

  def __emit_button_knit_enabled(self, enabled):
    self.__parent_ui.signalUpdateButtonKnitEnabled.emit(enabled)

  def __emit_widget_knitcontrol_enabled(self, enabled):
    self.__parent_ui.signalUpdateWidgetKnitcontrolEnabled.emit(enabled)

  def __emit_needles(self):
    """Sends the updateNeedles QtSignal."""

    start_needle_text = self.options_ui.start_needle_edit.value()
    start_needle_color = self.options_ui.start_needle_color.currentText()
    start_needle = self.readNeedleSettings(
        start_needle_color,
        start_needle_text)

    stop_needle_text = self.options_ui.stop_needle_edit.value()
    stop_needle_color = self.options_ui.stop_needle_color.currentText()
    stop_needle = self.readNeedleSettings(
        stop_needle_color,
        stop_needle_text)

    self.__parent_ui.signalUpdateNeedles.emit(start_needle, stop_needle)

  def __emit_alignment(self):
    """Sends the updateAlignment QtSignal"""
    alignment_text = self.options_ui.alignment_combo_box.currentText()
    self.__parent_ui.signalUpdateAlignment.emit(alignment_text)

  def __emit_playsound(self, event):
    self.__parent_ui.signalPlaysound.emit(event)

  def slotSetImageDimensions(self, width, height):
    """Called by Main UI on loading of an image to set Start/Stop needle
    to image width. Updates the maximum value of the Start Line UI element"""
    left_side = math.trunc(width/2)
    self.options_ui.start_needle_edit.setValue(left_side)
    self.options_ui.stop_needle_edit.setValue(width - left_side)
    self.options_ui.start_row_edit.setMaximum(height)

  def __onStartLineChanged(self):
    """ """
    start_row_edit = self.options_ui.start_row_edit.value()
    self.__emit_progress(start_row_edit)

  def setup_ui(self, parent_ui):
    """Sets up UI elements from ayab_options.Ui_DockWidget in parent_ui."""
    self.set_translator()
    self.__parent_ui = parent_ui
    self.options_ui = Ui_DockWidget()
    self.dock = parent_ui.ui.knitting_options_dock  # findChild(QtGui.QDockWidget, "knitting_options_dock")
    self.options_ui.setupUi(self.dock)
    self.options_ui.tabWidget.setTabEnabled(1, False)
    self.options_ui.label_progress.setText("")
    self.options_ui.label_direction.setText("")
    self.setup_behaviour_ui()

    # Disable "continuous reporting" checkbox and Status tab for now
    parent_ui.findChild(QtWidgets.QCheckBox, 
                        "checkBox_ContinuousReporting").setVisible(False)
    parent_ui.findChild(QtWidgets.QTabWidget, 
                        "tabWidget").removeTab(1)

  def set_translator(self):
    dirname = os.path.dirname(__file__)
    self.translator = QtCore.QTranslator()
    self.translator.load(QtCore.QLocale.system(), "ayab_options", ".", dirname, ".qm")
    app = QtCore.QCoreApplication.instance()
    app.installTranslator(self.translator)

  def unset_translator(self):
    app = QtCore.QCoreApplication.instance()
    app.removeTranslator(self.translator)

  def populate_ports(self, combo_box=None, port_list=None):
    if not combo_box:
        combo_box = self.__parent_ui.findChild(QtWidgets.QComboBox,
                                               "serial_port_dropdown")
    if not port_list:
        port_list = self.getSerialPorts()

    combo_box.clear()

    def populate(combo_box, port_list):
        for item in port_list:
          #TODO: should display the info of the device.
          combo_box.addItem(item[0])
    populate(combo_box, port_list)


  def setup_behaviour_ui(self):
    """Connects methods to UI elements."""
    conf_button = self.options_ui.configure_button  # Used instead of findChild(QtGui.QPushButton, "configure_button")
    conf_button.clicked.connect(self.conf_button_function)

    self.populate_ports()
    refresh_ports = self.options_ui.refresh_ports_button
    refresh_ports.clicked.connect(self.populate_ports)

    start_needle_edit = self.options_ui.start_needle_edit
    start_needle_edit.valueChanged.connect(self.__emit_needles)
    stop_needle_edit = self.options_ui.stop_needle_edit
    stop_needle_edit.valueChanged.connect(self.__emit_needles)

    start_needle_color = self.options_ui.start_needle_color
    start_needle_color.currentIndexChanged.connect(self.__emit_needles)
    stop_needle_color = self.options_ui.stop_needle_color
    stop_needle_color.currentIndexChanged.connect(self.__emit_needles)

    alignment_combo_box = self.options_ui.alignment_combo_box
    alignment_combo_box.currentIndexChanged.connect(self.__emit_alignment)

    start_row_edit = self.options_ui.start_row_edit
    start_row_edit.valueChanged.connect(self.__onStartLineChanged)

  def conf_button_function(self):
    self.configure()

  def cleanup_ui(self, parent_ui):
    """Cleans up UI elements inside knitting option dock."""
    #dock = parent_ui.knitting_options_dock
    dock = self.dock
    cleaner = QtCore.QObjectCleanupHandler()
    cleaner.add(dock.widget())
    self.__qw = QtGui.QWidget()
    dock.setWidget(self.__qw)
    self.unset_translator()

  def readNeedleSettings(self, color, needle):
    '''Reads the Needle Settings UI Elements and normalizes'''
    if(color == "orange"):
        return 100 - int(needle)
    elif(color == "green"):
        return 99 + int(needle)

  def get_configuration_from_ui(self, ui):
    """Creates a configuration dict from the ui elements.

    Returns:
      dict: A dict with configuration.

    """

    self.conf = {}
    continuousReporting = ui.findChild(QtWidgets.QCheckBox, 
                            "checkBox_ContinuousReporting").isChecked()
    if continuousReporting == 1:
        self.conf["continuousReporting"] = True
    else:
        self.conf["continuousReporting"] = False


    color_line_text = ui.findChild(QtWidgets.QSpinBox, "color_edit").value()
    self.conf["num_colors"] = int(color_line_text)

    # Internally, we start counting from zero (for easier handling of arrays)
    start_line_text = ui.findChild(QtWidgets.QSpinBox, "start_row_edit").value()
    self.conf["start_line"] = int(start_line_text) - 1

    start_needle_color = ui.findChild(QtWidgets.QComboBox, "start_needle_color").currentText()
    start_needle_text = ui.findChild(QtWidgets.QSpinBox, "start_needle_edit").value()

    self.conf["start_needle"] = self.readNeedleSettings(
        start_needle_color,
        start_needle_text)

    stop_needle_color = ui.findChild(QtWidgets.QComboBox, "stop_needle_color").currentText()
    stop_needle_text = ui.findChild(QtWidgets.QSpinBox, "stop_needle_edit").value()

    self.conf["stop_needle"] = self.readNeedleSettings(
        stop_needle_color,
        stop_needle_text)

    alignment_text = ui.findChild(QtWidgets.QComboBox, "alignment_combo_box").currentText()
    self.conf["alignment"] = alignment_text

    self.conf["inf_repeat"] = \
        int(ui.findChild(QtWidgets.QCheckBox, "infRepeat_checkbox").isChecked())

    knitting_mode_index = ui.findChild(QtWidgets.QComboBox, 
                                      "knitting_mode_box").currentIndex()
    self.conf["knitting_mode"] = knitting_mode_index

    serial_port_text = ui.findChild(QtWidgets.QComboBox, "serial_port_dropdown").currentText()
    self.conf["portname"] = str(serial_port_text)

    # getting file location from textbox
    filename_text = ui.findChild(QtWidgets.QLineEdit, "filename_lineedit").text()
    self.conf["filename"] = str(filename_text)

    self.__logger.debug(self.conf)
    ## Add more config options.
    return self.conf

  def getSerialPorts(self):
        """
        Returns a list of all USB Serial Ports
        """
        return list(serial.tools.list_ports.grep("USB"))

  def __init__(self):
    super(AyabPluginControl, self).__init__({})
    
    self.__logger = logging.getLogger(type(self).__name__)

    #Copying from ayab_control
    self.__API_VERSION = 0x05
    self.__ayabCom = AyabCommunication()

    self.__formerRequest = 0
    self.__lineBlock = 0

  def __del__(self):
    self.__close_serial()

###Copied from ayab_control
#####################################

  def __setBit(self, int_type, offset):
      mask = 1 << int(offset)
      return(int_type | mask)

  def __setPixel(self, bytearray_, pixel):
      numByte = int(pixel / 8)
      bytearray_[numByte] = self.__setBit(int(bytearray_[numByte]), 
                                          pixel - (8 * numByte))
      return bytearray_

  def __checkSerial(self):
        msg = self.__ayabCom.update()

        if msg == None:            
            return("none", 0)

        msgId = msg[0]
        if msgId == 0xC1:    # cnfStart
            # print "> cnfStart: " + str(ord(line[1]))
            return ("cnfStart", msg[1])

        elif msgId == 0xC3:  # cnfInfo
            # print "> cnfInfo: Version=" + str(ord(line[1]))
            api = msg[1]
            log = "API v" + str(api)

            if api >= 5:
                log += ", FW v" + str(msg[2]) + "." + str(msg[3])

            self.__logger.info(log)
            return ("cnfInfo", msg[1])

        elif msgId == 0x82:  # reqLine
            # print "> reqLine: " + str(ord(line[1]))
            return ("reqLine", msg[1])

        elif msgId == 0xC4:  # cnfTest
            return ("cnfTest", msg[1])

        elif msgId == 0x84:
            hall_l = int((msg[2] << 8) + msg[3])
            hall_r = int((msg[4] << 8) + msg[5])

            carriage_type = ""
            if msg[6] == 1:
                carriage_type = "K Carriage"
            elif msg[6] == 2:
                carriage_type = "L Carriage"
            elif msg[6] == 3:
                carriage_type = "G Carriage"

            carriage_position = int(msg[7])

            self.__emit_status(hall_l, hall_r,
                               carriage_type, carriage_position)   

            return ("indState", msg[1])

        else:
            self.__logger.debug("unknown message: ") # drop crlf
            pp = pprint.PrettyPrinter(indent=4)
            pp.pprint(msg)
            return ("unknown", 0)
            
  def __cnfLine(self, lineNumber):
        imgHeight = self.__image.imgHeight()
        lenImgExpanded = len(self.__image.imageExpanded())
        color = 0
        indexToSend = 0
        sendBlankLine = False
        lastLine = 0x00

        # TODO optimize performance
        # initialize bytearray to 0x00
        bytes = bytearray(25)
        for x in range(0, 25):
            bytes[x] = 0x00

        if lineNumber < 256:
            # TODO some better algorithm for block wrapping
            # if the last requested line number was 255, wrap to next block of
            # lines
            if self.__formerRequest == 255 and lineNumber == 0:
                self.__lineBlock += 1
            # store requested line number for next request
            self.__formerRequest = lineNumber
            reqestedLine = lineNumber

            # adjust lineNumber with current block
            lineNumber = lineNumber \
                + (self.__lineBlock * 256)


            # TODO implement CRC8
            crc8 = 0x00
            colorRow, byteRow, imageRow = self.__image.pattern()
            color = colorRow[lineNumber]
            bytes = byteRow[lineNumber]
            imgRow = imageRow[lineNumber]

            if self.__infRepeat:
                lineNumber = lineNumber % len(byteRow)

            if(lineNumber == len(colorRow)-1):
                lastLine = 0x01

            # send line to machine
            if self.__infRepeat:
              flags = 0 | sendBlankLine << 1 | color << 3
              self.__ayabCom.cnf_line(reqestedLine, bytes, flags, crc8)
            else:
              flags = lastLine | sendBlankLine << 1 | color << 3
              self.__ayabCom.cnf_line(reqestedLine, bytes, flags, crc8)

            # screen output
            colorNames = "A", "B", "C", "D", "E", "F", "G", "H"
            msg = str(self.__lineBlock) # Block
            msg += ' ' + str(lineNumber) # Total Line Number
            msg += ' reqLine: ' + str(reqestedLine)
            msg += ' imgRow: ' + str(imgRow)
            msg += ' color: ' +  colorNames[color]
            if sendBlankLine == True:
                msg += ' BLANK LINE'
            else:
                msg += ' indexToSend: ' + str(indexToSend)
                msg += ' color: ' + str(color)
                #msg += ' ' + str((self.__image.imageExpanded())[indexToSend])
            self.__logger.debug(msg)

            if self.__knitting_mode == KnittingMode.SINGLEBED.value:
                self.__emit_color("")
            elif sendBlankLine == True:
                pass
            else:
                self.__emit_color(colorNames[color])

            #sending line progress to gui
            self.__emit_progress(imgRow+1,
                                 imgHeight,
                                 self.__infRepeat_repeats)
            self.__emit_playsound("nextline")

        else:
            self.__logger.error("requested lineNumber out of range")

        if lastLine:
          if self.__infRepeat:
              self.__infRepeat_repeats += 1
              return 0  # keep knitting
          else:
              return 1  # image finished
        else:
            return 0  # keep knitting

  def __knitImage(self, pImage, pOptions):
      self.__formerRequest = 0
      self.__image = pImage
      self.__startLine = pImage.startLine()

      self.__numColors = pOptions["num_colors"]
      self.__knitting_mode = pOptions["knitting_mode"]
      self.__infRepeat = pOptions["inf_repeat"]
      self.__infRepeat_repeats = 0

      API_VERSION = self.__API_VERSION
      curState = 's_init'
      oldState = 'none'

      if not self.__ayabCom.open_serial(pOptions["portname"]):
          self.__logger.error("Could not open serial port")
          return

      self._knitImage = True
      while self._knitImage:
          # TODO catch keyboard interrupts to abort knitting
          # TODO: port to state machine or similar.
          rcvMsg, rcvParam = self.__checkSerial()
          if curState == 's_init':
              if rcvMsg == 'cnfInfo':
                  if rcvParam == API_VERSION:
                      curState = 's_waitForInit'
                      self.__updateNotification("Please init machine. (Set the carriage to mode KC-I or KC-II and move the carriage over the left turn mark).")
                  else:
                      self.__notify_user("Wrong Arduino Firmware Version. "
                                         + "Please check if you have flashed "
                                         + "the latest version. ("
                                         + str(rcvParam) + "/"
                                         + str(API_VERSION) + ")")
                      self.__logger.error("wrong API version: " + str(rcvParam)
                                        + (" ,expected: ") + str(API_VERSION))                                        
                      return
              else:
                  self.__updateNotification("Connecting to machine...")                  
                  self.__ayabCom.req_info()

          if curState == 's_waitForInit':
              if rcvMsg == "indState":
                if rcvParam == 1:
                    curState = 's_start'
                else:
                    self.__logger.debug("init failed")

          if curState == 's_start':
              if oldState != curState:
                    self.__ayabCom.req_start(self.__image.knitStartNeedle(),
                                             self.__image.knitStopNeedle(),
                                             pOptions["continuousReporting"])

              if rcvMsg == 'cnfStart':
                  if rcvParam == 1:
                      curState = 's_operate'
                      self.__updateNotification("Please Knit")
                      self.__emit_playsound("start")
                  else:
                      self.__updateNotification()
                      self.__wait_for_user_action("Device not ready, configure and try again.")
                      self.__logger.error("device not ready")
                      return

          if curState == 's_operate':
              if rcvMsg == 'reqLine':
                  imageFinished = self.__cnfLine(rcvParam)
                  if imageFinished:
                      curState = 's_finished'

          if curState == 's_finished':
              self.__updateNotification("Image transmission finished. " \
                                        "Please knit until you hear the " \
                                        "double beep sound.")
              self.__emit_playsound("finished")
              break


          oldState = curState

      self.options_ui.label_carriage.setText("No carriage detected")
      self.options_ui.tabWidget.setCurrentIndex(0)
      return
