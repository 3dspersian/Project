#!/usr/bin/python3
import subprocess
import sys
import re
from colorama import Fore, Style
import os
from ftplib import FTP 
from smb.SMBConnection import SMBConnection
import requests
from concurrent.futures import ThreadPoolExecutor

netrover_ascii = '''
   ____   ____   ____   ____   ____   ____   ____   ____
  /  _/  /  _/  /  _/  /  _/  /  _/  /  _/  /  _/  /  _/
 _/  _/ _/  _/ _/  _/ _/  _/ _/  _/ _/  _/ _/  _/ _/  _/
/ N  / / E  / / T  / / R  / / O  / / V  / / E  / / R  /
\__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  \__/  
'''

print(Fore.LIGHTCYAN_EX + netrover_ascii + Style.RESET_ALL)

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


# deep nmap scan
def nmap_scan(t,ports):
    output_file = 'nmap.scan'

    # Formatting the discovered ports by separating them by commas
    discovery = ','.join(ports)
    
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

#  FTP

ftp_dir = working_dir.strip() + "/ftp"
# Checks ftp for anon login
def ftp_login_download(server=target):
    print("\nEnumerating FTP with ANON credentials...")

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
        print(Fore.RED + "\n[!] Exiting, probably doesnt allow anonymous login..." + Style.RESET_ALL)
        print(e)
    ftp.quit()

# checks if the item is a directory, if yes returns true.
def is_ftp_directory(ftp, item):
    try:
        ftp.cwd(item)
        ftp.cwd("..")
        return True
    except:
        return False

# download files 
def download_ftp_files(ftp, path, local_dir=ftp_dir):
    ftp.cwd(path) # Change directory to the specified path
    items = ftp.nlst() # List items in current directory
    if items:
        print(f"\nFound the following files in '{path}':")
        for item in items:
            if is_ftp_directory(ftp, item):
                print(Fore.BLUE + item + Style.RESET_ALL)
                # Create a local subdirectory to save files in
                local_subdir = os.path.join(ftp_dir, item)
                os.makedirs(local_subdir, exist_ok=True)
                # Recursively go into subdirectories
                download_ftp_files(ftp, item, local_subdir)
            else:
                print(Fore.YELLOW + item + Style.RESET_ALL)
                # Download files in the current directory
                local_file_path = os.path.join(local_dir, item)
                with open(local_file_path, 'wb') as local_file:
                    ftp.retrbinary('RETR ' + item, local_file.write)

    else:
        print(Fore.RED + f"[!] The folder: {path} is empty" + Style.RESET_ALL)
        ftp.cwd("..")

#  SMB
smb_dir = working_dir.strip() + "/smb"

def smb_login_download(server_name=target):

    # check if the local ftp_directory to store the downloaded files is already created
    if not os.path.exists(smb_dir):
        os.makedirs(smb_dir)

    # create smb connection object
    smb_connection = SMBConnection('', '', 'client', server_name, use_ntlm_v2=False)
    try:
        # Connect
        smb_connection.connect(server_name, 139)

        # List shares and download files from each share
        shares = smb_connection.listShares()
        if shares:
            for share in shares:
                try:
                    print(f"\nConnecting to '{share.name}'...")
                    smb_list_download_shares(smb_connection, share.name, '/')
                except Exception as e:
                    print(Fore.RED + f"\n[!] Can't connect to {share.name}..." + Style.RESET_ALL)
    except Exception as e:
        print(Fore.RED + f"[!] An error has occurred while processing the smb share.: {e}")
    finally:
        smb_connection.close
   
def smb_list_download_shares(smb, share_name, path):
    files = smb.listPath(share_name, path)
    for item in files:
        if item.filename != "." and item.filename != "..":

            if item.isDirectory:
                directory = f"{path}/{item.filename}"
                print(Fore.BLUE + directory + Style.RESET_ALL)
                smb_list_download_shares(smb, share_name, directory)
            else:
                smb_download_shares(smb, share_name, path, item.filename)

def smb_download_shares(smb, share_name, path, filename):
    local_file_path = os.path.join(smb_dir, filename)
    if path == '/':
        remote_file_path = f"{filename}"
    else:
        remote_file_path = f"{path}/{filename}"
    print(Fore.YELLOW + remote_file_path + Style.RESET_ALL)
    with open(local_file_path, 'wb') as local_file:
        smb.retrieveFile(share_name, remote_file_path, local_file)


# Fuzzing
def scan_directory(directory_url):
    try:
        response = requests.get(directory_url)
        status_code = response.status_code
        if response.status_code in [200, 301, 302, 307, 308]:
            print(Fore.BLUE + f"{directory_url} ==> [{status_code}]" + Style.RESET_ALL)
    except requests.exceptions.RequestException as e:
        print(Fore.RED + f"[!] Error accessing {directory_url}: {e}" + Style.RESET_ALL)

def directory_fuzzing(wordlist, url):
    if not url.endswith('/'):
        url += '/'
    with open(wordlist, 'r') as words:
        directory_urls = [url + line.strip() for line in words]
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(scan_directory, directory_urls)


# Check if the user wants to continue to do all advanced scans.
print("What type of scan do you want to perform?(input numbers 1 by 1.)")
print(Fore.GREEN + "\nNmap Scan (1)\nFTP Enumeration (2)\nSMB Enumeration (3)\nDirectory Fuzzing (4)\nAll Scans (5)\nDone (9)" + Style.RESET_ALL)
scans = []
while True:
    check = input()
    if str(check) == '9':
        #scans.append(str(check))
        break
    elif str(check) not in scans:
        scans.append(str(check))

if '1' in scans:
    port_list = initial_scan(target)
    deep_scan = nmap_scan(target, port_list)
elif '2' in scans:
    ftp_enum = ftp_login_download()
elif '3' in scans:
    smb_enum = smb_login_download()
elif '4' in scans:
    url = input("URL: ")
    wordlist = input("Wordlist: ")
    if url and wordlist:
        print("\nDirectory Fuzzing...\n")
        directory_fuzzing(wordlist, url)
    else:
        print(Fore.RED + "You need both a url and a wordlist..." + Style.RESET_ALL)
        sys.exit(0)
elif '5' in scans:
    url = input("URL: ")
    wordlist = input("Wordlist: ")
    port_list = initial_scan(target)
    deep_scan = nmap_scan(target, port_list)    
    ftp_enum = ftp_login_download()
    smb_enum = smb_login_download()

    if url and wordlist:
        directory_fuzzing(wordlist, url)
    else:
        print(Fore.RED + "\n[!] You need both a url and a wordlist..." + Style.RESET_ALL)
        sys.exit(0)
else:
    print(Fore.RED + "\n[!] Invalid option, Exiting..." + Style.RESET_ALL)
    sys.exit(0)