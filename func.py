#
# adb-python-load version 1.0.
#

import io
import json
import cx_Oracle
import oci
import os
import string
import random
import requests
import base64
import sys

from timeit import default_timer as timer
from zipfile import ZipFile
from fdk import response

def move_object(signer, namespace, source_bucket, destination_bucket, object_name):
    objstore = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
    objstore_composite_ops = oci.object_storage.ObjectStorageClientCompositeOperations(objstore)
    resp = objstore_composite_ops.copy_object_and_wait_for_state(
        namespace, 
        source_bucket, 
        oci.object_storage.models.CopyObjectDetails(
            destination_bucket=destination_bucket, 
            destination_namespace=namespace,
            destination_object_name=object_name,
            destination_region=signer.region,
            source_object_name=object_name
            ),
        wait_for_states=[
            oci.object_storage.models.WorkRequest.STATUS_COMPLETED,
            oci.object_storage.models.WorkRequest.STATUS_FAILED])
    if resp.data.status != "COMPLETED":
        raise Exception("cannot copy object {0} to bucket {1}".format(object_name,destination_bucket))
    else:
        resp = objstore.delete_object(namespace, source_bucket, object_name)
        print("INFO - Object {0} moved to Bucket {1}".format(object_name,destination_bucket), flush=True)

# Retrieve secret
def read_secret_value(secret_client, secret_id):
    response = secret_client.get_secret_bundle(secret_id)
    base64_Secret_content = response.data.secret_bundle_content.content
    base64_secret_bytes = base64_Secret_content.encode('ascii')
    base64_message_bytes = base64.b64decode(base64_secret_bytes)
    secret_content = base64_message_bytes.decode('ascii')
    return secret_content

def get_dbwallet_from_autonomousdb():
    signer = oci.auth.signers.get_resource_principals_signer()   # authentication based on instance principal
    atp_client = oci.database.DatabaseClient(config={}, signer=signer)
    atp_wallet_pwd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=15)) # random string
    # the wallet password is only used for creation of the Java jks files, which aren't used by cx_Oracle so the value is not important
    atp_wallet_details = oci.database.models.GenerateAutonomousDatabaseWalletDetails(password=atp_wallet_pwd)
    print(atp_wallet_details, flush=True)
    obj = atp_client.generate_autonomous_database_wallet(adb_ocid, atp_wallet_details)
    with open(dbwalletzip_location, 'w+b') as f:
        for chunk in obj.data.raw.stream(1024 * 1024, decode_content=False):
            f.write(chunk)
    with ZipFile(dbwalletzip_location, 'r') as zipObj:
            zipObj.extractall(dbwallet_dir)

#
# Instantiation code: executed once when the function container is initialized
#
if os.getenv("DBUSER") != None:
    dbuser = os.getenv("DBUSER")
else:
    raise ValueError("ERROR: Missing configuration key DBUSER")
if os.getenv("DBSVC") != None:
    dbsvc = os.getenv("DBSVC")
else:
    raise ValueError("ERROR: Missing configuration key DBSVC")
if os.getenv("ADB_OCID") != None:
    adb_ocid = os.getenv("ADB_OCID")
    wallet_from_adb = True
    print("INFO: DB wallet has to be generated from ADB ", adb_ocid, flush=True)
else:
    raise ValueError("ERROR: Missing configuration key ADB_OCID")
# Get Secret
if os.getenv("password_id") != None:
    signer = oci.auth.signers.get_resource_principals_signer()
    secret_client = oci.secrets.SecretsClient(config={}, signer=signer)
    secret_id = os.getenv("password_id")
    secret_contents = read_secret_value(secret_client, secret_id)
    dbpwd = format(secret_contents)
else:
    raise ValueError("ERROR: Missing configuration key password_id")
# Download the DB Wallet
dbwalletzip_location = "/tmp/dbwallet.zip"
dbwallet_dir = os.getenv('TNS_ADMIN')
if wallet_from_adb:
    get_dbwallet_from_autonomousdb()
print('INFO: DB wallet dir content =', os.listdir(dbwallet_dir), flush=True)
# Update SQLNET.ORA
with open(dbwallet_dir + '/sqlnet.ora') as orig_sqlnetora:
    newText=orig_sqlnetora.read().replace('DIRECTORY=\"?/network/admin\"', 'DIRECTORY=\"{}\"'.format(dbwallet_dir))
with open(dbwallet_dir + '/sqlnet.ora', "w") as new_sqlnetora:
    new_sqlnetora.write(newText)
# Create the DB Session Pool
dbpool = cx_Oracle.SessionPool(dbuser, dbpwd, dbsvc, min=1, max=1, encoding="UTF-8", nencoding="UTF-8")
print("INFO: DB pool created", flush=True)

#
# Function Handler: executed every time the function is invoked
#
def handler(ctx, data: io.BytesIO = None):
    object_name = bucket_name = namespace = db_tns = dbuser = dbpwd = password_id = ""
    try:
        cfg = ctx.Config()
        REGION = cfg["region-name"]
        input_bucket = cfg["input-bucket"]
        processed_bucket = cfg["processed-bucket"]
        DBUSER = cfg["DBUSER"]
        DBSVC = cfg["DBSVC"]
    except Exception as e:
        print('Missing function parameters: bucket_name, dbuser, password_id', flush=True)
        raise

    try:
        body = json.loads(data.getvalue())
        print("INFO - Event ID {} received".format(body["eventID"]), flush=True)
        print("INFO - Namespace: " + body["data"]["additionalDetails"]["namespace"], flush=True)
        namespace = body["data"]["additionalDetails"]["namespace"]
        print("INFO - Bucket name: " + body["data"]["additionalDetails"]["bucketName"], flush=True)
        print("INFO - Object name: " + body["data"]["resourceName"], flush=True)
        object_name = body["data"]["resourceName"]
        source_name = "https://objectstorage." + REGION + ".oraclecloud.com/n/" + namespace +"/b/" + body["data"]["additionalDetails"]["bucketName"] + "/o/" + body["data"]["resourceName"]
        print("INFO - Source name: " + source_name, flush=True)
    except Exception as e:
        print('ERROR: bad Event!', flush=True)
        raise

    with dbpool.acquire() as dbconnection:
        with dbconnection.cursor() as dbcursor:
            start_query = timer()
            dbcursor.callproc('csvload',[source_name])
            end_query = timer()
            print("INFO: CSV LOAD executed in {} sec".format(end_query - start_query), flush=True)
    move_object(signer, namespace, input_bucket, processed_bucket, object_name)

    return response.Response(
        ctx, 
        response_data=json.dumps({"status": "Success"}),
        headers={"Content-Type": "application/json"}
    )