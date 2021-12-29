import boto3
from boto3.s3.transfer import TransferConfig

# source: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html

# Multipart upload is used for uploading large files (larger than threshold value) in smaller chunks
# Set the desired multipart threshold value (5GB)
GB = 1024 ** 3
config = TransferConfig(multipart_threshold=5*GB)

# Perform the transfer
s3_client = boto3.client('s3')
# s3.upload_file('FILE_NAME', 'BUCKET_NAME', 'OBJECT_NAME', Config=config)

# bucket_name = 's3://skynetlibrarybucket/bookshelf000/'
bucket_name = 'skynetlibrarybucket'
file = 's3_sample_upload_1.png'
s3_folder_name = 'bookshelf000/'
object_name = s3_folder_name + 'demo_client_upload_2.png' # to upload to a folder include the folder name in the object name

s3_client.upload_file(file, bucket_name, object_name, Config=config)

# Get buckets (upload_file requires a bucket name)
# response = s3_client.list_buckets()

# Output the bucket names
# print('Existing buckets:')
# for bucket in response['Buckets']:
#     print(f'  {bucket["Name"]}')
