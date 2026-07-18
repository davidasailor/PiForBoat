class Vedirect:

    def __init__(self):

        self.header1 = ord('\r')
        self.header2 = ord('\n')
        self.hexmarker = ord(':')
        self.delimiter = ord('\t')
        self.key = ''
        self.value = ''
        self.bytes_sum = 0;
        self.state = self.WAIT_HEADER
        self.dict = {}


    (HEX, WAIT_HEADER, IN_KEY, IN_VALUE, IN_CHECKSUM) = range(5)

    def input(self, byte):

        if byte == self.hexmarker and self.state != self.IN_CHECKSUM:
            self.state = self.HEX
        
        if self.state == self.WAIT_HEADER:
            self.bytes_sum = self.bytes_sum + byte
            if byte == self.header1:
                self.state = self.WAIT_HEADER
            elif byte == self.header2:
                self.state = self.IN_KEY
            return None
        elif self.state == self.IN_KEY:
            self.bytes_sum = self.bytes_sum + byte
            if byte == self.delimiter:
                if (self.key == 'Checksum'):
                    self.state = self.IN_CHECKSUM
                else:
                    self.state = self.IN_VALUE
            else:
                self.key = self.key + chr(byte)
            return None
        elif self.state == self.IN_VALUE:
            self.bytes_sum = self.bytes_sum + byte
            if byte == self.header1:
                self.state = self.WAIT_HEADER
                self.dict[self.key] = self.value;
                self.key = '';
                self.value = '';
            else:
                self.value = self.value + chr(byte)
            return None
        elif self.state == self.IN_CHECKSUM:

            self.bytes_sum = self.bytes_sum + byte
            self.key = ''
            self.value = ''
            self.state = self.WAIT_HEADER
            if (self.bytes_sum % 256 == 0):
                self.bytes_sum = 0
                return self.dict
            else:
                self.bytes_sum = 0
        elif self.state == self.HEX:
            self.bytes_sum = 0
            if byte == self.header2:
                self.state = self.WAIT_HEADER
        else:
            raise AssertionError()

    def read_data_single(self, message):
        while True:
            for data in message:
                packet = self.input(data)
                if (packet != None):
                    return packet
