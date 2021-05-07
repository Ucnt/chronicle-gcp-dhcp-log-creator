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
    historic_ip_host_list="{folder}/gcp-ip-host-list".format(folder=FOLDER_FOR_HISTORIC_LOGS)
    asset_dhcp_list="{folder}/staticip.log".format(folder=FOLDER_FOR_CHRONICLE_LOGS)


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
            print("Error: {}".format(error))
        return output.decode('utf-8', 'ignore').strip()
    except Exception as e:
        logger.critical("Error getting cmd output from %s.  Exiting - %s" % (command, str(e)))


def get_prior_host_dict(project):
    '''
    For a given project, return the historic, cached hostname to IP+Mac results as a dictionary

    Dict format: d[hostname] = {"ip" : ip, "mac" : mac}
    '''
    hosts = {}
    with open("{}-{}".format(historic_ip_host_list, project), "r") as f:
        for line in f:
            if "," in line:
                # Skip malformed lines, preventing errors and re-writing them later
                try:
                    ip, hostname, mac = line.strip().split(",")
                    hosts[hostname] = {"ip" : ip, "mac" : mac}
                except:
                    pass
    return hosts


def get_compute_instance_list(project):
    '''
    For a given project, return the current hostname to IP+Mac results from gcloud as a dictionary

    Dict format: d[hostname] = {"ip" : ip, "mac" : mac}
    '''
    command = '''
        {gcloud_cmd} compute instances list --project {project} --format=json | jq -r '.[] | "\(.name) \(.networkInterfaces[0].networkIP)"'
    '''.format(gcloud_cmd=gcloud_cmd, project=project)
    output = get_cmd_output(command=command)

    hosts = {}
    for line in output.splitlines():
        hostname, ip = line.split()
        hosts[hostname] = {"ip": ip, "mac": None}
    return hosts


def merge_dicts(prior_host_dict, current_instance_dict):
    '''
    Given the cached and current hostname to IP+Mac dictionaries, return an updated dictionary to cache

    The dictionary will add an "update" value in order to identify if the host needs to be send to Chronicle    
    '''
    # Merge the dictionaries into one single dictionary, marking which ones need to be updated
    for hostname, attributes in current_instance_dict.items():
        # If the host has already been seen
        if hostname in prior_host_dict:
                # If the IP address is new, update the IP only
                if current_instance_dict[hostname]["ip"] != prior_host_dict[hostname]["ip"]:
                    print("updating {}: {} to {}".format(
                        hostname, prior_host_dict[hostname]["ip"], current_instance_dict[hostname]["ip"]))
                    prior_host_dict[hostname]["ip"] = current_instance_dict[hostname]["ip"]
                    prior_host_dict[hostname]["update"] = True
        # It's a new host that needs a new mac
        else:
            print("Adding new host: {}".format(hostname))
            new_mac_address = "%02x:%02x:%02x:%02x:%02x:%02x" % (random.randint(0, 255),
                 random.randint(0, 255),
                 random.randint(0, 255),
                 random.randint(0, 255),
                 random.randint(0, 255),
                 random.randint(0, 255))

            prior_host_dict[hostname] = {
                "ip" : current_instance_dict[hostname]["ip"],
                "mac" : new_mac_address,
                "update" : True
            }

    # Return back the newly update host list
    return prior_host_dict


def write_new_logs(project, host_dict):
    '''
    Given the project name and its new hostname to IP+Mac dictionary

    Write the updated (or all logs if --log-all-hosts is specified) to be read by Chronicle
    '''
    # Open a writer for the new historic and DHCP file to upload to Chronicle
    historics_host_file = open("{}-{}".format(historic_ip_host_list, project), "w+")
    dhcp_file = open(asset_dhcp_list, "w+")

    # Create properly formatted date time
    date_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    # For all the hosts, write DHCP entries for new/updated or if it's time to write daily new ones
    for hostname, attributes in host_dict.items():
        if "update" in attributes or args.log_all_hosts:
            dhcp_file.write('{date_time},RENEW,{ip_address},{hostname},{mac_address}\n'.format(
                date_time=date_time,
                ip_address=attributes["ip"],
                hostname=hostname,
                mac_address=attributes["mac"]
            ))

        # Be sure the historic host file has ALL hosts
        historics_host_file.write("{},{},{}\n".format(
            attributes["ip"], hostname, attributes["mac"]))

    # Close the files
    historics_host_file.close()
    dhcp_file.close()


if __name__ == "__main__":
    # Be sure all variables have been set
    check_for_updated_constants_vars()

    # Get current hosts
    for project in PROJECTS:
        print("Checking {}".format(project))

        # Be sure the host file is there
        get_cmd_output(command="touch {}-{}".format(historic_ip_host_list, project))

        # Get prior host list
        prior_host_dict = get_prior_host_dict(project=project)

        # Get the current hosts for the project
        current_instance_dict = get_compute_instance_list(project=project)

        # Merge the dicts so you have all old and current in one full dictionary
        # While doing this, mark those that need to be updated as host_dict[hostname]["updated"] = True
        host_dict = merge_dicts(prior_host_dict=prior_host_dict, current_instance_dict=current_instance_dict)

        # Write new DHCP and prior host list file
        write_new_logs(project=project, host_dict=host_dict)
