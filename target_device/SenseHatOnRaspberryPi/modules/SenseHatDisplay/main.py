# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for
# full license information.

import time
import os
import sys
from six.moves import input
import threading
from azure.iot.device import IoTHubModuleClient, Message, MethodResponse
import json
from sense_hat import SenseHat
import datetime
import math

COLOR_INDEX_RED = 0
COLOR_INDEX_GREEN = 1
COLOR_INDEX_BLUE = 2
COLOR_VALUE_MAX = 255
COLOR_VALUE_MIN = 0
PIXEL_COLOR_OFF = [0,0,0]

st_forground_color = [0,0,0]
st_background_color = [0,0,0]
st_current_pixels = [
    PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF,
    PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF,
    PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF,
    PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF,
    PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF,
    PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF,
    PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF,
    PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF, PIXEL_COLOR_OFF
]

st_current_text = ""
st_current_float_speed = 0.0
st_current_round = 2
st_current_showing_image = False

sensehat = SenseHat()

def showMessage(param_lock):
    global st_current_text, st_forground_color, st_background_color, st_current_float_speed, st_current_round
    param_lock.acquire()
    round = st_current_round
    st_current_showing_image = True
    param_lock.release()
    while round > 0:
        param_lock.acquire()
        sensehat.show_message(st_current_text, st_current_float_speed, st_forground_color, st_background_color)
        param_lock.release()
        round = round - 1
    param_lock.acquire()
    st_current_showing_image = False
    param_lock.release()

def stShowText(payload, param_lock):
    global st_current_text, st_forground_color, st_background_color, st_current_float_speed, st_current_round
    param_lock.acquire()
    st_current_text = payload['text']
    print('text - {}'.format(st_current_text))
    if 'forground' in payload:
        st_forground_color = payload['forground']
        print('forground - {}'.format(st_forground_color))
    if 'background' in payload:
        st_background_color = payload['background']
        print('background - {}'.format(st_background_color))
    if 'float' in payload:
        st_current_float_speed = payload['float']
    if 'round' in payload:
        st_current_round = payload['round']
    if st_forground_color[0] == st_background_color[0] and st_forground_color[1] == st_background_color[1] and st_forground_color[2] == st_background_color[2]:
        st_forground_color[0] = COLOR_VALUE_MAX - st_background_color[0]
        st_forground_color[1] = COLOR_VALUE_MAX - st_background_color[1]
        st_forground_color[2] = COLOR_VALUE_MAX - st_background_color[2]
    param_lock.release()
    print('set complete')
    if len(st_current_text) == 1:
        param_lock.acquire()
        sensehat.show_letter(st_current_text, st_forground_color, st_background_color)
        param_lock.release()
    else:
        messageShowThread = threading.Thread(target=showMessage, args=(param_lock,))
        messageShowThread.start()
#        sensehat.show_message(st_current_text, st_current_float_speed, st_forground_color, st_background_color)

def parseImageData(data):
    image = []
    lines = data.replace('\n','').split(']],[[')
    lines[0] = lines[0][2:]
    lines[7] = lines[7][:-2]
    for i,l in enumerate(lines):
        points = l.split('],[')
        for p in points:
            pc = []
            for s in p.split(','):
                pc.append(int(s))
            image.append(pc)
    
    return image
        
def stShowImage(payload, param_lock):
    global st_current_showing_image
    if 'image' in payload:
        image = parseImageData(payload['image'])
        print('drawing - {}'.format(image))
        param_lock.acquire()
        st_current_showing_image = True
        param_lock.release()
        sensehat.set_pixels(image)
    else:
        param_lock.acquire()
        st_current_showing_image = False
        param_lock.release()
        sensehat.clear()

def stSetOptions(payload, param_lock):
    global st_forground_color, st_background_color, st_current_float_speed
    param_lock.acquire()
    if 'forground' in payload:
        st_forground_color = payload['forground']
    if 'background' in payload:
        st_background_color = payload['background']
    if 'float' in payload:
        st_current_float_speed = payload['float']
    param_lock.release()

def stClear(payload, param_lock):
    global st_current_showing_image
    param_lock.acquire()
    st_current_showing_image = False
    sensehat.clear(payload['color'])
    param_lock.release()


def adjustColor(temp, humi, press, param_lock):
    global st_current_showing_image
    blues = []
    reds = []
    greens = []
    for y in range(8):
        b = int(((humi / 100.0) * 256.0) * (float(y) / 7.0))
        r = int((((temp-10.0) / 50.0) * 256.0) * (float(y) / 7.0))
        if b < 0 :
            b = 0
        elif b > 255:
            b = 255
        if r < 0 :
            r = 0
        elif r > 255:
            r = 255
        blues.append(b)
        reds.append(r)
        rmax = math.sqrt(98.0)
        for x in range(8):
            r = math.sqrt(math.pow(float(x),2) + math.pow(float(y),2))
            p = int((((press - 950.0) / 100.0) * (r / rmax)) * 256.0)
            if p < 0:
                p = 0
            elif p > 255:
                p = 255
            greens.append(p)
        #    print("press:{} -> r:{}-> green level[{}][{}]={}".format(press,r,x,y,p))

    param_lock.acquire()
    if st_current_showing_image == False:
        for x in range(8):
            for y in range(8):
                st_current_pixels[y*8+x] = [reds[x],greens[y*8+(7-x)], blues[y]]
        sensehat.set_pixels(st_current_pixels)
    param_lock.release()

def main():
    try:
        if not sys.version >= "3.5.3":
            raise Exception( "The sample requires python 3.5.3+. Current version of Python: %s" % sys.version )
        print ( "IoT Hub Client for Python" )


        # The client object is used to interact with your Azure IoT hub.
        module_client = IoTHubModuleClient.create_from_edge_environment()

        # connect the client.
        module_client.connect()

        # define behavior for receiving an input message on input1
        def input1_listener(module_client,param_lock):
            count = 0
            while True:
                print("Waiting for message")
                input_message = module_client.receive_message_on_input("input1")  # blocking call
                print("the data in the message received on input1 was ")
                print(input_message.data)
                print("custom properties are")
                print(input_message.custom_properties)
                content = json.loads(input_message.data.decode('utf8'))
                if 'command' in content:
                    if content['command'] == "ShowText":
                        stShowText(content['payload'], param_lock)
                    elif content['command'] == "ShowImage":
                        stShowImage(content['payload'], param_lock)
                    elif content['command'] == "SetOptions":
                        stSetOptions(content['payload'], param_lock)
                    elif content['command'] == "Clear":
                        stClear(content['payload'], param_lock)
                elif 'timeCreated' in content:
                    if (count % 10) == 0:
                        temp = content['temperature']
                        humi = content['humidity']
                        pres = content['pressure']
                        adjustColor(temp,humi,pres, param_lock)

        def direct_method_listener(module_client, param_lock):
            while True:
                try:
                    print("waiting for method invocation...")
                    methodRequest = module_client.receive_method_request()
                    print("received method invocation - '{}'({})".format(methodRequest.name, methodRequest.payload))
                    response = {}
                    response_status = 200
                    if methodRequest.name == "ShowText":
                        stShowText(methodRequest.payload, param_lock)
                    elif methodRequest.name == "ShowImage":
                        stShowImage(methodRequest.payload, param_lock)
                    elif methodRequest.name == "SetOptions":
                        stSetOptions(methodRequest.payload, param_lock)
                    elif methodRequest.name == "Clear":
                        stClear(methodRequest.payload, param_lock)
                    else:
                        response['message'] = "bad method name"
                        response_status = 404
                    response = MethodResponse(methodRequest.request_id, response_status, payload=response )
                    module_client.send_method_response(response)
                except Exception as error:
                    print("exception happens - {}".format(error))

        print ( "The sample is now waiting for messages. ")

        param_lock = threading.Lock()
        message_thread = threading.Thread(target=input1_listener, args=(module_client, param_lock))
        message_thread.daemon = True
        message_thread.start()
        method_thread = threading.Thread(target=direct_method_listener, args=(module_client, param_lock))
        method_thread.daemon = True
        method_thread.start()

        reported = {'application':'sensehat-led'}
        module_client.patch_twin_reported_properties(reported)
        
        while True:
            time.sleep(1)

        # Finally, disconnect
        module_client.disconnect()

    except Exception as e:
        print ( "Unexpected error %s " % e )
        raise

if __name__ == "__main__":
    main()

    # If using Python 3.7 or above, you can use following code instead:
    # asyncio.run(main())