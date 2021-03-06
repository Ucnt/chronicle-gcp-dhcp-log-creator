# Chronicle GCP DHCP Log Creator

## UPDATE
If you cloned this repo before May 29th, 2021 at 7pm EST, please do a git pull of make_dhcp_logs.py.  There was a small logic error that, over time, would cause correlation issues in that it cached multiple hostnames per IP address.

## Purpose
This script uses Google Cloud's gcloud command line tool to create Chronicle compatible CSV logs to allow it to correlate IP addresses to hostnames.

## Chronicle Blog Post
Chronicle has a [blog post](https://chroniclesec.medium.com/how-to-dynamically-correlate-google-cloud-compute-engine-instance-network-traffic-using-chronicle-2e39f629b553) discussing the below problem statement and solution.

## Background
If you are sending logs to Chronicle that contain GCP IP addresses, you need to get DHCP logs to Chronicle so it can correlate the IP address to a hostname.  

Unfortunately, GCP doesn't have DHCP logs.  Even if you use Packet Mirroring (e.g. a software defined span/tap), GCP instances don't use normal DHCP requests and responses.

Luckily, Chronicle allows you to send it DHCP logs in a CSV format like 

```2020-05-29T14:00:00Z,RENEW,192.168.1.1,router1,AABBCC123456 ```

With a format of

```{datetime},{DHCP Operation},{IP Address},{hostname},{MAC Address}```

Note: Because GCP doesn't easily expose MAC addresses, and they don't provide value in investigations, random one are generated for hosts.

## Chronicle Integration
This script will output a file called staticip.log, which will contain newly seen hosts' DHCP logs.

To get these logs to Chronicle you can:
1. Run this script on your Chronicle forwarder and setup the file to be ingested in its "collectors" list by mounting the folder when you run the docker container.
2. Run this script apart from the Chronicle forwarder and setup a pipeline to send logs to your Chronicle forwarder via syslog.

## Script options:
* --dev:  Used to test locally
* --log_all_hosts: Instead of only logging new+updated hosts log all hosts
  * This acts like a keep-alive for the host record without overloading Chronicle with dozens of logs per host every day (which breaks their backend correlation)

## Script Methodology

- For each project
  - Run *gcloud compute instances list --project {desired_project}* to get all current compute instances.
  - For every compute instance
    - Check if the ip is in your cache
    - If yes
      - Ensure you have an updated hostname, keeping the same MAC address
    - If not
      - Cache the new IP and hostname, with a random MAC address
  - If --log_all_hosts is given
    - Log all hosts
  - Else
    - Log new or updated hosts

## Requirements
* Python3
* Google Cloud Account with *compute.instances.list* and *compute.zones.list* permissions to do [compute instances list](https://cloud.google.com/sdk/gcloud/reference/compute/instances/list) on the projects you will be running this script on. 
* Authenticated (logged in) [Google Cloud SDK](https://cloud.google.com/sdk)
* [jq](https://stedolan.github.io/jq/download/) to parse the gcloud output

## Setup
* Update the variables in constants.py
* If you haven't yet, authenticate your Google Cloud SDK: *gcloud auth login*

## Execution

### Test

1. Run: *python3 make_dhcp_logs.py --dev*

2. Validation

   * Output showing iteration through projects and new/updated hosts, like below

     ```
     Checking example-project-1
         Adding new host: new-jump-host-us-cen-1
         Adding new host: new-dev-test-host
     Checking example-project-2
     Checking example-project-3
         Adding new host: new-test-mysql-host-us-east-1
     ```

   * Check for cached hosts in gcp-ip-host-list-{project}

   * Check for new or updated hosts in staticip.log

### Production (assuming running locally on the Chronicle forwarder)

1. Create the local log file for ingest (necessary to prevent step 2 from failing), i.e. {FOLDER_FOR_CHRONICLE_LOGS}/staticip.log

2. Setup ingest into Chronicle by adding a new "collector" to your configuration file, e.g. 

   ```
     - file:
          common:
            enabled: true
            data_type: ASSET_STATIC_IP
            data_hint:
            batch_n_seconds: 10
            batch_n_bytes: 1048576
          file_path: /opt/chronicle/assetlogs/staticip.log
          poll: true
   ```

3. Restart the forwarder's docker container, adding a new volume mount for your logs e.g.

   ```
   sudo docker stop cfps

   sudo docker rm cfps

   sudo docker run \
   --detach \
   --name cfps \
   --restart=always \
   --log-opt max-size=100m \
   --log-opt max-file=10 \
   --net=host \
   -v /opt/conf:/opt/chronicle/external \
   -v {FOLDER_FOR_CHRONICLE_LOGS}:/opt/chronicle/assetlogs \
   gcr.io/chronicle-container/cf_production_stable
   ```

4. Setup cronjobs to run the script.

   ```
   # Run every to 2 minutes to look for new instances
   # Every 2 minutes is giving plenty of time.  You likely could do every minute.
   */2 * * * * python3 {FOLDER_FOR_SCRIPT}/make_dhcp_logs.py
   # Run every day to upload DHCP logs for ALL instances, not just new ones.
   0 0 * * * python3 {FOLDER_FOR_SCRIPT}/make_dhcp_logs.py --log_all_hosts
   ```

5. Validation

   * Check for cached hosts in {FOLDER_FOR_HISTORIC_LOGS}/gcp-ip-host-list-{project}

   * Check for new or updated hosts in {FOLDER_FOR_CHRONICLE_LOGS}/staticip.log

   * On the Chronicle forwarder, run *sudo docker logs cfps*

     * You should see a line like below after the script has run and written files to staticip.log.  The below example indicates that 5 new log lines have been uploaded to Chronicle.

       ```Batch (5, ASSET_STATIC_IP) successfully uploaded.```
