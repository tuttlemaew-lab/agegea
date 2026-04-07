import os
import re
import requests
import imaplib
import poplib
poplib._MAXLINE = 1000000 * 1024
import time
import email
import html
import socket
from concurrent.futures import ThreadPoolExecutor
from email import policy
from email.parser import BytesParser
from email import parser
from email import message_from_bytes
from email.policy import default


def find_value(data, key, value, return_key):
    for item in data:
        if item.get(key) == value:
            return item.get(return_key)
    return None  # Return None if no match is found


# Read credentials from the file
list_creds = []
with open('emails.txt', encoding='utf-8') as f:
    for e in f:
        em = e.strip().split(':')
        list_creds.append(em)

# Folder creation
folder_name = 'newsletters'
os.makedirs(folder_name, exist_ok=True)


# Determine IMAP server based on domain
def get_imap_server(domain):
    responce = requests.get(
        f"https://emailsettings.firetrust.com/settings?q={domain}")
    if responce.status_code == 200:
        setting = responce.json()["settings"]
        adresse = find_value(setting,
                             key="protocol",
                             value="IMAP",
                             return_key="address")

        if adresse != None:
            port = find_value(setting,
                              key="protocol",
                              value="IMAP",
                              return_key="port")
            return adresse, port, "IMAP"
        else:
            return find_value(setting,
                              key="protocol",
                              value="POP3",
                              return_key="address"), find_value(
                                  setting,
                                  key="protocol",
                                  value="POP3",
                                  return_key="port"), "POP3"
    else:
        raise Exception(f"No IMAP server found for domain: {domain}")


# Email checker function
def checker(em):
    try:
        email_address = em[0]
        password = em[1].strip()
        domain = email_address.split('@')[1]
        alias = email_address.split('@')[0]

        imap_server, port, protocol = get_imap_server(domain)
        socket.setdefaulttimeout(8)
        status, messages = '', ''

        if protocol == "IMAP":

            if port == 143:
                mail = imaplib.IMAP4(imap_server)
            else:
                mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(email_address, password)
            print(email_address + ' logged in')

            mail.select("inbox")
            status, messages = mail.search(None, 'ALL')
            if status == "OK":
                message_ids = messages[0].split()
                total_emails = len(message_ids)
                print(
                    f"{email_address}: Total emails in inbox: {int(total_emails)}"
                )

                # message_ids.reverse()  # Process from newest to oldest
                newsletters = []
                extracted_count = 0
                batch_count = 1  # Start with the first batch

                # Process emails in batches of 10
                for i in range(0, total_emails, 100):
                    batch = message_ids[i:i + 100]
                    for msg_id in batch:
                        _, msg_data = mail.fetch(msg_id, "(RFC822)")
                        for response_part in msg_data:
                            if isinstance(response_part, tuple):
                                email_message = response_part[1]
                                parsed_message = email.message_from_bytes(
                                    email_message)
                                html_content = None
                                for part in parsed_message.walk():
                                    if part.get_content_type() == "text/html":
                                        # charset = part.get_content_charset(
                                        # ) or 'utf-8'
                                        charset = 'utf-8'
                                        html_content = part.get_payload(
                                            decode=True).decode(
                                                charset, errors='ignore')
                                        # html_content = html.unescape(
                                        #     html_content)
                                        break

                                if html_content:
                                    # Regex pattern to match email addresses
                                    #email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                                    #Find all email addresses in the HTML content
                                    #emails = re.findall(
                                    #   email_pattern, html_content)
                                    # Extract email addresses from the HTML content
                                    #for e in emails:
                                        # html_content = re.sub(
                                        #     e, f"{alias}@gmail.com", html_content)
                                    #   html_content = re.sub(
                                    #        e, "", html_content)
                                    html_one_line = " ".join(
                                        html_content.split())

                                    newsletters.append(html_one_line)
                                    extracted_count += 1

                    # Save newsletters after each batch of 100
                    save_newsletters(email_address, newsletters, batch_count)
                    batch_count += 1
                    newsletters = []  # Clear the list for the next batch

            mail.logout()
        else:
            if port == 110:
                mail = poplib.POP3(imap_server)
            else:
                mail = poplib.POP3_SSL(imap_server)
            mail.user(email_address)
            mail.pass_(password)
            print(email_address + ' logged in')
            # status, messages_ids, octets = mail.list()
            uidl_status, uidl_listings, octets = mail.uidl()
            total_emails = len(uidl_listings)
            print(f"{email_address}: Total emails in inbox: {total_emails}")
            # Reset the session state.
            if uidl_status.strip().startswith(b'+OK'):
                # Create a map from unique IDs to message numbers
                newsletters = []
                batch_count = 1  # Start with the first batch
                init = 0
                for listing in uidl_listings:
                    message_number, unique_id = listing.decode('utf-8').split()
                    try:
                        response, lines, octets = mail.retr(message_number)
                    except Exception as e:
                        print(
                            f"Error retrieving message {message_number}: {e}")
                        exit()
                    mail.rset()
                    if response.startswith(b'+OK'):
                        init += 1
                        # msg_content = b'\r\n'.join(lines).decode('utf-8', errors='replace')
                        # msg = parser.Parser().parsestr(msg_content)
                        msg_data = b'\r\n'.join(lines)
                        msg = message_from_bytes(msg_data, policy=default)
                        # Initialize variable to hold the HTML content.
                        html_content = None
                        # Check if the email is multipart.
                        if msg.is_multipart():
                            # Walk through each part of the email.
                            for part in msg.walk():
                                # Check for 'text/html' content type.
                                if part.get_content_type() == 'text/html':
                                    html_content = part.get_content()
                                    break
                        else:
                            # For non-multipart messages, directly check the content type.
                            if msg.get_content_type() == 'text/html':
                                html_content = msg.get_content()
                        if html_content:
                            # Regex pattern to match email addresses
                            #email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                            #Find all email addresses in the HTML content
                            #emails = re.findall(email_pattern, html_content)
                            # Extract email addresses from the HTML content
                            #for e in emails:
                                # html_content = re.sub(
                                #     e, f"{alias}@gmail.com", html_content)
                            #    html_content = re.sub(e, "", html_content)
                            html_one_line = " ".join(html_content.split())
                            newsletters.append(html_one_line)
                        if init == 100:
                            # Save newsletters after each batch of 10
                            save_newsletters(email_address, newsletters,
                                             batch_count)
                            batch_count += 1
                            init = 0
                            newsletters = []

            mail.quit()
        return email_address + ' success log out'
    except Exception as e:
        error_message = f"{email_address} --- {str(e)}"
        print(error_message)
        with open('notworking.txt', 'a') as f:
            f.write(f"{email_address}:{password} ---- {str(e)}\n")
        return error_message


def save_newsletters(email_address, newsletters, batch_count):
    if newsletters:
        file_name = os.path.join(folder_name,
                                 f"{email_address}_batch_{batch_count}.txt")
        with open(file_name, "w", encoding='utf-8') as file:
            for newsletter in newsletters:
                file.write(newsletter + "\n")
        print(
            f"Saved {len(newsletters)} newsletters for {email_address} in {file_name}"
        )


# Execute checker function concurrently
with ThreadPoolExecutor(max_workers=20) as executor:
    results = list(executor.map(checker, list_creds))

# Optionally, process results here if needed
for result in results:
    print(result)
