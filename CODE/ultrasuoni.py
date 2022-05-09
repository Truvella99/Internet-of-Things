# ultrasuoni_distanza
# Created at 2021-05-04 19:18:53.496906

import streams
streams.serial()

class hcsr04:
    
    @c_native("HCRS04_readDistanceRaw", ["hcsr04.c"], [])
    def _getDistanceRaw(trig, echo):
        pass
    
    def getDistanceRaw(self):
        return hcsr04._getDistanceRaw(self.trigger, self.echo)
    
    def getDistanceCM(self):
        return self.getDistanceRaw() / 58
    
    def getDistanceINCH(self):
        return self.getDistanceRaw() / 148
    
    def __init__(self, trigger, echo):
        self.trigger = trigger
        self.echo = echo
        
        pinMode(self.trigger, OUTPUT)
        pinMode(self.echo, INPUT)
