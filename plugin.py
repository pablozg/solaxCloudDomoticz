"""
Solax Cloud Monitor python plugin for Domoticz

Author: pablozg, adapted using NUT_UPS plugin and Domoticz-SolaxCloud-Plugin

Version:    0.0.1: alpha
            
"""
"""
<plugin key="SolaxCloud" name="Solax Cloud Monitor" author="pablozg" version="0.0.1" wikilink="http://www.domoticz.com/wiki/plugins/?.html">
    <params>
        <param field="Username" label="Solax Cloud Username" width="200px" required="true" default="username"/>
        <param field="Password" label="Solax Cloud Password" width="200px" required="true" default="password"/>
        <param field="Address"  label="Solax Cloud Address" width="200px" required="true" default="www.solaxcloud.com"/>
        <param field="Port"     label="Solax Cloud Port" width="200px" required="true" default="6080"/>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
    </params>
</plugin>
"""

import Domoticz
import requests
import json
from datetime import datetime, timedelta

class BasePlugin:

    def __init__(self):
        self.debug = False
        self.error = True
        self.nextpoll = datetime.now()
        self.pollinterval = 300  # Time in seconds between two polls, as default 300 secs like cloud server update time
        self.variables = {
            # key:               [device label,             unit, value, device number, used by default, device name, device type, device subtype]
            "server.status":     ["Server Status",          "",    0,     1,  1, "Alert",  0,   0],
            "enableFlag":        ["Inverter Status",        "",    0,     2,  1, "Alert",  0,   0],
            "pv1Voltage":        ["PV1 Voltage",            "V",   None,  3,  1, "Custom", 243, 8],
            "pv1Current":        ["PV1 Amperage",           "A",   None,  4,  1, "Custom", 243, 23],
            "powerdc1":          ["PV1 Power",              "W",   None,  5,  1, "Custom", 248, 1], 
            "temperature":       ["Inverter Temperature",   "C",   None,  6,  1, "Custom", 80,  5],
            "gridPower":         ["Inverter Power",         "W",   None,  7,  1, "Custom", 248, 1],
            "feedinPower":       ["Grid Power",             "W",   None,  8,  1, "Custom", 248, 1],
            "pv2Voltage":        ["PV2 Voltage",            "V",   None,  9,  0, "Custom", 243, 8],
            "pv2Current":        ["PV2 Amperage",           "A",   None,  10, 0, "Custom", 243, 23],
            "powerdc2":          ["PV2 Power",              "W",   None,  11, 0, "Custom", 248, 1],
            "vac1":              ["Inverter Voltage",       "V",   None,  12, 0, "Custom", 243, 8],
            "iac1":              ["Inverter Amperage",      "A",   None,  13, 0, "Custom", 243, 23],
            "fac1":              ["Inverter Frecuency",     "Hz",  None,  14, 0, "Custom", 0,   0],
        }
        return


    def onStart(self):
        Domoticz.Debug("onStart called")
        self.error = True
        
        if Parameters["Mode6"] == 'Debug':
            self.debug = True
            Domoticz.Debugging(1)
            DumpConfigToLog()
        else:
            Domoticz.Debugging(0)
        
        # create the mandatory child device if it does not yet exist
        if 1 not in Devices:
            Domoticz.Device(Name="Server Status", Unit=1, TypeName="Alert", Used=1).Create()
            Devices[1].Update(nValue=0, sValue="") # Grey icon to reflect not yet polled


    def onStop(self):
        Domoticz.Debug("onStop called")
        Domoticz.Debugging(0)


    def onHeartbeat(self):
        now = datetime.now()
        
        if now >= self.nextpoll:
            self.nextpoll = now + timedelta(seconds=self.pollinterval)
            # poll the Solax Cloud server
            try:
                tokenurl = 'http://'+str(Parameters["Address"])+':'+str(Parameters["Port"])+'/proxy//login/login?password='+str(Parameters["Password"])+'&userName='+str(Parameters["Username"])+'&userType=5'
                mysiteurl = 'http://'+str(Parameters["Address"])+':'+str(Parameters["Port"])+'/proxy//mysite/mySite'
                
                tokendata = requests.post(tokenurl).json()
                tokenanduser = {'tokenId': tokendata['result']['tokenId'],'userId': tokendata['result']['userId']}
                
                mysitedata = requests.post(mysiteurl, data=tokenanduser).json()
                
                try:
                    alldataurl = 'http://'+str(Parameters["Address"])+':'+str(Parameters["Port"])+'/proxy//mysite/getInverterInfo?siteId='+str(mysitedata['result'][0]['siteId'])+'&tokenId='+str(tokendata['result']['tokenId'])
                    alldata = requests.post(alldataurl).json()
                    
                except Exception as errorcode:
                    Domoticz.Error("Cannot communicate with Solax Server at {}:{} due to {}".format(
                        Parameters["Address"], Parameters["Port"], errorcode.args))
                    self.error = True
                    self.UpdateDevice("server.status")  # we flag the error to the status device
            
            except Exception as errorcode:
                Domoticz.Error("Cannot communicate with Solax Server at {}:{} due to {}".format(
                    Parameters["Address"], Parameters["Port"], errorcode.args))
                self.error = True
                self.UpdateDevice("server.status")  # we flag the error to the status device
            
            else:
                self.error = False
                
                for current in alldata['result']:
                    for key, data in current.items():
                        if key in self.variables:
                            self.variables[key][2] = data
                            
                            Domoticz.Debug("Variable {} = {}".format(self.variables[key][0], self.variables[key][2]))
                            
                            if self.variables[key][2]:  # skip any variables not reported by the Solax Cloud server
                                self.UpdateDevice(key)  # create/update the relevant child devices

    def UpdateDevice(self, key):

        # inner function to perform the actual update
        def DoUpdate(Unit=0, nValue=0, sValue=""):
            try:
                Devices[Unit].Update(nValue=nValue, sValue=sValue)
                
            except Exception as errorcode:
                Domoticz.Error("Failed to update device unit {} due to {}".format(Unit, errorcode.args))

        # Make sure that the Domoticz device still exists (they can be deleted) before updating it
        if self.variables[key][3] in Devices:
            if key == "server.status":
                if self.error:
                    nvalue = 0
                    svalue = "Solax Cloud Server Down"
                else:
                    nvalue = 1
                    svalue = "Solax Cloud Server Up"
                    
            if key == "enableFlag":
                if self.variables["enableFlag"][2] == "0":
                    nvalue = 0
                    svalue = "Solax Inverter Offline"
                else:
                    nvalue = 1
                    svalue = "Solax Inverter Online"
                    
            if not self.error and key != "server.status" and key != "enableFlag":
                nvalue = 0
                svalue = str(self.variables[key][2])
                # If the inverter is offline, then all svalues are 0;
                if self.variables["enableFlag"][2] == "0":
                    svalue = "0"
                #DoUpdate(self.variables[key][3], nvalue, svalue)
                
            if Devices[self.variables[key][3]].sValue != svalue:
                DoUpdate(self.variables[key][3], nvalue, svalue)
        
        elif key != "server.status" or key != "enableFlag":
            if self.variables[key][6] == 0:
                Domoticz.Device(Name=self.variables[key][0], Unit=self.variables[key][3], TypeName=self.variables[key][5],
                                Image= 17, Options={"Custom": "1;{}".format(self.variables[key][1])},
                                Used=self.variables[key][4]).Create()
            else:
                Domoticz.Device(Name=self.variables[key][0], Unit=self.variables[key][3], Type=self.variables[key][6], Subtype=self.variables[key][7],
                                Image= 17, Used=self.variables[key][4]).Create()
            # Update upon next poll (recursive call to update device broken in some domoticz versions)


global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Plugin specific functions ---------------------------------------------------

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return