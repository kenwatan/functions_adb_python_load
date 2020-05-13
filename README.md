# Execute a PLSQL Procedure against Autonomous Database using the Oracle client
This function connects to Oracle Autonomous Database (either Transaction Processing or Data Warehouse) using the Oracle Client and execute a PLSQL Procedure for loading CSV file. 

## Prerequisites
Before you deploy this sample function, make sure you have run step A and B of the [Oracle Functions Quick Start Guide for Cloud Shell](https://www.oracle.com/webfolder/technetwork/tutorials/infographics/oci_functions_cloudshell_quickview/functions_quickview_top/functions_quickview/index.html)
* A - Set up your tenancy
* B - Create application

## List Applications 
Assuming your have successfully completed the prerequisites, you should see your 
application in the list of applications.
```
fn ls apps
```

## Create or Update your Dynamic Group
In order to use other OCI Services, your function must be part of a dynamic group. For information on how to create a dynamic group, refer to the [documentation](https://docs.cloud.oracle.com/iaas/Content/Identity/Tasks/managingdynamicgroups.htm#To).

When specifying the *Matching Rules*, we suggest matching all functions in a compartment with:
```
ALL {resource.type = 'fnfunc', resource.compartment.id = 'ocid1.compartment.oc1..aaaaaxxxxx'}
```
Please check the [Accessing Other Oracle Cloud Infrastructure Resources from Running Functions](https://docs.cloud.oracle.com/en-us/iaas/Content/Functions/Tasks/functionsaccessingociresources.htm) for other *Matching Rules* options.


## Deploy the function
In Cloud Shell, run the *fn deploy* command to build the function and its dependencies as a Docker image, 
push the image to OCIR, and deploy the function to Oracle Functions in your application.

![user input icon](./images/userinput.png)
```
fn -v deploy --app <app-name>
```

## Create an Autonomous Database
Use an existing Autonomous Database (either Transaction Processing or Datawarehouse) or create a new one.

### Create a Procedure 
Use DDL.sql
Create Table, Create CREDENTIAL (OCI User/Auth Token), Create Procedure

## Database Wallet and IAM Policies
The Database wallet is not part of the Docker image because it is not secure. The function downloads the wallet while it is executed.
The wallet can be retrieved from Autonomous Database.

Note the OCID of the Autonomous Database and create an IAM policy that allows the dynamic group to use the autonomous Database with the specific permission 'AUTONOMOUS_DATABASE_CONTENT_READ'.
```
Allow dynamic-group <dynamic-group-name> to use autonomous-databases in compartment <compartment-name> where request.permission='AUTONOMOUS_DATABASE_CONTENT_READ'
```

## Create Object Storege Buckets and IAM Policies
You need two buckets in Object Storage. The first bucket is the location where you will drop the CSV files to be imported into Autonomous Datawarehouse. The files will be moved to the second bucket once they are processed.

Create the two buckets, for example "input-bucket" and "processed-bucket". Check the Emit Object Events box for the first bucket (for input).

Add Policy Statement that allows the dynamic group to manage objects in your two buckets.
```
Allow dynamic-group <dynamic-group-name> to manage objects in compartment <compartment-name> where target.bucket.name=<input-bucket-name>
Allow dynamic-group <dynamic-group-name> to manage objects in compartment <compartment-name> where target.bucket.name=<processed-bucket-name>
```

## Create a Vault with a key and secret for Database User Password and IAM Policies

    Login to the OCI Console as an Administrator
    Go to Menu > Security > Vault
    Select the compartment
    Click the Create Vault button
    Enter the following: 
        Name: my-vault
    Click Create Vault button to save
    Click on the my-vault that was just created
    Click on the Keys link under Resources
    Click Create Key button ** Enter a Name for the key; e.g. my-vault-key 
        Select 256 bits from the Key Shape
    Click Create Key button to save
    Click on the Secrets link under Resources
    Click Create Secret button
    Enter the following: 
        Name: my-secret
        Description: My Secret
        Encryption Key: select my-vault-key created earlier
        Secret Contents: <(DB) Admin User Password>
    Click Create Secret button
    Click on the secret “my-secret”
    Copy the secret OCID to be used next.

Add Policy Statement that allows Function to manage Vault and Key in your tenancy.
```
Allow dynamic-group <dynamic-group-name> to read secret-family in compartment <compartment-name>
allow service objectstorage-<region-name :us-ashburn-1> to manage object-family in compartment <compartment-name>
```

## Create an Event rule
configure a Cloud Event to trigger the function when files are dropped into your input bucket.

Go to the OCI console > Application Integration > Events Service. Click Create Rule.
Assign a display name and a description. In the Rule Conditions section,create 3 conditions:

    type = Event Type, Service Name = Object Storage, Event Type = Object - Create
    type = Attribute, Attribute Name = compartmentName, Attribute Value = your compartment name
    type = Attribute, Attribute Name = bucketName, Attribute Value = your input bucket In the Actions section, set the Action type as "Functions", select your Function Compartment, your Function Application, and your Function ID.


## Set the function configuration values
The function requires several config value to be set.

![user input icon](../images/userinput.png)

Use the *fn CLI* to set the config value:
```
fn config function <app-name> <function-name> region-name <region name>
fn config function <app-name> <function-name> input-bucket <input bucket name>
fn config function <app-name> <function-name> processed-bucket <processed bucket name>
fn config function <app-name> <function-name> password_id <Secret-OCID>
fn config function <app-name> <function-name> DBSVC <DB-service-name>
fn config function <app-name> <function-name> DBUSR <DB-username>
```
Additionally, depending on where the DB wallet should be downloaded, specify the Autonomouns Database OCID:
```
fn config function <app-name> <function name> ADB_OCID <Autonomous-DB-OCID>
```
e.g. with a DB wallet in a bucket:
```
fn config function myapp adw-python-load region-name "us-ashburn-1"
fn config function myapp adw-python-load input-bucket input-bucket
fn config function myapp adw-python-load processed-bucket processed-bucket
fn config function myapp adw-python-load password_id "ocid1.vaultsecret.oc1.iad.AAAAA"
fn config function myapp adw-python-load DBSVC "adb_tp"
fn config function myapp adw-python-load DBUSER "admin"

fn config function myapp adw-python-load ADB_OCID "ocid1.autonomousdatabase.oc1.iad.AAAAA"
```


## Test
Upload one or all CSV files from the current folder to your input bucket. Let's imagine those files contains sales data from different regions of the world.

On the OCI console, navigate to Autonomous Data Warehouse and click on your database, click on Service Console, navigate to Development, and click on SQL Developer Web. Authenticate with your ADMIN username and password. Enter the following query in the worksheet of SQL Developer Web:

```
select * from funtest;
```

You should see the data from the CSV files.