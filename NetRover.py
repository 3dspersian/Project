#!/usr/bin/python3
import subprocess
import sys
import re
from colorama import Fore, Style
import os
from ftplib import FTP 
import time
#____
working_dir = subprocess.Popen('pwd',shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
working_dir, _ = working_dir.communicate()
#____

# displays how to use the program if there arent enough args provided
if len(sys.argv) != 2 or sys.argv[1] == '-h':
    print("Usage: ./scanner.py <ip_address>")
    sys.exit(1)
else:
    target = sys.argv[1]

# Nmap scan to discover open ports
def initial_scan(target):
    initial_command = f"nmap -p- -Pn -T5 -vv {target}"
    port_list = []
    
    # Regex Pattern to find open ports
    pattern_for_ports = r"^Discovered.*?(\d+)/tcp"
    
    # Running first scan 
    try:
        process = subprocess.Popen(initial_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

        # parsing through the output looking for open ports from verbose.
        print("\nOpen Ports:")
        for line in process.stdout:
            match = re.search(pattern_for_ports, line)

            # If it finds an open port, print the port.
            if match:
                port = match.group(1)
                print(Fore.YELLOW + port + Style.RESET_ALL)
                # adding the port number to a list for deep scan
                port_list.append(match.group(1))
                        
        # Wait for nmap scan to finish
        process.wait()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    return port_list
port_list = initial_scan(target)

# deep nmap scan
def nmap_scan(t):
    output_file = 'nmap.scan'

    # Formatting the discovered ports by separating them by commas
    discovery = ','.join(port_list)
    
    # Deep nmap scan
    command = ['nmap', '-p', discovery, '-A', t, '-oN', output_file]

    try:
        print("Now running a deeper scan.")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, _ = process.communicate()
        print(stdout)
        return stdout
    except Exception as e:
        print(f"Error while running the deep nmap scan: {str(e)}")

deep_scan = nmap_scan(target)

# Check if the user wants to continue to do all advanced scans.
check = input(Fore.GREEN + "\nDo you want to perform all advanced scans? (y/N)" + Style.RESET_ALL)
if check.lower() == 'n':
    print(Fore.RED + "\nExiting..." + Style.RESET_ALL)
    sys.exit(0)

# Checks ftp for anon login
def ftp_login_download(server=target):
    global ftp_dir
    ftp_dir = f"{working_dir}/ftp"
    # check if the local ftp_directory to store the downloaded files is already created
    if not os.path.exists(ftp_dir):
        os.makedirs(ftp_dir)
      
    # Creating an FTP object to connect to the server
    ftp = FTP(server)
    
    # Attempt to  Log in anonymously
    try:
        ftp.login()
        # starts going through files from the root directory
        download_ftp_files(ftp, '/')
    except Exception as e:
        print(Fore.RED + "\n Exiting..." + Style.RESET_ALL)
        print(e)
    # else:
        # list files and directories in the current dir
        # files = ftp.nlst()
        # if files:
        #     print("\nFound the following files:\n")
        #     for file in files:
        #         print(Fore.YELLOW + file + Style.RESET_ALL)
        #         if is_ftp_directory(ftp, file):
        #             try:
        #                 ftp.cwd(file)
        #                 items = ftp.nlst()
        #                 for item in items:
        #                     with open(item, 'wb') as local_file:
        #                         ftp.retrbinary('RETR ' + item, local_file.write)
        #                 ftp.cwd('..')
        #             except Exception as e:
        #                 print(f"An error occurred: {e}")
    ftp.quit()

# checks if the item is a directory, if yes returns true.
def is_ftp_directory(ftp, item):
    try:
        ftp.cwd(item)
        ftp.cwd("..")
        return True
    except:
        return False
noxing = []
# download files  !!!!!!!! There's an error with this function. Need to take a look next time i open it.
def download_ftp_files(ftp, path):
    ftp.cwd(path) # Change directory to the specified path
    items = ftp.nlst() # List items in curr directory

    for item in items:
        if is_ftp_directory(ftp, item):
            #Create local dir to save files in
            local_subdir = os.path.join(ftp_dir, item)
            os.makedirs(local_subdir, exist_ok=True)

            # Recursively go into subdirectories
            download_ftp_files(ftp, item)
        else:
            # Download files in curr directory
            local_file_path = os.path.join(ftp_dir, item)
            with open(local_file_path, 'wb') as local_file:
                ftp.retrbinary('RETR ' + item, local_file.write)
            noxing.append(item)
                


# list ftp directory
# def list_ftp_directory(ftp, directory=".", level=0):
#     try:
#         ftp.cwd(directory)
#     except Exception as e:
#         print(f"\nCould not change to directory {directory}: {e}")
#         return
#     # list files and directories in the current dir
#     files = ftp.nlst()

#     if files:
#         print("\nFound the following files:\n")
#         for file in files:
#             print(Fore.YELLOW + file + Style.RESET_ALL)
#             if is_ftp_directory(ftp, file):

ftp_login_download()

if noxing:
    print("\nFound the following files:\n")
    for item in noxing:
        print(Fore.YELLOW + item + Style.RESET_ALL)