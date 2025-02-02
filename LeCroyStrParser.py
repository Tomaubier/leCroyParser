""" LecroyStrParser.py
(c) Benno Meier, 2018 published under an MIT license.

LecroyStrParser.py is derived from the matlab programme ReadLeCroyBinaryWaveform.m,
which is available at Matlab Central.
a useful resource for modifications is the LeCroy Remote Control Manual
available at http://cdn.teledynelecroy.com/files/manuals/dda-rcm-e10.pdf
------------------------------------------------------
Original version (c)2001 Hochschule fr Technik+Architektur Luzern
Fachstelle Elektronik
6048 Horw, Switzerland
Slightly modified by Alan Blankman, LeCroy Corporation, 2006

Further elements for the code were taken from pylecroy, written by Steve Bian
Slightly modified by Tom Aubier to support binary string decoding.

LecroyStrParser defines the ScopeData object.
Tested in Python 3.7
"""

import sys
import numpy as np

class ScopeData:
    """
    Decodes LeCroy scope data stored in binaryString given as an argument.
    """
    def __init__(self, binaryString):
        self.binaryString = binaryString
        self.x, self.y = self.parseBinaryData()

    def parseBinaryData(self):
        self.endianness = "<"

        waveSourceList = ["Channel 1", "Channel 2", "Channel 3", "Channel 4", "Unknown"]
        verticalCouplingList = ["DC50", "GND", "DC1M", "GND", "AC1M"]
        bandwidthLimitList = ["off", "on"]
        recordTypeList = ["single_sweep", "interleaved", "histogram", "graph",
                          "filter_coefficient", "complex", "extrema", "sequence_obsolete",
                          "centered_RIS", "peak_detect"]
        processingList = ["No Processing", "FIR Filter", "interpolated", "sparsed",
                          "autoscaled", "no_resulst", "rolling", "cumulative"]

        #convert the first 50 bytes to a string to find position of substring WAVEDESC
        self.posWAVEDESC = self.binaryString[:50].decode("ascii").index("WAVEDESC")

        self.commOrder = self.parseInt16(34) #big endian (>) if 0, else little
        self.endianness = [">", "<"][self.commOrder]

        self.templateName = self.parseString(16)
        self.commType = self.parseInt16(32) # encodes whether data is stored as 8 or 16bit


        self.waveDescriptor = self.parseInt32(36)
        self.userText = self.parseInt32(40)
        self.trigTimeArray = self.parseInt32(48)
        self.waveArray1 = self.parseInt32(60)

        self.instrumentName = self.parseString(76)
        self.instrumentNumber = self.parseInt32(92)

        self.traceLabel = "NOT PARSED"
        self.waveArrayCount = self.parseInt32(116)

        self.verticalGain = self.parseFloat(156)
        self.verticalOffset = self.parseFloat(160)

        self.nominalBits = self.parseInt16(172)

        self.horizInterval = self.parseFloat(176)
        self.horizOffset = self.parseDouble(180)

        self.vertUnit = "NOT PARSED"
        self.horUnit = "NOT PARSED"

        self.triggerTime = self.parseTimeStamp(296)
        self.recordType = recordTypeList[self.parseInt16(316)]
        self.processingDone = processingList[self.parseInt16(318)]
        self.timeBase = self.parseTimeBase(324)
        self.verticalCoupling = verticalCouplingList[self.parseInt16(326)]
        self.bandwidthLimit = bandwidthLimitList[self.parseInt16(334)]
        self.waveSource = waveSourceList[self.parseInt16(344)]

        self.startIndex = self.posWAVEDESC + self.waveDescriptor + self.userText + self.trigTimeArray
        # self.file.seek()

        if self.commType == 0: #data is stored in 8bit integers
            y = np.frombuffer(self.binaryString[self.startIndex:self.startIndex+self.waveArray1], dtype = np.dtype((self.endianness + "i1", self.waveArray1)))[0]
        else: #16 bit integers
            length = self.waveArray1//2
            y = np.frombuffer(self.binaryString[self.startIndex:self.startIndex+self.waveArray1], dtype = np.dtype((self.endianness + "i2", length)))[0]

        #now scale the ADC values
        y = self.verticalGain*np.array(y) - self.verticalOffset

        x = np.linspace(0, self.waveArrayCount*self.horizInterval,
                             num = self.waveArrayCount) + self.horizOffset

        return x, y

    def unpack(self, pos, formatSpecifier, length):
        """ a wrapper that reads binary data
        in a given position in the binary data string, with correct endianness, and returns the parsed
        data as a tuple, according to the format specifier. """
        x = np.frombuffer(self.binaryString[pos+self.posWAVEDESC:pos+self.posWAVEDESC+length], self.endianness + formatSpecifier)[0]
        return x

    def parseString(self, pos, length = 16):
        s = self.unpack(pos, "S{}".format(length), length)
        if sys.version_info > (3, 0):
            s = s.decode('ascii')
        return s

    def parseInt16(self, pos):
        return self.unpack(pos, "u2", 2)

    def parseWord(self, pos):
        return self.unpack(pos, "i2", 2)

    def parseInt32(self, pos):
        return self.unpack(pos, "i4", 4)

    def parseFloat(self, pos):
        return self.unpack(pos, "f4", 4)

    def parseDouble(self, pos):
        return self.unpack(pos, "f8", 8)

    def parseByte(self, pos):
        return self.unpack(pos, "u1", 1)

    def parseTimeStamp(self, pos):
        second = self.parseDouble(pos)
        minute = self.parseByte(pos + 8)
        hour = self.parseByte(pos + 9)
        day = self.parseByte(pos + 10)
        month = self.parseByte(pos + 11)
        year = self.parseWord(pos + 12)

        return "{}-{:02d}-{:02d} {:02d}:{:02d}:{:.2f}".format(year, month, day,
                                                              hour, minute, second)

    def parseTimeBase(self, pos):
        """ time base is an integer, and encodes timing information as follows:
        0 : 1 ps  / div
        1:  2 ps / div
        2:  5 ps/div, up to 47 = 5 ks / div. 100 for external clock"""

        timeBaseNumber = self.parseInt16(pos)

        if timeBaseNumber < 48:
            unit = "pnum k"[int(timeBaseNumber/9)]
            value = [1, 2, 5, 10, 20, 50, 100, 200, 500][timeBaseNumber % 9]
            return "{} ".format(value) + unit.strip() + "s/div"
        elif timeBaseNumber == 100:
            return "EXTERNAL"

    def __repr__(self):
        string = "Le Croy Scope Data\n"
        string += "Endianness: " + self.endianness + "\n"
        string += "Instrument: " + self.instrumentName + "\n"
        string += "Instrunemt Number: " + str(self.instrumentNumber) + "\n"
        string += "Template Name: " + self.templateName + "\n"
        string += "Channel: " + self.waveSource + "\n"
        string += "Vertical Coupling: " + self.verticalCoupling + "\n"
        string += "Bandwidth Limit: " + self.bandwidthLimit + "\n"
        string += "Record Type: " + self.recordType + "\n"
        string += "Processing: " + self.processingDone + "\n"
        string += "TimeBase: " + self.timeBase + "\n"
        string += "TriggerTime: " + self.triggerTime + "\n"

        return string
