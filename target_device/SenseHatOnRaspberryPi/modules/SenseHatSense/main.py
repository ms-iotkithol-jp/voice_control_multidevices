# Copyright (c) Embedded D. George - @embedded_george All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for
# full license information.


import os
import random
import time
import sys
import iothub_client
# pylint: disable=E0611
# Disabling linting that is not supported by Pylint for C extensions such as iothub_client. See issue https://github.com/PyCQA/pylint/issues/1955 
from iothub_client import IoTHubModuleClient, IoTHubClientError, IoTHubTransportProvider, IoTHubClientRetryPolicy
from iothub_client import IoTHubMessage, IoTHubMessageDispositionResult, IoTHubError, DeviceMethodReturnValue
import json
from sense_hat import SenseHat
import datetime

application_name = None
telemetryCycleMSecKey = "telemetryCycleMSec"

RECEIVE_CALLBACKS = 0
SEND_SENSEHAT_CALLBACKS = 0
SEND_CALLBACKS = 0
TWIN_CONTEXT = 0
sense = SenseHat()

# read sense hat and send
def read_and_send_measurements_from_sensehat(sense, hubManager):
    global SEND_SENSEHAT_CALLBACKS
    # sense.clear()
    temperature = sense.get_temperature()
    temperature_h = sense.get_temperature_from_humidity()
    temperature_p = sense.get_temperature_from_pressure()
    humidity = sense.get_humidity()
    pressure = sense.get_pressure()
    accelerometer = sense.get_accelerometer_raw()
    accel = "\"x\":{x:.5f},\"y\":{y:.5f},\"z\":{z:.5f}".format(**accelerometer)
    print("accelerometer - %s" % accel)

    timeCreated = datetime.datetime.utcnow().isoformat()
    MSG_TXT = "{\"temperature\": %.2f,\"temperature_h\": %.2f,\"temperature_p\": %.2f,\"humidity\": %.2f,\"pressure\": %.2f,\"accelerometer\":{%s},\"timeCreated\": \"%s\"}"
    msg_txt_formatted = MSG_TXT % (temperature, temperature_h, temperature_p, humidity, pressure, accel, timeCreated)
    print("Sending - :%s\n" % msg_txt_formatted)
    message = IoTHubMessage(msg_txt_formatted)
    prop_map = message.properties()
    prop_map.add("data-type","sensing")
    prop_map.add("application","Custom-vision-service-iot-edge-raspberry-pi-ext")

    hubManager.send_event_to_output("output2", message, 0)
    SEND_SENSEHAT_CALLBACKS += 1
    print ( "    Total sensehat messages sent: %d" % SEND_SENSEHAT_CALLBACKS )

# Callback received when the message that we're forwarding is processed.
def send_confirmation_callback(message, result, user_context):
    global SEND_CALLBACKS
    print ( "Confirmation[%d] received for message with result = %s" % (user_context, result) )
    map_properties = message.properties()
    key_value_pair = map_properties.get_internals()
    print ( "    Properties: %s" % key_value_pair )
    SEND_CALLBACKS += 1
    print ( "    Total calls confirmed: %d" % SEND_CALLBACKS )

# receive_message_callback is invoked when an incoming message arrives on the specified  input queue
def receive_message_callback(message, hubManager):
    global RECEIVE_CALLBACKS
    message_buffer = message.get_bytearray()
    size = len(message_buffer)
    print ( "    Data: <<<%s>>> & Size=%d" % (message_buffer[:size].decode('utf-8'), size) )
    map_properties = message.properties()
    key_value_pair = map_properties.get_internals()
    print ( "    Properties: %s" % key_value_pair )
    RECEIVE_CALLBACKS += 1
    print ( "    Total calls received: %d" % RECEIVE_CALLBACKS )
    hubManager.send_event_to_output("output1", message, 0)
    return IoTHubMessageDispositionResult.ACCEPTED

twin_telemetry_cycle_ms = 5000

# module_twin_callback is invokged when module twin desired properties are updated.
def module_twin_callback(update_state, payload, user_context):
    global twin_telemetry_cycle_ms, telemetryCycleMSecKey
    print("")
    print("Twin callback called with:")
    print("updateStatus: %s" % update_state)
    print("context: %s" % user_context)
    print("payload: %s" % payload)
    data = json.loads(payload)
    if telemetryCycleMSecKey in data :
        twin_telemetry_cycle_ms = data[telemetryCycleMSecKey]
        print("received - %d msec" % twin_telemetry_cycle_ms)



class HubManager(object):

    def __init__(self):
        global TWIN_CONTEXT, application_name
        # Defines settings of the IoT SDK
        protocol = IoTHubTransportProvider.MQTT
        self.client_protocol = protocol
        self.client = IoTHubModuleClient()
        self.client.create_from_environment(protocol)
        self.client.set_option("logtrace", 1)#enables MQTT logging
        self.client.set_option("messageTimeout", 10000)

        # sets the callback when a message arrives on "input1" queue.  Messages sent to 
        # other inputs or to the default will be silently discarded.
        self.client.set_message_callback("input1", receive_message_callback, self)
        print("Module is now waiting for messages in the input1 queue.")
        self.client.set_module_twin_callback(module_twin_callback, TWIN_CONTEXT)
        print("Module is now waiting for device twin updating.")
        if application_name is not None:
            reported = {'application':application_name}
            self.client.patch_twin_reported_properties(reported)

    def send_event_to_output(self, outputQueueName, event, send_context):
        self.client.send_event_async(outputQueueName, event, send_confirmation_callback, send_context)

#    def send_event_to_output(self, outputQueueName, event, send_context):
#        self.client.send_event_async(outputQueueName, event, send_confirmation_callback, send_context)


def main():
    global twin_telemetry_cycle_ms
    try:
        print ( "\nPython %s\n" % sys.version )
        print ( "IoT Hub Client for Python" )

        hub_manager = HubManager()

        print ( "Starting the IoT Hub Python sample using protocol %s..." % hub_manager.client_protocol )
        print("The sample is now waiting for messages and will indefinitely.  Press Ctrl-C to exit. ")
        
        sense = SenseHat()
        time.sleep(1)
        sense.set_imu_config(False,False,True)

        while True:
            read_and_send_measurements_from_sensehat(sense, hub_manager)
            time.sleep(float(twin_telemetry_cycle_ms)/1000.0)

    except IoTHubError as iothub_error:
        print ( "Unexpected error %s from IoTHub" % iothub_error )
        return
    except KeyboardInterrupt:
        print ( "IoTHubClient sample stopped" )


if __name__ == '__main__':
    main()
    application_name = os.environ['APPLICATION_NAME']
