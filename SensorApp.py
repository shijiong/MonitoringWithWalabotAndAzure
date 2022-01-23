from __future__ import print_function # WalabotAPI works on both Python 2 an 3.
from sys import platform
from os import system
from imp import load_source
from os.path import join
from azure.iot.device import Message
from azure.iot.device.aio import IoTHubDeviceClient
import asyncio
import time
import cv2
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
from msrest.authentication import CognitiveServicesCredentials
from azure.storage.blob import ContentSettings, BlobClient

#Computer Vision
subscription_key = "Your Computer Vision Key"
endpoint = "https://***.cognitiveservices.azure.com/"
computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(subscription_key))
#Bolb Storage
conn_str="DefaultEndpointsProtocol=https;AccountName=***;AccountKey=***;BlobEndpoint=https://***.blob.core.windows.net/;QueueEndpoint=https://***.queue.core.windows.net/;TableEndpoint=https://***.table.core.windows.net/;FileEndpoint=https://myiotservicestorage.file.core.windows.net/;"
container_name="raspberrypic"
blob_name="face_detect"
blob_client = BlobClient.from_connection_string(conn_str, container_name, blob_name)
#Azure IoTHub
CONNECTION_STRING = "HostName=***.azure-devices.net;DeviceId=***;SharedAccessKey=***"
DELAY = 5
PAYLOAD = '{{"Target": {tobject},"x": {x_value},"y": {y_value},"z": {z_value},"amplitude": {amp_value},"distance": {dis_value}}}'
client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)
Distance_Threshold = 200

#load Walabot API
if platform == 'win32':
	modulePath = join('C:/', 'Program Files', 'Walabot', 'WalabotSDK',
		'python', 'WalabotAPI.py')
elif platform.startswith('linux'):
    modulePath = join('/usr', 'share', 'walabot', 'python', 'WalabotAPI.py')     

wlbt = load_source('WalabotAPI', modulePath)
wlbt.Init()

# Set the size of the image (in pixels)
img_width = 1280
img_height = 720

#load OpenCV
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, img_width)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, img_height)

# Select color for the bounding box
color = (238,232,170)

async def SendSensorTargets(targets):
    system('cls' if platform == 'win32' else 'clear')
    if targets:
        for i, target in enumerate(targets):
            distance = (target.xPosCm ** 2 + target.yPosCm ** 2 + target.zPosCm ** 2) ** 0.5
            if distance < Distance_Threshold:
                #global Operation_Flag
                Operation_Flag = 1
            print('Target #{}:\nx: {}\ny: {}\nz: {}\namplitude: {}\n'.format(
                i + 1, target.xPosCm, target.yPosCm, target.zPosCm,
                target.amplitude))
            send_data = PAYLOAD.format(tobject=i+1,x_value=target.xPosCm,
                                       y_value=target.yPosCm,z_value=target.zPosCm,
                                       amp_value=target.amplitude,dis_value=distance)
            message = Message(send_data)
            # Send a message to the IoT hub
            print(f"Sending message: {message}")
            await client.send_message(message)
            print("Message successfully sent")               

    else:
        print('No Target Detected')
    # Do face detection according to Operation_Flag
    if Operation_Flag == 1:
        Operation_Flag = 0
        try:                              
            ret, image = camera.read()
            cv2.imwrite('capture.jpg', image)
            # Open local image file
            local_image = open("capture.jpg", "rb")
            print("===== Detect Faces - camera =====")
            # Select visual features(s) you want
            local_image_features = ["faces"]
            # Call API with local image and features
            detect_faces_results_local = computervision_client.analyze_image_in_stream(local_image, local_image_features)
            # Print results with confidence score
            print("Faces in the local image: ")
            if (len(detect_faces_results_local.faces) == 0):
                print("No faces detected.")
            else:
                for face in detect_faces_results_local.faces:
                    left = face.face_rectangle.left
                    top = face.face_rectangle.top
                    right = face.face_rectangle.left + face.face_rectangle.width
                    bottom = face.face_rectangle.top + face.face_rectangle.height         
                    print("'{}' of age {} at location {}, {}, {}, {}".format(face.gender, face.age, \
                    face.face_rectangle.left, face.face_rectangle.top, \
                    face.face_rectangle.left + face.face_rectangle.width, \
                    face.face_rectangle.top + face.face_rectangle.height))
                    result_image = cv2.rectangle(image,(left,top),(right,bottom),color,3)
                    cv2.putText(result_image, f"{face.gender},{face.age}", (int(left), int(top)-10), fontFace = cv2.FONT_HERSHEY_SIMPLEX, fontScale = 0.7, color = color, thickness = 2)
                    cv2.imwrite('result.jpg', result_image)
                # show local image file
                img = cv2.imread('result.jpg') 
                cv2.imshow('result',img)
                if cv2.waitKey(1000) & 0xFF == ord('q'):
                    cv2.destroyAllWindows()
                # upload the image to Azure Blob Storage, Overwrite if it already exists!
                image_content_setting = ContentSettings(content_type='image/jpeg')
                with open("result.jpg", "rb") as data:
                    blob_client.upload_blob(data,overwrite=True,content_settings=image_content_setting)
                    print("Upload completed")                
        except KeyboardInterrupt:
            print("Detection stopped")
            camera.release()
    else:
        print('No operation')

async def SensorApp():
    # wlbt.SetArenaR - input parameters
    minInCm, maxInCm, resInCm = 30, 200, 3
    # wlbt.SetArenaTheta - input parameters
    minIndegrees, maxIndegrees, resIndegrees = -15, 15, 5
    # wlbt.SetArenaPhi - input parameters
    minPhiInDegrees, maxPhiInDegrees, resPhiInDegrees = -60, 60, 5
    # Set MTI mode
    mtiMode = False
    # Initializes walabot lib
    wlbt.Initialize()
    # 1) Connect : Establish communication with walabot.
    wlbt.ConnectAny()
    # 2) Configure: Set scan profile and arena
    # Set Profile - to Sensor.
    wlbt.SetProfile(wlbt.PROF_SENSOR)
    # Setup arena - specify it by Cartesian coordinates.
    wlbt.SetArenaR(minInCm, maxInCm, resInCm)
    # Sets polar range and resolution of arena (parameters in degrees).
    wlbt.SetArenaTheta(minIndegrees, maxIndegrees, resIndegrees)
    # Sets azimuth range and resolution of arena.(parameters in degrees).
    wlbt.SetArenaPhi(minPhiInDegrees, maxPhiInDegrees, resPhiInDegrees)
    # Moving Target Identification: standard dynamic-imaging filter
    filterType = wlbt.FILTER_TYPE_MTI if mtiMode else wlbt.FILTER_TYPE_NONE
    wlbt.SetDynamicImageFilter(filterType)
    # 3) Start: Start the system in preparation for scanning.
    wlbt.Start()
    if not mtiMode: # if MTI mode is not set - start calibrartion
        # calibrates scanning to ignore or reduce the signals
        wlbt.StartCalibration()
        while wlbt.GetStatus()[0] == wlbt.STATUS_CALIBRATING:
            wlbt.Trigger()
    while True:
        appStatus, calibrationProcess = wlbt.GetStatus()
        # 5) Trigger: Scan(sense) according to profile and record signals
        # to be available for processing and retrieval.
        wlbt.Trigger()
        # 6) Get action: retrieve the last completed triggered recording
        targets = wlbt.GetSensorTargets()
        rasterImage, _, _, sliceDepth, power = wlbt.GetRawImageSlice()
        # SendSensorTargets(targets)
        await SendSensorTargets(targets)
        await asyncio.sleep(DELAY)
    # 7) Stop and Disconnect.
    wlbt.Stop()
    wlbt.Disconnect()
    wlbt.Clean()
    print('Terminate successfully')

if __name__ == '__main__':
    asyncio.run(SensorApp())
