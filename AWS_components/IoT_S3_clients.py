# For AWS IoT Core
# Import SDK packages
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import time
import json
import pandas as pd
import datetime
import numpy as np
from threading import Lock 
import time
from datetime import datetime

# For S3 & DynamoDB
import boto3
from boto3.s3.transfer import TransferConfig

# S3 Parameters/Variables
# Set the desired multipart threshold value (5GB)
GB = 1024 ** 3
config = TransferConfig(multipart_threshold=5*GB)
# Create S3 client
# s3_client = boto3.client('s3')

bucket_name = 'skynetlibrarybucket'

# IoT Core Parameters/Variables
#TODO 1: modify the following parameters
#Starting and end index, modify this
device_st = 0 # first device in group 
device_end = 1

#Path to the dataset, modify this
data_path = "data/bookshelf{}.csv"

#Path to your certificates, modify this
# certificate_formatter = "./certificates/device_{}/device_{}.cert.pem"
# key_formatter = "./certificates/device_{}/device_{}.private.key"

host = "https://sts.us-west-2.amazonaws.com"
rootCAPath = "./certificates/AmazonRootCA1.cer"
certificatePath = "./certificates/3dff6911c8092c897bdf912b9812e0a3b025794389fbcae220e21478660c4abe-certificate.pem.crt"
privateKeyPath = "./certificates/3dff6911c8092c897bdf912b9812e0a3b025794389fbcae220e21478660c4abe-private.pem.key"
clientId = "libraryScanner"
device_id = 0 # also used for bookshelf number & data parameter
thingName = "libraryScanner"
topic = "scanner/books"
mode = "publish" # options: 'publish', 'subscribe', 'both'
bookshelf_message = {
	'id': int(time.time()),

	'shelf': [
	# old sample data
	# {'id': int(time.time()),'shelf': 1, 'book_number': 1, 'call_number': ('612', 'NAG'), 'out_of_order': False, "createdAt": str(datetime.now()),},
	# {'id': int(time.time()),'shelf': 1, 'book_number': 2, 'call_number': ('801.1', 'TED'), 'out_of_order': True, "createdAt": str(datetime.now()),},
	# {'id': int(time.time()),'shelf': 1, 'book_number': 3, 'call_number': ('612', 'BIL'), 'out_of_order': False, "createdAt": str(datetime.now()),},

	# datetime formatted for AWSDateTime object
	{'id': int(time.time()),'shelf': 1, 'book_number': 1, 'call_number': ('160.9', 'ADR'), 'out_of_order': False, "updatedAt": str(datetime.now()).replace(' ', 'T') + 'Z'},
	{'id': int(time.time()),'shelf': 1, 'book_number': 2, 'call_number': ('204', 'DER'), 'out_of_order': False, "updatedAt": str(datetime.now()).replace(' ', 'T') + 'Z'},
	{'id': int(time.time()),'shelf': 1, 'book_number': 3, 'call_number': ('616', 'MER'), 'out_of_order': False, "updatedAt": str(datetime.now()).replace(' ', 'T') + 'Z'}],
	
	'createdAt': str(datetime.now()).replace(' ', 'T') + 'Z',
	'updatedAt': str(datetime.now()).replace(' ', 'T') + 'Z'
	}

class MQTTClient:
	def __init__(self, device_id, cert, key):
		# For certificate based connection
		self.device_id = str(device_id)
		self.state = 0
		self.client = AWSIoTMQTTClient(self.device_id)
		#TODO 2: modify your broker address
		self.client.configureEndpoint("a99o74r5xgj17-ats.iot.us-west-2.amazonaws.com", 8883)
		self.client.configureCredentials("./certificates/AmazonRootCA1.cer", key, cert)
		self.client.configureOfflinePublishQueueing(-1)  # Infinite offline Publish queueing
		self.client.configureDrainingFrequency(2)  # Draining: 2 Hz
		self.client.configureConnectDisconnectTimeout(10)  # 10 sec
		self.client.configureMQTTOperationTimeout(5)  # 5 sec
		self.client.onMessage = self.customOnMessage
		self.s3_client = boto3.client('s3') # AWS S3 client

	def customOnMessage(self,bookshelf_message):
		#TODO3: fill in the function to show your received message
		print("client {0} received from Lambda function 'basicGetMaxCO2':\n{1}\n\n".format(self.device_id, bookshelf_message.payload), end = " ")

		#Don't delete this line
		self.client.disconnectAsync()


	# Suback callback
	def customSubackCallback(self,mid, data):
		#You don't need to write anything here
	    pass

	# Puback callback
	def customPubackCallback(self,mid):
		#You don't need to write anything here
	    pass

	def publish(self):
		#TODO4: fill in this function for your publish
		self.client.connect()
		# self.client.subscribeAsync(("lambda_data" + str(self.device_id)), 0, ackCallback=self.customSubackCallback)
		book_data = {'shelf': '00' + str(self.device_id), 'data': str(data[int(self.device_id)]['books'].tolist())}
		# messageJson = json.dumps(book_data) # convert data to json string
		messageJson = json.dumps(bookshelf_message)
		# self.put_bookshelf(bookshelf_message) # publish message to DynamoDB
		print('Uploading message...\n\n {}\n\n...to DynamoDB'.format(messageJson))
		self.client.publishAsync(topic, messageJson, 0, ackCallback=self.customPubackCallback) # make device publish its CO2 data to IoT Core

	def upload_file(self, file):
		s3_folder_name = 'bookshelf' + '00' + str(self.device_id) + '/'
		object_name = s3_folder_name + 'demo_client_upload_' + str(self.device_id) + '.png' # to upload to a folder include the folder name in the object name
		self.s3_client.upload_file(file, bucket_name, object_name, Config=config)
		print('Uploading file {} to S3 bucket {}/{}'.format(file, bucket_name, s3_folder_name))

	def put_bookshelf(self,message, dynamodb=None):
		if not dynamodb:
			dynamodb = boto3.resource('dynamodb', endpoint_url="https://dynamodb.us-west-2.amazonaws.com")
		table = dynamodb.Table('Bookshelf-dczkwezjvvebbpu5hlekgtcawe-staging')
		print(message)
		response = table.put_item(
			Item=message
		)
		return response


# Don't change the code below
print("wait")
lock = Lock()
data = []
for i in range(device_end):
	a = pd.read_csv(data_path.format(i))
	data.append(a)

clients = []
client = MQTTClient(device_id, certificatePath, privateKeyPath)
clients.append(client)

print("send now?")
x = input()
if x == "s":
	for i,c in enumerate(clients):
		c.publish()
		file = 's3_sample_upload_1.png'
		# c.upload_file(file)
	# print("done")
elif x == "d":
	for c in clients:
		c.disconnect()
		print("All devices disconnected")
else:
	print("wrong key pressed")

time.sleep(10)





