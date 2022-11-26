# FastChat 

A simple WhatsApp-like chat service. Supports groups and DMs with secure end-to-end encryption. Server architecture supports even load distribution. Was made as part of the CS 251 course project in Autumn 2022, by the team Konigsberg.

Detailed documentation can be found in ```/build/html/index.html```

## Running the Code
To run the Client, execute ```python client.py```
To run the Servers, execute ```python system.py```

Change globals to change IP addresses, number of servers, etc.


Here is a brief overview of the code

## Clients
 Implement DMs, creating groups, and all other client-side features, like
 * Clients can login with single factor authentication **from any device**.
 * Restore their **chat history** as far back as they wish, on **any device**.
 * Messages can be sent to recipients who are **offline**, and pending messages can be restored on demand. Program also supports a **QuickChat** feature where history is not imported.
 * Groups support message broadcasting to a select set of users.

The Client module handles all client-side requirements like IO with Selectors, and personal database management with PostGreSQL. Sockets are handled by the MessageHandler module, which takes care of the message transmission protocol. All cryptography is handled by the crypto module.

## End-to-End Encryption
Each user generates his own private-public key pair (RSA). The keys are encrypted with the password and stored on the server database for exporting to other devices. The server doesn't know the passwords since it stores only the SHA256 hash value. Public keys are made available.

The message encryption protocol first generates a symmetric-encryption Fernet key. The message plaintext is encrypted with this, and the key itself is encrypted with the RSA token of the recipient. This encrypted key is appended to the message and sent to all intended recipients, including DMs and Groups.

Messages on the client's personal database are stored with password encryption, and can be securely **exported to any device**.

## Client Database Management
Each client owns a personal database on the 'cloud'. This database is inaccesible to the server architecture, but simultaneously enables easy export of messaging history and contacts to clients across many devices. Messages are stored password encrypted. The database stores a chats table, and a message history table.

## Servers
The server architecture consists of a set of servers, each connected to one another. These server programs are launched when the Load Balancer is launched. The load balancer is a special server which knows the host and ports of each server. The client sends a login request to the Load Balancer. Upon valid authentication/new account creation, the generated RSA tokens are preserved, and the client gets added to the servers' database of users. The load balancer returns the least busy server to the client, which the client then connects to.

* The main server loop engages the clients through multiple sockets, and contains sockets to other servers.
* The server knows where each online client is connected, and sends the message to the recipients server.
* Pending messages are maintained on a database, and deleted once popped by request.


Server message protocol is handled by MessageHandler, and databasing managed by PostGreSQL. 

## Server Database Management
* The server architecture maintains a database of FastChat users and their RSA tokens, and their password hashes for authentication.
* It also maintains a database of groups, where the Group members are in a python-list-formatted string.
* Further, it maintains a database of pending messages which were sent when a given client was offline, and can restore them on prompt, then remove them from the pending table.

The Load Balancer system runs the PostGreSQL server for database management.

## Load Balancing
The Load Balancer is a special type of Server program that
* Initializes the servers, the (local)PostGreSQL server and the database.
* Authenticates clients, and exports their keys whenever required. It also handles new account creation requests.
* Monitors the traffic on each of the main servers.
* When a valid authentication is complete, the Load Balancer sends to the client the address of the least busy server, and all further client-server interactions are handled there.
* The load balancer is never under stress of receiving actual content.

## References 
https://stackoverflow.com/questions/32439167/psql-could-not-connect-to-server-connection-refused-error-when-connecting-to

https://gist.github.com/zhouchangxun/5750b4636cc070ac01385d89946e0a7b

https://superuser.com/questions/174576/opening-a-new-terminal-from-the-command-line-and-running-a-command-on-mac-os-x
https://stackoverflow.com/questions/34913078/importing-and-changing-variables-from-another-file
