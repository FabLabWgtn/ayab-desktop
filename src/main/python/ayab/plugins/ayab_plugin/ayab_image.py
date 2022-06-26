# -*- coding: utf-8 -*-
#This file is part of AYAB.
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
#    Copyright 2013 Christian Obersteiner, Andreas Müller, Christian Gerbrandt
#    https://github.com/AllYarnsAreBeautiful/ayab-desktop

from PIL import Image
from enum import Enum

class KnittingMode(Enum):
    SINGLEBED = 0
    CLASSIC_RIBBER_1 = 1            # Classic Ribber 1
    #CLASSIC_RIBBER_2 = 2            # Classic Ribber 2
    MIDDLECOLORSTWICE_RIBBER = 2    # Middle-Colors-Twice Ribber
    HEARTOFPLUTO_RIBBER = 3         # Heart-of-Pluto Ribber
    CIRCULAR_RIBBER = 4             # Circular Ribber


class ayabImage(object):
  def __init__(self, pil_image, pOptions):
    self.__numColors = pOptions["num_colors"]
    self.__knitting_mode = pOptions["knitting_mode"]
    self.__infRepeat = pOptions["inf_repeat"]

    self.__imgPosition    = 'center'
    self.__imgStartNeedle = '0'
    self.__imgStopNeedle  = '0'

    self.__knitStartNeedle = 0
    self.__knitStopNeedle  = 199

    self.__startLine  = 0

    self.__image = pil_image

    self.__image = self.__image.convert('L') # convert to 1 byte depth
    self.__byteRow = []
    self.__colorRow = []
    self.__imageRow = []
    self.__updateImageData()

  def imageIntern(self):
    return self.__imageIntern

  def imageExpanded(self):
    return self.__imageExpanded

  def imgWidth(self):
    return self.__imgWidth

  def imgHeight(self):
    return self.__imgHeight

  def knitStartNeedle(self):
    return self.__knitStartNeedle

  def knitStopNeedle(self):
    return self.__knitStopNeedle

  def imgStartNeedle(self):
    return self.__imgStartNeedle

  def imgStopNeedle(self):
    return self.__imgStopNeedle

  def imgPosition(self):
    return self.__imgPosition

  def startLine(self):
    return self.__startLine

  def numColors(self):
    return self.__numColors

  def pattern(self):
    return self.__colorRow, self.__byteRow, self.__imageRow

  def __updateImageData(self):
    self.__imgWidth   = self.__image.size[0]
    self.__imgHeight  = self.__image.size[1]

    self.__convertImgToIntern()
    self.__calcImgStartStopNeedles()


  def __setBit(self, int_type, offset):
      mask = 1 << int(offset)
      return(int_type | mask)

  def __setPixel(self, bytearray_, pixel):
      numByte = int(pixel / 8)
      bytearray_[numByte] = self.__setBit(int(bytearray_[numByte]),
                                          pixel - (8 * numByte))
      return bytearray_

  def __convertImgToIntern(self):
    num_colors = self.__numColors
    clr_range  = float(256)/num_colors

    imgWidth   = self.__imgWidth
    imgHeight  = self.__imgHeight

    self.__imageIntern = \
      [[0 for i in range(imgWidth)] \
      for j in range(imgHeight)]
    self.__imageColors = \
      [[0 for i in range(num_colors)] \
      for j in range(imgHeight)]
    self.__imageExpanded = \
      [[0 for i in range(imgWidth)] \
      for j in range(num_colors*imgHeight)]

    # Distill image to x colors
    for row in range(0, imgHeight):
      for col in range(0, imgWidth):
        pxl = self.__image.getpixel((col, row))

        for color in range(0, num_colors):
          lowerBound = int(color*clr_range)
          upperBound = int((color+1)*clr_range)
          if pxl>=lowerBound and pxl<upperBound:
            # color map
            self.__imageIntern[row][col]    = color
            # amount of bits per color per line
            self.__imageColors[row][color]  += 1
            # colors separated per line
            self.__imageExpanded[(num_colors*row)+color][col] = 1



    lenImgExpanded = len(self.imageExpanded())
    byteRow = []
    colorRow = []
    imageRow = []

    for lineNumber in range(lenImgExpanded):
        bytes = bytearray(25)
        reqestedLine = lineNumber
        sendBlankLine = False

        #########################
        # decide which line to send according to machine type and amount of colors
        # singlebed, 2 color
        if self.__knitting_mode == KnittingMode.SINGLEBED.value \
                and self.__numColors == 2:

            # when knitting infinitely, keep the requested
            # lineNumber in its limits
            if self.__infRepeat:
                lineNumber = lineNumber % imgHeight

            # color is always 0 in singlebed,
            # because both colors are knitted at once
            color = 0

            # calculate imgRow
            imgRow = (lineNumber + self.__startLine) % imgHeight

            # 0   1   2   3   4 .. (imgRow)
            # |   |   |   |   |
            # 0 1 2 3 4 5 6 7 8 .. (imageExpanded)
            indexToSend = imgRow * 2

        # doublebed, 2 color
        elif self.__knitting_mode == KnittingMode.CLASSIC_RIBBER_1.value and self.__numColors == 2:

            # calculate imgRow
            imgRow = (int(lineNumber / 2) + self.__startLine) % imgHeight

            # 0 0 1 1 2 2 3 3 4 4 .. (imgRow)
            # 0 1 2 3 4 5 6 7 8 9 .. (lineNumber)
            # | |  X  | |  X  | |
            # 0 1 3 2 4 5 7 6 8 9 .. (imageExpanded)
            # A B B A A B B A A B .. (color)
            indexToSend = self.__startLine * 2

            color = 0  # A
            if lineNumber % 4 == 1 or lineNumber % 4 == 2:
                color = 1  # B

            # Decide if lineNumber has to be switched or not
            if reqestedLine % 4 == 2:
                indexToSend += lineNumber + 1
            elif reqestedLine % 4 == 3:
                indexToSend += lineNumber - 1
            else:
                indexToSend += lineNumber

            indexToSend = indexToSend % lenImgExpanded

        # doublebed, multicolor
        elif self.__knitting_mode == KnittingMode.CLASSIC_RIBBER_1.value \
                and self.__numColors > 2:


            # calculate imgRow
            imgRow = (int(
                lineNumber / (self.__numColors * 2)) + self.__startLine) % imgHeight

            if (lineNumber % 2) == 1:
                sendBlankLine = True
            # else:
            #     self.__logger.debug("COLOR" + str(color))

            color = int((lineNumber / 2) % self.__numColors)

            #indexToSend = self.__startLine * self.__numColors
            indexToSend = int((imgRow * self.__numColors) + color)

            indexToSend = indexToSend % lenImgExpanded

        # Ribber, Middle-Colors-Twice
        elif self.__knitting_mode == KnittingMode.MIDDLECOLORSTWICE_RIBBER.value:

            # doublebed middle-colors-twice multicolor
            # 0-00 1-11 2-22 3-33 4-44 5-55 .. (imgRow)
            # 0123 4567 8911 1111 1111 2222.. (lineNumber)
            #             01 2345 6789 0123
            #
            # 0-21 4-53 6-87 1-19 1-11 1-11 .. (imageExpanded)
            #                0 1  2 43 6 75
            #
            # A-CB B-CA A-CB B-CA A-CB B-CA .. (color)

            #Double the line minus the 2 you save on the beg and end of each imgRow
            passesPerRow = self.__numColors * 2 - 2

            imgRow = self.__startLine + int(lineNumber/passesPerRow)

            indexToSend = imgRow * self.__numColors

            if imgRow % 2 != 0:
                color = int(((lineNumber % passesPerRow) + 1) / 2)
            else:
                color = int((passesPerRow - (lineNumber % passesPerRow)) / 2)

            if lineNumber % passesPerRow == 0 or (lineNumber + 1) % passesPerRow == 0 or lineNumber % 2 ==0:
                sendBlankLine = False
            else:
                sendBlankLine = True

            indexToSend += color

        # doublebed, multicolor <3 of pluto - advances imgRow as soon as possible
        elif self.__knitting_mode == KnittingMode.HEARTOFPLUTO_RIBBER.value \
                and self.__numColors >= 2:
            #Double the line minus the 2 you save from early advancing to next row
            passesPerRow = num_colors * 2 - 2

            imgRow = self.__startLine + int(lineNumber/passesPerRow)


            indexToSend = imgRow * num_colors

            #check if it's time to send a blank line
            if lineNumber % passesPerRow != 0 and lineNumber % 2 == 0:
                sendBlankLine = True
            #if not set a color
            else:
                color = num_colors - 1 - int(((lineNumber + 1) % (num_colors * 2)) / 2)
            #use color to adjust index
            indexToSend += color


        # Ribber, Circular
        elif self.__knitting_mode == KnittingMode.CIRCULAR_RIBBER.value \
                and self.__numColors == 2:


            imgRow = (int(lineNumber / 4) + self.__startLine) % imgHeight

            # Color      A B  A B  A B
            # ImgRow     0-0- 1-1- 2-2-
            # Index2Send 0 1  2 3  4 5
            # LineNumber 0123 4567 8911
            #                        01

            if (lineNumber % 2) == 1:
                sendBlankLine = True

            indexToSend = self.__startLine * self.__numColors
            indexToSend += lineNumber / 2
            indexToSend = int(indexToSend)

            indexToSend = indexToSend % lenImgExpanded



        ### CALC bytes

        imgStartNeedle = self.imgStartNeedle()
        if imgStartNeedle < 0:
            imgStartNeedle = 0

        imgStopNeedle = self.imgStopNeedle()
        if imgStopNeedle > 199:
            imgStopNeedle = 199

        # set the bitarray
        if (color == 0 and self.__knitting_mode == KnittingMode.CLASSIC_RIBBER_1.value)\
                or ( color == self.__numColors - 1 \
                        and (self.__knitting_mode == KnittingMode.MIDDLECOLORSTWICE_RIBBER.value \
                                or self.__knitting_mode == KnittingMode.HEARTOFPLUTO_RIBBER.value )):

            for col in range(0, 200):
                if col < imgStartNeedle \
                        or col > imgStopNeedle:
                    bytes = self.__setPixel(bytes, col)

        for col in range(0, self.imgWidth()):
            pxl = (self.imageExpanded())[indexToSend][col]
            # take the image offset into account
            if pxl == True and sendBlankLine == False:
                pxlNumber = col + self.imgStartNeedle()
                # TODO implement for generic machine width
                if  0 <= pxlNumber and pxlNumber < 200:
                    bytes = self.__setPixel(bytes, pxlNumber)
        if ((self.__knitting_mode != KnittingMode.SINGLEBED.value\
                and self.__knitting_mode != KnittingMode.CIRCULAR_RIBBER.value)\
                        and sum(bytes)==0 and sum(byteRow[-1])==0 and color == colorRow[-1]):
            byteRow.pop()
            colorRow.pop()
            imageRow.pop()
        else:
            byteRow.append(bytes)
            colorRow.append(color)
            imageRow.append(imgRow)

    for color,image,row in zip(colorRow,imageRow, byteRow):
        print(color, image, row)
    self.__byteRow = byteRow
    self.__colorRow = colorRow
    self.__imageRow = imageRow
    #print(self.__imageIntern)
    #print(self.__imageColors)
    #print(self.__imageExpanded)


  def __calcImgStartStopNeedles(self):
    if self.__imgPosition == 'center':
        needleWidth = (self.__knitStopNeedle - self.__knitStartNeedle) +1
        self.__imgStartNeedle = (self.__knitStartNeedle + needleWidth/2) - self.__imgWidth/2
        self.__imgStopNeedle  = self.__imgStartNeedle + self.__imgWidth -1

    elif self.__imgPosition == 'left':
        self.__imgStartNeedle = self.__knitStartNeedle
        self.__imgStopNeedle  = self.__imgStartNeedle + self.__imgWidth

    elif self.__imgPosition == 'right':
        self.__imgStopNeedle  = self.__knitStopNeedle
        self.__imgStartNeedle = self.__imgStopNeedle - self.__imgWidth

    elif int(self.__imgPosition) > 0 and int(self.__imgPosition) < 200:
        self.__imgStartNeedle = int(self.__imgPosition)
        self.__imgStopNeedle  = self.__imgStartNeedle + self.__imgWidth

    else:
        return False
    return True

  def setNumColors(self, pNumColors):
      """
      sets the number of colors the be used for knitting
      """
      if pNumColors > 1 and pNumColors < 7:
        self.__numColors      = pNumColors
        self.__updateImageData()
      return

  def invertImage(self):
      """
      invert the pixels of the image
      """
      for y in range(0, self.__image.size[1]):
        for x in range(0, self.__image.size[0]):
          pxl = self.__image.getpixel((x, y))
          self.__image.putpixel((x,y),255-pxl)
      self.__updateImageData()
      return


  def rotateImage(self):
      """
      rotate the image 90 degrees clockwise
      """
      self.__image = self.__image.rotate(-90)

      self.__updateImageData()
      return


  def resizeImage(self, pNewWidth):
      """
      resize the image to a given width, keeping the aspect ratio
      """
      wpercent = (pNewWidth/float(self.__image.size[0]))
      hsize = int((float(self.__image.size[1])*float(wpercent)))
      self.__image = self.__image.resize((pNewWidth,hsize), Image.ANTIALIAS)

      self.__updateImageData()
      return

  def repeatImage(self, pHorizontal=1, pVertical=1):
      """
      Repeat image.
      Repeat pHorizontal times horizontally, pVertical times vertically
      Sturla Lange 2017-12-30
      """
      old_h = self.__image.size[1]
      old_w = self.__image.size[0]
      new_h = old_h*pVertical
      new_w = old_w*pHorizontal
      new_im = Image.new('RGB', (new_w,new_h))
      for h in range(0,new_h,old_h):
        for w in range(0,new_w,old_w):
          new_im.paste(self.__image, (w,h))
      self.__image = new_im
      self.__updateImageData()
      return


  def setKnitNeedles(self, pKnitStart, pKnitStop):
      """
      set the start and stop needle
      """
      if (pKnitStart < pKnitStop) \
          and pKnitStart >= 0 \
          and pKnitStop < 200:
        self.__knitStartNeedle = pKnitStart
        self.__knitStopNeedle  = pKnitStop

      self.__updateImageData()
      return


  def setImagePosition(self, pImgPosition):
      """
      set the position of the pattern
      """
      ok = False
      if pImgPosition == 'left' \
            or pImgPosition == 'center' \
            or pImgPosition == 'right':
        ok = True
      elif (int(pImgPosition) >= 0 and int(pImgPosition) < 200):
        ok = True

      if ok:
        self.__imgPosition = pImgPosition
        self.__updateImageData()
      return

  def setStartLine(self, pStartLine):
      """
      set the line where to start knitting
      """
      #Check if StartLine is in valid range (picture height)
      if pStartLine >= 0 \
            and pStartLine < self.__image.size[1]:
        self.__startLine = pStartLine
      return
