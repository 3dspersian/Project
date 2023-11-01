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
    print("Usage: ./NetRover.py <ip_address>")
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

        if _:
            print(Fore.RED + f"[!] Error while printing the deep nmap scan, check the saved 'nmap.scan' file for results" + Style.RESET_ALL)

        decoded_output = stdout.encode('utf-8', errors='ignore').decode('utf-8')
        print(decoded_output)
        return decoded_output
    except Exception as e:
        print(Fore.RED + f"[!] Error while running the deep nmap scan: {str(e)}" + Style.RESET_ALL)

#  FTP

ftp_dir = working_dir.strip() + "/ftp"
# Checks FTP for anon login
def ftp_login_download(server=target):
    print("\nEnumerating FTP with ANON credentials...")

    # Check if the local FTP directory to store the downloaded files is already created
    if not os.path.exists(ftp_dir):
        os.makedirs(ftp_dir)

    # Creating an FTP object to connect to the server
    # ftp = FTP(server)
    allowed = False
    # Attempt to log in anonymously
    try:
        ftp = FTP(server)
        
        ftp.login()
        if ftp:
            allowed = True
        # Start going through files from the root directory
        download_ftp_files(ftp, '/')
    except Exception as e:
        print(Fore.RED + "\n[!] Exiting, probably doesn't allow anonymous login..." + Style.RESET_ALL + e)
    if allowed == True:
        ftp.quit()
    else:
        pass

# Checks if the item is a directory, if yes, returns True.

# Download files, including hidden files
def download_ftp_files(ftp, path, local_dir=ftp_dir):
    ftp.cwd(path)  # Change directory to the specified path

    # Use the LIST command to get a detailed directory listing
    lines = []
    ftp.retrlines("LIST -a", lines.append)

    for line in lines:
        parts = line.split()
        item_name = parts[-1]

        # Skip parent directory and current directory entries
        if item_name in ['.', '..']:
            continue

        is_directory = line.startswith('d')
        try:
            if is_directory:
                print(Fore.BLUE + item_name + Style.RESET_ALL)
                # Create a local subdirectory to save files in
                local_subdir = os.path.join(ftp_dir, item_name)
                os.makedirs(local_subdir, exist_ok=True)
                # Recursively go into subdirectories
                download_ftp_files(ftp, item_name, local_subdir)
            else:
                print(Fore.YELLOW + item_name + Style.RESET_ALL)
                # Download files in the current directory
                local_file_path = os.path.join(local_dir, item_name)
                with open(local_file_path, 'wb') as local_file:
                    ftp.retrbinary(f"RETR {item_name}", local_file.write)
        except Exception as e:
            print(Fore.RED + f"[!] Error downloading '{item_name}'... :{e}" + Style.RESET_ALL)

#  SMB
smb_dir = working_dir.strip() + "/smb"

def smb_login_download(server_name=target):
    print("\nStarting SMB Enumeration...")
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
        print(Fore.RED + f"[!] An error has occurred while processing the smb share.: {e}" + Style.RESET_ALL)
    finally:
        smb_connection.close
   
def smb_list_download_shares(smb, share_name, path):
    try:
        files = smb.listPath(share_name, path)
        for item in files:
            if item.filename != "." and item.filename != "..":

                if item.isDirectory:
                    if path == "/":
                        directory = f"{path}{item.filename}"
                    else:
                        directory = f"{path}/{item.filename}"
                    print(Fore.BLUE + directory + Style.RESET_ALL)
                    smb_list_download_shares(smb, share_name, directory)
                else:
                    smb_download_shares(smb, share_name, path, item.filename)
    except:
        print(Fore.RED + f"[!] There aren't any files in this share." + Style.RESET_ALL)

def smb_download_shares(smb, share_name, path, filename):
    share_path = os.path.join(smb_dir, share_name)
    if not os.path.exists(share_path):
        os.makedirs(share_path)
    local_file_path = os.path.join(share_path, filename)
    if path == '/':
        remote_file_path = f"{filename}"
    else:
        remote_file_path = f"{path}/{filename}"
    print(Fore.YELLOW + remote_file_path + Style.RESET_ALL)
    with open(local_file_path, 'wb') as local_file:
        smb.retrieveFile(share_name, remote_file_path, local_file)


# Fuzzing
def scan_directory(directory_url):
    results_file = os.path.join(working_dir, "fuzz_results.txt")
    if not os.path.exists(results_file):
        with open(results_file, 'w'):
            pass
    try:
        response = requests.get(directory_url)
        status_code = response.status_code
        if response.status_code in [200, 301, 302, 307, 308]:
            print(Fore.BLUE + f"{directory_url} ==> [{status_code}]" + Style.RESET_ALL)
            with open(results_file, "a+") as results:
                results.write(directory_url+"\n")
    except requests.exceptions.RequestException as e:
        pass
        # print(Fore.RED + f"[!] Error accessing {directory_url}: {e}" + Style.RESET_ALL)

def directory_fuzzing(wordlist, url):
    if not url.endswith('/'):
        url += '/'
    with open(wordlist, 'r') as words:
        directory_urls = [url + line.strip() for line in words]
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(scan_directory, directory_urls)


def main():
    print("What type of scan do you want to perform?(input numbers 1 by 1.)")
    print(Fore.GREEN + "\nNmap Scan (1)\nFTP Enumeration (2)\nSMB Enumeration (3)\nDirectory Fuzzing (4)\nAll Scans (5)\nDone (9)" + Style.RESET_ALL)
    scans = []
    
    while True:
        check = input()
        if check == '9':
            break
        elif check not in scans:
            scans.append(check)
    if '4' in scans:
        url = input("URL: ")
        wordlist = input("Wordlist: ")
    if '1' in scans:
        port_list = initial_scan(target)
        deep_scan = nmap_scan(target, port_list)

    if '2' in scans:
        ftp_enum = ftp_login_download()

    if '3' in scans:
        smb_enum = smb_login_download()

    if '4' in scans:
        if url and wordlist:
            print("\nDirectory Fuzzing...\n")
            directory_fuzzing(wordlist, url)
        else:
            print(Fore.RED + "You need both a URL and a wordlist..." + Style.RESET_ALL)
            sys.exit(0)

    if '5' in scans:
        url = input("URL: ")
        wordlist = input("Wordlist: ")
        port_list = initial_scan(target)
        deep_scan = nmap_scan(target, port_list)
        ftp_enum = ftp_login_download()
        smb_enum = smb_login_download()

        if url and wordlist:
            print("\nDirectory Fuzzing...\n")
            directory_fuzzing(wordlist, url)
        else:
            print(Fore.RED + "\n[!] You need both a URL and a wordlist..." + Style.RESET_ALL)
            sys.exit(0)

    if not scans:
        print(Fore.RED + "\n[!] No scan selected, Exiting..." + Style.RESET_ALL)
        sys.exit(0)

if __name__ == "__main__":
    main()