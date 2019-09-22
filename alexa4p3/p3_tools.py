'''
Created on 29.12.2018

@author: andrek
'''
import os
import sys
from argparse import Namespace
import logging
from datetime import datetime,timedelta
from .device import AlexaDevices, AlexaDevice
import json


def CreateStreamSettings(myItemConf):
    myRetVal = []
    for k,v in myItemConf.camera_setting.items():
        myRetVal.append(v)
    return myRetVal

def CreateStreamPayLoad(myItemConf):
    now = datetime.now()
    offset = timedelta(seconds=86400) # Experition time 24h 
    now = now + offset
    now = now.isoformat()
    expirationDate = now[0:22]+'Z'
    cameraStream = []
    cameraUri = []
    imageuri = myItemConf.camera_imageUri
    if myItemConf.alexa_auth_cred != '':
            imageuri = imageuri.replace("//","//"+myItemConf.alexa_auth_cred+"@")

    if len(myItemConf.proxied_Urls) == 0:
        for k,v in myItemConf.camera_uri.items():
            cameraUri.append(v)
    else:
        for k,v in myItemConf.proxied_Urls.items():
            cameraUri.append(v)
    
    i=0
    for k,v in myItemConf.camera_setting.items():
        if myItemConf.alexa_auth_cred != '':
            uri = v['protocols'][0].lower()+"://"+myItemConf.alexa_auth_cred+'@'+cameraUri[i]
        else:
            uri = v['protocols'][0].lower()+"://"+cameraUri[i]
        # Find highest resolution
        streamResolution = {}
        highestRes = 0
        for res in v['resolutions']:
            test = res['width']
            if res['width'] > highestRes:
                streamResolution = res
                highestRes = res['width']
            
        
        myStream= {
                     "uri":uri,
                     "expirationTime":  expirationDate,
                     "idleTimeoutSeconds": 30,
                     "protocol": v['protocols'][0].upper(),
                     "resolution":streamResolution,
                     "authorizationType": v['authorizationTypes'][0].upper(),
                     "videoCodec": v['videoCodecs'][0].upper(),
                     "audioCodec": v['audioCodecs'][0].upper()
                  }
        cameraStream.append(myStream)
        i +=1
    response = {"cameraStreams": cameraStream}
    response.update({ "imageUri":imageuri})
    return response

def DumpStreamInfo(directive):
    myFile = open("streamdump.txt","a+")
    myString=json.dumps(directive)
    
    
    myFile.write(myString+"\r\n")
    myFile.write("=====================\r\n")
    myFile.close()


# Calculating HSV to RGB based on
# https://www.rapidtables.com/convert/color/hsv-to-rgb.html
def hsv_to_rgb(h, s, v):
            if( h=="" ):
                 h=0
            if( s=="" ):
                 s=0
            if( v=="" ):
                 v=0
            if( h<0 ):
                 h=0
            if( s<0 ):
                 s=0
            if( v<0 ):
                 v=0
            if( h>=360 ):
                 h=359
            if( s>100 ):
                 s=100
            if( v>100 ):
                 v=100
            C = v*s
            hh = h/60
            X = C*(1-abs(hh%2-1))
            r = g = b = 0
            if( hh>=0 and hh<1 ):
                r = C
                g = X

            elif( hh>=1 and hh<2 ):
                r = X
                g = C

            elif( hh>=2 and hh<3 ):
                g = C
                b = X

            elif( hh>=3 and hh<4 ):
                g = X
                b = C
            elif( hh>=4 and hh<5 ):
                r = X
                b = C
            else:
                r = C
                b = X

            m = v-C
            r += m
            g += m
            b += m
            r *= 255.0
            g *= 255.0
            b *= 255.0
            r = round(r)
            g = round(g)
            b = round(b)
            return r,g,b
def rgb_to_hsv(r, g, b): 
            if( r=="" ):
                 r=0
            if( g=="" ):
                 g=0
            if( b=="" ):
                 b=0

            if( r<0 ):
                 r=0
            if( g<0 ):
                 g=0
            if( b<0 ):
                 b=0
            if( r>255 ):
                 r=255
            if( g>255 ):
                 g=255
            if( b>255 ):
                 b=255
            
            r/=255.0
            g/=255.0
            b/=255.0
             
            M = max(r,g,b)
            m = min(r,g,b)
            C = M-m
            if( C==0 ):
                h=0
            elif( M==r ):
                h=((g-b)/C)
                h=h%6
            elif( M==g ):
                h=(b-r)/C+2
            else:
                h=(r-g)/C+4
                h*=60;
            if( h<0 ):
                h+=360
            else:
                h*=60
            v = M
            if( v==0 ):
                s = 0
            else:
                s = C/v
            h = round(h,0)
            s = round(s,4)
            v = round(v,4)
            return h,s,v
