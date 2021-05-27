#!/usr/bin/env python3
'''

Author: Matt Svensson

Purpose: Create Chronicle CSV static IP lists from gcloud compute instances list

Chronicle Log format: 2020-05-29T14:00:00Z,RENEW,192.168.1.1,router1,AABBCC123456

Example Cron jobs for this script

# Run every to minutes to look for new instances
*/2 * * * * python3 {folder where this script is put}/make_dhcp_logs.py
# Run every day to upload DHCP logs for ALL instances, not just new ones.
0 0 * * * python3 {folder where this script is put}/make_dhcp_logs.py --log_all_hosts


'''
import time
import sys
import os
import random
import datetime
from arg_parse import args
from constants import *

# Set gcloud and output variables dependant on constants.py and --dev argument.
if args.dev:
    gcloud_cmd=PATH_TO_GCLOUD_COMMAND_DEV
    historic_ip_host_list="gcp-ip-host-list"
    asset_dhcp_list="staticip.log"
else:
    gcloud_cmd=PATH_TO_GCLOUD_COMMAND
    historic_ip_host_list=f"{FOLDER_FOR_HISTORIC_LOGS}/gcp-ip-host-list"
    asset_dhcp_list=f"{FOLDER_FOR_CHRONICLE_LOGS}/staticip.log"


def check_for_updated_constants_vars():
    '''
    Ensure that all arguments have been populated

    If not, print error and exit.
    '''
    if not (PATH_TO_GCLOUD_COMMAND_DEV or PATH_TO_GCLOUD_COMMAND or FOLDER_FOR_HISTORIC_LOGS or FOLDER_FOR_CHRONICLE_LOGS):
        print("You need to set all constants.py variables")
        sys.exit()

    if PROJECTS == ["example-project-name","example-project-name2"]:
        print("You need to set the projects you want to run this on")
        sys.exit()


def get_cmd_output(command):
    import subprocess
    '''
    Given a terminal command, run the command and return the output

    If an error occurs, log the error
    '''
    try:
        'Get output from a given command'
        #logger.warning("Running: %s" % (command))
        p = subprocess.Popen(command,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                shell=True,)
        output, error = p.communicate()
        p_status = p.wait()
        if error:
            print(f"Error: {error}")
        return output.decode('utf-8', 'ignore').strip()
    except Exception as e:
        print(f"Error getting cmd output from {command} - {str(e)}")


def get_prior_host_dict(project):
    '''
    For a given project, return the historic, cached hostname to IP+Mac results as a dictionary

    Dict format: d[hostname] = {"ip" : ip, "mac" : mac}
    '''
    hosts = {}
    try:
        with open(f"{historic_ip_host_list}-{project}", "r") as f:
            for line in f:
                if "," in line:
                    # Skip malformed lines, preventing errors and re-writing them later
                    try:
                        ip, hostname, mac = line.strip().split(",")
                        hosts[ip] = {"hostname" : hostname, "mac" : mac}
                    except:
                        pass
    except FileNotFoundError:
        pass
    return hosts


def get_compute_instance_list(project):
    '''
    For a given project, return the current hostname to IP+Mac results from gcloud as a dictionary

    Dict format: d[hostname] = {"ip" : ip, "mac" : mac}
    '''
    command = f'''
        {gcloud_cmd} compute instances list --project {project} --format=json | jq -r '.[] | "\(.name) \(.networkInterfaces[0].networkIP)"'
    '''
    output = get_cmd_output(command=command)

    hosts = {}
    for line in output.splitlines():
        hostname, ip = line.split()
        hosts[ip] = {"hostname": hostname, "mac": None}
    return hosts


def merge_dicts(prior_host_dict, current_instance_dict):
    '''
    Given the cached and current hostname to IP+Mac dictionaries, return an updated dictionary to cache

    The dictionary will add an "update" value in order to identify if the host needs to be send to Chronicle
    '''
    # Merge the dictionaries into one single dictionary, marking which ones need to be updated
    for ip, attributes in current_instance_dict.items():
        # If the host has already been seen
        if ip in prior_host_dict:
                # If the hostname is different, update it
                if current_instance_dict[ip]["hostname"] != prior_host_dict[ip]["hostname"]:
                    print(f'    Updating {ip}: {prior_host_dict[ip]["hostname"]} to {current_instance_dict[ip]["hostname"]}')
                    prior_host_dict[ip]["hostname"] = current_instance_dict[ip]["hostname"]
                    prior_host_dict[ip]["update"] = True
        # It's a new host that needs a new mac
        else:
            new_mac_address = "%02x:%02x:%02x:%02x:%02x:%02x" % (random.randint(0, 255),
                 random.randint(0, 255),
                 random.randint(0, 255),
                 random.randint(0, 255),
                 random.randint(0, 255),
                 random.randint(0, 255))

            prior_host_dict[ip] = {
                "hostname" : current_instance_dict[ip]["hostname"],
                "mac" : new_mac_address,
                "update" : True
            }
            print(f'    Adding new host: {ip} - {current_instance_dict[ip]["hostname"]} {prior_host_dict[ip]["mac"]} ')

    # Return back the newly update host list
    return prior_host_dict


def write_new_logs(project, host_dict, dhcp_file):
    '''
    Given the project name and its new hostname to IP+Mac dictionary

    Write the updated (or all logs if --log-all-hosts is specified) to be read by Chronicle
    '''
    # Open a writer for the new historic and DHCP file to upload to Chronicle
    historics_host_file = open(f"{historic_ip_host_list}-{project}", "w+")

    # Create properly formatted date time
    date_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    # For all the hosts, write DHCP entries for new/updated or if it's time to write daily new ones
    for ip, attributes in host_dict.items():
        # Write new or updated hosts to the Chronicle DHCP list to ingest
        if "update" in attributes or args.log_all_hosts:
            dhcp_file.write(f'{date_time},RENEW,{attributes["hostname"]},{ip},{attributes["mac"]}\n')

        # Be sure the historic host file has ALL hosts
        historics_host_file.write(f'{ip},{attributes["hostname"]},{attributes["mac"]}\n')

    # Close the files
    historics_host_file.close()


if __name__ == "__main__":
    # Be sure all variables have been set
    check_for_updated_constants_vars()

    # Create new DHCP file for output to Chronicle
    # Could do this for each project but simpler for seeing all results
    dhcp_file = open(asset_dhcp_list, "w+")

    for project in PROJECTS:
        print(f"Checking {project}")

        # Get prior host list
        prior_host_dict = get_prior_host_dict(project=project)

        # Get the current hosts for the project
        current_instance_dict = get_compute_instance_list(project=project)

        # Merge the dicts so you have all old and current in one full dictionary
        # While doing this, mark those that need to be updated as host_dict[hostname]["updated"] = True
        host_dict = merge_dicts(prior_host_dict=prior_host_dict, current_instance_dict=current_instance_dict)

        # Write new DHCP logs and update the cache
        write_new_logs(project=project, host_dict=host_dict, dhcp_file=dhcp_file)

    dhcp_file.close()
